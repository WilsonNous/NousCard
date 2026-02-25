from flask import Blueprint, render_template, request, redirect, url_for, flash, g, abort
from utils.auth_middleware import master_required
from models import db, Empresa, Usuario, LogAuditoria, MovAdquirente, MovBanco
from datetime import datetime, timezone
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
import logging
import re

logger = logging.getLogger(__name__)

master_bp = Blueprint("master", __name__, url_prefix="/master")

# ============================================================
# VALIDAÇÕES
# ============================================================
def validar_senha_forte(senha):
    if len(senha) < 8:
        return False, "Mínimo 8 caracteres"
    if not re.search(r"[A-Z]", senha):
        return False, "Precisa de letra maiúscula"
    if not re.search(r"[a-z]", senha):
        return False, "Precisa de letra minúscula"
    if not re.search(r"\d", senha):
        return False, "Precisa de número"
    return True, "Senha válida"

def log_acao_master(acao, detalhes, empresa_id=None):
    """Log centralizado para ações master"""
    try:
        log = LogAuditoria(
            usuario_id=g.user.id,
            empresa_id=empresa_id,
            acao=acao,
            detalhes=detalhes,
            ip=request.remote_addr,
            criado_em=datetime.now(timezone.utc)
        )
        db.session.add(log)
        db.session.commit()
    except Exception as e:
        logger.error(f"Erro ao logar ação master: {str(e)}")
        db.session.rollback()

# ============================================================
# LISTAR EMPRESAS
# ============================================================
@master_bp.route("/empresas")
@master_required
def empresas_listar():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    
    empresas = Empresa.query.order_by(Empresa.id.desc())\
        .paginate(page=page, per_page=per_page, error_out=False)
    
    return render_template("master/empresas_listar.html", empresas=empresas)

# ============================================================
# CRIAR EMPRESA
# ============================================================
@master_bp.route("/empresa/nova", methods=["GET", "POST"])
@master_required
def empresa_nova():
    if request.method == "GET":
        return render_template("master/empresa_nova.html")
    
    # Coletar dados
    nome = (request.form.get("nome") or "").strip()
    admin_nome = (request.form.get("admin_nome") or "").strip()
    email = (request.form.get("email") or "").lower().strip()
    senha = request.form.get("senha")
    
    # Validações
    if not all([nome, admin_nome, email, senha]):
        flash("Preencha todos os campos obrigatórios", "error")
        return render_template("master/empresa_nova.html")
    
    valido, msg = validar_senha_forte(senha)
    if not valido:
        flash(msg, "error")
        return render_template("master/empresa_nova.html")
    
    # Verificar email duplicado
    if Usuario.query.filter_by(email=email).first():
        flash("Email já cadastrado em outra empresa", "error")
        return render_template("master/empresa_nova.html")
    
    try:
        # Criar empresa
        empresa = Empresa(nome=nome, documento="", email=email, ativo=True)
        db.session.add(empresa)
        db.session.flush()
        
        # Criar usuário admin
        usuario = Usuario(
            empresa_id=empresa.id,
            nome=admin_nome,
            email=email,
            admin=True,
            master=False,
            ativo=True
        )
        usuario.set_password(senha)
        db.session.add(usuario)
        
        # Log de auditoria
        log_acao_master("master_criou_empresa", f"Empresa: {nome}, Admin: {email}", empresa.id)
        
        db.session.commit()
        
        flash(f"Empresa '{nome}' criada com sucesso!", "success")
        logger.info(f"Master criou empresa: {nome}, admin={email}")
        
        return redirect(url_for("master.empresas_listar"))
        
    except IntegrityError as e:
        db.session.rollback()
        logger.error(f"Erro de integridade: {str(e)}")
        flash("Erro ao criar. Email já existe?", "error")
        return render_template("master/empresa_nova.html")
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error(f"Erro de banco: {str(e)}")
        flash("Erro interno. Tente novamente.", "error")
        return render_template("master/empresa_nova.html")

# ============================================================
# VER EMPRESA + USUÁRIOS
# ============================================================
@master_bp.route("/empresa/<int:empresa_id>")
@master_required
def empresa_ver(empresa_id):
    empresa = Empresa.query.get_or_404(empresa_id)
    usuarios = Usuario.query.filter_by(empresa_id=empresa_id).order_by(Usuario.nome).all()
    
    return render_template("master/empresa_ver.html", empresa=empresa, usuarios=usuarios)

