# ============================================================
# NOUSCARD
# Dashboard Service V3 - Refatorado com GROUP BY categoria
#
# Responsável pelos indicadores financeiros do Dashboard
#
# ✅ ZERO LIKEs - Tudo via GROUP BY no banco
# ✅ Usa categoria_principal, subcategoria, score_classificacao
# ✅ Compatível com Classificador Financeiro v2
# ============================================================

from datetime import datetime, timedelta
from decimal import Decimal
import logging

from sqlalchemy import func

from models import (
    db,
    MovAdquirente,
    MovBanco,
    Adquirente,
)

logger = logging.getLogger(__name__)

ZERO = Decimal("0.00")


# ============================================================
# HELPERS
# ============================================================

def _to_decimal(valor):
    """Converte qualquer valor numérico para Decimal."""
    if valor is None:
        return ZERO
    try:
        return Decimal(str(valor))
    except Exception:
        return ZERO


def _obter_periodo(periodo, data_inicio=None, data_fim=None):
    """Calcula início e fim do período."""
    hoje = datetime.now().date()
    
    if periodo == "todos":
        return None, None
    
    if periodo == "personalizado" and data_inicio and data_fim:
        return (
            datetime.strptime(data_inicio, "%Y-%m-%d").date(),
            datetime.strptime(data_fim, "%Y-%m-%d").date(),
        )
    
    if periodo == "semana":
        return hoje - timedelta(days=7), hoje
    
    if periodo == "ano":
        return hoje.replace(month=1, day=1), hoje
    
    return hoje.replace(day=1), hoje


def _formatar_moeda(valor):
    """Formata Decimal para string monetária brasileira."""
    if valor is None:
        return "R$ 0,00"
    
    valor = _to_decimal(valor)
    negativo = valor < 0
    valor = abs(valor)
    
    inteiro = int(valor)
    centavos = int((valor - inteiro) * 100)
    
    partes = []
    while inteiro > 0:
        partes.insert(0, str(inteiro % 1000))
        inteiro //= 1000
    
    if not partes:
        partes = ["0"]
    
    resultado = ".".join(partes) + f",{centavos:02d}"
    
    if negativo:
        resultado = "-" + resultado
    
    return f"R$ {resultado}"


# ============================================================
# FILTROS
# ============================================================

def _filtrar_periodo(query, campo_data, inicio, fim):
    """Aplica filtro de período em qualquer Query."""
    if inicio:
        query = query.filter(campo_data >= inicio)
    if fim:
        query = query.filter(campo_data <= fim)
    return query


# ============================================================
# QUERIES BASE
# ============================================================

def _query_mov_adquirente(empresa_id, inicio=None, fim=None):
    """Query base das vendas (MovAdquirente)."""
    query = db.session.query(MovAdquirente).filter(
        MovAdquirente.empresa_id == empresa_id,
        MovAdquirente.ativo.is_(True)
    )
    return _filtrar_periodo(query, MovAdquirente.data_venda, inicio, fim)


def _query_mov_banco(empresa_id, inicio=None, fim=None):
    """Query base dos movimentos bancários (MovBanco)."""
    query = db.session.query(MovBanco).filter(
        MovBanco.empresa_id == empresa_id
    )
    return _filtrar_periodo(query, MovBanco.data_movimento, inicio, fim)


# ============================================================
# ✅ AGRUPAMENTO POR CATEGORIA (ZERO LIKEs)
# ============================================================

