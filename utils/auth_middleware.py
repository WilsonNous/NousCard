from flask import session, redirect, url_for, g
from functools import wraps
from db_conn import get_conn


def _carregar_usuario(usuario_id: int):
    """
    Busca usuário no banco via pymysql.
    Retorna um dict ou None.
    """
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                id,
                empresa_id,
                nome,
                email,
                admin,
                master,
                criado_em
            FROM usuarios
            WHERE id = %s
            """,
            (usuario_id,),
        )
        return cur.fetchone()


# ---------------------------------------------------------
# Verifica se usuário está logado
# ---------------------------------------------------------
def login_required(view_func):
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        usuario_id = session.get("usuario_id")
        if not usuario_id:
            return redirect(url_for("auth.login_page"))

        usuario = _carregar_usuario(usuario_id)
        if not usuario:
            session.clear()
            return redirect(url_for("auth.login_page"))

        # Disponibiliza o usuário globalmente na requisição
        g.user = usuario

        return view_func(*args, **kwargs)

    return wrapper


# ---------------------------------------------------------
# Apenas para usuários administradores da empresa OU master
# ---------------------------------------------------------
def admin_required(view_func):
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        usuario_id = session.get("usuario_id")
        if not usuario_id:
            return redirect(url_for("auth.login_page"))

        usuario = _carregar_usuario(usuario_id)
        if not usuario:
            session.clear()
            return redirect(url_for("auth.login_page"))

        g.user = usuario

        # MASTER sempre pode
        if usuario.get("master"):
            return view_func(*args, **kwargs)

        # Admin da empresa pode
        if not usuario.get("admin"):
            return "Acesso restrito a administradores.", 403

        return view_func(*args, **kwargs)

    return wrapper


# ---------------------------------------------------------
# Apenas o master pode acessar
# ---------------------------------------------------------
def master_required(view_func):
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        usuario_id = session.get("usuario_id")
        if not usuario_id:
            return redirect(url_for("auth.login_page"))

        usuario = _carregar_usuario(usuario_id)
        if not usuario:
            session.clear()
            return redirect(url_for("auth.login_page"))

        g.user = usuario

        if not usuario.get("master"):
            return "Acesso permitido apenas ao usuário MASTER.", 403

        return view_func(*args, **kwargs)

    return wrapper


# ---------------------------------------------------------
# Rotas que exigem vínculo com empresa (menos master)
# ---------------------------------------------------------
def empresa_required(view_func):
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        usuario_id = session.get("usuario_id")
        if not usuario_id:
            return redirect(url_for("auth.login_page"))

        usuario = _carregar_usuario(usuario_id)
        if not usuario:
            session.clear()
            return redirect(url_for("auth.login_page"))

        g.user = usuario

        if usuario.get("master"):
            return view_func(*args, **kwargs)

        if not usuario.get("empresa_id"):
            return "Você precisa estar vinculado a uma empresa para acessar esta área.", 403

        return view_func(*args, **kwargs)

    return wrapper
