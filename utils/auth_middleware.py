# utils/auth_middleware.py
# Compatível com Flask 2.3+ / Python 3.13+

from flask import session, redirect, url_for, g, request, jsonify
from functools import wraps
from models import Usuario, db
from datetime import datetime, timezone, timedelta
from secrets import token_urlsafe
import logging
import hmac

logger = logging.getLogger(__name__)


# ============================================================
# CONFIGURAÇÕES DE SEGURANÇA
# ============================================================

SESSION_TIMEOUT_HOURS = 8

# Se ativado, a sessão fica vinculada ao IP de origem.
# Em ambientes com proxy, Render, redes móveis etc., isso pode gerar
# encerramentos indevidos de sessão. Manter False por padrão.
ENABLE_IP_BINDING = False

CSRF_TOKEN_EXPIRY_HOURS = 2


# ============================================================
# CARREGAR USUÁRIO
# ============================================================

def carregar_usuario(usuario_id: int):
    """
    Carrega usuário ativo do banco usando SQLAlchemy.

    Args:
        usuario_id: ID do usuário.

    Returns:
        Usuario ou None se não encontrado/inativo.
    """
    try:
        usuario = Usuario.query.filter_by(
            id=usuario_id,
            ativo=True
        ).first()

        if usuario:
            logger.debug(
                f"✅ Usuário carregado: "
                f"id={usuario_id}, email={usuario.email}"
            )

        return usuario

    except Exception as e:
        logger.error(
            f"❌ Erro ao carregar usuário {usuario_id}: {str(e)}",
            exc_info=True
        )
        return None


# ============================================================
# GERAR CSRF TOKEN
# ============================================================

def gerar_csrf_token() -> str:
    """
    Gera token CSRF criptograficamente seguro.

    Returns:
        str: Token CSRF.
    """
    return token_urlsafe(32)


# ============================================================
# OBTER / CRIAR CSRF TOKEN DA SESSÃO
# ============================================================

def get_csrf_token() -> str:
    """
    Retorna o token CSRF atual da sessão.

    Se ainda não existir, cria um novo token,
    grava-o na sessão e retorna o valor.

    Uso em Jinja2:

        <input
            type="hidden"
            name="csrf_token"
            value="{{ get_csrf_token() }}"
        >
    """

    token = session.get("csrf_token")

    if not token:
        token = gerar_csrf_token()
        session["csrf_token"] = token
        session.modified = True

    return token


# ============================================================
# VALIDAR CSRF TOKEN
# ============================================================

def validar_csrf_token(token_provided: str) -> bool:
    """
    Valida o token CSRF recebido contra o token armazenado na sessão.

    Args:
        token_provided:
            Token enviado pelo formulário ou header.

    Returns:
        bool:
            True se válido.
            False se inexistente ou diferente.
    """

    if not token_provided:
        logger.warning(
            f"⚠️ CSRF ausente: "
            f"path={request.path}, ip={request.remote_addr}"
        )
        return False

    token_session = session.get("csrf_token")

    if not token_session:
        logger.warning(
            f"⚠️ CSRF não encontrado na sessão: "
            f"path={request.path}, ip={request.remote_addr}"
        )
        return False

    try:
        # hmac.compare_digest realiza comparação constant-time,
        # evitando timing attacks.
        valido = hmac.compare_digest(
            str(token_provided),
            str(token_session)
        )

        if not valido:
            logger.warning(
                f"⚠️ CSRF inválido: "
                f"path={request.path}, ip={request.remote_addr}"
            )

        return valido

    except (TypeError, ValueError) as e:
        logger.warning(
            f"⚠️ Erro ao validar CSRF: {str(e)}"
        )
        return False


# ============================================================
# VALIDAR SESSÃO
# ============================================================

