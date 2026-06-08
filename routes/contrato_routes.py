# routes/contrato_routes.py - VERSÃO CORRIGIDA E COMPLETA

from flask import Blueprint, render_template, request, redirect, url_for, flash, g, abort
from utils.auth_middleware import login_required, empresa_required
from models import db, ContratoTaxa, Adquirente
from datetime import datetime, timezone, timedelta
from decimal import Decimal, InvalidOperation
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
import logging
import re

logger = logging.getLogger(__name__)

contrato_bp = Blueprint("contrato", __name__, url_prefix="/contratos")

# ============================================================
# VALIDAÇÕES
# ============================================================
def validar_taxa_percentual(valor):
    """Valida taxa percentual (0-100%)"""
    try:
        taxa = Decimal(str(valor or 0))
        if taxa < 0 or taxa > 100:
            return False, "Taxa deve estar entre 0% e 100%"
        return True, taxa.quantize(Decimal("0.01"))  # 2 casas decimais
    except (InvalidOperation, ValueError, TypeError):
        return False, "Formato de taxa inválido"

def validar_tarifa_fixa(valor):
    """Valida tarifa fixa (>= 0)"""
    try:
        tarifa = Decimal(str(valor or 0))
        if tarifa < 0:
            return False, "Tarifa não pode ser negativa"
        return True, tarifa.quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError, TypeError):
        return False, "Formato de tarifa inválido"

def validar_csrf_token():
    """Valida token CSRF manualmente"""
    token_form = request.form.get('csrf_token')
    token_header = request.headers.get('X-CSRF-Token')
    session_token = g.get('csrf_token') or (lambda: None)()
    
    token = token_form or token_header
    if not token or not session_token or token != session_token:
        logger.warning("CSRF token inválido ou ausente")
        return False
    return True

# ============================================================
# LISTAR CONTRATOS (COM PAGINAÇÃO)
# ============================================================
@contrato_bp.route("/")
@login_required
@empresa_required
def listar_contratos():
    empresa_id = g.user.empresa_id
    
    # Paginação
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 20, type=int), 100)
    
    # Query com paginação
    pagination = ContratoTaxa.query.filter_by(
        empresa_id=empresa_id, 
        ativo=True
    ).order_by(
        ContratoTaxa.vigencia_inicio.desc()
    ).paginate(page=page, per_page=per_page, error_out=False)
    
    return render_template(
        "contratos_listar.html", 
        contratos=pagination.items,
        pagination=pagination,
        page=page,
        per_page=per_page
    )

