from models import db, MovAdquirente, MovBanco, Adquirente, ContaBancaria
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
import logging

logger = logging.getLogger(__name__)

# ============================================================
# CONFIGURAÇÕES
# ============================================================
BATCH_SIZE = 100

# ============================================================
# CONVERTERS SEGUROS
# ============================================================
def to_date(valor):
    """Converte valor para date de forma segura"""
    if not valor:
        return None
    
    if isinstance(valor, (datetime,)):
        return valor.date()
    
    if isinstance(valor, str):
        formatos = ["%Y-%m-%d", "%d/%m/%Y", "%Y-%m-%d %H:%M:%S"]
        for fmt in formatos:
            try:
                return datetime.strptime(valor, fmt).date()
            except:
                pass
    
    return None

def to_decimal(valor, default=Decimal("0")):
    """Converte valor para Decimal de forma segura"""
    try:
        if valor is None:
            return default
        return Decimal(str(valor))
    except (InvalidOperation, ValueError, TypeError):
        logger.warning(f"Valor inválido para Decimal: {valor}")
        return default

def to_int(valor, default=None):
    """Converte valor para int de forma segura"""
    try:
        return int(valor) if valor is not None else default
    except (ValueError, TypeError):
        return default

# ============================================================
# VALIDAÇÕES
# ============================================================
def validar_adquirente(adquirente_id):
    """Valida se adquirente existe"""
    if not adquirente_id:
        return None
    adquirente = Adquirente.query.filter_by(id=int(adquirente_id)).first()
    return adquirente.id if adquirente else None

def validar_conta_bancaria(conta_id, empresa_id):
    """Valida se conta bancária existe e pertence à empresa"""
    if not conta_id:
        return None
    conta = ContaBancaria.query.filter_by(id=int(conta_id), empresa_id=empresa_id).first()
    return conta.id if conta else None

def verificar_venda_duplicada(empresa_id, nsu, adquirente_id):
    """Verifica se venda já existe pelo NSU"""
    if not nsu:
        return False
    venda = MovAdquirente.query.filter_by(
        empresa_id=empresa_id,
        adquirente_id=adquirente_id,
        nsu=str(nsu)
    ).first()
    return venda is not None

# ============================================================
# SALVAR VENDAS
# ============================================================
def salvar_vendas(registros, empresa_id, arquivo_id, usuario_id=None):
    """Salva vendas em batches com validação e tratamento de erro"""
    
    logger.info(f"Início importação vendas: empresa={empresa_id}, registros={len(registros)}")
    
    estatisticas = {
        "total": len(registros),
        "sucesso": 0,
        "falhas": 0,
        "duplicatas": 0,
        "invalidos": 0
    }
    
    for i in range(0, len(registros), BATCH_SIZE):
        batch = registros[i:i+BATCH_SIZE]
        
        try:
            db.session.begin_nested()
            
            for r in batch:
                try:
                    # Validar dados obrigatórios
                    valor_bruto = to_decimal(r.get("valor_bruto"))
                    if valor_bruto <= 0:
                        estatisticas["invalidos"] += 1
                        continue
                    
                    # Validar adquirente
                    adquirente_id = validar_adquirente(r.get("adquirente_id"))
                    if not adquirente_id:
                        estatisticas["falhas"] += 1
                        continue
                    
                    # Verificar duplicata
                    if verificar_venda_duplicada(empresa_id, r.get("nsu"), adquirente_id):
                        estatisticas["duplicatas"] += 1
                        continue
                    
                    # Criar venda
                    venda = MovAdquirente(
                        empresa_id=empresa_id,
                        adquirente_id=adquirente_id,
                        data_venda=to_date(r.get("data_venda")),
                        data_prevista_pagamento=to_date(r.get("data_prevista")),
                        bandeira=str(r.get("bandeira", ""))[:50] if r.get("bandeira") else None,
                        produto=str(r.get("produto", ""))[:50] if r.get("produto") else None,
                        parcela=to_int(r.get("parcela")),
                        total_parcelas=to_int(r.get("total_parcelas")),
                        nsu=str(r.get("nsu", ""))[:50] if r.get("nsu") else None,
                        autorizacao=str(r.get("autorizacao", ""))[:50] if r.get("autorizacao") else None,
                        valor_bruto=valor_bruto,
                        taxa_cobrada=to_decimal(r.get("taxa")),
                        valor_liquido=to_decimal(r.get("valor_liquido")),
                        valor_conciliado=Decimal("0"),
                        status_conciliacao="pendente",
                        arquivo_origem=str(arquivo_id)[:255] if arquivo_id else None
                    )
                    
                    db.session.add(venda)
                    estatisticas["sucesso"] += 1
                    
                except Exception as e:
                    logger.error(f"Erro ao processar venda: {str(e)}")
                    estatisticas["falhas"] += 1
                    continue
            
            db.session.commit()
            
        except SQLAlchemyError as e:
            db.session.rollback()
            logger.error(f"Erro no batch {i}: {str(e)}")
            estatisticas["falhas"] += len(batch)
    
    logger.info(f"Fim importação vendas: {estatisticas}")
    
    return estatisticas

# ============================================================
# SALVAR RECEBIMENTOS
# ============================================================
def salvar_recebimentos(registros, empresa_id, arquivo_id, usuario_id=None):
    """Salva recebimentos em batches com validação e tratamento de erro"""
    
    logger.info(f"Início importação recebimentos: empresa={empresa_id}, registros={len(registros)}")
    
    estatisticas = {
        "total": len(registros),
        "sucesso": 0,
        "falhas": 0,
        "duplicatas": 0,
        "invalidos": 0
    }
    
    for i in range(0, len(registros), BATCH_SIZE):
        batch = registros[i:i+BATCH_SIZE]
        
        try:
            db.session.begin_nested()
            
            for r in batch:
                try:
                    # Validar dados obrigatórios
                    valor = to_decimal(r.get("valor"))
                    if valor <= 0:
                        estatisticas["invalidos"] += 1
                        continue
                    
                    # Validar conta bancária
                    conta_id = validar_conta_bancaria(r.get("conta_id"), empresa_id)
                    if not conta_id:
                        estatisticas["falhas"] += 1
                        continue
                    
                    # Criar recebimento
                    mov = MovBanco(
                        empresa_id=empresa_id,
                        conta_bancaria_id=conta_id,
                        data_movimento=to_date(r.get("data")),
                        historico=str(r.get("descricao", ""))[:255] if r.get("descricao") else None,
                        documento=str(r.get("documento", ""))[:100] if r.get("documento") else None,
                        origem=str(r.get("origem", ""))[:50] if r.get("origem") else None,
                        valor=valor,
                        valor_conciliado=Decimal("0"),
                        conciliado=False,
                        arquivo_origem=str(arquivo_id)[:255] if arquivo_id else None
                    )
                    
                    db.session.add(mov)
                    estatisticas["sucesso"] += 1
                    
                except Exception as e:
                    logger.error(f"Erro ao processar recebimento: {str(e)}")
                    estatisticas["falhas"] += 1
                    continue
            
            db.session.commit()
            
        except SQLAlchemyError as e:
            db.session.rollback()
            logger.error(f"Erro no batch {i}: {str(e)}")
            estatisticas["falhas"] += len(batch)
    
    logger.info(f"Fim importação recebimentos: {estatisticas}")
    
    return estatisticas
