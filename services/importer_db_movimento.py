# services/importer_db_movimento.py - VERSÃO FINAL COM CATEGORIZAÇÃO

from models import db, MovAdquirente, MovBanco, Adquirente, ContaBancaria
from datetime import datetime, date, timezone
from decimal import Decimal, InvalidOperation
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from sqlalchemy import func
import logging
import time

logger = logging.getLogger(__name__)
BATCH_SIZE = 200  # ✅ Otimizado para evitar estouro de memória

# ============================================================
# CONVERTERS SEGUROS
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
        for fmt in ["%Y-%m-%d", "%d/%m/%Y", "%Y-%m-%d %H:%M:%S", "%d/%m/%Y %H:%M:%S"]:
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

# ============================================================
# SALVAR RECEBIMENTOS (COM LÓGICA DE CONTA BANCÁRIA)
# ============================================================
def salvar_recebimentos(registros, empresa_id, arquivo_id, usuario_id=None, dados_conta=None):
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
                logger.info(f"✅ Conta criada: {conta.nome} (ID: {conta.id})")
            
            conta_id = conta.id
            estatisticas["conta_id"] = conta_id
            
        except Exception as e:
            logger.error(f"❌ Erro ao criar conta: {str(e)}")
    
    # Fallback: pegar a primeira conta ativa da empresa
    if not conta_id:
        conta_fallback = ContaBancaria.query.filter_by(empresa_id=empresa_id, ativo=True).first()
        if conta_fallback:
            conta_id = conta_fallback.id
            estatisticas["conta_id"] = conta_id
        else:
            logger.error(f"❌ Nenhuma conta bancária encontrada para empresa {empresa_id}")
            return estatisticas

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
                    
                    # O OFX já vem com valor negativo para débito e positivo para crédito.
                    # Salvamos o valor absoluto e o sistema entende pela categoria/tipo, 
                    # ou mantemos o sinal se o modelo permitir. Vamos manter o sinal para DRE.
                    
                    mov = MovBanco(
                        empresa_id=empresa_id,
                        conta_bancaria_id=conta_id,
                        data_movimento=to_date(r.get("data")),
                        historico=str(r.get("descricao") or "").strip()[:255],
                        documento=str(r.get("nsu") or r.get("id") or "").strip()[:100],
                        origem="OFX",
                        valor=valor,  # Mantém o sinal (+ para entrada, - para saída)
                        tipo_pagamento=r.get("tipo_pagamento", "outros"),  # ✅ NOVO
                        categoria=r.get("categoria", "outros"),            # ✅ NOVO
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
            logger.info(f"✅ Batch {i//BATCH_SIZE + 1} salvo: {len(batch)} registros")
            
        except SQLAlchemyError as e:
            db.session.rollback()
            logger.error(f"❌ Erro no batch {i//BATCH_SIZE + 1}: {str(e)}")
            estatisticas["falhas"] += len(batch)
    
    tempo_total = time.time() - inicio_total
    logger.info(f"✅ Fim importação recebimentos: {estatisticas} em {tempo_total:.2f}s")
    return estatisticas


# ============================================================
# SALVAR VENDAS (Mantido estável)
# ============================================================
def salvar_vendas(registros, empresa_id, arquivo_id, usuario_id=None):
    # ... (Mantenha sua função atual de salvar_vendas, ela já está funcionando bem) ...
    pass
