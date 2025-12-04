# utils/auth_middleware.py
from flask import session, redirect, url_for, g
from functools import wraps
from db_conn import get_conn


# ---------------------------------------------------------
# Função auxiliar: carrega usuário direto do MySQL
# ---------------------------------------------------------
def carregar_usuario(usuario_id):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        SELECT id, empresa_id, nome, email, admin, master
        FROM usuarios
        WHERE id = %s
        LIMIT 1
    """, (usuario_id,))
    
    row = cur.fetchone()
    if not row:
        return None

    # Criando um objeto simples só para segurar os dados:
    class SimpleUser:
        pass

    u = SimpleUser()
    u.id = row["id"]
    u.empresa_id = row["empresa_id"]
    u.nome = row["nome"]
    u.email = row["email"]
    u.admin = bool(row["admin"])
    u.master = bool(row["master"])

    return u


# ---------------------------------------------------------
# LOGIN REQUIRED
# ---------------------------------------------------------
def login_required(view_func):
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        usuario_id = session.get("usuario_id")
        if not usuario_id:
            return redirect(url_for("auth.login_page"))

        usuario = carregar_usuario(usuario_id)
        if not usuario:
            return redirect(url_for("auth.login_page"))

        g.user = usuario
        return view_func(*args, **kwargs)

    return wrapper


# ---------------------------------------------------------
# ADMIN REQUIRED
# ---------------------------------------------------------
def admin_required(view_func):
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        usuario_id = session.get("usuario_id")
        if not usuario_id:
            return redirect(url_for("auth.login_page"))

        usuario = carregar_usuario(usuario_id)
        if not usuario:
            return redirect(url_for("auth.login_page"))

        g.user = usuario

        # MASTER sempre pode tudo
        if usuario.master:
            return view_func(*args, **kwargs)

        if not usuario.admin:
            return "Acesso restrito a administradores.", 403

        return view_func(*args, **kwargs)

    return wrapper


# ---------------------------------------------------------
# MASTER REQUIRED
# ---------------------------------------------------------
def master_required(view_func):
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        usuario_id = session.get("usuario_id")
        if not usuario_id:
            return redirect(url_for("auth.login_page"))

        usuario = carregar_usuario(usuario_id)
        if not usuario:
            return redirect(url_for("auth.login_page"))

        g.user = usuario

        if not usuario.master:
            return "Acesso permitido apenas ao usuário MASTER.", 403

        return view_func(*args, **kwargs)

    return wrapper


# ---------------------------------------------------------
# EMPRESA REQUIRED
# ---------------------------------------------------------
def empresa_required(view_func):
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        usuario_id = session.get("usuario_id")
        if not usuario_id:
            return redirect(url_for("auth.login_page"))

        usuario = carregar_usuario(usuario_id)
        if not usuario:
            return redirect(url_for("auth.login_page"))

        g.user = usuario

        # MASTER pode ver tudo, mesmo sem empresa
        if usuario.master:
            return view_func(*args, **kwargs)

        if not usuario.empresa_id:
            return "Você precisa estar vinculado a uma empresa para acessar esta área.", 403

        return view_func(*args, **kwargs)

    return wrapper
