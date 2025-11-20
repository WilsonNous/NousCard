from flask import session, redirect, url_for, g
from functools import wraps
from models.usuarios import Usuario


# ---------------------------------------------------------
# Verifica se usuário está logado
# ---------------------------------------------------------
def login_required(view_func):
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        usuario_id = session.get("usuario_id")
        if not usuario_id:
            return redirect(url_for("auth.login_page"))

        usuario = Usuario.query.get(usuario_id)
        if not usuario:
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

        # Primeiro garante que está logado
        usuario_id = session.get("usuario_id")
        if not usuario_id:
            return redirect(url_for("auth.login_page"))

        usuario = Usuario.query.get(usuario_id)
        g.user = usuario

        if usuario.master:   # MASTER sempre pode
            return view_func(*args, **kwargs)

        if not usuario.admin:  # Admin da empresa pode
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

        usuario = Usuario.query.get(usuario_id)
        g.user = usuario

        if not usuario.master:
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

        usuario = Usuario.query.get(usuario_id)
        g.user = usuario

        if usuario.master:
            return view_func(*args, **kwargs)

        if not usuario.empresa_id:
            return "Você precisa estar vinculado a uma empresa para acessar esta área.", 403

        return view_func(*args, **kwargs)

    return wrapper
