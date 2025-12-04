# services/importer_db_movimento.py

from models import db, MovAdquirente, MovBanco
from datetime import datetime


# ============================================================
# 🔧 Função segura para converter datas
# ============================================================
def to_date(valor):
    if not valor:
        return None

    if isinstance(valor, datetime):
        return valor.date()

    formatos = ["%Y-%m-%d", "%d/%m/%Y"]

    for fmt in formatos:
        try:
            return datetime.strptime(valor, fmt).date()
        except:
            pass

    return None  # fallback


# ============================================================
#  SALVAR VENDAS (Cielo, Rede, Stone, Getnet etc.)
# ============================================================
def salvar_vendas(registros, empresa_id, arquivo_id):

    for r in registros:

        venda = MovAdquirente(
            empresa_id=empresa_id,
            adquirente_id=int(r.get("adquirente_id") or 1),

            data_venda=to_date(r.get("data_venda")),
            data_prevista_pagamento=to_date(r.get("data_prevista")),

            bandeira=r.get("bandeira"),
            produto=r.get("produto"),

            parcela=int(r.get("parcela") or 1),
            total_parcelas=int(r.get("total_parcelas") or 1),

            nsu=r.get("nsu"),
            autorizacao=r.get("autorizacao"),

            valor_bruto=float(r.get("valor_bruto") or 0),
            taxa_cobrada=float(r.get("taxa") or 0),
            valor_liquido=float(r.get("valor_liquido") or 0),

            valor_conciliado=0,
            status_conciliacao="pendente",

            arquivo_origem=str(arquivo_id)
        )

        db.session.add(venda)

    db.session.commit()



# ============================================================
#  SALVAR RECEBIMENTOS (Extratos bancários)
# ============================================================
def salvar_recebimentos(registros, empresa_id, arquivo_id):

    for r in registros:

        mov = MovBanco(
            empresa_id=empresa_id,
            conta_bancaria_id=int(r.get("conta_id") or 1),

            data_movimento=to_date(r.get("data")),
            banco=r.get("banco") or r.get("origem"),
            historico=r.get("descricao") or r.get("historico"),

            documento=r.get("documento"),

            origem=r.get("origem") or "extrato",

            valor=float(r.get("valor") or 0),
            valor_conciliado=0,
            conciliado=False,

            arquivo_origem=str(arquivo_id)
        )

        db.session.add(mov)

    db.session.commit()
