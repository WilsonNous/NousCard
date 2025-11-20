from flask import Blueprint, render_template, request, redirect, session, url_for, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, Usuario, Empresa

auth_bp = Blueprint("auth", __name__)

# ---------------------------------------------------------
# Página de login
# ---------------------------------------------------------
@auth_bp.route("/login", methods=["GET"])
def login_page():
    return render_template("login.html")

# ---------------------------------------------------------
# Login
# ---------------------------------------------------------
@auth_bp.route("/login", methods=["POST"])
def login_post():
    email = request.form.get("email")
    senha = request.form.get("senha")

    usuario = Usuario.query.filter_by(email=email).first()

    if not usuario or not check_password_hash(usuario.senha_hash, senha):
        return render_template("login.html", error="Credenciais inválidas.")

    # Salva sessão
    session["usuario_id"] = usuario.id
    session["empresa_id"] = usuario.empresa_id

    return redirect(url_for("dashboard.dashboard"))

# ---------------------------------------------------------
# Logout
# ---------------------------------------------------------
@auth_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login_page"))

# ---------------------------------------------------------
# Registro inicial (opcional)
# ---------------------------------------------------------
@auth_bp.route("/registrar", methods=["GET", "POST"])
def registrar():
    if request.method == "GET":
        return render_template("registrar.html")

    nome = request.form.get("nome")
    email = request.form.get("email")
    senha = request.form.get("senha")
    empresa_nome = request.form.get("empresa")

    # Cria empresa
    empresa = Empresa(nome=empresa_nome)
    db.session.add(empresa)
    db.session.commit()

    # Cria usuário admin
    usuario = Usuario(
        nome=nome,
        email=email,
        senha_hash=generate_password_hash(senha),
        empresa_id=empresa.id,
        admin=True
    )
    db.session.add(usuario)
    db.session.commit()

    return redirect(url_for("auth.login_page"))
