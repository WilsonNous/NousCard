# services/importer_db_movimento.py
# ✅ VERSÃO FINAL CORRIGIDA: to_date() reconhece datetime.date + datetime.datetime

from models import db, MovAdquirente, MovBanco, Adquirente, ContaBancaria
from datetime import datetime, date, timezone  # ← ✅ IMPORTANTE: importar 'date'
from decimal import Decimal, InvalidOperation
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from sqlalchemy import func
import logging

logger = logging.getLogger(__name__)

# ============================================================
# CONFIGURAÇÕES
# ============================================================
BATCH_SIZE = 100

# ============================================================
# CONVERTERS SEGUROS (CORRIGIDOS)
# ============================================================

def to_date(valor):
    """
    Converte valor para date de forma segura.
    
    ✅ Suporta:
        - datetime.date (já é date, retorna direto)
        - datetime.datetime (converte para date)
        - str (parseia nos formatos suportados)
        - None/empty (retorna None)
    """
    if not valor:
        return None
    
    # ✅ Se já for um objeto date (mas não datetime), retorna diretamente
    # Isso evita que dates do parser sejam convertidos para None
    if isinstance(valor, date) and not isinstance(valor, datetime):
        return valor
    
    # ✅ Se for datetime, extrai a parte de date
    if isinstance(valor, datetime):
        return valor.date()
    
    # ✅ Se for string, tenta parsear em múltiplos formatos
    if isinstance(valor, str):
        valor = valor.strip()  # Remove espaços extras que podem quebrar o parse
        formatos = [
            "%Y-%m-%d",           # 2026-02-01 (ISO, mais comum)
            "%d/%m/%Y",           # 01/02/2026 (formato BR)
            "%Y-%m-%d %H:%M:%S",  # 2026-02-01 10:30:00 (com hora)
            "%d/%m/%Y %H:%M:%S",  # 01/02/2026 10:30:00 (BR com hora)
        ]
        for fmt in formatos:
            try:
                return datetime.strptime(valor, fmt).date()
            except (ValueError, TypeError):
                continue  # Tenta próximo formato
        
        # Se nenhum formato funcionou, loga warning para debug
        logger.warning(f"⚠️ Não foi possível parsear data: '{valor}'")
        return None
    
    # Tipo não suportado
    logger.warning(f"⚠️ Tipo de data não suportado: {type(valor).__name__} = {valor}")
    return None


def to_decimal(valor, default=Decimal("0")):
    """Converte valor para Decimal de forma segura"""
    try:
        if valor is None:
            return default
        # Se já for Decimal, retorna direto
        if isinstance(valor, Decimal):
            return valor
        return Decimal(str(valor))
    except (InvalidOperation, ValueError, TypeError) as e:
        logger.warning(f"⚠️ Valor inválido para Decimal: {valor} (erro: {e})")
        return default


def to_int(valor, default=None):
    """Converte valor para int de forma segura"""
    try:
        if valor is None:
            return default
        if isinstance(valor, str):
            valor = valor.strip()
            if not valor:
                return default
        return int(valor)
    except (ValueError, TypeError) as e:
        logger.warning(f"⚠️ Valor inválido para int: {valor} (erro: {e})")
        return default

# ============================================================
# VALIDAÇÕES INTELIGENTES
# ============================================================

