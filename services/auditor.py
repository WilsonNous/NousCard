# services/auditor.py
# ✅ VERSÃO PRODUÇÃO: Auditoria de taxas, conciliação e integridade

from models import db, MovAdquirente, MovBanco, Adquirente, Conciliacao
from sqlalchemy import func, and_, or_
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
import logging

logger = logging.getLogger(__name__)

# ============================================================
# CONFIGURAÇÕES DE AUDITORIA
# ============================================================
TOLERANCIA_TAXA_PERCENTUAL = Decimal("0.5")  # Tolerância de 0.5% na taxa
TOLERANCIA_VALOR_ABSOLUTO = Decimal("0.10")  # Tolerância de R$ 0,10
DIAS_RETENCAO_AUDITORIA = 90  # Manter alertas por X dias

# ============================================================
# UTILITÁRIOS
# ============================================================

def calcular_taxa_efetiva(valor_bruto, valor_liquido):
    """
    Calcula a taxa efetiva cobrada: (bruto - líquido) / bruto * 100
    Retorna Decimal ou None se não for possível calcular.
    """
    try:
        bruto = Decimal(str(valor_bruto or 0))
        liquido = Decimal(str(valor_liquido or 0))
        if bruto <= 0:
            return None
        taxa = ((bruto - liquido) / bruto) * Decimal("100")
        return taxa.quantize(Decimal("0.01"))  # Arredonda para 2 casas
    except (InvalidOperation, ValueError, TypeError, ZeroDivisionError):
        return None


def comparar_valores_monetarios(valor1, valor2, tolerancia_absoluta=TOLERANCIA_VALOR_ABSOLUTO):
    """Compara dois valores monetários com tolerância"""
    try:
        v1 = Decimal(str(valor1 or 0))
        v2 = Decimal(str(valor2 or 0))
        return abs(v1 - v2) <= tolerancia_absoluta
    except:
        return False


def formatar_alerta(tipo, mensagem, severidade="medio", detalhes=None):
    """Formata um alerta de auditoria padronizado"""
    return {
        "tipo": tipo,
        "mensagem": mensagem,
        "severidade": severidade,  # baixo, medio, alto, critico
        "detalhes": detalhes or {},
        "timestamp": datetime.now().isoformat()
    }

# ============================================================
# AUDITORIA DE TAXAS (PRINCIPAL)
# ============================================================

