"""Camada executiva do NousCard.

Traduz movimentos financeiros em poucos fatos objetivos para a superfície
"Meu Resumo". Nesta primeira versão o motor é determinístico: não usa IA
generativa e não altera classificações, lançamentos ou saldos.
"""
from datetime import datetime
from decimal import Decimal

from sqlalchemy import func

from models import db, MovBanco

ZERO = Decimal("0.00")


def _decimal(value):
    try:
        return Decimal(str(value or 0))
    except Exception:
        return ZERO


def _money(value):
    value = _decimal(value)
    sign = "-" if value < 0 else ""
    value = abs(value)
    raw = f"{value:.2f}"
    integer, cents = raw.split(".")
    groups = []
    while integer:
        groups.insert(0, integer[-3:])
        integer = integer[:-3]
    return f"{sign}R$ {'.'.join(groups)},{cents}"


def _month_bounds(reference=None):
    reference = reference or datetime.now().date()
    return reference.replace(day=1), reference


def calcular_resumo_executivo(empresa_id, reference=None):
    """Retorna a leitura executiva do mês da empresa.

    A v1 usa somente movimentos bancários já existentes. O conceito de
    "comprometido" ficará zerado até existir uma fonte confiável de contas a
    pagar/parcelas futuras; não inferimos compromissos a partir de saídas já
    realizadas.
    """
    start, end = _month_bounds(reference)
    base = db.session.query(MovBanco).filter(
        MovBanco.empresa_id == empresa_id,
        MovBanco.data_movimento >= start,
        MovBanco.data_movimento <= end,
    )

    entradas = _decimal(
        base.filter(MovBanco.valor > 0)
        .with_entities(func.sum(MovBanco.valor)).scalar()
    )
    saidas_raw = _decimal(
        base.filter(MovBanco.valor < 0)
        .with_entities(func.sum(MovBanco.valor)).scalar()
    )
    saidas = abs(saidas_raw)
    saldo_periodo = entradas - saidas

    # Ainda não há no domínio atual uma agenda consolidada de contas futuras.
    comprometido = ZERO
    saldo_livre = saldo_periodo - comprometido

    if saldo_periodo > 0:
        situacao = "positivo"
        headline = f"O mês está positivo em {_money(saldo_periodo)}."
    elif saldo_periodo < 0:
        situacao = "atencao"
        headline = f"As saídas superam as entradas em {_money(abs(saldo_periodo))}."
    else:
        situacao = "neutro"
        headline = "Entradas e saídas estão equilibradas neste período."

    insights = [headline]
    if entradas > 0:
        indice = (saidas / entradas * Decimal("100")).quantize(Decimal("0.1"))
        insights.append(
            f"As saídas representam {str(indice).replace('.', ',')}% das entradas do mês."
        )
    else:
        insights.append("Ainda não há entradas registradas neste mês.")

    return {
        "periodo": {"inicio": start, "fim": end},
        "entradas": float(entradas),
        "saidas": float(saidas),
        "saldo_periodo": float(saldo_periodo),
        "comprometido": float(comprometido),
        "saldo_livre": float(saldo_livre),
        "tem_previsao_compromissos": False,
        "situacao": situacao,
        "insights": insights,
        "formatado": {
            "entradas": _money(entradas),
            "saidas": _money(saidas),
            "saldo_periodo": _money(saldo_periodo),
            "comprometido": _money(comprometido),
            "saldo_livre": _money(saldo_livre),
        },
    }
