# routes/dashboard_routes.py
from flask import Blueprint, render_template, g
from utils.auth_middleware import login_required

dashboard_bp = Blueprint("dashboard", __name__)

@dashboard_bp.route("/")
@login_required
def dashboard():
    usuario = g.user

    # Depois conectamos com dados reais
    kpis = {
        "total_vendas": 0.00,
        "total_recebido": 0.00,
        "diferenca": 0.00,
        "alertas": 0,
    }

    return render_template("dashboard.html", kpis=kpis)
