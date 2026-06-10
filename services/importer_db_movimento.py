# services/importer_db_movimento.py - VERSÃO FINAL

from models import db, MovAdquirente, MovBanco, Adquirente, ContaBancaria
from datetime import datetime, date, timezone
from decimal import Decimal, InvalidOperation
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from sqlalchemy import func
import logging

logger = logging.getLogger(__name__)

BATCH_SIZE = 100


# ============================================================
# ✅ NOVO: AUTO-CRIAR CONTA PADRÃO
# ============================================================
def obter_ou_criar_conta_padrao(empresa_id, nome_banco=None):
    """
    Obtém a conta padrão da empresa ou cria uma automaticamente.
    
    ✅ Campos usados (confirmados no modelo):
    - nome: "Conta Principal" ou nome do banco
    - banco: Nome extraído do OFX
    - agencia: "0000" (placeholder)
    - conta: "00000-0" (placeholder)
    - tipo: "corrente"
    
    Args:
        empresa_id: ID da empresa
        nome_banco: Nome do banco extraído do OFX (opcional)
    
    Returns:
        int: ID da conta bancária ou None se falhar
    """
    # Tentar encontrar conta existente
    conta = ContaBancaria.query.filter_by(
        empresa_id=empresa_id,
        ativo=True
    ).first()
    
    if conta:
        return conta.id
    
    # ✅ NÃO EXISTE: Criar conta padrão
    nome_conta = nome_banco or "Conta Principal"
    
    try:
        nova_conta = ContaBancaria(
            empresa_id=empresa_id,
            nome=nome_conta,
            banco=nome_banco or "Não informado",
            agencia="0000",
            conta="00000-0",
            tipo="corrente",
            ativo=True
        )
        db.session.add(nova_conta)
        db.session.flush()  # Gera ID sem commit
        
        logger.info(f"✅ Conta padrão criada: id={nova_conta.id}, nome={nome_conta}, empresa={empresa_id}")
        return nova_conta.id
        
    except Exception as e:
        logger.error(f"❌ Erro ao criar conta padrão: {str(e)}")
        return None


# ============================================================
# CONVERTERS (mantém igual)
# ============================================================

def to_date(valor):
    if not valor:
        return None
    if isinstance(valor, date) and not isinstance(valor, datetime):
        return valor
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, str):
        valor = valor.strip()
        formatos = ["%Y-%m-%d", "%d/%m/%Y", "%Y-%m-%d %H:%M:%S", "%d/%m/%Y %H:%M:%S"]
        for fmt in formatos:
            try:
                return datetime.strptime(valor, fmt).date()
            except (ValueError, TypeError):
                continue
    return None


def to_decimal(valor, default=Decimal("0")):
    try:
        if valor is None:
            return default
        if isinstance(valor, Decimal):
            return valor
        return Decimal(str(valor))
    except (InvalidOperation, ValueError, TypeError):
        return default


def to_int(valor, default=None):
    try:
        if valor is None:
            return default
        if isinstance(valor, str):
            valor = valor.strip()
            if not valor:
                return default
        return int(valor)
    except (ValueError, TypeError):
        return default


def inferir_tipo_pagamento(registro):
    produto = str(registro.get('produto') or '').strip().lower()
    bandeira = str(registro.get('bandeira') or '').strip().lower()
    
    if 'pix' in produto or bandeira == 'pix':
        return 'pix'
    if 'boleto' in produto or 'billet' in produto:
        return 'boleto'
    if any(kw in produto for kw in ['crédito', 'credito', 'débito', 'debito', 'credit', 'debit']):
        return 'cartao'
    return 'cartao'


# ============================================================
# VALIDAÇÕES
# ============================================================

def validar_adquirente(valor, empresa_id=None):
    if not valor:
        return None
    
    if isinstance(valor, int) or (isinstance(valor, str) and valor.strip().isdigit()):
        try:
            adquirente = Adquirente.query.filter_by(id=int(valor)).first()
            if adquirente:
                return adquirente.id
        except (ValueError, TypeError):
            pass
    
    if isinstance(valor, str):
        nome_normalizado = valor.strip().lower()
        adquirente = Adquirente.query.filter(func.lower(Adquirente.nome) == nome_normalizado).first()
        if adquirente:
            return adquirente.id
        
        adquirente = Adquirente.query.filter(func.lower(Adquirente.nome).contains(nome_normalizado)).first()
        if adquirente:
            return adquirente.id
    
    return None


def validar_conta_bancaria(conta_id, empresa_id):
    if not conta_id:
        return None
    if isinstance(conta_id, str) and conta_id.strip().isdigit():
        try:
            conta_id = int(conta_id.strip())
        except (ValueError, TypeError):
            return None
    try:
        conta = ContaBancaria.query.filter_by(id=int(conta_id), empresa_id=empresa_id).first()
        return conta.id if conta else None
    except (ValueError, TypeError):
        return None


def verificar_venda_duplicada(empresa_id, nsu, adquirente_id):
    if not nsu:
        return False
    try:
        venda = MovAdquirente.query.filter_by(
            empresa_id=empresa_id,
            adquirente_id=adquirente_id,
            nsu=str(nsu).strip()
        ).first()
        return venda is not None
    except Exception:
        return False


# ============================================================
# SALVAR VENDAS (mantém igual)
# ============================================================

