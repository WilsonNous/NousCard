# routes/operacoes_routes.py
from flask import Blueprint, render_template, request, jsonify, session
from utils.auth_middleware import login_required, empresa_required
from utils.parsers import parse_csv_generic  # você já tem
from utils.concilia import (
    conciliar,
    normalizar_registros_vendas,
    normalizar_registros_recebimentos,
)

operacoes_bp = Blueprint("operacoes", __name__, url_prefix="/operacoes")


# ============================================================
# Tela de IMPORTAÇÃO
# ============================================================
@operacoes_bp.route("/importar", methods=["GET"])
@login_required
@empresa_required
def importar_page():
    return render_template("importar_arquivos.html")


# ============================================================
# Upload de arquivos – separa VENDAS x RECEBIMENTOS
# ============================================================
@operacoes_bp.route("/upload", methods=["POST"])
@login_required
@empresa_required
def upload_arquivos():
    if "files[]" not in request.files:
        return jsonify({"ok": False, "message": "Nenhum arquivo enviado."}), 400

    arquivos = request.files.getlist("files[]")

    vendas = []
    recebimentos = []

    for file_storage in arquivos:
        filename = (file_storage.filename or "").strip()
        if not filename:
            continue

        nome_lower = filename.lower()

        # CSV / TXT / XLS / XLSX usando parse genérico
        if nome_lower.endswith((".csv", ".txt", ".xls", ".xlsx")):
            registros = parse_csv_generic(file_storage)
        else:
            # formato ainda não suportado aqui
            continue

        # Heurística simples:
        #  - se nome contém "extrato" => recebimento
        #  - se contém "bb", "itau" etc com padrão de extrato – também recebimento
        #  - caso contrário, consideramos vendas
        if "extrato" in nome_lower or "ofx" in nome_lower:
            recebimentos.extend(normalizar_registros_recebimentos(registros, filename))
        else:
            vendas.extend(normalizar_registros_vendas(registros, filename))

    # Guarda na sessão para a conciliação
    session["vendas"] = [
        {**v, "valor": float(v["valor"])} for v in vendas
    ]  # jsonify-friendly
    session["recebimentos"] = [
        {**r, "valor": float(r["valor"])} for r in recebimentos
    ]

    resumo = {
        "ok": True,
        "total_arquivos": len(arquivos),
        "qtde_vendas": len(vendas),
        "qtde_recebimentos": len(recebimentos),
        "total_vendas": float(sum(v["valor"] for v in vendas)),
        "total_recebimentos": float(sum(r["valor"] for r in recebimentos)),
        "message": "Arquivos importados e analisados com sucesso. Agora execute a conciliação.",
    }

    return jsonify(resumo)


# ============================================================
# Rota de CONCILIAÇÃO – usa os dados na sessão
# ============================================================
@operacoes_bp.route("/conciliar", methods=["POST"])
@login_required
@empresa_required
def conciliar_endpoint():
    vendas = session.get("vendas", [])
    recebimentos = session.get("recebimentos", [])

    if not vendas and not recebimentos:
        return jsonify(
            {
                "ok": False,
                "message": "Nenhum dado encontrado para conciliação. Importe arquivos primeiro.",
            }
        ), 400

    resultado = conciliar(vendas, recebimentos)
    resultado["ok"] = True
    resultado["message"] = "Conciliação executada com sucesso."

    return jsonify(resultado)