def _agrupar_por_categoria_principal(empresa_id, inicio=None, fim=None, natureza='todos'):
    """
    Agrupa movimentos por categoria_principal diretamente no banco.
    
    ✅ Usa GROUP BY categoria_principal
    ✅ ZERO LIKEs
    ✅ ZERO IFs no Python
    
    Args:
        natureza: 'receita' (valores > 0), 'despesa' (valores < 0), 'todos'
    
    Returns:
        list[dict]: [{categoria, total, quantidade, percentual}]
    """
    query = db.session.query(
        MovBanco.categoria_principal,
        func.sum(func.abs(MovBanco.valor)).label('total'),
        func.count().label('quantidade')
    ).filter(
        MovBanco.empresa_id == empresa_id,
        MovBanco.categoria_principal.isnot(None),
        MovBanco.categoria_principal != '',
        MovBanco.categoria_principal != 'Outros'
    )
    
    # Filtrar por natureza
    if natureza == 'receita':
        query = query.filter(MovBanco.valor > 0)
    elif natureza == 'despesa':
        query = query.filter(MovBanco.valor < 0)
    
    query = _filtrar_periodo(query, MovBanco.data_movimento, inicio, fim)
    
    resultados = query.group_by(MovBanco.categoria_principal).all()
    
    # Calcular total geral para percentuais
    total_geral = sum(item[1] for item in resultados) if resultados else 0
    
    categorias = []
    for cat, total, qtd in resultados:
        if total and total > 0:
            percentual = (float(total) / float(total_geral) * 100) if total_geral > 0 else 0
            categorias.append({
                'categoria': cat,
                'total': float(total),
                'quantidade': qtd,
                'percentual': round(percentual, 1)
            })
    
    return sorted(categorias, key=lambda x: x['total'], reverse=True)


def _agrupar_por_subcategoria(empresa_id, inicio=None, fim=None, categoria_principal=None, natureza='todos'):
    """
    Agrupa por subcategoria, opcionalmente filtrando por categoria_principal.
    
    ✅ GROUP BY subcategoria no banco
    """
    query = db.session.query(
        MovBanco.subcategoria,
        func.sum(func.abs(MovBanco.valor)).label('total'),
        func.count().label('quantidade')
    ).filter(
        MovBanco.empresa_id == empresa_id,
        MovBanco.subcategoria.isnot(None),
        MovBanco.subcategoria != ''
    )
    
    if categoria_principal:
        query = query.filter(MovBanco.categoria_principal == categoria_principal)
    
    if natureza == 'receita':
        query = query.filter(MovBanco.valor > 0)
    elif natureza == 'despesa':
        query = query.filter(MovBanco.valor < 0)
    
    query = _filtrar_periodo(query, MovBanco.data_movimento, inicio, fim)
    
    resultados = query.group_by(MovBanco.subcategoria).all()
    
    total_geral = sum(item[1] for item in resultados) if resultados else 0
    
    subcategorias = []
    for sub, total, qtd in resultados:
        if total and total > 0:
            percentual = (float(total) / float(total_geral) * 100) if total_geral > 0 else 0
            subcategorias.append({
                'subcategoria': sub,
                'total': float(total),
                'quantidade': qtd,
                'percentual': round(percentual, 1)
            })
    
    return sorted(subcategorias, key=lambda x: x['total'], reverse=True)


def _agrupar_por_score(empresa_id, inicio=None, fim=None):
    """
    Agrupa por faixa de score de classificação.
    
    ✅ GROUP BY no banco com CASE WHEN
    """
    from sqlalchemy import case
    
    faixa_score = case(
        (MovBanco.score_classificacao >= 80, 'Alta (80-100)'),
        (MovBanco.score_classificacao >= 50, 'Média (50-79)'),
        (MovBanco.score_classificacao > 0, 'Baixa (1-49)'),
        else_='Sem classificação'
    )
    
    query = db.session.query(
        faixa_score.label('faixa'),
        func.count().label('quantidade'),
        func.sum(func.abs(MovBanco.valor)).label('total')
    ).filter(
        MovBanco.empresa_id == empresa_id
    )
    
    query = _filtrar_periodo(query, MovBanco.data_movimento, inicio, fim)
    
    resultados = query.group_by('faixa').all()
    
    faixas = []
    for faixa, qtd, total in resultados:
        faixas.append({
            'faixa': faixa,
            'quantidade': qtd,
            'total': float(total or 0)
        })
    
    return faixas


# ============================================================
# CÁLCULOS FINANCEIROS PRINCIPAIS
# ============================================================

def _calcular_vendas(empresa_id, inicio=None, fim=None):
    """Calcula todas as vendas da empresa."""
    query = _query_mov_adquirente(empresa_id, inicio, fim)
    
    return {
        "valor_bruto": _to_decimal(query.with_entities(func.sum(MovAdquirente.valor_bruto)).scalar()),
        "valor_liquido": _to_decimal(query.with_entities(func.sum(MovAdquirente.valor_liquido)).scalar()),
        "valor_conciliado": _to_decimal(query.with_entities(func.sum(MovAdquirente.valor_conciliado)).scalar()),
        "taxas": _to_decimal(query.with_entities(func.sum(MovAdquirente.taxa_cobrada)).scalar()),
        "quantidade": query.count()
    }


