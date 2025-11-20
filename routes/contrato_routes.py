from flask import Blueprint, jsonify

contrato_bp = Blueprint("contrato", __name__)

@contrato_bp.route("/taxas", methods=["GET"])
def listar_contratos():
    # TODO: retornar contratos reais
    return jsonify({"ok": True, "items": []})