def auditar_taxas(
    empresa_id,
    data_inicio=None,
    data_fim=None,
    adquirente_id=None,
    tipo_pagamento=None,
    apenas_com_alertas=True
):
    """
    Auditoria de taxas: compara taxas contratadas x taxas cobradas.
    
    ✅ Detecta:
        - Taxa cobrada diferente da esperada (por adquirente/bandeira)
        - Valores líquidos inconsistentes com taxa declarada
        - Vendas sem taxa registrada
        - Discrepâncias acima da tolerância configurada
    
    Args:
        empresa_id: ID da empresa para auditar
        data_inicio/data_fim: Filtro de período (opcional)
        adquirente_id: Filtrar por adquirente específica (opcional)
        tipo_pagamento: Filtrar por tipo (cartao/pix/boleto) (opcional)
        apenas_com_alertas: Se True, retorna apenas registros com problemas
    
    Returns:
        dict: {
            "total_analisados": int,
            "com_alertas": int,
            "alertas": [...],
            "resumo_por_adquirente": {...},
            "resumo_por_bandeira": {...}
        }
    """
    
    logger.info(f"Iniciando auditoria de taxas: empresa={empresa_id}")
    
    try:
        # Query base para vendas
        query = db.session.query(MovAdquirente).filter(
            MovAdquirente.empresa_id == empresa_id,
            MovAdquirente.ativo == True,
            MovAdquirente.valor_bruto > 0  # Ignorar vendas zeradas
        )
        
        # Aplicar filtros
        if data_inicio:
            query = query.filter(MovAdquirente.data_venda >= data_inicio)
        if data_fim:
            query = query.filter(MovAdquirente.data_venda <= data_fim)
        if adquirente_id:
            query = query.filter(MovAdquirente.adquirente_id == adquirente_id)
        if tipo_pagamento and tipo_pagamento != 'todos':
            query = query.filter(MovAdquirente.tipo_pagamento == tipo_pagamento)
        
        vendas = query.all()
        total_analisados = len(vendas)
        
        if total_analisados == 0:
            return {
                "total_analisados": 0,
                "com_alertas": 0,
                "alertas": [],
                "resumo_por_adquirente": {},
                "resumo_por_bandeira": {},
                "mensagem": "Nenhuma venda encontrada para o período/filtros especificados"
            }
        
        alertas = []
        resumo_adquirentes = {}
        resumo_bandeiras = {}
        
        for v in vendas:
            # Calcular taxa efetiva cobrada
            taxa_efetiva = calcular_taxa_efetiva(v.valor_bruto, v.valor_liquido)
            
            # Obter taxa esperada da adquirente (se disponível no modelo)
            taxa_esperada = None
            if v.adquirente and hasattr(v.adquirente, 'taxa_padrao'):
                taxa_esperada = v.adquirente.taxa_padrao
            
            # Inicializar resumos
            adq_nome = v.adquirente.nome if v.adquirente else "Não identificada"
            bandeira = v.bandeira or "Não identificada"
            
            if adq_nome not in resumo_adquirentes:
                resumo_adquirentes[adq_nome] = {"total": 0, "alertas": 0, "taxa_media": []}
            if bandeira not in resumo_bandeiras:
                resumo_bandeiras[bandeira] = {"total": 0, "alertas": 0, "taxa_media": []}
            
            resumo_adquirentes[adq_nome]["total"] += 1
            resumo_bandeiras[bandeira]["total"] += 1
            
            if taxa_efetiva is not None:
                resumo_adquirentes[adq_nome]["taxa_media"].append(taxa_efetiva)
                resumo_bandeiras[bandeira]["taxa_media"].append(taxa_efetiva)
            
            # ✅ Verificação 1: Taxa cobrada vs taxa esperada
            if taxa_esperada is not None and taxa_efetiva is not None:
                diferenca = abs(taxa_efetiva - taxa_esperada)
                if diferenca > TOLERANCIA_TAXA_PERCENTUAL:
                    alerta = formatar_alerta(
                        tipo="taxa_divergente",
                        mensagem=f"Taxa cobrada ({taxa_efetiva}%) difere da contratada ({taxa_esperada}%) em {diferenca:.2f}%",
                        severidade="alto" if diferenca > Decimal("2.0") else "medio",
                        detalhes={
                            "venda_id": v.id,
                            "nsu": v.nsu,
                            "adquirente": adq_nome,
                            "bandeira": bandeira,
                            "data_venda": v.data_venda.strftime("%d/%m/%Y") if v.data_venda else None,
                            "valor_bruto": str(v.valor_bruto),
                            "valor_liquido": str(v.valor_liquido),
                            "taxa_cobrada": str(taxa_efetiva),
                            "taxa_esperada": str(taxa_esperada),
                            "diferenca_percentual": str(diferenca)
                        }
                    )
                    alertas.append(alerta)
                    resumo_adquirentes[adq_nome]["alertas"] += 1
                    resumo_bandeiras[bandeira]["alertas"] += 1
            
            # ✅ Verificação 2: Taxa não registrada (valor_liquido == valor_bruto)
            elif taxa_efetiva is not None and taxa_efetiva == Decimal("0"):
                alerta = formatar_alerta(
                    tipo="taxa_nao_cobrada",
                    mensagem="Venda sem taxa registrada (valor líquido = valor bruto)",
                    severidade="baixo",
                    detalhes={
                        "venda_id": v.id,
                        "nsu": v.nsu,
                        "adquirente": adq_nome,
                        "bandeira": bandeira,
                        "data_venda": v.data_venda.strftime("%d/%m/%Y") if v.data_venda else None,
                        "valor_bruto": str(v.valor_bruto)
                    }
                )
                alertas.append(alerta)
                resumo_adquirentes[adq_nome]["alertas"] += 1
                resumo_bandeiras[bandeira]["alertas"] += 1
            
            # ✅ Verificação 3: Taxa excessivamente alta (possível erro de importação)
            if taxa_efetiva is not None and taxa_efetiva > Decimal("20"):  # Mais de 20% é suspeito
                alerta = formatar_alerta(
                    tipo="taxa_excessiva",
                    mensagem=f"Taxa cobrada ({taxa_efetiva}%) está acima do limite esperado",
                    severidade="critico",
                    detalhes={
                        "venda_id": v.id,
                        "nsu": v.nsu,
                        "adquirente": adq_nome,
                        "bandeira": bandeira,
                        "data_venda": v.data_venda.strftime("%d/%m/%Y") if v.data_venda else None,
                        "valor_bruto": str(v.valor_bruto),
                        "valor_liquido": str(v.valor_liquido),
                        "taxa_cobrada": str(taxa_efetiva)
                    }
                )
                alertas.append(alerta)
                resumo_adquirentes[adq_nome]["alertas"] += 1
                resumo_bandeiras[bandeira]["alertas"] += 1
        
        # Calcular médias de taxa por adquirente/bandeira
        for adq in resumo_adquirentes.values():
            if adq["taxa_media"]:
                adq["taxa_media_percentual"] = str(
                    sum(adq["taxa_media"]) / len(adq["taxa_media"])
                )
            del adq["taxa_media"]  # Remover lista bruta para resposta mais limpa
        
        for band in resumo_bandeiras.values():
            if band["taxa_media"]:
                band["taxa_media_percentual"] = str(
                    sum(band["taxa_media"]) / len(band["taxa_media"])
                )
            del band["taxa_media"]
        
        # Filtrar apenas alertas se solicitado
        if apenas_com_alertas:
            alertas_filtrados = [a for a in alertas if a["severidade"] in ("medio", "alto", "critico")]
        else:
            alertas_filtrados = alertas
        
        logger.info(f"Auditoria concluída: {total_analisados} analisados, {len(alertas_filtrados)} alertas")
        
        return {
            "total_analisados": total_analisados,
            "com_alertas": len(alertas_filtrados),
            "alertas": alertas_filtrados,
            "resumo_por_adquirente": resumo_adquirentes,
            "resumo_por_bandeira": resumo_bandeiras,
            "configuracoes": {
                "tolerancia_taxa_percentual": str(TOLERANCIA_TAXA_PERCENTUAL),
                "tolerancia_valor_absoluto": str(TOLERANCIA_VALOR_ABSOLUTO)
            }
        }
        
    except Exception as e:
        logger.error(f"❌ Erro na auditoria de taxas: {str(e)}", exc_info=True)
        raise


