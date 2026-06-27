# ============================================================
# NOUSCARD
# Dashboard Service V2 - Versão Completa
#
# Responsável pelos indicadores financeiros do Dashboard
#
# Compatível com:
#   Flask-SQLAlchemy 3.x
#   SQLAlchemy 1.4+
#
# Futuras integrações:
#   ✔ DRE
#   ✔ Fluxo de Caixa
#   ✔ BI
#   ✔ API Mobile
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
    """
    Converte qualquer valor numérico para Decimal.
    
    Args:
        valor: int, float, str ou None
    
    Returns:
        Decimal: Valor convertido ou ZERO
    """
    if valor is None:
        return ZERO
    try:
        return Decimal(str(valor))
    except Exception:
        return ZERO


def _obter_periodo(periodo, data_inicio=None, data_fim=None):
    """
    Calcula início e fim do período.
    
    Args:
        periodo: 'todos', 'mes', 'semana', 'ano', 'personalizado'
        data_inicio: Data início (YYYY-MM-DD) para período personalizado
        data_fim: Data fim (YYYY-MM-DD) para período personalizado
    
    Returns:
        tuple: (inicio, fim) onde None = sem filtro
    """
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
    
    # Padrão: mês atual
    return hoje.replace(day=1), hoje


def _formatar_moeda(valor):
    """
    Formata Decimal para string monetária brasileira.
    
    Args:
        valor: Decimal
    
    Returns:
        str: "R$ 1.234,56"
    """
    if valor is None:
        return "R$ 0,00"
    
    valor = _to_decimal(valor)
    negativo = valor < 0
    valor = abs(valor)
    
    # Formatar com separadores brasileiros
    inteiro = int(valor)
    centavos = int((valor - inteiro) * 100)
    
    # Separador de milhar
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
    """
    Aplica filtro de período em qualquer Query.
    
    Args:
        query: SQLAlchemy Query
        campo_data: Coluna de data (MovAdquirente.data_venda, MovBanco.data_movimento)
        inicio: Data início ou None
        fim: Data fim ou None
    
    Returns:
        Query filtrada
    """
    if inicio:
        query = query.filter(campo_data >= inicio)
    if fim:
        query = query.filter(campo_data <= fim)
    return query


# ============================================================
# QUERIES BASE
# ============================================================

def _query_mov_adquirente(empresa_id, inicio=None, fim=None, tipo_pagamento=None):
    """
    Query base das vendas (MovAdquirente).
    
    Args:
        empresa_id: ID da empresa
        inicio: Data início (opcional)
        fim: Data fim (opcional)
        tipo_pagamento: 'cartao', 'pix', 'boleto', 'todos' ou None
    
    Returns:
        Query filtrada
    """
    query = db.session.query(MovAdquirente).filter(
        MovAdquirente.empresa_id == empresa_id,
        MovAdquirente.ativo.is_(True)
    )
    
    query = _filtrar_periodo(query, MovAdquirente.data_venda, inicio, fim)
    
    if tipo_pagamento and tipo_pagamento != "todos":
        query = query.filter(MovAdquirente.tipo_pagamento == tipo_pagamento)
    
    return query


def _query_mov_banco(empresa_id, inicio=None, fim=None):
    """
    Query base dos movimentos bancários (MovBanco).
    
    Args:
        empresa_id: ID da empresa
        inicio: Data início (opcional)
        fim: Data fim (opcional)
    
    Returns:
        Query filtrada
    """
    query = db.session.query(MovBanco).filter(
        MovBanco.empresa_id == empresa_id
    )
    
    query = _filtrar_periodo(query, MovBanco.data_movimento, inicio, fim)
    
    return query


# ============================================================
# CONSULTAS SIMPLES
# ============================================================

def _somar_coluna(query, coluna):
    """
    Soma uma coluna e retorna Decimal.
    
    Args:
        query: SQLAlchemy Query
        coluna: Coluna a ser somada
    
    Returns:
        Decimal
    """
    valor = query.with_entities(func.sum(coluna)).scalar()
    return _to_decimal(valor)


def _contar(query):
    """
    Conta registros na query.
    
    Args:
        query: SQLAlchemy Query
    
    Returns:
        int
    """
    return query.count()


