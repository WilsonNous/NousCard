from flask import Blueprint, jsonify, session
from services.dashboard_service import calcular_kpis

dashboard_api = Blueprint("dashboard_api", __name__, url_prefix="/api/dashboard")

@dashboard_api.route("/kpis")
def api_kpis():
    empresa_id = session.get("empresa_id")

    data = calcular_kpis(empresa_id)

    return jsonify({ "ok": True, "kpis": data })