# ============================================================
# AUDITORIA DE CONCILIAÇÃO
# ============================================================

def auditar_conciliacao(
    empresa_id,
    data_inicio=None,
    data_fim=None,
    apenas_pendentes=True
):
    """
    Auditoria de conciliação: identifica vendas não conciliadas e discrepâncias.
    
    ✅ Detecta:
        - Vendas pendentes além do prazo esperado
        - Recebimentos sem venda correspondente
        - Diferenças de valor entre venda e recebimento
        - Conciliações com valor divergente
    
    Returns:
        dict: {
            "vendas_pendentes": [...],
            "recebimentos_sem_origem": [...],
            "discrepancias_valor": [...],
            "resumo": {...}
        }
    """
    
    logger.info(f"Iniciando auditoria de conciliação: empresa={empresa_id}")
    
    try:
        # ✅ Vendas pendentes além do prazo
        query_pendentes = db.session.query(MovAdquirente).filter(
            MovAdquirente.empresa_id == empresa_id,
            MovAdquirente.ativo == True,
            MovAdquirente.status_conciliacao == "pendente"
        )
        
        if data_inicio:
            query_pendentes = query_pendentes.filter(MovAdquirente.data_venda >= data_inicio)
        if data_fim:
            query_pendentes = query_pendentes.filter(MovAdquirente.data_venda <= data_fim)
        
        # Considerar pendente crítico se > 30 dias da data prevista
        hoje = datetime.now().date()
        vendas_pendentes = []
        for v in query_pendentes.all():
            dias_atraso = None
            if v.data_prevista_pagamento:
                dias_atraso = (hoje - v.data_prevista_pagamento).days
            
            # Só incluir se estiver realmente atrasado ou se não filtrar por pendentes
            if not apenas_pendentes or (dias_atraso and dias_atraso > 0):
                vendas_pendentes.append({
                    "venda_id": v.id,
                    "nsu": v.nsu,
                    "adquirente": v.adquirente.nome if v.adquirente else None,
                    "bandeira": v.bandeira,
                    "data_venda": v.data_venda.strftime("%d/%m/%Y") if v.data_venda else None,
                    "data_prevista": v.data_prevista_pagamento.strftime("%d/%m/%Y") if v.data_prevista_pagamento else None,
                    "valor_liquido": str(v.valor_liquido),
                    "dias_atraso": dias_atraso,
                    "severidade": "critico" if (dias_atraso and dias_atraso > 30) else "medio" if (dias_atraso and dias_atraso > 7) else "baixo"
                })
        
        # ✅ Recebimentos sem origem (não conciliados)
        query_recebimentos = db.session.query(MovBanco).filter(
            MovBanco.empresa_id == empresa_id,
            MovBanco.conciliado == False,
            MovBanco.valor > 0
        )
        
        if data_inicio:
            query_recebimentos = query_recebimentos.filter(MovBanco.data_movimento >= data_inicio)
        if data_fim:
            query_recebimentos = query_recebimentos.filter(MovBanco.data_movimento <= data_fim)
        
        recebimentos_sem_origem = [{
            "recebimento_id": r.id,
            "documento": r.documento,
            "banco": r.banco,
            "data_movimento": r.data_movimento.strftime("%d/%m/%Y") if r.data_movimento else None,
            "valor": str(r.valor),
            "historico": r.historico[:100] if r.historico else None
        } for r in query_recebimentos.all()]
        
        # ✅ Discrepâncias de valor em conciliações existentes
        query_conciliacoes = db.session.query(Conciliacao, MovAdquirente, MovBanco).join(
            MovAdquirente, Conciliacao.mov_adquirente_id == MovAdquirente.id
        ).join(
            MovBanco, Conciliacao.mov_banco_id == MovBanco.id
        ).filter(
            MovAdquirente.empresa_id == empresa_id,
            Conciliacao.ativo == True
        )
        
        discrepancias = []
        for conc, venda, recebimento in query_conciliacoes.all():
            valor_previsto = Decimal(str(venda.valor_liquido or 0))
            valor_conciliado = Decimal(str(conc.valor_conciliado or 0))
            
            if not comparar_valores_monetarios(valor_previsto, valor_conciliado):
                diferenca = valor_previsto - valor_conciliado
                discrepancias.append({
                    "conciliacao_id": conc.id,
                    "venda_id": venda.id,
                    "nsu": venda.nsu,
                    "valor_previsto": str(valor_previsto),
                    "valor_conciliado": str(valor_conciliado),
                    "diferenca": str(diferenca),
                    "severidade": "alto" if abs(diferenca) > Decimal("10") else "medio"
                })
        
        logger.info(f"Auditoria de conciliação concluída: {len(vendas_pendentes)} pendentes, {len(recebimentos_sem_origem)} sem origem, {len(discrepancias)} discrepâncias")
        
        return {
            "vendas_pendentes": vendas_pendentes,
            "recebimentos_sem_origem": recebimentos_sem_origem,
            "discrepancias_valor": discrepancias,
            "resumo": {
                "total_pendentes": len(vendas_pendentes),
                "pendentes_criticos": len([v for v in vendas_pendentes if v["severidade"] == "critico"]),
                "total_sem_origem": len(recebimentos_sem_origem),
                "total_discrepancias": len(discrepancias)
            }
        }
        
    except Exception as e:
        logger.error(f"❌ Erro na auditoria de conciliação: {str(e)}", exc_info=True)
        raise


