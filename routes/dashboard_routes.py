from flask import Blueprint, render_template, g
from utils.auth_middleware import login_required

dashboard_bp = Blueprint("dashboard", __name__)

@dashboard_bp.route("/")
@login_required
def dashboard():

    # Depois conectamos aos dados reais
    kpis = {
        "total_vendas": 0.00,
        "total_recebido": 0.00,
        "diferenca": 0.00,
        "alertas": 0,
    }

    # Enviar o usuário logado (g.user vem do middleware)
    return render_template("dashboard.html", kpis=kpis, user=g.user)