# ============================================================
# NOVO CONTRATO
# ============================================================
@contrato_bp.route("/novo", methods=["GET", "POST"])
@login_required
@empresa_required
def novo_contrato():
    empresa_id = g.user.empresa_id
    
    if request.method == "GET":
        adquirentes = Adquirente.query.filter_by(ativo=True).order_by(Adquirente.nome).all()
        return render_template("contrato_form.html", contrato=None, adquirentes=adquirentes)
    
    # ✅ Validar CSRF
    if not validar_csrf_token():
        flash("Erro de segurança. Recarregue a página.", "error")
        return redirect(url_for("contrato.novo_contrato"))
    
    # Coletar e sanitizar dados
    adquirente_id = request.form.get("adquirente_id", type=int)
    bandeira = (request.form.get("bandeira") or "").strip()
    produto = (request.form.get("produto") or "").strip()
    taxa_percentual_raw = request.form.get("taxa_percentual")
    tarifa_fixa_raw = request.form.get("tarifa_fixa")
    vigencia_fim_raw = request.form.get("vigencia_fim")  # Opcional
    
    # ✅ Validar campos obrigatórios
    if not adquirente_id:
        flash("Adquirente é obrigatório", "error")
        adquirentes = Adquirente.query.filter_by(ativo=True).all()
        return render_template("contrato_form.html", contrato=None, adquirentes=adquirentes)
    
    # ✅ Validar que adquirente existe e pertence à empresa (opcional, se adquirente for multi-tenant)
    adquirente = Adquirente.query.filter_by(id=adquirente_id, ativo=True).first()
    if not adquirente:
        flash("Adquirente inválida", "error")
        adquirentes = Adquirente.query.filter_by(ativo=True).all()
        return render_template("contrato_form.html", contrato=None, adquirentes=adquirentes)
    
    # ✅ Validar taxa percentual
    valido, resultado = validar_taxa_percentual(taxa_percentual_raw)
    if not valido:
        flash(resultado, "error")  # resultado contém a mensagem de erro
        adquirentes = Adquirente.query.filter_by(ativo=True).all()
        return render_template("contrato_form.html", contrato=None, adquirentes=adquirentes)
    taxa_percentual = resultado
    
    # ✅ Validar tarifa fixa
    valido, resultado = validar_tarifa_fixa(tarifa_fixa_raw)
    if not valido:
        flash(resultado, "error")
        adquirentes = Adquirente.query.filter_by(ativo=True).all()
        return render_template("contrato_form.html", contrato=None, adquirentes=adquirentes)
    tarifa_fixa = resultado
    
    # ✅ Verificar duplicata: mesmo adquirente + bandeira + produto + período sobreposto
    contrato_existente = ContratoTaxa.query.filter_by(
        empresa_id=empresa_id,
        adquirente_id=adquirente_id,
        bandeira=bandeira or None,  # NULL-safe comparison
        produto=produto or None,
        ativo=True
    ).first()
    
    if contrato_existente:
        flash("Já existe um contrato ativo para esta combinação (Adquirente + Bandeira + Produto)", "warning")
        adquirentes = Adquirente.query.filter_by(ativo=True).all()
        return render_template("contrato_form.html", contrato=None, adquirentes=adquirentes)
    
    try:
        # Parse de vigencia_fim se fornecido
        vigencia_fim = None
        if vigencia_fim_raw:
            try:
                vigencia_fim = datetime.strptime(vigencia_fim_raw, "%Y-%m-%d").date()
            except ValueError:
                flash("Formato de data de vigência inválido. Use AAAA-MM-DD", "error")
                adquirentes = Adquirente.query.filter_by(ativo=True).all()
                return render_template("contrato_form.html", contrato=None, adquirentes=adquirentes)
        
        contrato = ContratoTaxa(
            empresa_id=empresa_id,
            adquirente_id=adquirente_id,
            bandeira=bandeira or None,
            produto=produto or None,
            taxa_percentual=taxa_percentual,  # ✅ Decimal, não string
            tarifa_fixa=tarifa_fixa,  # ✅ Decimal, não string
            ativo=True,
            vigencia_inicio=datetime.now(timezone.utc).date(),
            vigencia_fim=vigencia_fim,
            criado_em=datetime.now(timezone.utc)
        )
        
        db.session.add(contrato)
        db.session.commit()
        
        logger.info(f"✅ Contrato criado: empresa={empresa_id}, adquirente={adquirente_id}, bandeira={bandeira}")
        flash("Contrato criado com sucesso", "success")
        return redirect(url_for("contrato.listar_contratos"))
        
    except IntegrityError as e:
        db.session.rollback()
        logger.warning(f"⚠️ Contrato duplicado ou erro de integridade: {str(e)}")
        flash("Erro: contrato com estas características já existe", "error")
        adquirentes = Adquirente.query.filter_by(ativo=True).all()
        return render_template("contrato_form.html", contrato=None, adquirentes=adquirentes)
        
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error(f"❌ Erro de banco ao criar contrato: {str(e)}")
        flash("Erro ao criar contrato. Tente novamente.", "error")
        adquirentes = Adquirente.query.filter_by(ativo=True).all()
        return render_template("contrato_form.html", contrato=None, adquirentes=adquirentes)

