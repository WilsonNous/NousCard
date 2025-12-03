# routes/dashboard_routes.py
from flask import Blueprint, render_template, g
from utils.auth_middleware import login_required

dashboard_bp = Blueprint("dashboard", __name__)

@dashboard_bp.route("/")
@login_required
def dashboard():
    usuario = g.user
    return render_template("dashboard.html")
