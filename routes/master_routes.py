from flask import Blueprint, render_template, request, redirect, url_for
from utils.auth_middleware import master_required
from db_conn import get_conn
from werkzeug.security import generate_password_hash

master_bp = Blueprint("master", __name__)


# ---------------------------------------------------------
# LISTAR EMPRESAS
# ---------------------------------------------------------
@master_bp.route("/master/empresas")
@master_required
def listar_empresas():
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute("SELECT id, nome, criado_em FROM empresas ORDER BY id DESC")
        empresas = cur.fetchall()

    return render_template("master/empresas_listar.html", empresas=empresas)


# ---------------------------------------------------------
# CRIAR EMPRESA
# ---------------------------------------------------------
@master_bp.route("/master/empresas/nova", methods=["GET", "POST"])
@master_required
def nova_empresa():
    if request.method == "GET":
        return render_template("master/empresa_nova.html")

    nome = (request.form.get("nome") or "").strip()
    if not nome:
        return render_template("master/empresa_nova.html", error="Informe o nome da empresa.")

    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute("INSERT INTO empresas (nome) VALUES (%s)", (nome,))
        empresa_id = cur.lastrowid

    return redirect(url_for("master.ver_empresa", empresa_id=empresa_id))


# ---------------------------------------------------------
# DETALHES DA EMPRESA + USUÁRIOS
# ---------------------------------------------------------
@master_bp.route("/master/empresas/<int:empresa_id>")
@master_required
def ver_empresa(empresa_id):
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM empresas WHERE id = %s", (empresa_id,))
        empresa = cur.fetchone()

        cur.execute(
            "SELECT id, nome, email, admin FROM usuarios WHERE empresa_id = %s",
            (empresa_id,)
        )
        usuarios = cur.fetchall()

    return render_template("master/empresa_ver.html", empresa=empresa, usuarios=usuarios)


# ---------------------------------------------------------
# CRIAR USUÁRIO NA EMPRESA
# ---------------------------------------------------------
@master_bp.route("/master/empresas/<int:empresa_id>/usuarios/novo", methods=["GET", "POST"])
@master_required
def novo_usuario_empresa(empresa_id):
    if request.method == "GET":
        return render_template("master/usuario_novo.html", empresa_id=empresa_id)

    nome = request.form.get("nome")
    email = request.form.get("email").lower()
    senha = request.form.get("senha")
    admin = 1 if request.form.get("admin") == "on" else 0

    senha_hash = generate_password_hash(senha)

    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO usuarios (empresa_id, nome, email, senha_hash, admin, master)
            VALUES (%s, %s, %s, %s, %s, 0)
            """,
            (empresa_id, nome, email, senha_hash, admin)
        )

    return redirect(url_for("master.ver_empresa", empresa_id=empresa_id))
