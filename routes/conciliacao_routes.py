from flask import Blueprint, request, jsonify
from services.conciliacao import executar_conciliacao

bp_conc = Blueprint("conciliacao", __name__)


@bp_conc.route("/api/conciliacao/executar")
def api_executar_conciliacao():
    empresa_id = request.args.get("empresa_id", type=int)

    if not empresa_id:
        return jsonify({"status": "error", "message": "empresa_id ausente"}), 400

    resultado = executar_conciliacao(empresa_id)

    return jsonify({
        "status": "success",
        "resultado": resultado
    })
