# routes/usuarios_routes.py - GESTÃO DE USUÁRIOS (APENAS MASTER)

from flask import Blueprint, render_template, request, redirect, url_for, flash, g
from models import db, Usuario, Empresa
from utils.auth_middleware import master_required
from werkzeug.security import generate_password_hash
from email_validator import validate_email, EmailNotValidError
import logging
import re

logger = logging.getLogger(__name__)

usuarios_bp = Blueprint("usuarios", __name__, url_prefix="/master/usuarios")


# ============================================================
# VALIDAÇÕES (reutilizadas do auth)
# ============================================================
def validar_email(email: str) -> tuple[bool, str]:
    """Valida email usando email-validator"""
    if not email:
        return False, "Email é obrigatório"
    
    try:
        valid = validate_email(email, check_deliverability=False)
        return True, valid.email.lower()
    except EmailNotValidError as e:
        return False, f"Email inválido: {str(e)}"


def validar_senha_forte(senha: str):
    """Valida força da senha"""
    if len(senha) < 8:
        return False, "Mínimo 8 caracteres"
    if not re.search(r"[A-Z]", senha):
        return False, "Precisa de letra maiúscula"
    if not re.search(r"[a-z]", senha):
        return False, "Precisa de letra minúscula"
    if not re.search(r"\d", senha):
        return False, "Precisa de número"
    if not re.search(r"[!@#$%^&*()_+\-=\[\]{};':\"\\|,.<>\/?]", senha):
        return False, "Precisa de caractere especial (!@#$%...)"
    return True, "Senha válida"


# ============================================================
# LISTAR USUÁRIOS
# ============================================================
@usuarios_bp.route("/")
@master_required
def listar_usuarios():
    """Lista todos os usuários (apenas master)"""
    usuarios = Usuario.query.order_by(Usuario.nome).all()
    empresas = Empresa.query.order_by(Empresa.nome).all()
    
    # Enriquecer com dados da empresa
    usuarios_data = []
    for u in usuarios:
        empresa = Empresa.query.get(u.empresa_id) if u.empresa_id else None
        usuarios_data.append({
            "usuario": u,
            "empresa_nome": empresa.nome if empresa else "—"
        })
    
    return render_template(
        "usuarios_listar.html", 
        usuarios_data=usuarios_data,
        total_usuarios=len(usuarios)
    )


# ============================================================
# CRIAR USUÁRIO
# ============================================================
@usuarios_bp.route("/novo", methods=["GET", "POST"])
@master_required
def criar_usuario():
    """Cria novo usuário (apenas master)"""
    
    if request.method == "GET":
        empresas = Empresa.query.filter_by(ativo=True).order_by(Empresa.nome).all()
        return render_template("usuario_form.html", empresas=empresas, usuario=None, modo="criar")
    
    # Coletar dados
    nome = (request.form.get("nome") or "").strip()
    email_raw = (request.form.get("email") or "").strip()
    senha = request.form.get("senha") or ""
    empresa_id = request.form.get("empresa_id", type=int)
    admin = request.form.get("admin") == "on"
    
    # Validações
    if not all([nome, email_raw, senha, empresa_id]):
        flash("Todos os campos são obrigatórios", "error")
        empresas = Empresa.query.filter_by(ativo=True).order_by(Empresa.nome).all()
        return render_template("usuario_form.html", empresas=empresas, usuario=None, modo="criar")
    
    # Validar email
    email_valido, email_result = validar_email(email_raw)
    if not email_valido:
        flash(email_result, "error")
        empresas = Empresa.query.filter_by(ativo=True).order_by(Empresa.nome).all()
        return render_template("usuario_form.html", empresas=empresas, usuario=None, modo="criar")
    
    email = email_result
    
    # Validar senha
    valido, msg = validar_senha_forte(senha)
    if not valido:
        flash(f"Senha fraca: {msg}", "error")
        empresas = Empresa.query.filter_by(ativo=True).order_by(Empresa.nome).all()
        return render_template("usuario_form.html", empresas=empresas, usuario=None, modo="criar")
    
    # Verificar duplicidade
    if Usuario.query.filter_by(email=email).first():
        flash("E-mail já cadastrado", "error")
        empresas = Empresa.query.filter_by(ativo=True).order_by(Empresa.nome).all()
        return render_template("usuario_form.html", empresas=empresas, usuario=None, modo="criar")
    
    # Verificar empresa
    empresa = Empresa.query.get(empresa_id)
    if not empresa:
        flash("Empresa não encontrada", "error")
        return redirect(url_for("usuarios.criar_usuario"))
    
    try:
        novo_usuario = Usuario(
            email=email,
            nome=nome,
            empresa_id=empresa_id,
            admin=admin,
            master=False,  # Nunca criar master via interface
            ativo=True,
            tentativas_login_falhas=0
        )
        novo_usuario.set_password(senha)
        
        db.session.add(novo_usuario)
        db.session.commit()
        
        flash(f"✅ Usuário '{nome}' criado com sucesso!", "success")
        logger.info(f"✅ Master {g.user.email} criou usuário: {email} (empresa: {empresa.nome})")
        
        return redirect(url_for("usuarios.listar_usuarios"))
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"❌ Erro ao criar usuário: {str(e)}", exc_info=True)
        flash(f"Erro ao criar usuário: {str(e)}", "error")
        empresas = Empresa.query.filter_by(ativo=True).order_by(Empresa.nome).all()
        return render_template("usuario_form.html", empresas=empresas, usuario=None, modo="criar")


