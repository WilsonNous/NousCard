from flask import session, redirect, url_for, g, request
from functools import wraps
from models import Usuario, db
from datetime import datetime, timezone, timedelta
import logging

logger = logging.getLogger(__name__)

# ============================================================
# CONFIGURAÇÕES
# ============================================================
SESSION_TIMEOUT_HOURS = 8
ENABLE_IP_BINDING = False  # Mudar para True em produção se necessário

# ============================================================
# CARREGAR USUÁRIO (COM SQLALCHEMY)
# ============================================================
def carregar_usuario(usuario_id):
    """Carrega usuário do banco usando SQLAlchemy"""
    try:
        usuario = Usuario.query.filter_by(id=usuario_id, ativo=True).first()
        return usuario
    except Exception as e:
        logger.error(f"Erro ao carregar usuário {usuario_id}: {str(e)}")
        return None

# ============================================================
# VALIDAR SESSÃO
# ============================================================
def validar_sessao():
    """Valida se a sessão é válida e não expirou"""
    usuario_id = session.get("usuario_id")
    if not usuario_id:
        return None
    
    # Verificar expiração
    last_activity = session.get("last_activity")
    if last_activity:
        try:
            last = datetime.fromisoformat(last_activity)
            if datetime.now(timezone.utc) - last > timedelta(hours=SESSION_TIMEOUT_HOURS):
                logger.info(f"Sessão expirada: usuario={usuario_id}")
                session.clear()
                return None
        except Exception:
            pass
    
    # Verificar IP binding (opcional)
    if ENABLE_IP_BINDING:
        session_ip = session.get("session_ip")
        if session_ip and session_ip != request.remote_addr:
            logger.warning(f"IP mismatch: session={session_ip}, current={request.remote_addr}")
            session.clear()
            return None
    
    # Atualizar last_activity
    session["last_activity"] = datetime.now(timezone.utc).isoformat()
    
    # Carregar usuário (com cache opcional)
    if not hasattr(g, "_usuario_cache"):
        g._usuario_cache = carregar_usuario(usuario_id)
    
    return g._usuario_cache

# ============================================================
# DECORATOR BASE
# ============================================================
def _check_acess(required_role=None):
    """Decorator base para validação de acesso"""
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(*args, **kwargs):
            usuario = validar_sessao()
            
            if not usuario:
                logger.info(f"Acesso negado (não autenticado): ip={request.remote_addr}")
                return redirect(url_for("auth.login_page"))
            
            g.user = usuario
            
            # Validações de role
            if required_role == "master":
                if not usuario.master:
                    logger.warning(f"Acesso master negado: usuario={usuario.id}")
                    return "Acesso master necessário.", 403
            
            elif required_role == "admin":
                if not (usuario.admin or usuario.master):
                    logger.warning(f"Acesso admin negado: usuario={usuario.id}")
                    return "Acesso admin necessário.", 403
            
            elif required_role == "empresa":
                if not usuario.empresa_id and not usuario.master:
                    logger.warning(f"Acesso empresa negado: usuario={usuario.id}")
                    return "Empresa necessária.", 403
            
            return view_func(*args, **kwargs)
        return wrapper
    return decorator

# ============================================================
# DECORATORS PÚBLICOS
# ============================================================
login_required = _check_acess()
admin_required = _check_acess("admin")
master_required = _check_acess("master")
empresa_required = _check_acess("empresa")

# ============================================================
# HELPER: ATUALIZAR SESSÃO NO LOGIN
# ============================================================
def iniciar_sessao_segura(usuario):
    """Chamar após login bem-sucedido"""
    session["usuario_id"] = usuario.id
    session["empresa_id"] = usuario.empresa_id
    session["is_admin"] = usuario.admin
    session["is_master"] = usuario.master
    session["session_ip"] = request.remote_addr
    session["session_user_agent"] = request.user_agent.string
    session["last_activity"] = datetime.now(timezone.utc).isoformat()
    session.permanent = True
