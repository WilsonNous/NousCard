from flask import Blueprint, render_template, request, redirect, url_for, flash, g
from utils.auth_middleware import login_required, empresa_required
from models import db, ContratoTaxa, Adquirente
from datetime import datetime, timezone
from sqlalchemy.exc import SQLAlchemyError
import logging

logger = logging.getLogger(__name__)

contrato_bp = Blueprint("contrato", __name__, url_prefix="/contratos")

@contrato_bp.route("/")
@login_required
@empresa_required
def listar_contratos():
    empresa_id = g.user.empresa_id
    contratos = ContratoTaxa.query.filter_by(empresa_id=empresa_id, ativo=True).all()
    return render_template("contratos_listar.html", contratos=contratos)

@contrato_bp.route("/novo", methods=["GET", "POST"])
@login_required
@empresa_required
def novo_contrato():
    empresa_id = g.user.empresa_id
    
    if request.method == "GET":
        adquirentes = Adquirente.query.filter_by(ativo=True).all()
        return render_template("contrato_form.html", contrato=None, adquirentes=adquirentes)
    
    try:
        adquirente_id = request.form.get("adquirente_id")
        bandeira = request.form.get("bandeira")
        produto = request.form.get("produto")
        taxa_percentual = request.form.get("taxa_percentual")
        tarifa_fixa = request.form.get("tarifa_fixa")
        
        contrato = ContratoTaxa(
            empresa_id=empresa_id,
            adquirente_id=adquirente_id,
            bandeira=bandeira,
            produto=produto,
            taxa_percentual=taxa_percentual,
            tarifa_fixa=tarifa_fixa,
            ativo=True,
            vigencia_inicio=datetime.now(timezone.utc).date()
        )
        
        db.session.add(contrato)
        db.session.commit()
        
        flash("Contrato criado com sucesso", "success")
        return redirect(url_for("contrato.listar_contratos"))
        
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error(f"Erro ao criar contrato: {str(e)}")
        flash("Erro ao criar contrato", "error")
        adquirentes = Adquirente.query.filter_by(ativo=True).all()
        return render_template("contrato_form.html", contrato=None, adquirentes=adquirentes)