def validar_adquirente(valor, empresa_id=None):
    """
    Valida adquirente por ID numérico OU por nome (string).
    
    Args:
        valor: ID (int) OU nome (str) da adquirente
        empresa_id: Opcional, para filtrar por empresa se necessário
    
    Returns:
        int: ID da adquirente se encontrado, None caso contrário
    """
    if not valor:
        return None
    
    # ✅ Se for número (int ou string numérica), tenta buscar por ID
    if isinstance(valor, int) or (isinstance(valor, str) and valor.strip().isdigit()):
        try:
            adquirente = Adquirente.query.filter_by(id=int(valor)).first()
            if adquirente:
                return adquirente.id
        except (ValueError, TypeError):
            pass  # Se não conseguir converter, tenta como nome abaixo
    
    # ✅ Se for string, tenta buscar por nome (case-insensitive, tolerante a espaços)
    if isinstance(valor, str):
        nome_normalizado = valor.strip().lower()
        
        # Match exato (case-insensitive)
        adquirente = Adquirente.query.filter(
            func.lower(Adquirente.nome) == nome_normalizado
        ).first()
        if adquirente:
            return adquirente.id
        
        # Match parcial (contém) - útil para variações como "Cielo Ltda"
        adquirente = Adquirente.query.filter(
            func.lower(Adquirente.nome).contains(nome_normalizado)
        ).first()
        if adquirente:
            return adquirente.id
        
        # Debug log para identificar adquirentes não mapeadas
        logger.warning(f"⚠️ Adquirente não encontrada: '{valor}' (normalizado: '{nome_normalizado}')")
    
    return None


def validar_conta_bancaria(conta_id, empresa_id):
    """Valida se conta bancária existe e pertence à empresa"""
    if not conta_id:
        return None
    
    # Se for string numérica, converter para int
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
    """Verifica se venda já existe pelo NSU (evita duplicatas)"""
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
        return False  # Em caso de erro, assume não duplicada para não bloquear

# ============================================================
# SALVAR VENDAS (CORRIGIDO)
# ============================================================

def salvar_vendas(registros, empresa_id, arquivo_id, usuario_id=None):
    """
    Salva vendas em batches com validação inteligente.
    
    ✅ Features:
        - Validação de adquirente por nome OU ID
        - Tratamento seguro de datas (to_date corrigido)
        - Prevenção de duplicatas por NSU
        - Logs detalhados para debug
    """
    
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
                    # 🔹 Validar dados obrigatórios
                    valor_bruto = to_decimal(r.get("valor_bruto"))
                    if valor_bruto <= 0:
                        estatisticas["invalidos"] += 1
                        continue
                    
                    # 🔹 Validar adquirente (flexível: nome OU ID)
                    adquirente_valor = r.get("adquirente_id") or r.get("adquirente")
                    adquirente_id = validar_adquirente(adquirente_valor, empresa_id)
                    
                    if not adquirente_id:
                        logger.warning(f"⚠️ Falha ao validar adquirente: {adquirente_valor}")
                        estatisticas["falhas"] += 1
                        continue
                    
                    # 🔹 Verificar duplicata por NSU
                    if verificar_venda_duplicada(empresa_id, r.get("nsu"), adquirente_id):
                        estatisticas["duplicatas"] += 1
                        continue
                    
                    # 🔹 Criar objeto MovAdquirente
                    venda = MovAdquirente(
                        empresa_id=empresa_id,
                        adquirente_id=adquirente_id,
                        
                        # ✅ CORREÇÃO CRÍTICA: to_date() agora reconhece date e datetime
                        data_venda=to_date(r.get("data_venda") or r.get("data") or r.get("dt_venda")),
                        data_prevista_pagamento=to_date(r.get("data_prevista") or r.get("data_prevista_pagamento")),
                        
                        # Campos opcionais com truncamento para evitar estouro de coluna
                        bandeira=str(r.get("bandeira", "")).strip()[:50] if r.get("bandeira") else None,
                        produto=str(r.get("produto", "")).strip()[:50] if r.get("produto") else None,
                        parcela=to_int(r.get("parcela")),
                        total_parcelas=to_int(r.get("total_parcelas")),
                        nsu=str(r.get("nsu", "")).strip()[:50] if r.get("nsu") else None,
                        autorizacao=str(r.get("autorizacao", "")).strip()[:50] if r.get("autorizacao") else None,
                        
                        # Valores monetários
                        valor_bruto=valor_bruto,
                        taxa_cobrada=to_decimal(r.get("taxa") or r.get("taxa_cobrada")),
                        valor_liquido=to_decimal(r.get("valor_liquido") or r.get("vl_liquido")),
                        
                        # Status padrão
                        valor_conciliado=Decimal("0"),
                        status_conciliacao="pendente",
                        
                        # Metadados
                        arquivo_origem=str(arquivo_id)[:255] if arquivo_id else None
                    )
                    
                    db.session.add(venda)
                    estatisticas["sucesso"] += 1
                    
                except Exception as e:
                    logger.error(f"❌ Erro ao processar venda: {str(e)}, registro={r}")
                    estatisticas["falhas"] += 1
                    continue
            
            db.session.commit()
            
        except SQLAlchemyError as e:
            db.session.rollback()
            logger.error(f"❌ Erro no batch {i}: {str(e)}")
            estatisticas["falhas"] += len(batch)
        except Exception as e:
            db.session.rollback()
            logger.error(f"❌ Erro inesperado no batch {i}: {str(e)}")
            estatisticas["falhas"] += len(batch)
    
    logger.info(f"✅ Fim importação vendas: {estatisticas}")
    
    return estatisticas