def _agrupar(query, campo, coluna_valor):
    """
    Agrupa por campo e retorna nome, quantidade e total.
    
    Args:
        query: SQLAlchemy Query
        campo: Coluna para agrupar
        coluna_valor: Coluna de valor para somar
    
    Returns:
        list[dict]: Lista com {'nome', 'quantidade', 'total'}
    """
    resultado = (
        query.with_entities(
            campo,
            func.count(),
            func.sum(coluna_valor)
        )
        .group_by(campo)
        .all()
    )
    
    retorno = []
    for item in resultado:
        retorno.append({
            "nome": item[0] or "Não informado",
            "quantidade": item[1] or 0,
            "total": str(_to_decimal(item[2]))
        })
    
    return retorno


# ============================================================
# CÁLCULOS FINANCEIROS PRINCIPAIS
# ============================================================

def _calcular_vendas(empresa_id, inicio=None, fim=None, tipo_pagamento=None):
    """
    Calcula todas as vendas da empresa.
    
    Returns:
        dict: {
            'valor_bruto': Decimal,
            'valor_liquido': Decimal,
            'valor_conciliado': Decimal,
            'taxas': Decimal,
            'quantidade': int
        }
    """
    query = _query_mov_adquirente(empresa_id, inicio, fim, tipo_pagamento)
    
    return {
        "valor_bruto": _somar_coluna(query, MovAdquirente.valor_bruto),
        "valor_liquido": _somar_coluna(query, MovAdquirente.valor_liquido),
        "valor_conciliado": _somar_coluna(query, MovAdquirente.valor_conciliado),
        "taxas": _somar_coluna(query, MovAdquirente.taxa_cobrada),
        "quantidade": _contar(query)
    }


def _calcular_recebimentos(empresa_id, inicio=None, fim=None):
    """
    Soma apenas ENTRADAS do banco (valores positivos).
    
    Returns:
        dict: {'total': Decimal, 'quantidade': int}
    """
    query = _query_mov_banco(empresa_id, inicio, fim)
    query = query.filter(MovBanco.valor > 0)
    
    return {
        "total": _somar_coluna(query, MovBanco.valor),
        "quantidade": _contar(query)
    }


def _calcular_despesas(empresa_id, inicio=None, fim=None):
    """
    Soma apenas SAÍDAS financeiras (valores negativos).
    
    ⚠️ IMPORTANTE: Retorna o valor absoluto para exibição.
    O valor real no banco é negativo.
    
    Returns:
        dict: {'total': Decimal (positivo), 'quantidade': int}
    """
    query = _query_mov_banco(empresa_id, inicio, fim)
    query = query.filter(MovBanco.valor < 0)
    
    total = _somar_coluna(query, MovBanco.valor)
    
    return {
        "total": abs(total),
        "quantidade": _contar(query)
    }


def _calcular_fluxo(empresa_id, inicio=None, fim=None):
    """
    Fluxo financeiro real: Entradas - Saídas.
    
    Returns:
        dict: {'entradas': Decimal, 'saidas': Decimal, 'saldo': Decimal}
    """
    recebimentos = _calcular_recebimentos(empresa_id, inicio, fim)
    despesas = _calcular_despesas(empresa_id, inicio, fim)
    
    saldo = recebimentos["total"] - despesas["total"]
    
    return {
        "entradas": recebimentos["total"],
        "saidas": despesas["total"],
        "saldo": saldo
    }


# ============================================================
# KPIs AUXILIARES
# ============================================================

def _ticket_medio(vendas):
    """
    Calcula o ticket médio das vendas.
    
    Args:
        vendas: dict retornado por _calcular_vendas()
    
    Returns:
        Decimal
    """
    if vendas["quantidade"] == 0:
        return ZERO
    return vendas["valor_bruto"] / Decimal(vendas["quantidade"])


def _percentual_conciliado(vendas):
    """
    Calcula o percentual de vendas já conciliadas.
    
    Args:
        vendas: dict retornado por _calcular_vendas()
    
    Returns:
        Decimal (0-100)
    """
    if vendas["valor_bruto"] == ZERO:
        return ZERO
    return (vendas["valor_conciliado"] / vendas["valor_bruto"]) * Decimal("100")


def _percentual_taxas(vendas):
    """
    Calcula o percentual de taxas sobre as vendas.
    
    Args:
        vendas: dict retornado por _calcular_vendas()
    
    Returns:
        Decimal (0-100)
    """
    if vendas["valor_bruto"] == ZERO:
        return ZERO
    return (vendas["taxas"] / vendas["valor_bruto"]) * Decimal("100")


