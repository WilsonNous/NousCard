from flask import Blueprint, render_template, request, redirect, session, url_for
from werkzeug.security import generate_password_hash, check_password_hash
from db_conn import get_conn

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
    email = (request.form.get("email") or "").strip().lower()
    senha = request.form.get("senha") or ""

    print("=== DEBUG LOGIN ===")
    print("email digitado:", email)
    print("senha digitada:", senha)

    conn = get_conn()
    cur = conn.cursor()

    # MOSTRA TODOS OS USUÁRIOS QUE O RENDER ESTÁ LENDO
    cur.execute("SELECT id, email, master, admin FROM usuarios")
    print("usuarios no banco:", cur.fetchall())

    # Agora sim busca o usuário
    cur.execute(
        """
        SELECT id, empresa_id, nome, email, senha_hash, admin, master
        FROM usuarios
        WHERE email = %s
        LIMIT 1
        """,
        (email,),
    )
    usuario = cur.fetchone()

    print("usuario encontrado:", usuario)

    if not usuario or not check_password_hash(usuario["senha_hash"], senha):
        return render_template("login.html", error="Credenciais inválidas.")

    # Salva sessão
    session["usuario_id"] = usuario["id"]
    session["empresa_id"] = usuario["empresa_id"]
    session["is_admin"] = bool(usuario.get("admin"))
    session["is_master"] = bool(usuario.get("master"))

    return redirect(url_for("dashboard.dashboard"))


# ---------------------------------------------------------
# Logout
# ---------------------------------------------------------
@auth_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login_page"))


# ---------------------------------------------------------
# Registro inicial (cliente se auto cadastra)
# ---------------------------------------------------------
@auth_bp.route("/registrar", methods=["GET", "POST"])
def registrar():
    if request.method == "GET":
        return render_template("registrar.html")

    nome = (request.form.get("nome") or "").strip()
    email = (request.form.get("email") or "").strip().lower()
    senha = request.form.get("senha") or ""
    empresa_nome = (request.form.get("empresa") or "").strip()

    if not nome or not email or not senha or not empresa_nome:
        return render_template("registrar.html", error="Preencha todos os campos.")

    senha_hash = generate_password_hash(senha)

    conn = get_conn()
    with conn.cursor() as cur:
        # Cria empresa
        cur.execute(
            "INSERT INTO empresas (nome) VALUES (%s)",
            (empresa_nome,),
        )
        empresa_id = cur.lastrowid

        # Cria usuário admin da empresa
        cur.execute(
            """
            INSERT INTO usuarios (empresa_id, nome, email, senha_hash, admin, master)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (empresa_id, nome, email, senha_hash, 1, 0),
        )

    return redirect(url_for("auth.login_page"))

@auth_bp.route("/genhash")
def genhash():
    from werkzeug.security import generate_password_hash
    return generate_password_hash("nouscard")