# ============================================================
# SALVAR RECEBIMENTOS
# ============================================================

def salvar_recebimentos(registros, empresa_id, arquivo_id, usuario_id=None):
    """
    Salva recebimentos em batches com validação e tratamento de erro.
    
    ✅ Features:
        - Validação de conta bancária por empresa
        - Tratamento seguro de datas (to_date corrigido)
        - Logs detalhados para debug
    """
    
    logger.info(f"🔍 Início importação recebimentos: empresa={empresa_id}, registros={len(registros)}")
    
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
                    # 🔹 Validar dados obrigatórios
                    valor = to_decimal(r.get("valor"))
                    if valor <= 0:
                        estatisticas["invalidos"] += 1
                        continue
                    
                    # 🔹 Validar conta bancária
                    conta_id = validar_conta_bancaria(r.get("conta_id"), empresa_id)
                    if not conta_id:
                        logger.warning(f"⚠️ Conta bancária não encontrada: {r.get('conta_id')}")
                        estatisticas["falhas"] += 1
                        continue
                    
                    # 🔹 Criar objeto MovBanco
                    mov = MovBanco(
                        empresa_id=empresa_id,
                        conta_bancaria_id=conta_id,
                        
                        # ✅ CORREÇÃO CRÍTICA: to_date() agora reconhece date e datetime
                        data_movimento=to_date(r.get("data") or r.get("data_movimento") or r.get("dt_movimento")),
                        
                        # Campos opcionais com truncamento
                        historico=str(r.get("descricao") or r.get("historico") or "").strip()[:255],
                        documento=str(r.get("documento") or "").strip()[:100],
                        origem=str(r.get("origem") or "").strip()[:50],
                        
                        # Valor monetário
                        valor=valor,
                        
                        # Status padrão
                        valor_conciliado=Decimal("0"),
                        conciliado=False,
                        
                        # Metadados
                        arquivo_origem=str(arquivo_id)[:255] if arquivo_id else None
                    )
                    
                    db.session.add(mov)
                    estatisticas["sucesso"] += 1
                    
                except Exception as e:
                    logger.error(f"❌ Erro ao processar recebimento: {str(e)}, registro={r}")
                    estatisticas["falhas"] += 1
                    continue
            
            db.session.commit()
            
        except SQLAlchemyError as e:
            db.session.rollback()
            logger.error(f"❌ Erro no batch {i}: {str(e)}")
            estatisticas["falhas"] += len(batch)
        except Exception as e:
            db.session.rollback()
            logger.error(f"❌ Erro inesperado no batch {i}: {str(e)}")
            estatisticas["falhas"] += len(batch)
    
    logger.info(f"✅ Fim importação recebimentos: {estatisticas}")
    
    return estatisticas
