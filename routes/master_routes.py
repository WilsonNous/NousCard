from flask import Blueprint, render_template, request, redirect, url_for, session
from werkzeug.security import generate_password_hash
from db_conn import get_conn
from utils.auth_middleware import master_required

master_bp = Blueprint("master", __name__, url_prefix="/master")


# =========================================================
# LISTAR EMPRESAS
# =========================================================
@master_bp.route("/empresas")
@master_required
def empresas_listar():
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute("""
            SELECT id, nome, criado_em
            FROM empresas
            ORDER BY id DESC
        """)
        empresas = cur.fetchall()

    return render_template("master/empresas_listar.html", empresas=empresas)


# =========================================================
# CRIAR EMPRESA
# =========================================================
@master_bp.route("/empresa/nova", methods=["GET", "POST"])
@master_required
def empresa_nova():
    if request.method == "GET":
        return render_template("master/empresa_nova.html")

    nome = request.form.get("nome")
    admin_nome = request.form.get("admin_nome")
    email = (request.form.get("email") or "").lower().strip()
    senha = request.form.get("senha")

    senha_hash = generate_password_hash(senha)

    conn = get_conn()
    with conn.cursor() as cur:

        # 1) Criar empresa
        cur.execute(
            "INSERT INTO empresas (nome) VALUES (%s)",
            (nome,)
        )
        empresa_id = cur.lastrowid

        # 2) Criar usuário admin
        cur.execute("""
            INSERT INTO usuarios
                (empresa_id, nome, email, senha_hash, admin, master)
            VALUES
                (%s, %s, %s, %s, %s, %s)
        """, (empresa_id, admin_nome, email, senha_hash, 1, 0))

    return redirect(url_for("master.empresas_listar"))


# =========================================================
# VER EMPRESA + LISTAR USUÁRIOS
# =========================================================
@master_bp.route("/empresa/<int:empresa_id>")
@master_required
def empresa_ver(empresa_id):

    conn = get_conn()
    with conn.cursor() as cur:

        # Dados da empresa
        cur.execute("SELECT id, nome, criado_em FROM empresas WHERE id = %s", (empresa_id,))
        empresa = cur.fetchone()

        # Usuários da empresa
        cur.execute("""
            SELECT id, nome, email, admin, criado_em
            FROM usuarios
            WHERE empresa_id = %s
            ORDER BY nome
        """, (empresa_id,))
        usuarios = cur.fetchall()

    return render_template(
        "master/empresa_ver.html",
        empresa=empresa,
        usuarios=usuarios
    )


# =========================================================
# CRIAR USUÁRIO DENTRO DA EMPRESA
# =========================================================
@master_bp.route("/empresa/<int:empresa_id>/usuario/novo", methods=["GET", "POST"])
@master_required
def usuario_novo(empresa_id):

    if request.method == "GET":
        conn = get_conn()
        with conn.cursor() as cur:
            cur.execute("SELECT id, nome FROM empresas WHERE id = %s", (empresa_id,))
            empresa = cur.fetchone()

        return render_template("master/usuario_novo.html", empresa=empresa)

    # POST
    nome = request.form.get("nome")
    email = (request.form.get("email") or "").strip().lower()
    senha = request.form.get("senha")
    admin_flag = 1 if request.form.get("admin") else 0

    senha_hash = generate_password_hash(senha)

    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO usuarios
                (empresa_id, nome, email, senha_hash, admin, master)
            VALUES
                (%s, %s, %s, %s, %s, %s)
        """, (empresa_id, nome, email, senha_hash, admin_flag, 0))

    return redirect(url_for("master.empresa_ver", empresa_id=empresa_id))


# =========================================================
# (OPCIONAL) DELETAR USUÁRIO
# =========================================================
@master_bp.route("/empresa/<int:empresa_id>/usuario/<int:user_id>/remover")
@master_required
def usuario_remover(empresa_id, user_id):

    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute("DELETE FROM usuarios WHERE id = %s AND empresa_id = %s", (user_id, empresa_id))

    return redirect(url_for("master.empresa_ver", empresa_id=empresa_id))


# =========================================================
# (OPCIONAL) DELETAR EMPRESA
# =========================================================
@master_bp.route("/empresa/<int:empresa_id>/remover")
@master_required
def empresa_remover(empresa_id):

    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute("DELETE FROM empresas WHERE id = %s", (empresa_id,))

    return redirect(url_for("master.empresas_listar"))
