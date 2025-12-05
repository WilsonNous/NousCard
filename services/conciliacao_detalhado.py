from models import MovAdquirente, MovBanco, Conciliacao
from datetime import datetime


def gerar_detalhamento(empresa_id):

    vendas = MovAdquirente.query.filter_by(empresa_id=empresa_id).all()

    linhas = []

    for v in vendas:

        linha = {
            "data_venda": v.data_venda.strftime("%Y-%m-%d") if v.data_venda else "-",
            "adquirente": v.adquirente.nome if v.adquirente else "-",
            "bandeira": v.bandeira or "-",
            "valor_liquido": float(v.valor_liquido or 0),
            "data_prevista": v.data_prevista_pagamento.strftime("%Y-%m-%d") if v.data_prevista_pagamento else "-",
            "valor_conciliado": float(v.valor_conciliado or 0),
            "status": v.status_conciliacao
        }

        linhas.append(linha)

    return linhas
