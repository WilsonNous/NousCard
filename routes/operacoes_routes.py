from flask import Blueprint, render_template, request
from utils.auth_middleware import login_required
from werkzeug.utils import secure_filename
import os

operacoes_bp = Blueprint("operacoes", __name__)

# =========================================================
# CONFIGURAÇÕES
# =========================================================
UPLOAD_DIR = "uploads"
ALLOWED_EXT = {".csv", ".xls", ".xlsx", ".txt", ".ofx"}


# =========================================================
# PÁGINA DE IMPORTAÇÃO
# =========================================================
@operacoes_bp.route("/importar", methods=["GET"])
@login_required
def importar_page():
    return render_template("importar.html")


# =========================================================
# PROCESSA UPLOAD DE ARQUIVOS
# =========================================================
@operacoes_bp.route("/importar", methods=["POST"])
@login_required
def importar_post():
    files = request.files.getlist("files[]")

    if not files:
        return {"erro": "Nenhum arquivo recebido."}, 400

    # Garante o diretório de upload
    os.makedirs(UPLOAD_DIR, exist_ok=True)

    arquivos_salvos = []

    for file in files:
        nome = secure_filename(file.filename)
        ext = os.path.splitext(nome)[1].lower()

        if ext not in ALLOWED_EXT:
            return {"erro": f"Extensão não permitida: {ext}"}, 400

        caminho = os.path.join(UPLOAD_DIR, nome)
        file.save(caminho)
        arquivos_salvos.append(nome)

    return {"sucesso": True, "arquivos": arquivos_salvos}


# =========================================================
# PÁGINA DA CONCILIAÇÃO
# =========================================================
@operacoes_bp.route("/conciliacao", methods=["GET"])
@login_required
def conciliacao_page():
    return render_template("conciliacao.html")


# =========================================================
# EXECUTA A CONCILIAÇÃO (SIMULAÇÃO)
# =========================================================
@operacoes_bp.route("/conciliar", methods=["POST"])
@login_required
def conciliar():
    # Aqui no futuro vamos plugar o motor real de conciliação
    resultado = {
        "vendas": 1250.60,
        "recebidos": 1202.90,
        "diferenca": 47.70,
        "pendencias": 3,
        "mensagem": "Conciliação executada com sucesso!"
    }
    return resultado
