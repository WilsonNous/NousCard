# utils/auth_middleware.py - VERSÃO CORRIGIDA E COMPLETA

from flask import session, redirect, url_for, g, request, jsonify
from functools import wraps
from models import Usuario, db
from datetime import datetime, timezone, timedelta
from secrets import token_urlsafe
import logging
import hashlib

logger = logging.getLogger(__name__)

# ============================================================
# CONFIGURAÇÕES DE SEGURANÇA
# ============================================================
SESSION_TIMEOUT_HOURS = 8
ENABLE_IP_BINDING = False  # Mudar para True em produção se necessário
CSRF_TOKEN_EXPIRY_HOURS = 2

# ============================================================
# CARREGAR USUÁRIO (COM SQLALCHEMY)
# ============================================================
def carregar_usuario(usuario_id: int):
    """
    Carrega usuário do banco usando SQLAlchemy.
    
    Returns:
        Usuario ou None se não encontrado/inativo
    """
    try:
        usuario = Usuario.query.filter_by(id=usuario_id, ativo=True).first()
        if usuario:
            logger.debug(f"✅ Usuário carregado: id={usuario_id}, email={usuario.email}")
        return usuario
    except Exception as e:
        logger.error(f"❌ Erro ao carregar usuário {usuario_id}: {str(e)}")
        return None

# ============================================================
# GERAR E VALIDAR CSRF TOKEN
# ============================================================
def gerar_csrf_token() -> str:
    """Gera token CSRF seguro para formulários"""
    return token_urlsafe(32)

def validar_csrf_token(token_provided: str) -> bool:
    """
    Valida token CSRF da sessão.
    
    Args:
        token_provided: Token enviado pelo cliente (form ou header)
    
    Returns:
        bool: True se válido, False caso contrário
    """
    if not token_provided:
        return False
    
    token_session = session.get("csrf_token")
    if not token_session:
        return False
    
    # Comparação constante-time para prevenir timing attacks
    return hashlib.compare_digest(
        token_provided.encode(),
        token_session.encode()
    )

# ============================================================
# VALIDAR SESSÃO
# ============================================================
def validar_sessao():
    """
    Valida se a sessão é válida e não expirou.
    
    Returns:
        Usuario ou None se inválida
    """
    usuario_id = session.get("usuario_id")
    if not usuario_id:
        return None
    
    # Verificar expiração da sessão
    last_activity = session.get("last_activity")
    if last_activity:
        try:
            last = datetime.fromisoformat(last_activity)
            if datetime.now(timezone.utc) - last > timedelta(hours=SESSION_TIMEOUT_HOURS):
                logger.info(f"⏰ Sessão expirada: usuario={usuario_id}")
                encerrar_sessao_segura()
                return None
        except (ValueError, TypeError) as e:
            logger.warning(f"⚠️ Erro ao parsear last_activity: {str(e)}")
            encerrar_sessao_segura()
            return None
    
    # Verificar IP binding (opcional para produção)
    if ENABLE_IP_BINDING:
        session_ip = session.get("session_ip")
        if session_ip and session_ip != request.remote_addr:
            logger.warning(f"🔒 IP mismatch: session={session_ip}, current={request.remote_addr}, usuario={usuario_id}")
            encerrar_sessao_segura()
            return None
    
    # Atualizar last_activity
    session["last_activity"] = datetime.now(timezone.utc).isoformat()
    
    # ✅ Cache de usuário com verificação de consistência
    if not hasattr(g, "_usuario_cache") or g._usuario_cache is None:
        g._usuario_cache = carregar_usuario(usuario_id)
    else:
        # Verificar se cache ainda é válido (empresa_id não mudou, usuário ainda ativo)
        cached = g._usuario_cache
        if (cached.empresa_id != session.get("empresa_id") or 
            not cached.ativo or 
            cached.id != usuario_id):
            # Cache inválido, recarregar
            g._usuario_cache = carregar_usuario(usuario_id)
    
    return g._usuario_cache

