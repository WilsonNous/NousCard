# services/importer_db_movimento.py
# ✅ VERSÃO FINAL COMPLETA: Suporte a Vendas, Recebimentos, Categorias e Contas Automáticas

from models import db, MovAdquirente, MovBanco, Adquirente, ContaBancaria
from datetime import datetime, date, timezone
from decimal import Decimal, InvalidOperation
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from sqlalchemy import func
import logging
import time

logger = logging.getLogger(__name__)

# ============================================================
# CONFIGURAÇÕES
# ============================================================
BATCH_SIZE = 200  # ✅ Otimizado para evitar estouro de memória no Render

# ============================================================
# CONVERTERS SEGUROS
# ============================================================
def to_date(valor):
    """Converte valor para date de forma segura."""
    if not valor:
        return None
    if isinstance(valor, date) and not isinstance(valor, datetime):
        return valor
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, str):
        valor = valor.strip()
        formatos = [
            "%Y-%m-%d", "%d/%m/%Y", "%Y-%m-%d %H:%M:%S", "%d/%m/%Y %H:%M:%S", "%Y%m%d"
        ]
        for fmt in formatos:
            try:
                return datetime.strptime(valor, fmt).date()
            except (ValueError, TypeError):
                continue
    return None


def to_decimal(valor, default=Decimal("0")):
    """Converte valor para Decimal de forma segura."""
    try:
        if valor is None:
            return default
        if isinstance(valor, Decimal):
            return valor
        return Decimal(str(valor))
    except (InvalidOperation, ValueError, TypeError):
        return default


def resolver_adquirente_id(valor, empresa_id=None):
    """
    Resolve o ID da adquirente por ID numérico OU por nome (string).
    Se não existir, cria um registro genérico para não perder a venda.
    """
    if not valor:
        return None
    
    # Se for número, retorna direto
    if isinstance(valor, (int, float)):
        return int(valor)
    if isinstance(valor, str) and valor.strip().isdigit():
        return int(valor.strip())
    
    # Se for nome (string), busca no banco
    if isinstance(valor, str):
        nome_normalizado = valor.strip()
        
        # Busca exata
        adquirente = Adquirente.query.filter(
            func.lower(Adquirente.nome) == nome_normalizado.lower()
        ).first()
        if adquirente:
            return adquirente.id
        
        # Busca parcial (contém)
        adquirente = Adquirente.query.filter(
            func.lower(Adquirente.nome).contains(nome_normalizado.lower())
        ).first()
        if adquirente:
            return adquirente.id
        
        # ✅ Fallback: Criar adquirente genérica se não encontrar
        try:
            nova_adquirente = Adquirente(
                nome=nome_normalizado[:100],
                codigo="GEN",
                empresa_id=empresa_id,  # Vincula à empresa se possível
                ativo=True
            )
            db.session.add(nova_adquirente)
            db.session.flush()
            logger.info(f"✅ Adquirente criada automaticamente: {nome_normalizado}")
            return nova_adquirente.id
        except Exception as e:
            logger.warning(f"⚠️ Falha ao criar adquirente '{nome_normalizado}': {str(e)}")
            return None
    
    return None