# ============================================================
# ADQUIRENTES
# ============================================================

def _calcular_adquirentes(empresa_id, inicio=None, fim=None):
    """
    Calcula totais por adquirente.
    
    Returns:
        dict: {nome_adquirente: {'quantidade': int, 'total': str}}
    """
    query = _query_mov_adquirente(empresa_id, inicio, fim)
    
    # Buscar relação de adquirentes
    adquirentes = _agrupar(query, MovAdquirente.adquirente_nome, MovAdquirente.valor_bruto)
    
    resultado = {}
    for item in adquirentes:
        nome = item["nome"]
        resultado[nome] = {
            "quantidade": item["quantidade"],
            "total": item["total"]
        }
    
    return resultado


# ============================================================
# BANDEIRAS
# ============================================================

def _calcular_bandeiras(empresa_id, inicio=None, fim=None):
    """
    Calcula distribuição por bandeira de cartão.
    
    Returns:
        dict: {bandeira: {'quantidade': int, 'total': str}}
    """
    query = _query_mov_adquirente(empresa_id, inicio, fim)
    
    bandeiras = _agrupar(query, MovAdquirente.bandeira, MovAdquirente.valor_bruto)
    
    resultado = {}
    for item in bandeiras:
        nome = item["nome"]
        resultado[nome] = {
            "quantidade": item["quantidade"],
            "total": item["total"]
        }
    
    return resultado


# ============================================================
# TIPOS DE PAGAMENTO
# ============================================================

def _calcular_tipos_pagamento(empresa_id, inicio=None, fim=None):
    """
    Calcula distribuição por tipo de pagamento.
    
    Returns:
        dict: {tipo: {'quantidade': int, 'total': str}}
    """
    query = _query_mov_adquirente(empresa_id, inicio, fim)
    
    tipos = _agrupar(query, MovAdquirente.tipo_pagamento, MovAdquirente.valor_bruto)
    
    resultado = {}
    for item in tipos:
        nome = item["nome"] or "cartao"
        resultado[nome] = {
            "quantidade": item["quantidade"],
            "total": item["total"]
        }
    
    return resultado


# ============================================================
# CONCILIAÇÃO
# ============================================================

def _calcular_conciliacao(empresa_id, inicio=None, fim=None):
    """
    Calcula status de conciliação.
    
    Returns:
        dict: {
            'total_vendas': Decimal,
            'total_conciliado': Decimal,
            'total_pendente': Decimal,
            'percentual': Decimal
        }
    """
    vendas = _calcular_vendas(empresa_id, inicio, fim)
    
    pendente = vendas["valor_bruto"] - vendas["valor_conciliado"]
    percentual = _percentual_conciliado(vendas)
    
    return {
        "total_vendas": vendas["valor_bruto"],
        "total_conciliado": vendas["valor_conciliado"],
        "total_pendente": pendente,
        "percentual": percentual
    }


# ============================================================
# FUNÇÃO PRINCIPAL: CALCULAR KPIs
# ============================================================