# ============================================================
# AUDITORIA DE INTEGRIDADE DE DADOS
# ============================================================

def auditar_integridade(empresa_id):
    """
    Auditoria de integridade: verifica consistência dos dados no banco.
    
    ✅ Detecta:
        - Vendas com valores negativos ou zerados
        - Datas inválidas ou futuras
        - Relacionamentos órfãos (adquirente deletada, etc.)
        - Registros duplicados por NSU
    
    Returns:
        dict: {
            "alertas": [...],
            "resumo": {...}
        }
    """
    
    logger.info(f"Iniciando auditoria de integridade: empresa={empresa_id}")
    alertas = []
    
    try:
        # ✅ Verificação 1: Valores inválidos
        vendas_valores = MovAdquirente.query.filter(
            MovAdquirente.empresa_id == empresa_id,
            or_(
                MovAdquirente.valor_bruto <= 0,
                MovAdquirente.valor_liquido <= 0,
                MovAdquirente.valor_liquido > MovAdquirente.valor_bruto
            )
        ).all()
        
        for v in vendas_valores:
            alertas.append(formatar_alerta(
                tipo="valor_invalido",
                mensagem="Venda com valores inconsistentes",
                severidade="alto",
                detalhes={
                    "venda_id": v.id,
                    "nsu": v.nsu,
                    "valor_bruto": str(v.valor_bruto),
                    "valor_liquido": str(v.valor_liquido)
                }
            ))
        
        # ✅ Verificação 2: Datas futuras ou muito antigas
        hoje = datetime.now().date()
        vendas_datas = MovAdquirente.query.filter(
            MovAdquirente.empresa_id == empresa_id,
            or_(
                MovAdquirente.data_venda > hoje + timedelta(days=30),  # Futuro > 30 dias
                MovAdquirente.data_venda < hoje - timedelta(days=730)  # Mais de 2 anos atrás
            )
        ).all()
        
        for v in vendas_datas:
            alertas.append(formatar_alerta(
                tipo="data_suspeita",
                mensagem=f"Data de venda fora do esperado: {v.data_venda}",
                severidade="medio",
                detalhes={
                    "venda_id": v.id,
                    "nsu": v.nsu,
                    "data_venda": v.data_venda.strftime("%d/%m/%Y") if v.data_venda else None
                }
            ))
        
        # ✅ Verificação 3: NSUs duplicados (mesma adquirente)
        from sqlalchemy import func
        duplicatas = db.session.query(
            MovAdquirente.nsu,
            MovAdquirente.adquirente_id,
            func.count().label('qtd')
        ).filter(
            MovAdquirente.empresa_id == empresa_id,
            MovAdquirente.nsu != None,
            MovAdquirente.nsu != ''
        ).group_by(
            MovAdquirente.nsu,
            MovAdquirente.adquirente_id
        ).having(
            func.count() > 1
        ).all()
        
        for nsu, adq_id, qtd in duplicatas:
            alertas.append(formatar_alerta(
                tipo="nsu_duplicado",
                mensagem=f"NSU '{nsu}' aparece {qtd} vezes para a mesma adquirente",
                severidade="alto",
                detalhes={
                    "nsu": nsu,
                    "adquirente_id": adq_id,
                    "quantidade": qtd
                }
            ))
        
        # ✅ Verificação 4: Adquirente não encontrada (chave estrangeira quebrada)
        vendas_orfas = MovAdquirente.query.filter(
            MovAdquirente.empresa_id == empresa_id,
            MovAdquirente.adquirente_id != None,
            ~MovAdquirente.adquirente_id.in_(
                db.session.query(Adquirente.id)
            )
        ).all()
        
        for v in vendas_orfas:
            alertas.append(formatar_alerta(
                tipo="adquirente_orfa",
                mensagem="Venda referencia adquirente que não existe mais",
                severidade="critico",
                detalhes={
                    "venda_id": v.id,
                    "nsu": v.nsu,
                    "adquirente_id": v.adquirente_id
                }
            ))
        
        logger.info(f"Auditoria de integridade concluída: {len(alertas)} alertas encontrados")
        
        return {
            "alertas": alertas,
            "resumo": {
                "total_alertas": len(alertas),
                "por_severidade": {
                    "critico": len([a for a in alertas if a["severidade"] == "critico"]),
                    "alto": len([a for a in alertas if a["severidade"] == "alto"]),
                    "medio": len([a for a in alertas if a["severidade"] == "medio"]),
                    "baixo": len([a for a in alertas if a["severidade"] == "baixo"])
                }
            }
        }
        
    except Exception as e:
        logger.error(f"❌ Erro na auditoria de integridade: {str(e)}", exc_info=True)
        raise


