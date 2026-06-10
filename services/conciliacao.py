# ============================================================
#  CONCILIAÇÃO • NousCard (PRODUÇÃO COM SUPORTE PIX)
#  Compatível com SQLAlchemy 1.4.x + Python 3.11
# ============================================================

from datetime import timedelta
from decimal import Decimal, InvalidOperation
from sqlalchemy import func, and_, or_
from sqlalchemy.orm import lazyload
from sqlalchemy.exc import SQLAlchemyError
from models import db, MovAdquirente, MovBanco, Conciliacao, LogAuditoria
import logging
import time

logger = logging.getLogger(__name__)

# ============================================================
# CONFIGURAÇÕES
# ============================================================
TOLERANCIA_CENTAVOS = Decimal("0.02")
TIMEOUT_SEGUNDOS = 25

# Tolerância de dias por tipo de pagamento
TOLERANCIA_DIAS_POR_TIPO = {
    'pix': 1,           # PIX: D+0 ou D+1
    'cartao': 3,        # Cartão: D+1 a D+30 (depende da adquirente)
    'boleto': 5,        # Boleto: pode levar alguns dias para compensar
    'outros': 3,        # Fallback
}

# ============================================================
# UTILITÁRIOS
# ============================================================

def get_tolerancia_dias(tipo_pagamento='cartao'):
    """Retorna tolerância de dias baseada no tipo de pagamento"""
    return TOLERANCIA_DIAS_POR_TIPO.get(tipo_pagamento, TOLERANCIA_DIAS_POR_TIPO['cartao'])


def datas_compatíveis(data_prevista, data_banco, tipo_pagamento='cartao'):
    """Verifica se datas estão dentro da tolerância configurada para o tipo de pagamento"""
    if not data_prevista or not data_banco:
        return False
    
    tolerancia = get_tolerancia_dias(tipo_pagamento)
    return abs((data_prevista - data_banco).days) <= tolerancia


def valores_compatíveis(valor1, valor2, tolerancia=TOLERANCIA_CENTAVOS):
    """
    Compara valores monetários com tolerância para centavos.
    Usa Decimal para precisão financeira.
    """
    try:
        v1 = Decimal(str(valor1 or 0))
        v2 = Decimal(str(valor2 or 0))
        return abs(v1 - v2) <= tolerancia
    except (InvalidOperation, ValueError, TypeError):
        return False


def valores_iguais(valor1, valor2):
    """
    Comparação exata para match perfeito.
    Usa Decimal para evitar erros de float.
    """
    try:
        v1 = Decimal(str(valor1 or 0))
        v2 = Decimal(str(valor2 or 0))
        return v1 == v2
    except (InvalidOperation, ValueError, TypeError):
        return False


def normalizar_nsu(valor):
    """Normaliza NSU/documento para comparação (remove espaços, hífens, etc.)"""
    if not valor:
        return ""
    return str(valor).strip().replace("-", "").replace(".", "").replace(" ", "").upper()

# ============================================================
# MATCH POR NSU/DOCUMENTO (PRIORIDADE MÁXIMA)
# ============================================================

def tentar_match_por_nsu(venda, recebimentos_disponiveis):
    """
    Tenta encontrar recebimento pelo NSU ou documento.
    Este é o match mais confiável e deve ser tentado primeiro.
    
    Returns:
        Tuple (venda, recebimento, valor) ou None
    """
    nsu_venda = normalizar_nsu(venda.nsu)
    if not nsu_venda:
        return None
    
    for r in recebimentos_disponiveis:
        # Verificar por documento (MovBanco.documento pode conter NSU)
        if normalizar_nsu(r.documento) == nsu_venda:
            # Verificar compatibilidade de valor (com tolerância)
            if valores_compatíveis(r.valor, venda.valor_liquido):
                return (venda, r, Decimal(str(r.valor)))
    
    return None

# ============================================================
# MATCH INDIVIDUAL E PARCIAL
# ============================================================

