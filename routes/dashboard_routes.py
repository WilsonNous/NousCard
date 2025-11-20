from flask import Blueprint, render_template

dashboard_bp = Blueprint("dashboard", __name__)

@dashboard_bp.route("/")
def dashboard():
    # Depois: carregar dados reais do banco
    kpis = {
        "total_vendas": 0.00,
        "total_recebido": 0.00,
        "diferenca": 0.00,
        "alertas": 0,
    }
    return render_template("dashboard.html", kpis=kpis)
