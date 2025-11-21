# routes/operacoes_routes.py
from flask import Blueprint, render_template, request, jsonify, session
from utils.auth_middleware import login_required, empresa_required
from services.importer import process_uploaded_files
from services.importer_db import listar_arquivos_importados, buscar_arquivo_por_id

operacoes_bp = Blueprint("operacoes", __name__, url_prefix="/operacoes")


# ============================================================
# Tela de IMPORTAÇÃO (GET)
# ============================================================
@operacoes_bp.route("/importar", methods=["GET"])
@login_required
@empresa_required
def importar_page():
    return render_template("importar.html")


# ============================================================
# Upload com salvamento no banco
# ============================================================
@operacoes_bp.route("/upload", methods=["POST"])
@login_required
@empresa_required
def upload_arquivos():

    files = request.files.getlist("files")
    if not files:
        return jsonify({"ok": False, "message": "Nenhum arquivo enviado."}), 400

    empresa_id = session.get("empresa_id")
    usuario_id = session.get("usuario_id")

    resultados = process_uploaded_files(files, empresa_id, usuario_id)

    total_arquivos = len(resultados)
    qtde_vendas = sum(1 for r in resultados if r["tipo"] == "venda")
    qtde_recebimentos = sum(1 for r in resultados if r["tipo"] == "recebimento")
    total_vendas = sum(r.get("linhas", 0) for r in resultados if r["tipo"] == "venda")
    total_recebimentos = sum(r.get("linhas", 0) for r in resultados if r["tipo"] == "recebimento")

    resumo = {
        "ok": True,
        "message": "Arquivos importados, analisados e salvos com sucesso.",
        "total_arquivos": total_arquivos,
        "qtde_vendas": qtde_vendas,
        "qtde_recebimentos": qtde_recebimentos,
        "total_vendas": total_vendas,
        "total_recebimentos": total_recebimentos,
        "result": resultados
    }

    return jsonify(resumo)


# ============================================================
# Tela de CONCILIAÇÃO (GET)
# ============================================================
@operacoes_bp.route("/conciliacao", methods=["GET"])
@login_required
@empresa_required
def conciliar_page():
    return render_template("conciliacao.html")


# ============================================================
# Tela: Arquivos Importados
# ============================================================
@operacoes_bp.route("/arquivos", methods=["GET"])
@login_required
@empresa_required
def arquivos_importados_page():
    empresa_id = session.get("empresa_id")

    arquivos = listar_arquivos_importados(empresa_id)
    return render_template("arquivos_importados.html", arquivos=arquivos)


# ============================================================
# Tela: Detalhamento do Arquivo
# ============================================================
@operacoes_bp.route("/arquivo/<int:arquivo_id>")
@login_required
@empresa_required
def arquivo_detalhe_page(arquivo_id):
    empresa_id = session.get("empresa_id")

    arquivo = buscar_arquivo_por_id(arquivo_id, empresa_id)

    if not arquivo:
        return render_template("erro.html", mensagem="Arquivo não encontrado ou não pertence à sua empresa.")

    return render_template("arquivo_detalhe.html", arquivo=arquivo)