def calcular_kpis(empresa_id, periodo="mes", data_inicio=None, data_fim=None, tipo_pagamento=None):
    """
    Calcula todos os KPIs do Dashboard.
    
    Args:
        empresa_id: ID da empresa
        periodo: 'todos', 'mes', 'semana', 'ano', 'personalizado'
        data_inicio: Data início (YYYY-MM-DD)
        data_fim: Data fim (YYYY-MM-DD)
        tipo_pagamento: 'cartao', 'pix', 'boleto', 'todos' ou None
    
    Returns:
        dict: {
            'ok': bool,
            'kpis': {
                'vendas': {...},
                'recebimentos': {...},
                'despesas': {...},
                'fluxo': {...},
                'adquirentes': {...},
                'bandeiras': {...},
                'tipos_pagamento': {...},
                'conciliacao': {...},
                'ticket_medio': str,
                'percentual_conciliado': str,
                'percentual_taxas': str,
                'periodo': str,
                'data_inicio': str,
                'data_fim': str
            }
        }
    """
    try:
        inicio, fim = _obter_periodo(periodo, data_inicio, data_fim)
        
        logger.info(
            f"📊 Calculando KPIs: empresa={empresa_id}, "
            f"periodo={periodo}, inicio={inicio}, fim={fim}"
        )
        
        # Cálculos principais
        vendas = _calcular_vendas(empresa_id, inicio, fim, tipo_pagamento)
        recebimentos = _calcular_recebimentos(empresa_id, inicio, fim)
        despesas = _calcular_despesas(empresa_id, inicio, fim)
        fluxo = _calcular_fluxo(empresa_id, inicio, fim)
        
        # Cálculos auxiliares
        adquirentes = _calcular_adquirentes(empresa_id, inicio, fim)
        bandeiras = _calcular_bandeiras(empresa_id, inicio, fim)
        tipos_pagamento = _calcular_tipos_pagamento(empresa_id, inicio, fim)
        conciliacao = _calcular_conciliacao(empresa_id, inicio, fim)
        
        # KPIs derivados
        ticket = _ticket_medio(vendas)
        perc_conciliado = _percentual_conciliado(vendas)
        perc_taxas = _percentual_taxas(vendas)
        
        kpis = {
            "vendas": {
                "valor_bruto": _formatar_moeda(vendas["valor_bruto"]),
                "valor_liquido": _formatar_moeda(vendas["valor_liquido"]),
                "valor_conciliado": _formatar_moeda(vendas["valor_conciliado"]),
                "taxas": _formatar_moeda(vendas["taxas"]),
                "quantidade": vendas["quantidade"]
            },
            "recebimentos": {
                "total": _formatar_moeda(recebimentos["total"]),
                "quantidade": recebimentos["quantidade"]
            },
            "despesas": {
                "total": _formatar_moeda(despesas["total"]),
                "quantidade": despesas["quantidade"]
            },
            "fluxo": {
                "entradas": _formatar_moeda(fluxo["entradas"]),
                "saidas": _formatar_moeda(fluxo["saidas"]),
                "saldo": _formatar_moeda(fluxo["saldo"])
            },
            "adquirentes": adquirentes,
            "bandeiras": bandeiras,
            "tipos_pagamento": tipos_pagamento,
            "conciliacao": {
                "total_vendas": _formatar_moeda(conciliacao["total_vendas"]),
                "total_conciliado": _formatar_moeda(conciliacao["total_conciliado"]),
                "total_pendente": _formatar_moeda(conciliacao["total_pendente"]),
                "percentual": f"{perc_conciliado:.1f}%"
            },
            "ticket_medio": _formatar_moeda(ticket),
            "percentual_conciliado": f"{perc_conciliado:.1f}%",
            "percentual_taxas": f"{perc_taxas:.1f}%",
            "periodo": periodo,
            "data_inicio": str(inicio) if inicio else None,
            "data_fim": str(fim) if fim else None
        }
        
        logger.info(f"✅ KPIs calculados com sucesso para empresa {empresa_id}")
        
        return {
            "ok": True,
            "kpis": kpis
        }
        
    except Exception as e:
        logger.error(f"❌ Erro ao calcular KPIs para empresa {empresa_id}: {str(e)}", exc_info=True)
        return {
            "ok": False,
            "error": str(e)
        }


# ============================================================
# FUNÇÕES AUXILIARES
# ============================================================

def tem_dados_cadastrados(empresa_id):
    """
    Verifica se a empresa tem dados cadastrados.
    
    Args:
        empresa_id: ID da empresa
    
    Returns:
        bool: True se existem vendas ou movimentos bancários
    """
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
    """
    Calcula um resumo rápido para exibição inicial.
    
    Args:
        empresa_id: ID da empresa
    
    Returns:
        dict: Resumo com vendas, recebimentos e despesas do mês atual
    """
    try:
        hoje = datetime.now().date()
        inicio_mes = hoje.replace(day=1)
        
        vendas = _calcular_vendas(empresa_id, inicio_mes, hoje)
        recebimentos = _calcular_recebimentos(empresa_id, inicio_mes, hoje)
        despesas = _calcular_despesas(empresa_id, inicio_mes, hoje)
        
        return {
            "ok": True,
            "resumo": {
                "vendas_mes": _formatar_moeda(vendas["valor_bruto"]),
                "recebimentos_mes": _formatar_moeda(recebimentos["total"]),
                "despesas_mes": _formatar_moeda(despesas["total"]),
                "saldo_mes": _formatar_moeda(
                    recebimentos["total"] - despesas["total"]
                ),
                "quantidade_vendas": vendas["quantidade"]
            }
        }
        
    except Exception as e:
        logger.error(f"❌ Erro ao calcular resumo rápido: {str(e)}")
        return {
            "ok": False,
            "error": str(e)
        }