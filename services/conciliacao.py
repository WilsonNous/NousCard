from datetime import timedelta
from decimal import Decimal, InvalidOperation
from sqlalchemy import func
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
TOLERANCIA_DIAS = 2
TIMEOUT_SEGUNDOS = 25

# ============================================================
# UTILITÁRIOS
# ============================================================
def datas_compatíveis(data_prevista, data_banco):
    if not data_prevista or not data_banco:
        return False
    return abs((data_prevista - data_banco).days) <= TOLERANCIA_DIAS

def valores_compatíveis(valor1, valor2, tolerancia=TOLERANCIA_CENTAVOS):
    """Compara valores monetários com tolerância para centavos"""
    v1 = Decimal(str(valor1 or 0))
    v2 = Decimal(str(valor2 or 0))
    return abs(v1 - v2) <= tolerancia

def valores_iguais(valor1, valor2):
    """Comparação exata para match perfeito"""
    v1 = Decimal(str(valor1 or 0))
    v2 = Decimal(str(valor2 or 0))
    return v1 == v2

# ============================================================
# MATCH EXATO E PARCIAL
# ============================================================
def tentar_matching(venda, recebimentos_disponiveis):
    """Tenta encontrar recebimento compatível com esta venda"""
    
    valor_liq = Decimal(str(venda.valor_liquido or 0))
    data_prevista = venda.data_prevista_pagamento
    
    # Match exato primeiro (prioridade)
    for r in recebimentos_disponiveis:
        if valores_iguais(r.valor, valor_liq) and datas_compatíveis(data_prevista, r.data_movimento):
            return [(venda, r, valor_liq)]
    
    # Match com tolerância
    for r in recebimentos_disponiveis:
        if valores_compatíveis(r.valor, valor_liq) and datas_compatíveis(data_prevista, r.data_movimento):
            return [(venda, r, Decimal(str(r.valor)))]
    
    # Match parcial (recebimento menor que venda)
    for r in recebimentos_disponiveis:
        valor_rec = Decimal(str(r.valor))
        if valor_rec < valor_liq and datas_compatíveis(data_prevista, r.data_movimento):
            return [(venda, r, valor_rec)]
    
    return None

# ============================================================
# MULTIVENDA
# ============================================================
def tentar_multivenda(recebimento, vendas_disponiveis):
    """Tenta combinar múltiplas vendas com um recebimento"""
    
    total = Decimal(str(recebimento.valor))
    acumulado = Decimal("0")
    vinculos = []
    
    # Ordenar por valor (maior primeiro - heuristic melhor que greedy puro)
    vendas_ordenadas = sorted(
        vendas_disponiveis,
        key=lambda v: Decimal(str(v.valor_liquido or 0)),
        reverse=True
    )
    
    for v in vendas_ordenadas:
        valor_v = Decimal(str(v.valor_liquido or 0))
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
    """Registra conciliações no banco com validação de duplicatas"""
    
    for venda, recebimento, valor in vinculos:
        
        # Verificar se já existe conciliação para este par
        conc_existente = Conciliacao.query.filter_by(
            mov_adquirente_id=venda.id,
            mov_banco_id=recebimento.id
        ).first()
        
        if conc_existente:
            logger.warning(f"Conciliação duplicada ignorada: venda={venda.id}, recebimento={recebimento.id}")
            continue
        
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
        venda.valor_conciliado = Decimal(str(venda.valor_conciliado or 0)) + valor
        venda.data_primeiro_recebimento = venda.data_primeiro_recebimento or recebimento.data_movimento
        venda.data_ultimo_recebimento = recebimento.data_movimento
        
        valor_liq = Decimal(str(venda.valor_liquido or 0))
        if venda.valor_conciliado >= valor_liq:
            venda.status_conciliacao = "conciliado"
        elif venda.valor_conciliado > 0:
            venda.status_conciliacao = "parcial"
        
        # Atualizar recebimento
        recebimento.valor_conciliado = Decimal(str(recebimento.valor_conciliado or 0)) + valor
        recebimento.conciliado = recebimento.valor_conciliado >= Decimal(str(recebimento.valor))
        
        logger.info(f"Conciliação registrada: venda={venda.id}, recebimento={recebimento.id}, valor={valor}")

# ============================================================
# FUNÇÃO PRINCIPAL
# ============================================================
def executar_conciliacao(empresa_id, usuario_id=None):
    """
    Executa conciliação automática para uma empresa.
    Retorna estatísticas do processamento.
    """
    
    inicio = time.time()
    logger.info(f"Iniciando conciliação: empresa={empresa_id}")
    
    try:
        # Carregar apenas pendentes (performance)
        vendas = list(
            MovAdquirente.query
            .filter_by(empresa_id=empresa_id, status_conciliacao="pendente")
            .options(lazyload('*'))
            .yield_per(1000)
        )
        
        recebimentos = list(
            MovBanco.query
            .filter_by(empresa_id=empresa_id, conciliado=False)
            .options(lazyload('*'))
            .yield_per(1000)
        )
        
        logger.info(f"Carregados: {len(vendas)} vendas, {len(recebimentos)} recebimentos")
        
        # Pool de recebimentos disponíveis (para não reutilizar)
        recebimentos_disponiveis = set(r.id for r in recebimentos)
        recebimentos_map = {r.id: r for r in recebimentos}
        
        resultado = {
            "conciliados": 0,
            "parciais": 0,
            "multivendas": 0,
            "nao_conciliados": 0,
            "creditos_sem_origem": 0
        }
        
        # MATCH INDIVIDUAL
        for venda in vendas:
            # Timeout check
            if time.time() - inicio > TIMEOUT_SEGUNDOS:
                logger.warning("Timeout na conciliação. Processamento parcial.")
                break
            
            # Filtrar recebimentos disponíveis
            recebs_disp = [recebimentos_map[rid] for rid in recebimentos_disponiveis if rid in recebimentos_map]
            
            vinculos = tentar_matching(venda, recebs_disp)
            
            if vinculos:
                registrar_conciliacao(vinculos, empresa_id, usuario_id)
                
                # Remover recebimentos usados do pool
                for _, r, _ in vinculos:
                    recebimentos_disponiveis.discard(r.id)
                
                total = sum(v[2] for v in vinculos)
                valor_liq = Decimal(str(venda.valor_liquido or 0))
                
                if valores_iguais(total, valor_liq):
                    resultado["conciliados"] += 1
                else:
                    resultado["parciais"] += 1
        
        # MULTIVENDA
        pend_vendas = [v for v in vendas if v.status_conciliacao == "pendente"]
        pend_receb_ids = recebimentos_disponiveis
        
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
        
        # Contagem final
        resultado["nao_conciliados"] = MovAdquirente.query.filter_by(
            empresa_id=empresa_id, status_conciliacao="pendente"
        ).count()
        
        resultado["creditos_sem_origem"] = MovBanco.query.filter_by(
            empresa_id=empresa_id, conciliado=False, valor>0
        ).count()
        
        duracao = time.time() - inicio
        logger.info(f"Conciliação concluída: {duracao:.2f}s, empresa={empresa_id}, resultado={resultado}")
        
        return resultado
        
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error(f"Erro de banco na conciliação: empresa={empresa_id}, erro={str(e)}")
        raise
    except Exception as e:
        db.session.rollback()
        logger.error(f"Erro desconhecido na conciliação: empresa={empresa_id}, erro={str(e)}")
        raise
