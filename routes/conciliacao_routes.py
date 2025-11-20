from flask import Blueprint, render_template, jsonify
from services.conciliador import executar_conciliacao_simples

conciliacao_bp = Blueprint("conciliacao", __name__)

@conciliacao_bp.route("/", methods=["GET"])
def conciliacao_page():
    return render_template("conciliacao.html")

@conciliacao_bp.route("/executar", methods=["POST"])
def executar_conciliacao():
    resumo = executar_conciliacao_simples()
    return jsonify({"ok": True, "resumo": resumo})