def tentar_matching(venda, recebimentos_disponiveis):
    """
    Tenta encontrar recebimento compatível com esta venda.
    
    Prioridade:
    1. ✅ Match por NSU/documento (mais confiável)
    2. Match exato (valor igual + data compatível)
    3. Match com tolerância de centavos
    4. Match parcial (recebimento menor que venda)
    
    Returns:
        List[Tuple] ou None
    """
    # ✅ PRIORIDADE 1: Match por NSU/documento
    match_nsu = tentar_match_por_nsu(venda, recebimentos_disponiveis)
    if match_nsu:
        return [match_nsu]
    
    valor_liq = Decimal(str(venda.valor_liquido or 0))
    data_prevista = venda.data_prevista_pagamento
    tipo_pagamento = getattr(venda, 'tipo_pagamento', 'cartao')
    
    # Match exato primeiro (valor igual + data compatível)
    for r in recebimentos_disponiveis:
        if (valores_iguais(r.valor, valor_liq) and 
            datas_compatíveis(data_prevista, r.data_movimento, tipo_pagamento)):
            return [(venda, r, valor_liq)]
    
    # Match com tolerância de centavos
    for r in recebimentos_disponiveis:
        if (valores_compatíveis(r.valor, valor_liq) and 
            datas_compatíveis(data_prevista, r.data_movimento, tipo_pagamento)):
            return [(venda, r, Decimal(str(r.valor)))]
    
    # Match parcial (recebimento menor que venda) - útil para parcelas
    for r in recebimentos_disponiveis:
        valor_rec = Decimal(str(r.valor))
        if (valor_rec < valor_liq and 
            valor_rec > 0 and
            datas_compatíveis(data_prevista, r.data_movimento, tipo_pagamento)):
            return [(venda, r, valor_rec)]
    
    return None

# ============================================================
# MULTIVENDA (VÁRIAS VENDAS → UM RECEBIMENTO)
# ============================================================

def tentar_multivenda(recebimento, vendas_disponiveis):
    """
    Tenta combinar múltiplas vendas com um único recebimento.
    Útil para:
    - Lotes de vendas conciliados em um único depósito
    - PIX que agrupa múltiplas transações
    
    Usa heurística greedy com ordenação por valor (maior primeiro).
    
    Returns:
        List[Tuple] de vínculos ou None
    """
    total = Decimal(str(recebimento.valor))
    acumulado = Decimal("0")
    vinculos = []
    
    # Ordenar por valor (maior primeiro - heuristic melhor que greedy puro)
    vendas_ordenadas = sorted(
        [v for v in vendas_disponiveis if v.valor_liquido and v.valor_liquido > 0],
        key=lambda v: Decimal(str(v.valor_liquido)),
        reverse=True
    )
    
    for v in vendas_ordenadas:
        valor_v = Decimal(str(v.valor_liquido or 0))
        tipo_pagamento = getattr(v, 'tipo_pagamento', 'cartao')
        
        # Verificar se data é compatível antes de incluir
        if datas_compatíveis(v.data_prevista_pagamento, recebimento.data_movimento, tipo_pagamento):
            if acumulado + valor_v <= total:
                acumulado += valor_v
                vinculos.append((v, recebimento, valor_v))
            
            if valores_iguais(acumulado, total):
                return vinculos
    
    # Retorna mesmo se não bater exato (match parcial)
    return vinculos if vinculos else None

# ============================================================
# SALVAR CONCILIAÇÃO
# ============================================================

