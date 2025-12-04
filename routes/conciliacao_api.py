from flask import Blueprint, request, jsonify, g
from models import db, MovAdquirente, MovBanco, Conciliacao
from services.conciliacao import executar_conciliacao

bp_conc = Blueprint("conciliacao_api", __name__)

# ============================================================
# 1️⃣ PROCESSAR CONCILIAÇÃO
# ============================================================
@bp_conc.route("/api/conciliacao/processar", methods=["POST"])
def api_processar_conciliacao():

    # empresa vem do usuário logado
    usuario = getattr(g, "user", None)

    if not usuario:
        return jsonify({"status": "error", "message": "Usuário não autenticado"}), 401

    empresa_id = usuario.empresa_id

    if not empresa_id:
        return jsonify({"status": "error", "message": "Usuário sem empresa vinculada"}), 400

    resultado = executar_conciliacao(empresa_id)

    return jsonify({
        "status": "success",
        "message": "Conciliação executada com sucesso",
        "resultado": resultado
    }), 200


# ============================================================
# 2️⃣ STATUS GERAL DA CONCILIAÇÃO
# ============================================================
@bp_conc.route("/api/conciliacao/status", methods=["GET"])
def api_status_conciliacao():

    empresa_id = request.args.get("empresa_id")

    if not empresa_id:
        return jsonify({"status": "error", "message": "empresa_id é obrigatório"}), 400

    # Quantidades por status
    totais = {
        "conciliado": MovAdquirente.query.filter_by(
            empresa_id=empresa_id, status_conciliacao="conciliado"
        ).count(),

        "parcial": MovAdquirente.query.filter_by(
            empresa_id=empresa_id, status_conciliacao="parcial"
        ).count(),

        "pendente": MovAdquirente.query.filter_by(
            empresa_id=empresa_id, status_conciliacao="pendente"
        ).count(),

        "nao_recebido": MovAdquirente.query.filter_by(
            empresa_id=empresa_id, status_conciliacao="nao_recebido"
        ).count(),
    }

    # Créditos sem origem
    creditos_sem_origem = MovBanco.query.filter(
        MovBanco.empresa_id == empresa_id,
        MovBanco.conciliado == False,         # noqa
        MovBanco.valor > 0
    ).count()

    totais["creditos_sem_origem"] = creditos_sem_origem

    return jsonify({
        "status": "success",
        "totais": totais
    }), 200



# ============================================================
# 3️⃣ DETALHES DA CONCILIAÇÃO
# ============================================================
@bp_conc.route("/api/conciliacao/detalhes", methods=["GET"])
def api_detalhes_conciliacao():

    empresa_id = request.args.get("empresa_id")

    if not empresa_id:
        return jsonify({"status": "error", "message": "empresa_id é obrigatório"}), 400

    vendas_conciliadas = MovAdquirente.query.filter(
        MovAdquirente.empresa_id == empresa_id,
        MovAdquirente.status_conciliacao == "conciliado"
    ).all()

    vendas_parciais = MovAdquirente.query.filter(
        MovAdquirente.empresa_id == empresa_id,
        MovAdquirente.status_conciliacao == "parcial"
    ).all()

    vendas_pendentes = MovAdquirente.query.filter(
        MovAdquirente.empresa_id == empresa_id,
        MovAdquirente.status_conciliacao == "pendente"
    ).all()

    vendas_nao_recebidas = MovAdquirente.query.filter(
        MovAdquirente.empresa_id == empresa_id,
        MovAdquirente.status_conciliacao == "nao_recebido"
    ).all()

    cred_sem_origem = MovBanco.query.filter(
        MovBanco.empresa_id == empresa_id,
        MovBanco.conciliado == False,       # noqa
        MovBanco.valor > 0
    ).all()


    # Formatação da resposta
    def venda_json(v):
        return {
            "id": v.id,
            "data_venda": str(v.data_venda),
            "data_prevista": str(v.data_prevista_pagamento),
            "valor_bruto": float(v.valor_bruto),
            "valor_liquido": float(v.valor_liquido or 0),
            "valor_conciliado": float(v.valor_conciliado or 0),
            "status": v.status_conciliacao,
            "bandeira": v.bandeira,
            "adquirente": v.adquirente.nome if v.adquirente else None
        }

    def receb_json(r):
        return {
            "id": r.id,
            "data_movimento": str(r.data_movimento),
            "valor": float(r.valor),
            "valor_conciliado": float(r.valor_conciliado or 0),
            "historico": r.historico,
            "origem": r.origem,
            "conciliado": r.conciliado
        }

    return jsonify({
        "status": "success",
        "conciliadas": [venda_json(v) for v in vendas_conciliadas],
        "parciais": [venda_json(v) for v in vendas_parciais],
        "pendentes": [venda_json(v) for v in vendas_pendentes],
        "nao_recebidas": [venda_json(v) for v in vendas_nao_recebidas],
        "creditos_sem_origem": [receb_json(r) for r in cred_sem_origem]
    }), 200


# ============================================================
# Registrar Blueprint
# (No seu app.py principal você fará app.register_blueprint(bp_conc))
# ============================================================
def register(app):
    app.register_blueprint(bp_conc)