# ============================================================
# EDITAR CONTRATO (NOVO)
# ============================================================
@contrato_bp.route("/editar/<int:contrato_id>", methods=["GET", "POST"])
@login_required
@empresa_required
def editar_contrato(contrato_id):
    empresa_id = g.user.empresa_id
    
    # Buscar contrato da empresa
    contrato = ContratoTaxa.query.filter_by(
        id=contrato_id, 
        empresa_id=empresa_id, 
        ativo=True
    ).first_or_404()
    
    if request.method == "GET":
        adquirentes = Adquirente.query.filter_by(ativo=True).order_by(Adquirente.nome).all()
        return render_template(
            "contrato_form.html", 
            contrato=contrato, 
            adquirentes=adquirentes,
            edit_mode=True
        )
    
    # ✅ Validar CSRF
    if not validar_csrf_token():
        flash("Erro de segurança. Recarregue a página.", "error")
        return redirect(url_for("contrato.editar_contrato", contrato_id=contrato_id))
    
    # Coletar dados (mesma validação do novo_contrato)
    adquirente_id = request.form.get("adquirente_id", type=int)
    bandeira = (request.form.get("bandeira") or "").strip()
    produto = (request.form.get("produto") or "").strip()
    taxa_percentual_raw = request.form.get("taxa_percentual")
    tarifa_fixa_raw = request.form.get("tarifa_fixa")
    vigencia_fim_raw = request.form.get("vigencia_fim")
    
    # Validar taxa
    valido, resultado = validar_taxa_percentual(taxa_percentual_raw)
    if not valido:
        flash(resultado, "error")
        return redirect(url_for("contrato.editar_contrato", contrato_id=contrato_id))
    taxa_percentual = resultado
    
    # Validar tarifa
    valido, resultado = validar_tarifa_fixa(tarifa_fixa_raw)
    if not valido:
        flash(resultado, "error")
        return redirect(url_for("contrato.editar_contrato", contrato_id=contrato_id))
    tarifa_fixa = resultado
    
    try:
        # Atualizar campos
        contrato.adquirente_id = adquirente_id
        contrato.bandeira = bandeira or None
        contrato.produto = produto or None
        contrato.taxa_percentual = taxa_percentual
        contrato.tarifa_fixa = tarifa_fixa
        
        if vigencia_fim_raw:
            try:
                contrato.vigencia_fim = datetime.strptime(vigencia_fim_raw, "%Y-%m-%d").date()
            except ValueError:
                flash("Formato de data de vigência inválido", "error")
                return redirect(url_for("contrato.editar_contrato", contrato_id=contrato_id))
        
        contrato.atualizado_em = datetime.now(timezone.utc)
        
        db.session.commit()
        
        logger.info(f"✅ Contrato atualizado: id={contrato_id}")
        flash("Contrato atualizado com sucesso", "success")
        return redirect(url_for("contrato.listar_contratos"))
        
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error(f"❌ Erro ao atualizar contrato {contrato_id}: {str(e)}")
        flash("Erro ao atualizar contrato", "error")
        return redirect(url_for("contrato.editar_contrato", contrato_id=contrato_id))

# ============================================================
# DESATIVAR CONTRATO (SOFT DELETE)
# ============================================================
@contrato_bp.route("/desativar/<int:contrato_id>", methods=["POST"])
@login_required
@empresa_required
def desativar_contrato(contrato_id):
    empresa_id = g.user.empresa_id
    
    # Validar CSRF para operações que alteram dados
    if not validar_csrf_token():
        flash("Erro de segurança", "error")
        return redirect(url_for("contrato.listar_contratos"))
    
    contrato = ContratoTaxa.query.filter_by(
        id=contrato_id,
        empresa_id=empresa_id,
        ativo=True
    ).first_or_404()
    
    try:
        contrato.ativo = False
        contrato.atualizado_em = datetime.now(timezone.utc)
        db.session.commit()
        
        logger.info(f"✅ Contrato desativado: id={contrato_id}")
        flash("Contrato desativado com sucesso", "success")
        
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error(f"❌ Erro ao desativar contrato {contrato_id}: {str(e)}")
        flash("Erro ao desativar contrato", "error")
    
    return redirect(url_for("contrato.listar_contratos"))