# ============================================================
# CRIAR USUÁRIO
# ============================================================
@master_bp.route("/empresa/<int:empresa_id>/usuario/novo", methods=["GET", "POST"])
@master_required
def usuario_novo(empresa_id):
    empresa = Empresa.query.get_or_404(empresa_id)
    
    if request.method == "GET":
        return render_template("master/usuario_novo.html", empresa=empresa)
    
    # Coletar dados
    nome = (request.form.get("nome") or "").strip()
    email = (request.form.get("email") or "").lower().strip()
    senha = request.form.get("senha")
    admin_flag = 1 if request.form.get("admin") else 0
    
    # Validações
    if not all([nome, email, senha]):
        flash("Preencha todos os campos obrigatórios", "error")
        return render_template("master/usuario_novo.html", empresa=empresa)
    
    valido, msg = validar_senha_forte(senha)
    if not valido:
        flash(msg, "error")
        return render_template("master/usuario_novo.html", empresa=empresa)
    
    # Verificar email duplicado
    if Usuario.query.filter_by(email=email).first():
        flash("Email já cadastrado", "error")
        return render_template("master/usuario_novo.html", empresa=empresa)
    
    try:
        usuario = Usuario(
            empresa_id=empresa_id,
            nome=nome,
            email=email,
            admin=bool(admin_flag),
            master=False,
            ativo=True
        )
        usuario.set_password(senha)
        db.session.add(usuario)
        
        # Log de auditoria
        log_acao_master("master_criou_usuario", f"Usuário: {email}, Empresa: {empresa.nome}", empresa_id)
        
        db.session.commit()
        
        flash(f"Usuário '{nome}' criado com sucesso!", "success")
        logger.info(f"Master criou usuário: {email}, empresa={empresa_id}")
        
        return redirect(url_for("master.empresa_ver", empresa_id=empresa_id))
        
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error(f"Erro ao criar usuário: {str(e)}")
        flash("Erro ao criar usuário", "error")
        return render_template("master/usuario_novo.html", empresa=empresa)

# ============================================================
# REMOVER USUÁRIO (SOFT DELETE)
# ============================================================
@master_bp.route("/empresa/<int:empresa_id>/usuario/<int:user_id>/remover", methods=["POST"])
@master_required
def usuario_remover(empresa_id, user_id):
    usuario = Usuario.query.filter_by(id=user_id, empresa_id=empresa_id).first_or_404()
    
    # Não permitir auto-exclusão
    if usuario.id == g.user.id:
        flash("Não pode excluir a si mesmo", "error")
        return redirect(url_for("master.empresa_ver", empresa_id=empresa_id))
    
    try:
        # Soft delete
        usuario.ativo = False
        usuario.nome = f"[EXCLUÍDO] {usuario.nome}"
        
        # Log de auditoria
        log_acao_master("master_excluiu_usuario", f"Usuário: {usuario.email}", empresa_id)
        
        db.session.commit()
        
        flash("Usuário removido com sucesso", "success")
        logger.info(f"Master removeu usuário: {usuario.id}, empresa={empresa_id}")
        
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error(f"Erro ao remover usuário: {str(e)}")
        flash("Erro ao remover usuário", "error")
    
    return redirect(url_for("master.empresa_ver", empresa_id=empresa_id))

# ============================================================
# REMOVER EMPRESA (SOFT DELETE COM VALIDAÇÃO)
# ============================================================
@master_bp.route("/empresa/<int:empresa_id>/remover", methods=["POST"])
@master_required
def empresa_remover(empresa_id):
    empresa = Empresa.query.get_or_404(empresa_id)
    
    # Verificar se tem dados financeiros
    tem_vendas = MovAdquirente.query.filter_by(empresa_id=empresa_id).count() > 0
    tem_recebimentos = MovBanco.query.filter_by(empresa_id=empresa_id).count() > 0
    
    if tem_vendas or tem_recebimentos:
        flash("Não é possível excluir empresa com dados financeiros. Contate o suporte.", "error")
        return redirect(url_for("master.empresas_listar"))
    
    try:
        # Soft delete
        empresa.ativo = False
        empresa.nome = f"[EXCLUÍDA] {empresa.nome}"
        
        # Desativar todos os usuários
        for usuario in Usuario.query.filter_by(empresa_id=empresa_id).all():
            usuario.ativo = False
        
        # Log de auditoria
        log_acao_master("master_excluiu_empresa", f"Empresa: {empresa.nome}", empresa_id)
        
        db.session.commit()
        
        flash("Empresa removida com sucesso", "success")
        logger.info(f"Master removeu empresa: {empresa_id}")
        
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error(f"Erro ao remover empresa: {str(e)}")
        flash("Erro ao remover empresa", "error")
    
    return redirect(url_for("master.empresas_listar"))
