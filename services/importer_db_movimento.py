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
# SALVAR VENDAS (MovAdquirente)
# ============================================================
def salvar_vendas(registros: list, empresa_id: int, arquivo_id: int = None) -> dict:
    """
    Salva registros de vendas (MovAdquirente) no banco.
    Aceita tanto formato OFX quanto Flow CSV.
    """
    from models import MovAdquirente, Adquirente
    
    stats = {
        "sucesso": 0,
        "falhas": 0,
        "duplicados": 0,
        "total_valor": Decimal("0"),
        "adquirente_criada": False,
        "adquirentes_processadas": set()
    }
    
    try:
        for reg in registros:
            try:
                # ✅ Extrair dados com fallbacks
                adquirente_nome = reg.get('adquirente') or reg.get('nome_adquirente') or 'Desconhecida'
                nsu = reg.get('nsu') or reg.get('id') or reg.get('fitid')
                data_transacao = reg.get('data_transacao') or reg.get('data_venda') or reg.get('data')
                valor = reg.get('valor') or reg.get('valor_liquido') or reg.get('valor_bruto') or 0
                valor_bruto = reg.get('valor_bruto') or valor
                bandeira = reg.get('bandeira')
                produto = reg.get('produto')
                quantidade = reg.get('quantidade') or 1
                descricao = reg.get('descricao') or reg.get('memo') or ''
                
                # Converter valor para Decimal
                if not isinstance(valor, Decimal):
                    try:
                        valor = Decimal(str(valor))
                    except:
                        valor = Decimal("0")
                
                if valor <= 0:
                    stats["falhas"] += 1
                    continue
                
                # ✅ Resolver adquirente
                adquirente = Adquirente.query.filter(
                    db.func.lower(Adquirente.nome) == adquirente_nome.lower()
                ).first()
                
                if not adquirente:
                    # Criar adquirente automaticamente
                    adquirente = Adquirente(
                        nome=adquirente_nome,
                        ativo=True,
                        criado_em=datetime.now(timezone.utc)
                    )
                    db.session.add(adquirente)
                    db.session.flush()
                    stats["adquirente_criada"] = True
                    logger.info(f"✅ Adquirente criada: {adquirente_nome}")
                
                stats["adquirentes_processadas"].add(adquirente_nome)
                
                # ✅ Verificar duplicata pelo NSU
                if nsu:
                    duplicata = MovAdquirente.query.filter_by(
                        empresa_id=empresa_id,
                        nsu=nsu,
                        ativo=True
                    ).first()
                    
                    if duplicata:
                        stats["duplicados"] += 1
                        continue
                
                # ✅ Parse data
                data_venda = None
                if data_transacao:
                    if isinstance(data_transacao, str):
                        try:
                            data_venda = datetime.strptime(data_transacao, '%Y-%m-%d').date()
                        except:
                            try:
                                data_venda = datetime.strptime(data_transacao, '%d/%m/%Y').date()
                            except:
                                data_venda = date.today()
                    elif isinstance(data_transacao, (date, datetime)):
                        data_venda = data_transacao if isinstance(data_transacao, date) else data_transacao.date()
                    else:
                        data_venda = date.today()
                else:
                    data_venda = date.today()
                
                # ✅ Criar registro MovAdquirente
                mov = MovAdquirente(
                    empresa_id=empresa_id,
                    adquirente_id=adquirente.id,
                    arquivo_id=arquivo_id,
                    nsu=nsu,
                    data_transacao=data_venda,
                    valor=valor,
                    valor_bruto=Decimal(str(valor_bruto)) if valor_bruto else valor,
                    bandeira=bandeira,
                    produto=produto,
                    quantidade=int(quantidade) if quantidade else 1,
                    descricao=descricao,
                    tipo_pagamento='cartao',
                    status='conciliado' if reg.get('conciliado') else 'pendente',
                    ativo=True,
                    criado_em=datetime.now(timezone.utc)
                )
                
                db.session.add(mov)
                stats["sucesso"] += 1
                stats["total_valor"] += valor
                
            except Exception as e:
                logger.error(f"❌ Erro ao salvar venda: {str(e)}", exc_info=True)
                stats["falhas"] += 1
                continue
        
        db.session.commit()
        logger.info(f"✅ Vendas salvas: {stats['sucesso']} sucesso, {stats['falhas']} falhas, {stats['duplicados']} duplicados")
        
        return stats
        
    except Exception as e:
        logger.error(f"❌ Erro geral ao salvar vendas: {str(e)}", exc_info=True)
        db.session.rollback()
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
