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
    qtde_vendas = sum(1 for r in resultados if r.get("tipo") == "venda")
    qtde_recebimentos = sum(1 for r in resultados if r.get("tipo") == "recebimento")
    total_vendas = sum(r.get("linhas", 0) for r in resultados if r.get("tipo") == "venda")
    total_recebimentos = sum(r.get("linhas", 0) for r in resultados if r.get("tipo") == "recebimento")

    resumo = {
        "ok": True,
        "message": "Arquivos importados, analisados e salvos com sucesso.",
        "total_arquivos": total_arquivos,
        "qtde_vendas": qtde_vendas,
        "qtde_recebimentos": qtde_recebimento