def salvar_vendas(registros, empresa_id, arquivo_id, usuario_id=None):
    logger.info(f"🔍 Início importação vendas: empresa={empresa_id}, registros={len(registros)}")
    
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
                    valor_bruto = to_decimal(r.get("valor_bruto"))
                    if valor_bruto <= 0:
                        estatisticas["invalidos"] += 1
                        continue
                    
                    adquirente_valor = r.get("adquirente_id") or r.get("adquirente")
                    adquirente_id = validar_adquirente(adquirente_valor, empresa_id)
                    
                    if not adquirente_id:
                        estatisticas["falhas"] += 1
                        continue
                    
                    if verificar_venda_duplicada(empresa_id, r.get("nsu"), adquirente_id):
                        estatisticas["duplicatas"] += 1
                        continue
                    
                    tipo_pagamento = r.get('tipo_pagamento') or inferir_tipo_pagamento(r)
                    
                    venda = MovAdquirente(
                        empresa_id=empresa_id,
                        adquirente_id=adquirente_id,
                        data_venda=to_date(r.get("data_venda") or r.get("data") or r.get("dt_venda")),
                        data_prevista_pagamento=to_date(r.get("data_prevista") or r.get("data_prevista_pagamento")),
                        bandeira=str(r.get("bandeira", "")).strip()[:50] if r.get("bandeira") else None,
                        produto=str(r.get("produto", "")).strip()[:50] if r.get("produto") else None,
                        parcela=to_int(r.get("parcela")),
                        total_parcelas=to_int(r.get("total_parcelas")),
                        nsu=str(r.get("nsu", "")).strip()[:50] if r.get("nsu") else None,
                        autorizacao=str(r.get("autorizacao", "")).strip()[:50] if r.get("autorizacao") else None,
                        valor_bruto=valor_bruto,
                        taxa_cobrada=to_decimal(r.get("taxa") or r.get("taxa_cobrada")),
                        valor_liquido=to_decimal(r.get("valor_liquido") or r.get("vl_liquido")),
                        tipo_pagamento=tipo_pagamento,
                        valor_conciliado=Decimal("0"),
                        status_conciliacao="pendente",
                        arquivo_origem=str(arquivo_id)[:255] if arquivo_id else None
                    )
                    
                    db.session.add(venda)
                    estatisticas["sucesso"] += 1
                    
                except Exception as e:
                    logger.error(f"❌ Erro ao processar venda: {str(e)}")
                    estatisticas["falhas"] += 1
                    continue
            
            db.session.commit()
            
        except SQLAlchemyError as e:
            db.session.rollback()
            logger.error(f"❌ Erro no batch {i}: {str(e)}")
            estatisticas["falhas"] += len(batch)
    
    return estatisticas


# ============================================================
# ✅ CORRIGIDO: SALVAR RECEBIMENTOS COM AUTO-CRIAÇÃO
# ============================================================

def salvar_recebimentos(registros, empresa_id, arquivo_id, usuario_id=None):
    """
    Salva recebimentos em batches com auto-criação de conta padrão.
    ✅ CORREÇÃO: Aceita valores negativos (padrão OFX) e cria conta automaticamente.
    """
    inicio_total = time.time()
    logger.info(f"🔍 Início importação recebimentos: empresa={empresa_id}, registros={len(registros)}")
    
    estatisticas = {
        "total": len(registros),
        "sucesso": 0,
        "falhas": 0,
        "duplicatas": 0,
        "invalidos": 0,
        "conta_criada": False,
        "conta_padrao_id": None
    }
    
    # ✅ GARANTIR que existe uma conta bancária antes de processar
    conta_padrao_id = obter_ou_criar_conta_padrao(empresa_id, "Extrato OFX")
    estatisticas["conta_padrao_id"] = conta_padrao_id
    if conta_padrao_id:
        estatisticas["conta_criada"] = True
    
    for i in range(0, len(registros), BATCH_SIZE):
        batch = registros[i:i+BATCH_SIZE]
        
        try:
            db.session.begin_nested()
            
            for r in batch:
                try:
                    valor = to_decimal(r.get("valor"))
                    
                    # ✅ CORREÇÃO: OFX usa valores negativos para créditos. Usar valor absoluto.
                    if valor == 0:
                        estatisticas["invalidos"] += 1
                        continue
                    
                    valor_absoluto = abs(valor)
                    
                    if not conta_padrao_id:
                        logger.error(f"❌ Conta bancária não encontrada para empresa {empresa_id}")
                        estatisticas["falhas"] += 1
                        continue
                    
                    mov = MovBanco(
                        empresa_id=empresa_id,
                        conta_bancaria_id=conta_padrao_id,
                        data_movimento=to_date(r.get("data") or r.get("data_movimento")),
                        historico=str(r.get("descricao") or "").strip()[:255],
                        documento=str(r.get("id") or "").strip()[:100],
                        origem="OFX",
                        valor=valor_absoluto,  # ✅ Salva valor positivo
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
            
        except SQLAlchemyError as e:
            db.session.rollback()
            logger.error(f"❌ Erro no batch: {str(e)}")
            estatisticas["falhas"] += len(batch)
    
    tempo_total = time.time() - inicio_total
    logger.info(f"✅ Fim importação recebimentos: {estatisticas} em {tempo_total:.2f}s")
    return estatisticas
