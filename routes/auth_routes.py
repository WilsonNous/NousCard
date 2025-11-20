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

    if not usuario or not usuario.check_password(senha):
        return render_template("login.html", error="Credenciais inválidas.")

    # 🔥 Salva sessão completa
    session["usuario_id"] = usuario.id
    session["empresa_id"] = usuario.empresa_id
    session["is_master"] = usuario.master
    session["is_admin"] = usuario.admin or usuario.master

    return redirect(url_for("dashboard.dashboard"))


# ---------------------------------------------------------
# Logout
# ---------------------------------------------------------
@auth_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login_page"))


# ---------------------------------------------------------
# Registro padrão (cria empresa + admin)
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

    # Cria usuário admin da empresa
    usuario = Usuario(
        nome=nome,
        email=email,
        empresa_id=empresa.id,
        admin=True
    )
    usuario.set_password(senha)

    db.session.add(usuario)
    db.session.commit()

    return redirect(url_for("auth.login_page"))


# ---------------------------------------------------------
# 🚀 Setup MASTER — Executado 1x (opcional)
# ---------------------------------------------------------
@auth_bp.route("/setup_master")
def setup_master():
    """
    Cria o usuário MASTER global caso ainda não exista.
    """
    ja_existe = Usuario.query.filter_by(master=True).first()
    if ja_existe:
        return "Master já existe.", 400

    master = Usuario(
        nome="MASTER ROOT",
        email="master@nouscard.com",
        master=True,
        admin=True,
        empresa_id=None
    )

    master.set_password("nouscard_master")

    db.session.add(master)
    db.session.commit()

    return jsonify({
        "status": "ok",
        "message": "Usuário MASTER criado.",
        "login": "master@nouscard.com",
        "senha": "nouscard_master"
    })
