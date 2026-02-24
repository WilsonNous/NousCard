from flask import Blueprint, render_template, request, redirect, session, url_for, g
from models import Usuario, Empresa, db
from utils.auth_middleware import iniciar_sessao_segura
from datetime import datetime, timezone, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
import logging
import re

logger = logging.getLogger(__name__)

auth_bp = Blueprint("auth", __name__)

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

# ============================================================
# LOGIN
# ============================================================
@auth_bp.route("/login", methods=["GET"])
def login_page():
    return render_template("login.html")

@auth_bp.route("/login", methods=["POST"])
def login_post():
    email = (request.form.get("email") or "").strip().lower()
    senha = request.form.get("senha") or ""
    
    usuario = Usuario.query.filter_by(email=email).first()
    
    # Verificar bloqueio
    if usuario and usuario.bloqueado_ate and usuario.bloqueado_ate > datetime.now(timezone.utc):
        logger.warning(f"Login bloqueado: {email}")
        return render_template("login.html", error="Conta temporariamente bloqueada.")
    
    # Validar credenciais
    if not usuario or not usuario.check_password(senha):
        if usuario:
            usuario.tentativas_login_falhas += 1
            if usuario.tentativas_login_falhas >= 5:
                usuario.bloqueado_ate = datetime.now(timezone.utc) + timedelta(minutes=15)
            db.session.commit()
        logger.warning(f"Tentativa de login falha: {email}")
        return render_template("login.html", error="Credenciais inválidas.")
    
    # Login bem-sucedido
    usuario.tentativas_login_falhas = 0
    usuario.bloqueado_ate = None
    usuario.ultimo_login = datetime.now(timezone.utc)
    db.session.commit()
    
    # Iniciar sessão segura
    iniciar_sessao_segura(usuario)
    
    logger.info(f"Login bem-sucedido: {email}")
    return redirect(url_for("dashboard.dashboard"))

# ============================================================
# LOGOUT
# ============================================================
@auth_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login_page"))

# ============================================================
# REGISTRO
# ============================================================
@auth_bp.route("/registrar", methods=["GET", "POST"])
def registrar():
    if request.method == "GET":
        return render_template("registrar.html")
    
    # Coletar dados
    empresa_nome = (request.form.get("empresa") or "").strip()
    nome = (request.form.get("nome") or "").strip()
    email = (request.form.get("email") or "").strip().lower()
    senha = request.form.get("senha") or ""
    termos = request.form.get("termos")
    
    # Validações
    if not all([empresa_nome, nome, email, senha]):
        return render_template("registrar.html", error="Preencha todos os campos obrigatórios.")
    
    if not termos:
        return render_template("registrar.html", error="Você deve aceitar os Termos de Uso e Política de Privacidade.")
    
    valido, msg = validar_senha_forte(senha)
    if not valido:
        return render_template("registrar.html", error=msg)
    
    # Verificar email duplicado
    if Usuario.query.filter_by(email=email).first():
        return render_template("registrar.html", error="Email já cadastrado.")
    
    try:
        # Criar empresa
        empresa = Empresa(nome=empresa_nome, email=email)
        db.session.add(empresa)
        db.session.flush()
        
        # Criar usuário
        usuario = Usuario(
            empresa_id=empresa.id,
            nome=nome,
            email=email,
            admin=True,
            master=False,
            ativo=True
        )
        usuario.set_password(senha)
        db.session.add(usuario)
        
        db.session.commit()
        logger.info(f"Nova empresa registrada: {empresa_nome}")
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Erro no registro: {str(e)}")
        return render_template("registrar.html", error="Erro ao registrar. Tente novamente.")
    
    return redirect(url_for("auth.login_page"))