def registrar_conciliacao(vinculos, empresa_id, usuario_id=None):
    """
    Registra conciliações no banco com validação de duplicatas.
    
    Args:
        vinculos: Lista de tuplas (venda, recebimento, valor)
        empresa_id: ID da empresa
        usuario_id: ID do usuário (para auditoria)
    """
    for venda, recebimento, valor in vinculos:
        
        # Verificar se já existe conciliação para este par
        conc_existente = Conciliacao.query.filter_by(
            empresa_id=empresa_id,  
            mov_adquirente_id=venda.id,
            mov_banco_id=recebimento.id
        ).first()
        
        if conc_existente:
            continue
        
        try:
            # Criar registro de conciliação
            conc = Conciliacao(
                empresa_id=empresa_id,
                mov_adquirente_id=venda.id,
                mov_banco_id=recebimento.id,
                valor_previsto=venda.valor_liquido,
                valor_conciliado=valor,
                tipo="automatico",
                status="conciliado"
            )
            
            db.session.add(conc)
            
            # Atualizar venda
            venda.valor_conciliado = (Decimal(str(venda.valor_conciliado or 0)) + valor)
            venda.data_primeiro_recebimento = venda.data_primeiro_recebimento or recebimento.data_movimento
            venda.data_ultimo_recebimento = recebimento.data_movimento
            
            valor_liq = Decimal(str(venda.valor_liquido or 0))
            if venda.valor_conciliado >= valor_liq:
                venda.status_conciliacao = "conciliado"
            elif venda.valor_conciliado > 0:
                venda.status_conciliacao = "parcial"
            
            # Atualizar recebimento
            recebimento.valor_conciliado = (Decimal(str(recebimento.valor_conciliado or 0)) + valor)
            recebimento.conciliado = recebimento.valor_conciliado >= Decimal(str(recebimento.valor or 0))
            
            logger.info(f"✅ Conciliação: venda={venda.id} ({venda.tipo_pagamento}), recebimento={recebimento.id}, valor={valor}")
            
        except Exception as e:
            logger.error(f"❌ Erro ao registrar conciliação: {str(e)}")
            continue  # Continua com os próximos vínculos

# ============================================================
# FUNÇÃO PRINCIPAL
# ============================================================