def _calcular_recebimentos(empresa_id, inicio=None, fim=None):
    """Soma apenas ENTRADAS do banco."""
    query = _query_mov_banco(empresa_id, inicio, fim).filter(MovBanco.valor > 0)
    return {
        "total": _to_decimal(query.with_entities(func.sum(MovBanco.valor)).scalar()),
        "quantidade": query.count()
    }


def _calcular_despesas(empresa_id, inicio=None, fim=None):
    """Soma apenas SAÍDAS financeiras."""
    query = _query_mov_banco(empresa_id, inicio, fim).filter(MovBanco.valor < 0)
    total = _to_decimal(query.with_entities(func.sum(MovBanco.valor)).scalar())
    return {
        "total": abs(total),
        "quantidade": query.count()
    }


def _calcular_fluxo(empresa_id, inicio=None, fim=None):
    """Fluxo financeiro: Entradas - Saídas."""
    recebimentos = _calcular_recebimentos(empresa_id, inicio, fim)
    despesas = _calcular_despesas(empresa_id, inicio, fim)
    return {
        "entradas": recebimentos["total"],
        "saidas": despesas["total"],
        "saldo": recebimentos["total"] - despesas["total"]
    }


# ============================================================
# BANDEIRAS (MovAdquirente)
# ============================================================

def _calcular_bandeiras(empresa_id, inicio=None, fim=None):
    """
    Agrupa vendas por bandeira de cartão.
    ✅ GROUP BY bandeira no banco - ZERO LIKEs
    """
    query = db.session.query(
        MovAdquirente.bandeira,
        func.sum(MovAdquirente.valor_bruto).label('total'),
        func.count().label('quantidade')
    ).filter(
        MovAdquirente.empresa_id == empresa_id,
        MovAdquirente.ativo.is_(True),
        MovAdquirente.valor_bruto > 0,
        MovAdquirente.bandeira.isnot(None),
        MovAdquirente.bandeira != ''
    )
    
    query = _filtrar_periodo(query, MovAdquirente.data_venda, inicio, fim)
    
    resultados = query.group_by(MovAdquirente.bandeira).all()
    
    bandeiras = {}
    for bandeira, total, qtd in resultados:
        nome = bandeira.strip().title()
        bandeiras[nome] = {
            'total': float(total or 0),
            'quantidade': qtd
        }
    
    return bandeiras


# ============================================================
# FUNÇÃO PRINCIPAL: CALCULAR KPIs
# ============================================================

