# routes/auth_routes.py - VERSÃO APRIMORADA COM SEGURANÇA REFORÇADA

from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app  # ← ✅ Adicionar current_app
from flask_login import login_user, logout_user, login_required, current_user
from models import Usuario, Empresa, db
from utils.auth_middleware import iniciar_sessao_segura
from datetime import datetime, timezone, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
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
RATE_LIMIT_WINDOW = 60  # segundos
RATE_LIMIT_MAX_REQUESTS = 10  # por janela para auth endpoints

# Cache simples para rate limiting (em produção usar Redis)
_auth_rate_limit_cache = {}

def check_auth_rate_limit(identifier: str) -> bool:
    """Verifica rate limiting para endpoints de autenticação"""
    now = time.time()
    key = f"auth:{identifier}"
    
    # Limpar entradas antigas
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
def validar_email(email: str) -> bool:
    """Valida formato de email com regex"""
    if not email:
        return False
    # Regex simples mas eficaz para formato básico de email
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def validar_senha_forte(senha: str):
    """
    Valida força da senha.
    Returns: (bool, mensagem)
    """
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
    """Valida token CSRF manualmente (para APIs ou forms sem Flask-WTF)"""
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
    
    email = (request.form.get("email") or "").strip().lower()
    senha = request.form.get("senha") or ""
    
    # ✅ Validar formato de email antes de query
    if not validar_email(email):
        logger.warning(f"Formato de email inválido: {email[:20]}...")
        return render_template("login.html", error="Email inválido.")
    
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
        # Mensagem genérica para não revelar existência do email
        logger.warning(f"Tentativa de login falha: email={email}, ip={ip}")
        return render_template("login.html", error="Email ou senha inválidos.")
    
    # Login bem-sucedido: resetar contadores
    usuario.tentativas_login_falhas = 0
    usuario.bloqueado_ate = None
    usuario.ultimo_login = datetime.now(timezone.utc)
    db.session.commit()
    
    # Iniciar sessão segura (deve regenerar session ID internamente)
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
# REGISTRO
# ============================================================
@auth_bp.route("/registrar", methods=["GET", "POST"])
def registrar():
    # ✅ Rate limiting para registro
    ip = request.remote_addr or "unknown"
    if not check_auth_rate_limit(f"registrar:{ip}"):
        return render_template("registrar.html", error="Muitas tentativas de registro. Aguarde.")
    
    # ✅ Validar CSRF
    if request.method == "POST" and request.app.config.get('WTF_CSRF_ENABLED', False):
        if not validar_csrf_token():
            return render_template("registrar.html", error="Erro de segurança. Recarregue a página."), 403
    
    if request.method == "GET":
        # ✅ Redirecionar se já autenticado
        if g.get('user'):
            return redirect(url_for("dashboard.dashboard"))
        return render_template("registrar.html")
    
    # Coletar e sanitizar dados
    empresa_nome = (request.form.get("empresa") or "").strip()
    nome = (request.form.get("nome") or "").strip()
    email = (request.form.get("email") or "").strip().lower()
    senha = request.form.get("senha") or ""
    termos = request.form.get("termos")
    
    # Validações
    if not all([empresa_nome, nome, email, senha]):
        return render_template("registrar.html", error="Preencha todos os campos obrigatórios.")
    
    if not validar_email(email):
        return render_template("registrar.html", error="Formato de email inválido.")
    
    if not termos:
        return render_template("registrar.html", error="Você deve aceitar os Termos de Uso e Política de Privacidade.")
    
    valido, msg = validar_senha_forte(senha)
    if not valido:
        return render_template("registrar.html", error=msg)
    
    # Verificar email duplicado
    if Usuario.query.filter_by(email=email).first():
        logger.warning(f"Tentativa de registro com email duplicado: {email}")
        return render_template("registrar.html", error="Email já cadastrado. Faça login ou use outro email.")
    
    # ✅ Verificar nome de empresa duplicado (opcional, mas recomendado)
    if Empresa.query.filter(func.lower(Empresa.nome) == empresa_nome.lower()).first():
        return render_template("registrar.html", error="Nome da empresa já cadastrado. Escolha outro nome.")
    
    try:
        # Criar empresa
        empresa = Empresa(
            nome=empresa_nome,
            email=email,
            ativo=True
        )
        db.session.add(empresa)
        db.session.flush()  # Gera ID sem commit
        
        # Criar usuário
        usuario = Usuario(
            empresa_id=empresa.id,
            nome=nome,
            email=email,
            admin=True,  # Primeiro usuário é admin da empresa
            master=False,
            ativo=True,
            tentativas_login_falhas=0
        )
        usuario.set_password(senha)  # Hash seguro
        db.session.add(usuario)
        
        db.session.commit()
        logger.info(f"✅ Nova empresa registrada: {empresa_nome}, email: {email}")
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"❌ Erro no registro: {str(e)}", exc_info=True)
        return render_template("registrar.html", error="Erro ao registrar. Tente novamente ou contate o suporte.")
    
    return redirect(url_for("auth.login_page"))

# ============================================================
# RECUPERAÇÃO DE SENHA (PLACEHOLDER - IMPLEMENTAR QUANDO NECESSÁRIO)
# ============================================================
@auth_bp.route("/recuperar-senha", methods=["GET", "POST"])
def recuperar_senha():
    """
    Fluxo de recuperação de senha.
    TODO: Implementar envio de email com token seguro.
    """
    if request.method == "GET":
        return render_template("recuperar_senha.html")
    
    email = (request.form.get("email") or "").strip().lower()
    
    if not validar_email(email):
        return render_template("recuperar_senha.html", error="Email inválido.")
    
    # ✅ Mensagem genérica para não revelar se email existe
    # (implementar envio real de email quando tiver SMTP configurado)
    logger.info(f"Solicitação de recuperação: {email}")
    
    return render_template("recuperar_senha.html", 
                          success="Se este email estiver cadastrado, você receberá instruções para redefinir sua senha.")