def executar_conciliacao(empresa_id, usuario_id=None, tipo_pagamento=None):
    """
    Executa conciliação automática para uma empresa.
    
    ✅ NOVO: Suporte a filtro por tipo_pagamento (pix/cartao/boleto)
    
    Fluxo:
    1. Carrega vendas pendentes e recebimentos não conciliados
    2. Tenta match por NSU/documento (prioridade máxima)
    3. Tenta match individual por valor/data
    4. Tenta match multivenda (várias vendas → um recebimento)
    5. Salva conciliações e atualiza status
    6. Retorna estatísticas do processamento
    
    Args:
        empresa_id: ID da empresa para conciliar
        usuario_id: ID do usuário (opcional, para auditoria)
        tipo_pagamento: Opcional - filtra apenas vendas deste tipo ('pix', 'cartao', etc.)
    
    Returns:
        Dict com estatísticas da conciliação
    """
    
    inicio = time.time()
    logger.info(f"Iniciando conciliação: empresa={empresa_id}, tipo_pagamento={tipo_pagamento or 'todos'}")
    
    try:
        # ✅ Query base para vendas pendentes
        query_vendas = MovAdquirente.query.filter_by(
            empresa_id=empresa_id, 
            status_conciliacao="pendente",
            ativo=True
        ).options(lazyload('*')).yield_per(1000)
        
        # ✅ Filtrar por tipo_pagamento se especificado
        if tipo_pagamento and tipo_pagamento != 'todos':
            query_vendas = query_vendas.filter(MovAdquirente.tipo_pagamento == tipo_pagamento)
        
        vendas = list(query_vendas)
        
        # Recebimentos não conciliados
        recebimentos = list(
            MovBanco.query
            .filter_by(empresa_id=empresa_id, conciliado=False)
            .options(lazyload('*'))
            .yield_per(1000)
        )
        
        logger.info(f"Carregados: {len(vendas)} vendas pendentes, {len(recebimentos)} recebimentos disponíveis")
        
        # Pool de recebimentos disponíveis (para não reutilizar)
        recebimentos_disponiveis = set(r.id for r in recebimentos)
        recebimentos_map = {r.id: r for r in recebimentos}
        
        resultado = {
            "conciliados": 0,
            "parciais": 0,
            "multivendas": 0,
            "nao_conciliados": 0,
            "creditos_sem_origem": 0,
            "por_tipo": {}  # ✅ Detalhamento por tipo de pagamento
        }
        
        # ============================================================
        # FASE 1: MATCH POR NSU/DOCUMENTO + INDIVIDUAL
        # ============================================================
        for venda in vendas:
            # Timeout check
            if time.time() - inicio > TIMEOUT_SEGUNDOS:
                logger.warning("⚠️ Timeout na conciliação. Processamento parcial.")
                break
            
            # Filtrar recebimentos disponíveis
            recebs_disp = [recebimentos_map[rid] for rid in recebimentos_disponiveis if rid in recebimentos_map]
            
            # ✅ Tenta match por NSU primeiro (mais confiável)
            vinculos = tentar_matching(venda, recebs_disp)
            
            if vinculos:
                registrar_conciliacao(vinculos, empresa_id, usuario_id)
                
                # Remover recebimentos usados do pool
                for _, r, _ in vinculos:
                    recebimentos_disponiveis.discard(r.id)
                
                total = sum(v[2] for v in vinculos)
                valor_liq = Decimal(str(venda.valor_liquido or 0))
                
                # Contabilizar por tipo de pagamento
                tipo = getattr(venda, 'tipo_pagamento', 'cartao')
                if tipo not in resultado['por_tipo']:
                    resultado['por_tipo'][tipo] = {"conciliados": 0, "parciais": 0}
                
                if valores_iguais(total, valor_liq):
                    resultado["conciliados"] += 1
                    resultado['por_tipo'][tipo]["conciliados"] += 1
                else:
                    resultado["parciais"] += 1
                    resultado['por_tipo'][tipo]["parciais"] += 1
        
        # ============================================================
        # FASE 2: MULTIVENDA
        # ============================================================
        # Recarregar vendas pendentes após fase 1
        pend_vendas_query = MovAdquirente.query.filter_by(
            empresa_id=empresa_id, 
            status_conciliacao="pendente",
            ativo=True
        ).options(lazyload('*'))
        
        if tipo_pagamento and tipo_pagamento != 'todos':
            pend_vendas_query = pend_vendas_query.filter(MovAdquirente.tipo_pagamento == tipo_pagamento)
        
        pend_vendas = list(pend_vendas_query.yield_per(1000))
        pend_receb_ids = recebimentos_disponiveis.copy()
        
        for rid in list(pend_receb_ids):
            if time.time() - inicio > TIMEOUT_SEGUNDOS:
                break
            
            r = recebimentos_map.get(rid)
            if not r:
                continue
            
            vinculos = tentar_multivenda(r, pend_vendas)
            if vinculos:
                registrar_conciliacao(vinculos, empresa_id, usuario_id)
                resultado["multivendas"] += 1
                
                for _, rec, _ in vinculos:
                    recebimentos_disponiveis.discard(rec.id)
        
        # Commit único (transação)
        db.session.commit()
        
        # ============================================================
        # CONTAGEM FINAL
        # ============================================================
        
        # Vendas pendentes restantes
        query_pendentes = MovAdquirente.query.filter_by(
            empresa_id=empresa_id,
            status_conciliacao="pendente",
            ativo=True
        )
        if tipo_pagamento and tipo_pagamento != 'todos':
            query_pendentes = query_pendentes.filter(MovAdquirente.tipo_pagamento == tipo_pagamento)
        
        resultado["nao_conciliados"] = query_pendentes.count()
        
        # Créditos sem origem (recebimentos não conciliados)
        resultado["creditos_sem_origem"] = MovBanco.query.filter(
            MovBanco.empresa_id == empresa_id,
            MovBanco.conciliado == False,
            MovBanco.valor > 0
        ).count()
        
        duracao = time.time() - inicio
        logger.info(f"✅ Conciliação concluída: {duracao:.2f}s, empresa={empresa_id}, resultado={resultado}")
        
        return resultado
        
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error(f"❌ Erro de banco na conciliação: empresa={empresa_id}, erro={str(e)}")
        raise
    except Exception as e:
        db.session.rollback()
        logger.error(f"❌ Erro desconhecido na conciliação: empresa={empresa_id}, erro={str(e)}")
        raise
