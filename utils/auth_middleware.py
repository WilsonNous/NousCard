# utils/auth_middleware.py
from flask import session, redirect, url_for, g
from functools import wraps
from models.usuarios import Usuario


def login_required(view_func):
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        usuario_id = session.get("usuario_id")
        if not usuario_id:
            return redirect(url_for("auth.login_page"))

        usuario = Usuario.query.get(usuario_id)
        if not usuario:
            return redirect(url_for("auth.login_page"))

        g.user = usuario
        return view_func(*args, **kwargs)

    return wrapper


def admin_required(view_func):
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        usuario_id = session.get("usuario_id")
        if not usuario_id:
            return redirect(url_for("auth.login_page"))

        usuario = Usuario.query.get(usuario_id)
        if not usuario:
            return redirect(url_for("auth.login_page"))

        g.user = usuario

        if usuario.is_master:
            return view_func(*args, **kwargs)

        if not usuario.is_admin:
            return "Acesso restrito a administradores.", 403

        return view_func(*args, **kwargs)

    return wrapper


def master_required(view_func):
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        usuario_id = session.get("usuario_id")
        if not usuario_id:
            return redirect(url_for("auth.login_page"))

        usuario = Usuario.query.get(usuario_id)
        if not usuario:
            return redirect(url_for("auth.login_page"))

        g.user = usuario

        if not usuario.is_master:
            return "Acesso permitido apenas ao usuário MASTER.", 403

        return view_func(*args, **kwargs)

    return wrapper


def empresa_required(view_func):
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        usuario_id = session.get("usuario_id")
        if not usuario_id:
            return redirect(url_for("auth.login_page"))

        usuario = Usuario.query.get(usuario_id)
        if not usuario:
            return redirect(url_for("auth.login_page"))

        g.user = usuario

        if usuario.is_master:
            return view_func(*args, **kwargs)

        if not usuario.empresa_id:
            return "Você precisa estar vinculado a uma empresa para acessar esta área.", 403

        return view_func(*args, **kwargs)

    return wrapper
