from flask import Blueprint, render_template, request, redirect, url_for, flash, g, abort
from models import db, Empresa, Usuario, LogAuditoria
from utils.auth_middleware import master_required
from datetime import datetime, timezone
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
import logging
import re

logger = logging.getLogger(__name__)

empresas_bp = Blueprint("empresas", __name__, url_prefix="/empresas")

# ============================================================
# VALIDAÇÕES
# ============================================================
def validar_cnpj(cnpj):
    """Valida CNPJ brasileiro"""
    if not cnpj:
        return True  # Opcional
    cnpj = re.sub(r'\D', '', cnpj)
    if len(cnpj) != 14:
        return False
    # Implementar dígitos verificadores
    return True

def log_acao_empresa(acao, empresa, detalhes_extra=""):
    """Log centralizado para ações em empresas"""
    try:
        log = LogAuditoria(
            usuario_id=g.user.id,
            empresa_id=empresa.id if empresa else None,
            acao=acao,
            detalhes=f"Nome: {empresa.nome if empresa else 'N/A'}, {detalhes_extra}",
            ip=request.remote_addr,
            criado_em=datetime.now(timezone.utc)
        )
        db.session.add(log)
        db.session.commit()
    except Exception as e:
        logger.error(f"Erro ao logar ação: {str(e)}")
        db.session.rollback()

# ============================================================
# LISTAR EMPRESAS
# ============================================================
@empresas_bp.route("/")
@master_required
def listar_empresas():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    
    empresas = Empresa.query.order_by(Empresa.criado_em.desc())\
        .paginate(page=page, per_page=per_page, error_out=False)
    
    return render_template("empresas_listar.html", empresas=empresas)

# ============================================================
# NOVA EMPRESA
# ============================================================
@empresas_bp.route("/nova", methods=["GET", "POST"])
@master_required
def nova_empresa():
    if request.method == "GET":
        return render_template("empresas_form.html", empresa=None)
    
    # Coletar e sanitizar dados
    nome = (request.form.get("nome") or "").strip()
    documento = (request.form.get("documento") or "").strip()
    
    # Validações
    if not nome or len(nome) > 150:
        flash("Nome deve ter entre 1 e 150 caracteres", "error")
        return render_template("empresas_form.html", empresa=None)
    
    if documento:
        if len(documento) > 20:
            flash("Documento muito longo", "error")
            return render_template("empresas_form.html", empresa=None)
        if not validar_cnpj(documento):
            flash("CNPJ inválido", "error")
            return render_template("empresas_form.html", empresa=None)
        
        # Verificar duplicidade
        if Empresa.query.filter_by(documento=documento).first():
            flash("Documento já cadastrado em outra empresa", "error")
            return render_template("empresas_form.html", empresa=None)
    
    try:
        empresa = Empresa(
            nome=nome,
            documento=documento,
            ativo=True
        )
        db.session.add(empresa)
        
        # Log de auditoria
        log_acao_empresa("master_criou_empresa", empresa)
        
        db.session.commit()
        
        flash("Empresa criada com sucesso", "success")
        logger.info(f"Master criou empresa: {nome}")
        
        return redirect(url_for("empresas.listar_empresas"))
        
    except IntegrityError as e:
        db.session.rollback()
        logger.error(f"Erro de integridade: {str(e)}")
        flash("Erro: documento já existe", "error")
        return render_template("empresas_form.html", empresa=None)
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error(f"Erro de banco: {str(e)}")
        flash("Erro interno. Tente novamente.", "error")
        return render_template("empresas_form.html", empresa=None)

# ============================================================
# EDITAR EMPRESA
# ============================================================
@empresas_bp.route("/<int:empresa_id>/editar", methods=["GET", "POST"])
@master_required
def editar_empresa(empresa_id):
    empresa = Empresa.query.get_or_404(empresa_id)
    
    if request.method == "GET":
        return render_template("empresas_form.html", empresa=empresa)
    
    # Coletar e sanitizar dados
    nome = (request.form.get("nome") or "").strip()
    documento = (request.form.get("documento") or "").strip()
    ativa = request.form.get("ativa") == "on"
    
    # Validações
    if not nome or len(nome) > 150:
        flash("Nome deve ter entre 1 e 150 caracteres", "error")
        return render_template("empresas_form.html", empresa=empresa)
    
    if documento:
        if len(documento) > 20:
            flash("Documento muito longo", "error")
            return render_template("empresas_form.html", empresa=empresa)
        if not validar_cnpj(documento):
            flash("CNPJ inválido", "error")
            return render_template("empresas_form.html", empresa=empresa)
        
        # Verificar duplicidade (excluindo esta empresa)
        existente = Empresa.query.filter(
            Empresa.documento == documento,
            Empresa.id != empresa_id
        ).first()
        if existente:
            flash("Documento já cadastrado em outra empresa", "error")
            return render_template("empresas_form.html", empresa=empresa)
    
    # Verificar desativação
    if not ativa and empresa.ativo:
        usuarios_ativos = Usuario.query.filter_by(empresa_id=empresa_id, ativo=True).count()
        if usuarios_ativos > 0:
            flash(f"Atenção: {usuarios_ativos} usuários serão afetados pela desativação", "warning")
    
    try:
        empresa.nome = nome
        empresa.documento = documento
        empresa.ativo = ativa
        
        # Log de auditoria
        log_acao_empresa("master_editou_empresa", empresa, f"Ativa: {ativa}")
        
        db.session.commit()
        
        flash("Empresa atualizada com sucesso", "success")
        logger.info(f"Master editou empresa: {empresa_id}")
        
        return redirect(url_for("empresas.listar_empresas"))
        
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error(f"Erro ao editar empresa: {str(e)}")
        flash("Erro ao atualizar empresa", "error")
        return render_template("empresas_form.html", empresa=empresa)