# ============================================================
# FUNÇÃO UNIFICADA DE AUDITORIA
# ============================================================

def executar_auditoria_completa(
    empresa_id,
    tipos=None,  # ['taxas', 'conciliacao', 'integridade'] ou None para todos
    **kwargs
):
    """
    Executa múltiplos tipos de auditoria em uma única chamada.
    
    Args:
        empresa_id: ID da empresa
        tipos: Lista de tipos de auditoria a executar (None = todos)
        **kwargs: Parâmetros adicionais passados para cada auditoria
    
    Returns:
        dict: Resultados consolidados de todas as auditorias executadas
    """
    
    if tipos is None:
        tipos = ['taxas', 'conciliacao', 'integridade']
    
    resultados = {
        "empresa_id": empresa_id,
        "timestamp": datetime.now().isoformat(),
        "auditorias": {}
    }
    
    if 'taxas' in tipos:
        resultados["auditorias"]["taxas"] = auditar_taxas(empresa_id, **kwargs)
    
    if 'conciliacao' in tipos:
        resultados["auditorias"]["conciliacao"] = auditar_conciliacao(empresa_id, **kwargs)
    
    if 'integridade' in tipos:
        resultados["auditorias"]["integridade"] = auditar_integridade(empresa_id)
    
    # Resumo consolidado
    total_alertas = sum(
        len(aud.get("alertas", [])) if isinstance(aud, dict) else 0
        for aud in resultados["auditorias"].values()
    )
    
    resultados["resumo_consolidado"] = {
        "auditorias_executadas": list(resultados["auditorias"].keys()),
        "total_alertas": total_alertas,
        "alertas_criticos": sum(
            len([a for a in aud.get("alertas", []) if a.get("severidade") == "critico"])
            if isinstance(aud, dict) else 0
            for aud in resultados["auditorias"].values()
        )
    }
    
    return resultados
