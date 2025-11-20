from flask import session, redirect, url_for

def login_required(view_func):
    """
    Middleware simples para proteção de rotas.
    """
    def wrapper(*args, **kwargs):
        if "usuario_id" not in session:
            return redirect(url_for("auth.login_page"))
        return view_func(*args, **kwargs)
    wrapper.__name__ = view_func.__name__
    return wrapper