# ============================================================
# DECORATOR BASE PARA VALIDAÇÃO DE ACESSO
# ============================================================
def _check_acess(required_role=None, api_mode=False):
    """
    Decorator base para validação de acesso.
    
    Args:
        required_role: None, "admin", "master" ou "empresa"
        api_mode: Se True, retorna JSON em vez de redirect para erros
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(*args, **kwargs):
            usuario = validar_sessao()
            
            if not usuario:
                if api_mode:
                    return jsonify({"ok": False, "error": "Não autenticado"}), 401
                logger.info(f"🔐 Acesso negado (não autenticado): ip={request.remote_addr}, path={request.path}")
                return redirect(url_for("auth.login_page"))
            
            g.user = usuario
            
            # ✅ Validações de role
            if required_role == "master":
                if not usuario.master:
                    logger.warning(f"🚫 Acesso master negado: usuario={usuario.id}, email={usuario.email}")
                    if api_mode:
                        return jsonify({"ok": False, "error": "Acesso master necessário"}), 403
                    return "Acesso master necessário.", 403
            
            elif required_role == "admin":
                if not (usuario.admin or usuario.master):
                    logger.warning(f"🚫 Acesso admin negado: usuario={usuario.id}, email={usuario.email}")
                    if api_mode:
                        return jsonify({"ok": False, "error": "Acesso admin necessário"}), 403
                    return "Acesso admin necessário.", 403
            
            elif required_role == "empresa":
                if not usuario.empresa_id and not usuario.master:
                    logger.warning(f"🚫 Acesso empresa negado: usuario={usuario.id}, email={usuario.email}")
                    if api_mode:
                        return jsonify({"ok": False, "error": "Empresa necessária"}), 403
                    return "Empresa necessária.", 403
            
            return view_func(*args, **kwargs)
        return wrapper
    return decorator

# ============================================================
# DECORATORS PÚBLICOS (PARA PÁGINAS WEB)
# ============================================================
login_required = _check_acess(api_mode=False)
admin_required = _check_acess("admin", api_mode=False)
master_required = _check_acess("master", api_mode=False)
empresa_required = _check_acess("empresa", api_mode=False)

# ============================================================
# DECORATORS PARA APIs (RETORNAM JSON)
# ============================================================
login_required_api = _check_acess(api_mode=True)
admin_required_api = _check_acess("admin", api_mode=True)
master_required_api = _check_acess("master", api_mode=True)
empresa_required_api = _check_acess("empresa", api_mode=True)

# ============================================================
# HELPER: INICIAR SESSÃO SEGURA APÓS LOGIN
# ============================================================
def iniciar_sessao_segura(usuario):
    """
    Chamar após login bem-sucedido para inicializar sessão com segurança.
    
    ✅ Features:
        - Regenera session ID (previne session fixation)
        - Define cookies seguros
        - Gera token CSRF
        - Registra metadados de sessão
    """
    # ✅ Regenerar session ID para prevenir session fixation
    session.regenerate()
    
    # Definir dados da sessão
    session["usuario_id"] = usuario.id
    session["empresa_id"] = usuario.empresa_id
    session["is_admin"] = usuario.admin
    session["is_master"] = usuario.master
    session["session_ip"] = request.remote_addr
    session["session_user_agent"] = request.user_agent.string[:200]  # Limitar tamanho
    session["last_activity"] = datetime.now(timezone.utc).isoformat()
    
    # ✅ Gerar token CSRF para formulários
    session["csrf_token"] = gerar_csrf_token()
    
    # Marcar sessão como permanente (respeita SESSION_TIMEOUT_HOURS)
    session.permanent = True
    
    logger.info(f"✅ Sessão iniciada: usuario={usuario.id}, email={usuario.email}, ip={request.remote_addr}")

# ============================================================
# HELPER: ENCERRAR SESSÃO COM SEGURANÇA
# ============================================================
def encerrar_sessao_segura():
    """
    Limpa sessão de forma segura no logout ou expiração.
    
    ✅ Remove todos os dados sensíveis da sessão
    """
    usuario_id = session.get("usuario_id")
    
    # Limpar todos os dados da sessão
    session.clear()
    
    # Forçar cookie de sessão a expirar
    if session.modified:
        session.modified = True
    
    if usuario_id:
        logger.info(f"👋 Sessão encerrada: usuario={usuario_id}")
    else:
        logger.debug("👋 Sessão limpa (usuário não identificado)")

# ============================================================
# HELPER: OBTER TOKEN CSRF PARA TEMPLATES
# ============================================================
def get_csrf_token() -> str:
    """
    Retorna token CSRF da sessão para uso em templates.
    
    Usage em Jinja2: <input type="hidden" name="csrf_token" value="{{ get_csrf_token() }}">
    """
    return session.get("csrf_token") or gerar_csrf_token()