# ============================================================
# EDITAR USUÁRIO
# ============================================================
@usuarios_bp.route("/<int:usuario_id>/editar", methods=["GET", "POST"])
@master_required
def editar_usuario(usuario_id):
    """Edita usuário existente (apenas master)"""
    
    usuario = Usuario.query.get_or_404(usuario_id)
    
    # Proteção: master não pode editar outro master (exceto a si mesmo)
    if usuario.master and usuario.id != g.user.id:
        flash("Você não pode editar outros usuários master", "error")
        return redirect(url_for("usuarios.listar_usuarios"))
    
    if request.method == "GET":
        empresas = Empresa.query.filter_by(ativo=True).order_by(Empresa.nome).all()
        return render_template("usuario_form.html", empresas=empresas, usuario=usuario, modo="editar")
    
    # Coletar dados
    nome = (request.form.get("nome") or "").strip()
    email_raw = (request.form.get("email") or "").strip()
    nova_senha = request.form.get("senha") or ""
    empresa_id = request.form.get("empresa_id", type=int)
    admin = request.form.get("admin") == "on"
    ativo = request.form.get("ativo") == "on"
    
    # Validações
    if not all([nome, email_raw, empresa_id]):
        flash("Nome, email e empresa são obrigatórios", "error")
        empresas = Empresa.query.filter_by(ativo=True).order_by(Empresa.nome).all()
        return render_template("usuario_form.html", empresas=empresas, usuario=usuario, modo="editar")
    
    # Validar email
    email_valido, email_result = validar_email(email_raw)
    if not email_valido:
        flash(email_result, "error")
        empresas = Empresa.query.filter_by(ativo=True).order_by(Empresa.nome).all()
        return render_template("usuario_form.html", empresas=empresas, usuario=usuario, modo="editar")
    
    email = email_result
    
    # Verificar duplicidade (excluindo o próprio usuário)
    existente = Usuario.query.filter(
        Usuario.email == email,
        Usuario.id != usuario_id
    ).first()
    if existente:
        flash("E-mail já cadastrado em outro usuário", "error")
        empresas = Empresa.query.filter_by(ativo=True).order_by(Empresa.nome).all()
        return render_template("usuario_form.html", empresas=empresas, usuario=usuario, modo="editar")
    
    # Validar senha (se foi fornecida)
    if nova_senha:
        valido, msg = validar_senha_forte(nova_senha)
        if not valido:
            flash(f"Senha fraca: {msg}", "error")
            empresas = Empresa.query.filter_by(ativo=True).order_by(Empresa.nome).all()
            return render_template("usuario_form.html", empresas=empresas, usuario=usuario, modo="editar")
    
    try:
        # Atualizar dados
        usuario.nome = nome
        usuario.email = email
        usuario.empresa_id = empresa_id
        usuario.admin = admin
        usuario.ativo = ativo
        
        # Atualizar senha se fornecida
        if nova_senha:
            usuario.set_password(nova_senha)
        
        db.session.commit()
        
        flash(f"✅ Usuário '{nome}' atualizado com sucesso!", "success")
        logger.info(f"✅ Master {g.user.email} editou usuário: {email}")
        
        return redirect(url_for("usuarios.listar_usuarios"))
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"❌ Erro ao editar usuário: {str(e)}", exc_info=True)
        flash(f"Erro ao atualizar usuário: {str(e)}", "error")
        empresas = Empresa.query.filter_by(ativo=True).order_by(Empresa.nome).all()
        return render_template("usuario_form.html", empresas=empresas, usuario=usuario, modo="editar")


# ============================================================
# RESETAR SENHA (AÇÃO RÁPIDA)
# ============================================================
@usuarios_bp.route("/<int:usuario_id>/reset-senha", methods=["POST"])
@master_required
def reset_senha(usuario_id):
    """Gera nova senha temporária (apenas master)"""
    import secrets
    
    usuario = Usuario.query.get_or_404(usuario_id)
    
    # Proteção
    if usuario.master and usuario.id != g.user.id:
        flash("Você não pode resetar senha de outros masters", "error")
        return redirect(url_for("usuarios.listar_usuarios"))
    
    # Gerar senha temporária
    nova_senha = secrets.token_urlsafe(12)
    usuario.set_password(nova_senha)
    usuario.tentativas_login_falhas = 0
    usuario.bloqueado_ate = None
    
    db.session.commit()
    
    flash(f"✅ Nova senha gerada para {usuario.nome}: <code>{nova_senha}</code><br>⚠️ Copie e envie ao usuário!", "success")
    logger.info(f"✅ Master {g.user.email} resetou senha de: {usuario.email}")
    
    return redirect(url_for("usuarios.listar_usuarios"))


# ============================================================
# REGISTRAR NO BLUEPRINT PRINCIPAL
# ============================================================
# Adicione em app.py:
# from routes.usuarios_routes import usuarios_bp
# app.register_blueprint(usuarios_bp)
