from models import MovAdquirente, MovBanco, Conciliacao, Adquirente
from sqlalchemy.orm import joinedload
from datetime import timedelta


def gerar_detalhamento(empresa_id):
    # Carrega vendas com conciliações e adquirentes
    vendas = (
        MovAdquirente.query
        .filter_by(empresa_id=empresa_id)
        .options(
            joinedload(MovAdquirente.conciliacoes).joinedload(Conciliacao.mov_banco),
            joinedload(MovAdquirente.adquirente_rel)
        )
        .all()
    )

    recebimentos = MovBanco.query.filter_by(empresa_id=empresa_id).all()

    linhas = []

    # -------------------------------
    # DETALHAMENTO POR VENDA
    # -------------------------------
    for v in vendas:
        adquirente = v.adquirente_rel.nome if hasattr(v, "adquirente_rel") and v.adquirente_rel else "-"

        data_prevista = v.data_prevista_pagamento.strftime("%Y-%m-%d") if v.data_prevista_pagamento else "-"

        # Prepara estrutura de saída
        linha = {
            "venda_id": v.id,
            "data_venda": v.data_venda.strftime("%Y-%m-%d") if v.data_venda else "-",
            "adquirente": adquirente,
            "bandeira": v.bandeira or "-",
            "produto": v.produto or "-",

            "valor_liquido": float(v.valor_liquido or 0),
            "valor_conciliado": float(v.valor_conciliado or 0),
            "faltante": float(v.valor_liquido) - float(v.valor_conciliado or 0),

            "previsao_pagamento": data_prevista,

            "recebimentos": [],
            "status": v.status_conciliacao,
        }

        # Adiciona detalhes dos recebimentos
        for c in v.conciliacoes:
            r = c.mov_banco
            linha["recebimentos"].append({
                "mov_banco_id": r.id,
                "data": r.data_movimento.strftime("%Y-%m-%d"),
                "banco": r.banco or "-",
                "valor": float(c.valor_conciliado or 0),
            })

        linhas.append(linha)

    # -------------------------------
    # RECEBIMENTOS SEM ORIGEM
    # -------------------------------
    creditos_sem_origem = []
    for r in recebimentos:
        if not r.conciliacoes:
            creditos_sem_origem.append({
                "mov_banco_id": r.id,
                "data_movimento": r.data_movimento.strftime("%Y-%m-%d"),
                "valor": float(r.valor or 0),
                "descricao": r.historico or "-",
            })

    return {
        "vendas": linhas,
        "creditos_sem_origem": creditos_sem_origem
    }
