from datetime import timedelta
from sqlalchemy import func
from models import db, MovAdquirente, MovBanco, Conciliacao, Adquirente


# ============================================================
# 🔧 UTILITÁRIOS
# ============================================================

def normalizar(texto):
    if not texto:
        return ""
    return texto.lower().replace(" ", "").replace("-", "").replace(".", "")


def datas_compatíveis(data_prevista, data_banco):
    if not data_prevista or not data_banco:
        return False
    return abs((data_prevista - data_banco).days) <= 2


# ============================================================
# 🎯 MATCH EXATO E PARCIAL
# ============================================================

def tentar_matching(venda, recebimentos):

    valor_liq = float(venda.valor_liquido or 0)

    # Match exato
    for r in recebimentos:
        if float(r.valor) == valor_liq and datas_compatíveis(venda.data_prevista_pagamento, r.data_movimento):
            return [(venda, r, float(r.valor))]

    # Match parcial
    for r in recebimentos:
        if float(r.valor) < valor_liq and datas_compatíveis(venda.data_prevista_pagamento, r.data_movimento):
            return [(venda, r, float(r.valor))]

    return None


# ============================================================
# 🔄 MULTIVENDA
# ============================================================

def tentar_multivenda(recebimento, vendas):
    total = float(recebimento.valor)
    acumulado = 0
    vinculos = []

    for v in vendas:
        valor_v = float(v.valor_liquido or 0)
        if acumulado + valor_v <= total:
            acumulado += valor_v
            vinculos.append((v, recebimento, valor_v))
        if acumulado == total:
            return vinculos

    return None


# ============================================================
# 💾 SALVAR CONCILIAÇÃO
# ============================================================

def registrar_conciliacao(vinculos, empresa_id):
    for venda, recebimento, valor in vinculos:

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

        venda.valor_conciliado = float(venda.valor_conciliado or 0) + valor
        venda.data_primeiro_recebimento = venda.data_primeiro_recebimento or recebimento.data_movimento
        venda.data_ultimo_recebimento = recebimento.data_movimento

        if float(venda.valor_conciliado) >= float(venda.valor_liquido):
            venda.status_conciliacao = "conciliado"
        elif float(venda.valor_conciliado) > 0:
            venda.status_conciliacao = "parcial"

        recebimento.valor_conciliado = float(recebimento.valor_conciliado or 0) + valor
        recebimento.conciliado = recebimento.valor_conciliado >= recebimento.valor

    db.session.commit()


# ============================================================
# 🚀 FUNÇÃO PRINCIPAL
# ============================================================

def executar_conciliacao(empresa_id):

    vendas = MovAdquirente.query.filter_by(empresa_id=empresa_id).all()
    recebimentos = MovBanco.query.filter_by(empresa_id=empresa_id, conciliado=False).all()

    resultado = {
        "conciliados": 0,
        "parciais": 0,
        "multivendas": 0,
        "nao_conciliados": 0,
        "creditos_sem_origem": 0
    }

    # MATCH INDIVIDUAL
    for venda in vendas:

        if venda.status_conciliacao == "conciliado":
            continue

        vinculos = tentar_matching(venda, recebimentos)

        if vinculos:
            registrar_conciliacao(vinculos, empresa_id)

            total = sum(v[2] for v in vinculos)

            if total == float(venda.valor_liquido):
                resultado["conciliados"] += 1
            else:
                resultado["parciais"] += 1

            continue

    # MULTIVENDA
    pend_vendas = [v for v in vendas if v.status_conciliacao == "pendente"]
    pend_receb = [r for r in recebimentos if not r.conciliado]

    for r in pend_receb:
        vinculos = tentar_multivenda(r, pend_vendas)
        if vinculos:
            registrar_conciliacao(vinculos, empresa_id)
            resultado["multivendas"] += 1

    # CONTAGEM FINAL
    for v in vendas:
        if v.status_conciliacao == "pendente":
            resultado["nao_conciliados"] += 1

    for r in recebimentos:
        if not r.conciliado and float(r.valor) > 0:
            resultado["creditos_sem_origem"] += 1

    return resultado