def validar_sessao():
    """
    Valida se a sessão autenticada ainda é válida.

    Verifica:
        - usuario_id
        - expiração por inatividade
        - IP binding, quando habilitado
        - existência e status do usuário
        - consistência empresa / usuário

    Returns:
        Usuario ou None.
    """

    usuario_id = session.get("usuario_id")

    if not usuario_id:
        return None

    # --------------------------------------------------------
    # Verificar expiração da sessão
    # --------------------------------------------------------

    last_activity = session.get("last_activity")

    if last_activity:
        try:
            last = datetime.fromisoformat(last_activity)

            # Compatibilidade defensiva caso exista alguma sessão antiga
            # com datetime sem timezone.
            if last.tzinfo is None:
                last = last.replace(tzinfo=timezone.utc)

            agora = datetime.now(timezone.utc)

            if agora - last > timedelta(hours=SESSION_TIMEOUT_HOURS):
                logger.info(
                    f"⏰ Sessão expirada: usuario={usuario_id}"
                )

                encerrar_sessao_segura()
                return None

        except (ValueError, TypeError) as e:
            logger.warning(
                f"⚠️ Erro ao interpretar last_activity: {str(e)}"
            )

            encerrar_sessao_segura()
            return None

    # --------------------------------------------------------
    # Verificar IP binding
    # --------------------------------------------------------

    if ENABLE_IP_BINDING:
        session_ip = session.get("session_ip")
        current_ip = request.remote_addr

        if session_ip and session_ip != current_ip:
            logger.warning(
                f"🔒 IP mismatch: "
                f"session={session_ip}, "
                f"current={current_ip}, "
                f"usuario={usuario_id}"
            )

            encerrar_sessao_segura()
            return None

    # --------------------------------------------------------
    # Atualizar atividade da sessão
    # --------------------------------------------------------

    session["last_activity"] = (
        datetime.now(timezone.utc).isoformat()
    )

    session.modified = True

    # --------------------------------------------------------
    # Cache do usuário dentro do contexto da requisição
    # --------------------------------------------------------

    if (
        not hasattr(g, "_usuario_cache")
        or g._usuario_cache is None
    ):
        g._usuario_cache = carregar_usuario(usuario_id)

    else:
        cached = g._usuario_cache

        if (
            cached.id != usuario_id
            or not cached.ativo
            or (
                not cached.master
                and cached.empresa_id != session.get("empresa_id")
            )
        ):
            g._usuario_cache = carregar_usuario(usuario_id)

    usuario = g._usuario_cache

    # --------------------------------------------------------
    # Usuário deixou de existir ou foi desativado
    # --------------------------------------------------------

    if not usuario:
        logger.warning(
            f"🚫 Usuário inválido/inativo na sessão: "
            f"usuario={usuario_id}"
        )

        encerrar_sessao_segura()
        return None

    return usuario


# ============================================================
# DECORATOR BASE PARA VALIDAÇÃO DE ACESSO
# ============================================================

def _check_acess(required_role=None, api_mode=False):
    """
    Decorator base para validação de autenticação e autorização.

    Args:
        required_role:
            None
            "admin"
            "master"
            "empresa"

        api_mode:
            True  -> retorna JSON
            False -> redirect / resposta HTML
    """

    def decorator(view_func):

        @wraps(view_func)
        def wrapper(*args, **kwargs):

            usuario = validar_sessao()

            # ------------------------------------------------
            # Não autenticado
            # ------------------------------------------------

            if not usuario:

                if api_mode:
                    return jsonify({
                        "ok": False,
                        "error": "Não autenticado"
                    }), 401

                logger.info(
                    f"🔐 Acesso negado (não autenticado): "
                    f"ip={request.remote_addr}, "
                    f"path={request.path}"
                )

                return redirect(
                    url_for("auth.login_page")
                )

            # Disponibilizar usuário para as rotas/templates
            g.user = usuario

            # ------------------------------------------------
            # MASTER
            # ------------------------------------------------

            if required_role == "master":

                if not usuario.master:

                    logger.warning(
                        f"🚫 Acesso master negado: "
                        f"usuario={usuario.id}, "
                        f"email={usuario.email}"
                    )

                    if api_mode:
                        return jsonify({
                            "ok": False,
                            "error": "Acesso master necessário"
                        }), 403

                    return "Acesso master necessário.", 403

            # ------------------------------------------------
            # ADMIN
            # ------------------------------------------------

            elif required_role == "admin":

                if not (usuario.admin or usuario.master):

                    logger.warning(
                        f"🚫 Acesso admin negado: "
                        f"usuario={usuario.id}, "
                        f"email={usuario.email}"
                    )

                    if api_mode:
                        return jsonify({
                            "ok": False,
                            "error": "Acesso admin necessário"
                        }), 403

                    return "Acesso admin necessário.", 403

            # ------------------------------------------------
            # EMPRESA
            # ------------------------------------------------

            elif required_role == "empresa":

                if not usuario.empresa_id and not usuario.master:

                    logger.warning(
                        f"🚫 Acesso empresa negado: "
                        f"usuario={usuario.id}, "
                        f"email={usuario.email}"
                    )

                    if api_mode:
                        return jsonify({
                            "ok": False,
                            "error": "Empresa necessária"
                        }), 403

                    return "Empresa necessária.", 403

            return view_func(*args, **kwargs)

        return wrapper

    return decorator


