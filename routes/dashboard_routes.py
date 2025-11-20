from flask import Blueprint, render_template, g
from utils.auth_middleware import login_required

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/")
@login_required
def dashboard():
    # Depois: carregar dados reais do banco por empresa_id = g.user["empresa_id"]
    kpis = {
        "total_vendas": 0.00,
        "total_recebido": 0.00,
        "diferenca": 0.00,
        "alertas": 0,
    }

    usuario = getattr(g, "user", None)

    return render_template("dashboard.html", kpis=kpis, usuario=usuario)
