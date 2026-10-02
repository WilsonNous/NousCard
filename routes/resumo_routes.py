from datetime import datetime

from flask import Blueprint, g, render_template, redirect, url_for

from models import Empresa
from services.executive_summary_service import calcular_resumo_executivo
from utils.auth_middleware import login_required, empresa_required

resumo_bp = Blueprint("resumo", __name__)


@resumo_bp.route("/meu-resumo")
@login_required
@empresa_required
def meu_resumo():
    usuario = g.user

    if getattr(usuario, "master", False):
        return redirect(url_for("master.dashboard_operacional_page"))

    empresa = Empresa.query.filter_by(
        id=usuario.empresa_id,
        ativo=True,
    ).first_or_404()

    resumo = calcular_resumo_executivo(usuario.empresa_id)

    return render_template(
        "dashboard/meu_resumo.html",
        usuario=usuario,
        empresa_id=usuario.empresa_id,
        empresa_nome=empresa.nome,
        is_admin=getattr(usuario, "admin", False),
        is_master=False,
        current_year=datetime.now().year,
        resumo=resumo,
    )