# ============================================================
# SALVAR VENDAS (MovAdquirente) - VERSÃO FINAL SEM NESTED TRANSACTIONS
# ============================================================
def salvar_vendas(registros: list, empresa_id: int, arquivo_id: int = None) -> dict:
    """
    Salva registros de vendas (MovAdquirente) em batches com commits independentes.
    Sem nested transactions para evitar PendingRollbackError.
    """
    from models import MovAdquirente, Adquirente
    
    stats = {
        "sucesso": 0,
        "falhas": 0,
        "duplicados": 0,
        "total_valor_bruto": Decimal("0"),
        "total_valor_liquido": Decimal("0"),
        "adquirente_criada": False,
        "adquirentes_processadas": set()
    }
    
    if not registros:
        logger.warning("⚠️ Nenhum registro para salvar como venda")
        return stats
    
    logger.info(f"💾 Iniciando salvamento de {len(registros)} vendas para empresa {empresa_id}")
    
    # ✅ OTIMIZAÇÃO 1: Resolver adquirentes UMA VEZ no início
    adquirentes_cache = {}
    
    # Extrair nomes únicos de adquirentes
    nomes_adquirentes = set()
    for reg in registros:
        nome = (
            reg.get('adquirente') or 
            reg.get('nome_adquirente') or 
            'Flow'
        )
        nomes_adquirentes.add(nome)
    
    logger.info(f"🔍 Resolvendo {len(nomes_adquirentes)} adquirente(s) únicas...")
    
    # Resolver cada adquirente uma vez
    for nome in nomes_adquirentes:
        try:
            adquirente = Adquirente.query.filter(
                func.lower(Adquirente.nome) == nome.lower()
            ).first()
            
            if not adquirente:
                # Criar adquirente
                adquirente = Adquirente(
                    nome=nome[:100],
                    codigo=nome[:20].upper().replace(' ', '_'),
                    ativo=True
                )
                db.session.add(adquirente)
                db.session.commit()  # ✅ Commit imediato
                stats["adquirente_criada"] = True
                logger.info(f"✅ Adquirente criada: {nome} (id={adquirente.id})")
            
            adquirentes_cache[nome.lower()] = adquirente
            stats["adquirentes_processadas"].add(nome)
            
        except Exception as e:
            logger.error(f"❌ Erro ao resolver adquirente '{nome}': {str(e)}", exc_info=True)
            db.session.rollback()  # ✅ Rollback em caso de erro
    
    # ✅ OTIMIZAÇÃO 2: Processar em batches pequenos com commits independentes
    BATCH_SIZE = 20  # Salvar 20 registros por vez
    total_batches = (len(registros) + BATCH_SIZE - 1) // BATCH_SIZE
    
    logger.info(f"📦 Processando em {total_batches} batches de {BATCH_SIZE} registros...")
    
    for batch_num in range(total_batches):
        inicio_idx = batch_num * BATCH_SIZE
        fim_idx = min((batch_num + 1) * BATCH_SIZE, len(registros))
        batch = registros[inicio_idx:fim_idx]
        
        logger.info(f"📦 Batch {batch_num + 1}/{total_batches}: registros {inicio_idx + 1}-{fim_idx}")
        
        batch_sucesso = 0
        batch_falhas = 0
        batch_duplicados = 0
        
        try:
            # ✅ SEM begin_nested() - usar apenas commit direto
            for idx, reg in enumerate(batch):
                try:
                    # ✅ Usar adquirente do cache (sem query!)
                    adquirente_nome = (
                        reg.get('adquirente') or 
                        reg.get('nome_adquirente') or 
                        'Flow'
                    ).lower()
                    
                    adquirente = adquirentes_cache.get(adquirente_nome)
                    if not adquirente:
                        logger.warning(f"⚠️ Adquirente '{adquirente_nome}' não encontrada no cache, pulando")
                        batch_falhas += 1
                        continue
                    
                    # Extrair dados
                    nsu = (
                        reg.get('nsu') or 
                        reg.get('id') or 
                        reg.get('fitid') or 
                        f"AUTO-{stats['sucesso'] + batch_sucesso}-{empresa_id}"
                    )
                    
                    data_venda_raw = (
                        reg.get('data_venda') or 
                        reg.get('data_transacao') or 
                        reg.get('data')
                    )
                    
                    valor_bruto_raw = reg.get('valor_bruto') or reg.get('valor') or 0
                    valor_liquido_raw = reg.get('valor_liquido') or valor_bruto_raw
                    desconto_raw = reg.get('desconto') or reg.get('taxa_cobrada') or 0
                    
                    bandeira = reg.get('bandeira')
                    produto = reg.get('produto')
                    tipo_pagamento = reg.get('tipo_pagamento', 'cartao')
                    
                    if tipo_pagamento not in ['cartao', 'pix', 'boleto', 'outros']:
                        tipo_pagamento = 'cartao'
                    
                    observacoes = (
                        reg.get('observacoes') or 
                        reg.get('descricao') or 
                        ''
                    )
                    
                    # Converter valores
                    try:
                        valor_bruto = Decimal(str(valor_bruto_raw))
                        valor_liquido = Decimal(str(valor_liquido_raw))
                        taxa_cobrada = Decimal(str(desconto_raw))
                    except:
                        valor_bruto = Decimal("0")
                        valor_liquido = Decimal("0")
                        taxa_cobrada = Decimal("0")
                    
                    if valor_bruto <= 0:
                        batch_falhas += 1
                        continue
                    
                    # Verificar duplicata
                    if nsu:
                        try:
                            duplicata = MovAdquirente.query.filter_by(
                                empresa_id=empresa_id,
                                nsu=nsu,
                                ativo=True
                            ).first()
                            
                            if duplicata:
                                batch_duplicados += 1
                                continue
                        except Exception as e:
                            logger.warning(f"⚠️ Erro ao verificar duplicata: {str(e)}")
                    
                    # Parse data
                    data_venda = None
                    if data_venda_raw:
                        if isinstance(data_venda_raw, (date, datetime)):
                            data_venda = data_venda_raw if isinstance(data_venda_raw, date) else data_venda_raw.date()
                        elif isinstance(data_venda_raw, str):
                            for fmt in ['%Y-%m-%d', '%d/%m/%Y', '%Y/%m/%d']:
                                try:
                                    data_venda = datetime.strptime(data_venda_raw, fmt).date()
                                    break
                                except:
                                    continue
                            if not data_venda:
                                data_venda = date.today()
                        else:
                            data_venda = date.today()
                    else:
                        data_venda = date.today()
                    
                    # Criar registro
                    mov = MovAdquirente(
                        empresa_id=empresa_id,
                        adquirente_id=adquirente.id,
                        data_venda=data_venda,
                        valor_bruto=valor_bruto,
                        valor_liquido=valor_liquido,
                        taxa_cobrada=taxa_cobrada,
                        arquivo_origem=str(arquivo_id) if arquivo_id else None,
                        bandeira=bandeira[:50] if bandeira else None,
                        tipo_pagamento=tipo_pagamento,
                        produto=produto[:50] if produto else None,
                        nsu=nsu[:50] if nsu else None,
                        status_conciliacao='pendente',
                        valor_conciliado=Decimal("0"),
                        observacoes=observacoes[:2000] if observacoes else None,
                        ativo=True,
                        criado_em=datetime.now(timezone.utc)
                    )
                    
                    db.session.add(mov)
                    batch_sucesso += 1
                    
                except Exception as e:
                    logger.error(f"❌ Erro ao processar registro {inicio_idx + idx + 1}: {str(e)}", exc_info=True)
                    batch_falhas += 1
                    continue
            
            # ✅ Commit deste batch (SEM begin_nested)
            if batch_sucesso > 0:
                db.session.commit()
                logger.info(f"✅ Batch {batch_num + 1}/{total_batches} salvo: {batch_sucesso} sucesso, {batch_falhas} falhas, {batch_duplicados} duplicados")
            else:
                logger.warning(f"⚠️ Batch {batch_num + 1}/{total_batches} sem registros válidos")
            
            # Atualizar estatísticas globais
            stats["sucesso"] += batch_sucesso
            stats["falhas"] += batch_falhas
            stats["duplicados"] += batch_duplicados
            
            # Calcular valores do batch
            for reg in batch:
                try:
                    valor_bruto = Decimal(str(reg.get('valor_bruto') or reg.get('valor') or 0))
                    valor_liquido = Decimal(str(reg.get('valor_liquido') or valor_bruto))
                    if valor_bruto > 0:
                        stats["total_valor_bruto"] += valor_bruto
                        stats["total_valor_liquido"] += valor_liquido
                except:
                    pass
            
        except Exception as e:
            logger.error(f"❌ Erro no batch {batch_num + 1}: {str(e)}", exc_info=True)
            # ✅ Rollback explícito antes de continuar
            try:
                db.session.rollback()
                logger.info(f"🔄 Rollback executado após erro no batch {batch_num + 1}")
            except Exception as rollback_error:
                logger.error(f"❌ Erro ao fazer rollback: {str(rollback_error)}")
            
            stats["falhas"] += len(batch)
            continue
    
    logger.info(
        f"✅ Vendas salvas: {stats['sucesso']} sucesso, "
        f"{stats['falhas']} falhas, {stats['duplicados']} duplicados, "
        f"bruto: R$ {stats['total_valor_bruto']:.2f}, "
        f"líquido: R$ {stats['total_valor_liquido']:.2f}"
    )
    
    return stats

