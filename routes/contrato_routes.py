from flask import Blueprint, jsonify
from utils.auth_middleware import login_required

contrato_bp = Blueprint("contrato", __name__)

@contrato_bp.route("/taxas", methods=["GET"])
@login_required
def listar_contratos():
    # TODO: retornar contratos reais
    return jsonify({"ok": True, "items": []})