# ============================================================
# DECORATORS PÚBLICOS - PÁGINAS WEB
# ============================================================

login_required = _check_acess(
    api_mode=False
)

admin_required = _check_acess(
    "admin",
    api_mode=False
)

master_required = _check_acess(
    "master",
    api_mode=False
)

empresa_required = _check_acess(
    "empresa",
    api_mode=False
)


# ============================================================
# DECORATORS PÚBLICOS - APIs
# ============================================================

login_required_api = _check_acess(
    api_mode=True
)

admin_required_api = _check_acess(
    "admin",
    api_mode=True
)

master_required_api = _check_acess(
    "master",
    api_mode=True
)

empresa_required_api = _check_acess(
    "empresa",
    api_mode=True
)


# ============================================================
# INICIAR SESSÃO SEGURA APÓS LOGIN
# ============================================================

def iniciar_sessao_segura(usuario):
    """
    Inicializa uma nova sessão após login bem-sucedido.

    Compatível com Flask 2.3+.

    Recursos:
        - limpa sessão anterior
        - reduz risco de session fixation
        - cria novo token CSRF
        - registra IP
        - registra User-Agent
        - registra última atividade
        - define sessão permanente
    """

    # --------------------------------------------------------
    # Dados seguros que podem eventualmente ser preservados
    # --------------------------------------------------------

    safe_data_to_preserve = {
        "next": session.get("next")
    }

    # --------------------------------------------------------
    # Limpar sessão anterior
    # --------------------------------------------------------

    session.clear()

    # --------------------------------------------------------
    # Restaurar somente informações permitidas
    # --------------------------------------------------------

    for key, value in safe_data_to_preserve.items():
        if value is not None:
            session[key] = value

    # --------------------------------------------------------
    # Criar dados autenticados
    # --------------------------------------------------------

    session["usuario_id"] = usuario.id
    session["empresa_id"] = usuario.empresa_id
    session["is_admin"] = bool(usuario.admin)
    session["is_master"] = bool(usuario.master)

    session["session_ip"] = request.remote_addr

    user_agent = request.user_agent.string or ""

    session["session_user_agent"] = user_agent[:200]

    session["last_activity"] = (
        datetime.now(timezone.utc).isoformat()
    )

    # --------------------------------------------------------
    # SEMPRE gerar um novo CSRF após login
    # --------------------------------------------------------

    session["csrf_token"] = gerar_csrf_token()

    # --------------------------------------------------------
    # Sessão permanente
    # --------------------------------------------------------

    session.permanent = True
    session.modified = True

    logger.info(
        f"✅ Sessão segura iniciada: "
        f"usuario={usuario.id}, "
        f"email={usuario.email}, "
        f"ip={request.remote_addr}"
    )


# ============================================================
# ENCERRAR SESSÃO COM SEGURANÇA
# ============================================================

def encerrar_sessao_segura():
    """
    Remove completamente os dados da sessão.

    Utilizado em:
        - logout
        - timeout
        - inconsistência de autenticação
        - IP binding
        - usuário desativado
    """

    usuario_id = session.get("usuario_id")

    session.clear()

    # Garantir que Flask envie a alteração do cookie
    session.modified = True

    if usuario_id:
        logger.info(
            f"👋 Sessão encerrada: usuario={usuario_id}"
        )
    else:
        logger.debug(
            "👋 Sessão limpa (usuário não identificado)"
        )
