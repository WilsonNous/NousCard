# services/importer_db_movimento.py

from models import db, MovAdquirente, MovBanco
from datetime import datetime


# ============================================================
#  SALVAR VENDAS (Cielo, Rede, Stone, Getnet etc.)
# ============================================================

def salvar_vendas(registros, empresa_id, arquivo_id):

    for r in registros:
        venda = MovAdquirente(
            empresa_id = empresa_id,
            adquirente_id = int(r.get("adquirente_id", 1)),
            data_venda = r.get("data_venda"),
            data_prevista_pagamento = r.get("data_prevista"),

            bandeira = r.get("bandeira"),
            produto = r.get("produto"),

            parcela = r.get("parcela"),
            total_parcelas = r.get("total_parcelas"),

            nsu = r.get("nsu"),
            autorizacao = r.get("autorizacao"),

            valor_bruto = r.get("valor_bruto", 0),
            taxa_cobrada = r.get("taxa", 0),
            valor_liquido = r.get("valor_liquido", 0),

            valor_conciliado = 0,
            status_conciliacao = "pendente",
            arquivo_origem = arquivo_id
        )

        db.session.add(venda)

    db.session.commit()



# ============================================================
#  SALVAR RECEBIMENTOS (extratos bancários)
# ============================================================

def salvar_recebimentos(registros, empresa_id, arquivo_id):

    for r in registros:
        mov = MovBanco(
            empresa_id = empresa_id,
            conta_bancaria_id = int(r.get("conta_id", 1)),   # padrão

            data_movimento = r.get("data"),
            historico = r.get("descricao"),
            documento = r.get("documento"),

            valor = r.get("valor", 0),
            valor_conciliado = 0,
            conciliado = False,

            arquivo_origem = arquivo_id
        )

        db.session.add(mov)

    db.session.commit()
