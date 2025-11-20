from flask import Blueprint, render_template, jsonify
from services.conciliador import executar_conciliacao_simples
from utils.auth_middleware import login_required

conciliacao_bp = Blueprint("conciliacao", __name__)

@conciliacao_bp.route("/", methods=["GET"])
@login_required
def conciliacao_page():
    return render_template("conciliacao.html")

@conciliacao_bp.route("/executar", methods=["POST"])
@login_required
def executar_conciliacao():
    resumo = executar_conciliacao_simples()
    return jsonify({"ok": True, "resumo": resumo})
