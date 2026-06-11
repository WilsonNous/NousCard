# routes/auth_routes.py - VERSÃO COM EMAIL-VALIDATOR

from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app, g  
from flask_login import login_user, logout_user, login_required, current_user
from models import Usuario, Empresa, db
from utils.auth_middleware import iniciar_sessao_segura
from datetime import datetime, timezone, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
from email_validator import validate_email, EmailNotValidError
import logging
import re
import time

logger = logging.getLogger(__name__)

auth_bp = Blueprint("auth", __name__)

# ============================================================
# CONFIGURAÇÕES DE SEGURANÇA
# ============================================================
MAX_LOGIN_ATTEMPTS = 5
BLOCK_DURATION_MINUTES = 15
RATE_LIMIT_WINDOW = 60
RATE_LIMIT_MAX_REQUESTS = 10

_auth_rate_limit_cache = {}

def check_auth_rate_limit(identifier: str) -> bool:
    """Verifica rate limiting para endpoints de autenticação"""
    now = time.time()
    key = f"auth:{identifier}"
    
    _auth_rate_limit_cache[key] = [
        t for t in _auth_rate_limit_cache.get(key, [])
        if now - t < RATE_LIMIT_WINDOW
    ]
    
    if len(_auth_rate_limit_cache.get(key, [])) >= RATE_LIMIT_MAX_REQUESTS:
        return False
    
    _auth_rate_limit_cache.setdefault(key, []).append(now)
    return True

# ============================================================
# VALIDAÇÕES
# ============================================================

def validar_email(email: str) -> tuple[bool, str]:
    """Valida email usando biblioteca robusta email-validator."""
    if not email:
        return False, "Email é obrigatório"
    
    try:
        valid = validate_email(email, check_deliverability=False)
        return True, valid.email.lower()
    except EmailNotValidError as e:
        error_msg = str(e)
        if "ascii" in error_msg.lower():
            return False, "Email não pode conter caracteres especiais"
        elif "local part" in error_msg.lower():
            return False, "Parte local do email inválida"
        elif "domain" in error_msg.lower():
            return False, "Domínio do email inválido"
        return False, f"Formato de email inválido: {error_msg}"


def validar_senha_forte(senha: str):
    """Valida força da senha."""
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


def validar_csrf_token():
    """Valida token CSRF manualmente"""
    token_form = request.form.get('csrf_token')
    token_header = request.headers.get('X-CSRF-Token')
    session_token = session.get('csrf_token')
    
    token = token_form or token_header
    if not token or not session_token or token != session_token:
        logger.warning("CSRF token inválido ou ausente")
        return False
    return True


# ============================================================
# LOGIN
# ============================================================
@auth_bp.route("/login", methods=["GET"])
def login_page():
    # ✅ Redirecionar para dashboard se já autenticado
    if g.get('user'):
        return redirect(url_for("dashboard.dashboard"))
    return render_template("login.html")


@auth_bp.route("/login", methods=["POST"])
def login_post():
    # ✅ Rate limiting por IP
    ip = request.remote_addr or "unknown"
    if not check_auth_rate_limit(f"login:{ip}"):
        logger.warning(f"Rate limit excedido no login: IP={ip}")
        return render_template("login.html", error="Muitas tentativas. Aguarde alguns segundos.")
    
    # ✅ Validar CSRF se habilitado
    if current_app.config.get('WTF_CSRF_ENABLED', False):
        if not validar_csrf_token():
            return render_template("login.html", error="Erro de segurança. Recarregue a página."), 403
    
    email_raw = (request.form.get("email") or "").strip()
    senha = request.form.get("senha") or ""
    
    # ✅ Validar formato de email usando email-validator
    email_valido, email_result = validar_email(email_raw)
    
    if not email_valido:
        logger.warning(f"Email inválido: raw={repr(email_raw)[:50]}, erro={email_result}")
        return render_template("login.html", error=f"Email inválido: {email_result}")
    
    email = email_result
    
    usuario = Usuario.query.filter_by(email=email).first()
    
    # Verificar bloqueio
    if usuario and usuario.bloqueado_ate and usuario.bloqueado_ate > datetime.now(timezone.utc):
        minutos_restantes = int((usuario.bloqueado_ate - datetime.now(timezone.utc)).total_seconds() / 60) + 1
        logger.warning(f"Login bloqueado: {email}, bloqueio por mais {minutos_restantes}min")
        return render_template("login.html", error=f"Conta bloqueada por segurança. Tente em {minutos_restantes} minutos.")
    
    # Validar credenciais
    if not usuario or not usuario.check_password(senha):
        if usuario:
            usuario.tentativas_login_falhas = (usuario.tentativas_login_falhas or 0) + 1
            if usuario.tentativas_login_falhas >= MAX_LOGIN_ATTEMPTS:
                usuario.bloqueado_ate = datetime.now(timezone.utc) + timedelta(minutes=BLOCK_DURATION_MINUTES)
                logger.warning(f"Conta bloqueada após {MAX_LOGIN_ATTEMPTS} tentativas: {email}")
            db.session.commit()
        logger.warning(f"Tentativa de login falha: email={email}, ip={ip}")
        return render_template("login.html", error="Email ou senha inválidos.")
    
    # Login bem-sucedido: resetar contadores
    usuario.tentativas_login_falhas = 0
    usuario.bloqueado_ate = None
    usuario.ultimo_login = datetime.now(timezone.utc)
    db.session.commit()
    
    # Iniciar sessão segura
    iniciar_sessao_segura(usuario)
    
    logger.info(f"✅ Login bem-sucedido: {email}, ip={ip}")
    return redirect(url_for("dashboard.dashboard"))


# ============================================================
# LOGOUT
# ============================================================
@auth_bp.route("/logout")
def logout():
    usuario_email = g.get('user', {}).get('email') if g.get('user') else 'desconhecido'
    session.clear()
    logger.info(f"Logout: {usuario_email}")
    return redirect(url_for("auth.login_page"))


# ============================================================
# RECUPERAÇÃO DE SENHA
# ============================================================
@auth_bp.route("/recuperar-senha", methods=["GET", "POST"])
def recuperar_senha():
    """Fluxo de recuperação de senha."""
    if request.method == "GET":
        return render_template("recuperar_senha.html")
    
    email_raw = (request.form.get("email") or "").strip()
    
    email_valido, email_result = validar_email(email_raw)
    if not email_valido:
        return render_template("recuperar_senha.html", error=f"Email inválido: {email_result}")
    
    email = email_result
    
    logger.info(f"Solicitação de recuperação: {email}")
    
    return render_template("recuperar_senha.html", 
                          success="Se este email estiver cadastrado, você receberá instruções para redefinir sua senha.")