def calcular_kpis(empresa_id, periodo="mes", data_inicio=None, data_fim=None, tipo_pagamento=None):
    """
    Calcula todos os KPIs do Dashboard.
    
    ✅ Usa GROUP BY categoria_principal (ZERO LIKEs)
    ✅ Retorna breakdown por categoria, subcategoria e score
    
    Returns:
        dict com todos os KPIs formatados para o frontend
    """
    try:
        inicio, fim = _obter_periodo(periodo, data_inicio, data_fim)
        
        logger.info(f"📊 KPIs: empresa={empresa_id}, periodo={periodo}")
        
        # ============================================================
        # TOTAIS
        # ============================================================
        vendas = _calcular_vendas(empresa_id, inicio, fim)
        recebimentos = _calcular_recebimentos(empresa_id, inicio, fim)
        despesas = _calcular_despesas(empresa_id, inicio, fim)
        fluxo = _calcular_fluxo(empresa_id, inicio, fim)
        
        total_entradas = recebimentos["total"] + vendas["valor_bruto"]
        total_saidas = despesas["total"]
        saldo = total_entradas - total_saidas
        
        # ============================================================
        # BREAKDOWN POR CATEGORIA PRINCIPAL (GROUP BY)
        # ============================================================
        receitas_categorias = _agrupar_por_categoria_principal(empresa_id, inicio, fim, 'receita')
        despesas_categorias = _agrupar_por_categoria_principal(empresa_id, inicio, fim, 'despesa')
        
        # ============================================================
        # BANDEIRAS
        # ============================================================
        bandeiras = _calcular_bandeiras(empresa_id, inicio, fim)
        vendas_cartao_total = sum(b['total'] for b in bandeiras.values())
        
        # ============================================================
        # CLASSIFICAÇÃO: SCORE E CONFIABILIDADE
        # ============================================================
        score_faixas = _agrupar_por_score(empresa_id, inicio, fim)
        
        # ============================================================
        # MONTAR RESPOSTA
        # ============================================================
        kpis = {
            # Totais
            "saldo": float(saldo),
            "entradas": float(total_entradas),
            "saidas": float(total_saidas),
            "vendas_cartao": float(vendas_cartao_total),
            
            # Vendas (MovAdquirente)
            "vendas": {
                "valor_bruto": _formatar_moeda(vendas["valor_bruto"]),
                "valor_liquido": _formatar_moeda(vendas["valor_liquido"]),
                "quantidade": vendas["quantidade"]
            },
            
            # Recebimentos e Despesas
            "recebimentos": {
                "total": _formatar_moeda(recebimentos["total"]),
                "quantidade": recebimentos["quantidade"]
            },
            "despesas": {
                "total": _formatar_moeda(despesas["total"]),
                "quantidade": despesas["quantidade"]
            },
            
            # Fluxo
            "fluxo": {
                "entradas": _formatar_moeda(fluxo["entradas"]),
                "saidas": _formatar_moeda(fluxo["saidas"]),
                "saldo": _formatar_moeda(fluxo["saldo"])
            },
            
            # ✅ Breakdown por categoria (vem do GROUP BY)
            "receitas_por_categoria": receitas_categorias,
            "despesas_por_categoria": despesas_categorias,
            
            # ✅ Bandeiras de cartão
            "vendas_por_bandeira": bandeiras,
            
            # ✅ Score de classificação
            "score_classificacao": score_faixas,
            
            # Metadados
            "periodo": periodo,
            "data_inicio": str(inicio) if inicio else None,
            "data_fim": str(fim) if fim else None,
            "total_registros": (
                recebimentos["quantidade"] + 
                despesas["quantidade"] + 
                vendas["quantidade"]
            )
        }
        
        logger.info(f"✅ KPIs calculados: {len(receitas_categorias)} categorias receita, {len(despesas_categorias)} despesa")
        
        return kpis
        
    except Exception as e:
        logger.error(f"❌ Erro ao calcular KPIs: {str(e)}", exc_info=True)
        return None


# ============================================================
# FUNÇÕES AUXILIARES
# ============================================================

def tem_dados_cadastrados(empresa_id):
    """Verifica se a empresa tem dados cadastrados."""
    try:
        tem_vendas = db.session.query(MovAdquirente).filter(
            MovAdquirente.empresa_id == empresa_id,
            MovAdquirente.ativo.is_(True)
        ).first() is not None
        
        tem_banco = db.session.query(MovBanco).filter(
            MovBanco.empresa_id == empresa_id
        ).first() is not None
        
        return tem_vendas or tem_banco
    except Exception as e:
        logger.error(f"❌ Erro ao verificar dados: {str(e)}")
        return False


def calcular_resumo_rapido(empresa_id):
    """Calcula um resumo rápido para exibição inicial."""
    try:
        hoje = datetime.now().date()
        inicio_mes = hoje.replace(day=1)
        
        vendas = _calcular_vendas(empresa_id, inicio_mes, hoje)
        recebimentos = _calcular_recebimentos(empresa_id, inicio_mes, hoje)
        despesas = _calcular_despesas(empresa_id, inicio_mes, hoje)
        
        # Top categorias do mês
        top_receitas = _agrupar_por_categoria_principal(empresa_id, inicio_mes, hoje, 'receita')[:3]
        top_despesas = _agrupar_por_categoria_principal(empresa_id, inicio_mes, hoje, 'despesa')[:3]
        
        return {
            "ok": True,
            "resumo": {
                "vendas_mes": _formatar_moeda(vendas["valor_bruto"]),
                "recebimentos_mes": _formatar_moeda(recebimentos["total"]),
                "despesas_mes": _formatar_moeda(despesas["total"]),
                "saldo_mes": _formatar_moeda(recebimentos["total"] - despesas["total"]),
                "quantidade_vendas": vendas["quantidade"],
                "top_receitas": top_receitas,
                "top_despesas": top_despesas
            }
        }
    except Exception as e:
        logger.error(f"❌ Erro ao calcular resumo rápido: {str(e)}")
        return {"ok": False, "error": str(e)}