# ============================================================
# SALVAR RECEBIMENTOS (MovBanco)
# ============================================================
def salvar_recebimentos(registros, empresa_id, arquivo_id, usuario_id=None, dados_conta=None):
    """
    Salva registros de recebimentos na tabela mov_banco em batches.
    
    ✅ NOVO: Cria conta bancária automaticamente se não existir, usando dados do OFX.
    ✅ NOVO: Salva 'tipo_pagamento' e 'categoria' para análise financeira.
    """
    inicio_total = time.time()
    logger.info(f"🔍 Início importação recebimentos: empresa={empresa_id}, registros={len(registros)}")
    
    estatisticas = {
        "total": len(registros),
        "sucesso": 0,
        "falhas": 0,
        "invalidos": 0,
        "conta_criada": False,
        "conta_id": None
    }
    
    # 1. Garantir que existe uma conta bancária vinculada
    conta_id = None
    if dados_conta and (dados_conta.get("banco") or dados_conta.get("conta")):
        try:
            conta = ContaBancaria.query.filter_by(
                empresa_id=empresa_id,
                banco=dados_conta.get("banco"),
                agencia=dados_conta.get("agencia"),
                conta=dados_conta.get("conta"),
                ativo=True
            ).first()
            
            if not conta:
                conta = ContaBancaria(
                    empresa_id=empresa_id,
                    nome=dados_conta.get("nome", "Conta OFX"),
                    banco=dados_conta.get("banco"),
                    agencia=dados_conta.get("agencia"),
                    conta=dados_conta.get("conta"),
                    tipo=dados_conta.get("tipo", "corrente"),
                    ativo=True
                )
                db.session.add(conta)
                db.session.flush()
                estatisticas["conta_criada"] = True
                logger.info(f"✅ Conta bancária criada automaticamente: {conta.nome} (ID: {conta.id})")
            
            conta_id = conta.id
            estatisticas["conta_id"] = conta_id
            
        except Exception as e:
            logger.error(f"❌ Erro ao criar/verificar conta bancária: {str(e)}")
    
    # Fallback: pegar a primeira conta ativa da empresa se nada foi extraído
    if not conta_id:
        conta_fallback = ContaBancaria.query.filter_by(empresa_id=empresa_id, ativo=True).first()
        if conta_fallback:
            conta_id = conta_fallback.id
            estatisticas["conta_id"] = conta_id
        else:
            logger.error(f"❌ Nenhuma conta bancária encontrada para empresa {empresa_id}. Registros serão marcados sem conta.")
    
    # 2. Processar em batches
    for i in range(0, len(registros), BATCH_SIZE):
        batch = registros[i:i+BATCH_SIZE]
        
        try:
            db.session.begin_nested()
            
            for r in batch:
                try:
                    valor = to_decimal(r.get("valor"))
                    if valor == 0:
                        estatisticas["invalidos"] += 1
                        continue
                    
                    mov = MovBanco(
                        empresa_id=empresa_id,
                        conta_bancaria_id=conta_id,
                        data_movimento=to_date(r.get("data") or r.get("data_movimento")),
                        historico=str(r.get("descricao") or "").strip()[:255],
                        documento=str(r.get("nsu") or r.get("id") or "").strip()[:100],
                        origem="OFX",
                        valor=valor,  # Mantém o sinal (+ entrada, - saída) para DRE
                        tipo_pagamento=str(r.get("tipo_pagamento") or "outros").strip()[:50],
                        categoria=str(r.get("categoria") or "outros").strip()[:100],
                        valor_conciliado=Decimal("0"),
                        conciliado=False,
                        arquivo_origem=str(arquivo_id)[:255] if arquivo_id else None
                    )
                    
                    db.session.add(mov)
                    estatisticas["sucesso"] += 1
                    
                except Exception as e:
                    logger.debug(f"⚠️ Erro ao processar recebimento: {str(e)}")
                    estatisticas["falhas"] += 1
                    continue
            
            db.session.commit()
            logger.info(f"✅ Batch recebimentos {i//BATCH_SIZE + 1} salvo: {len(batch)} registros")
            
        except SQLAlchemyError as e:
            db.session.rollback()
            logger.error(f"❌ Erro de banco no batch de recebimentos {i//BATCH_SIZE + 1}: {str(e)}")
            estatisticas["falhas"] += len(batch)
        except Exception as e:
            db.session.rollback()
            logger.error(f"❌ Erro inesperado no batch de recebimentos {i//BATCH_SIZE + 1}: {str(e)}")
            estatisticas["falhas"] += len(batch)
    
    tempo_total = time.time() - inicio_total
    logger.info(f"✅ Fim importação recebimentos: {estatisticas} em {tempo_total:.2f}s")
    return estatisticas
