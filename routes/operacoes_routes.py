from flask import Blueprint, render_template, request, jsonify, session, g, current_app
from utils.auth_middleware import login_required, empresa_required
from services.importer import process_uploaded_files
from services.importer_db import listar_arquivos_importados, buscar_arquivo_por_id
import logging

logger = logging.getLogger(__name__)

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

    # ✅ CORREÇÃO CRÍTICA: Validar empresa_id explicitamente
    usuario = g.user
    empresa_id = getattr(usuario, 'empresa_id', None)
    usuario_id = getattr(usuario, 'id', None)
    
    # Debug log (remover após teste em produção)
    logger.info(f"DEBUG UPLOAD: usuario_id={usuario_id}, empresa_id={empresa_id}, user_obj={usuario}")
    
    if not empresa_id:
        logger.error(f"❌ Upload bloqueado: usuario_id={usuario_id} não tem empresa_id vinculado")
        return jsonify({
            "ok": False, 
            "message": "Usuário não está vinculado a uma empresa. Contate o administrador."
        }), 403

    try:
        resultados = process_uploaded_files(files, empresa_id, usuario_id)
    except Exception as e:
        logger.error(f"❌ Erro ao processar upload: {str(e)}", exc_info=True)
        return jsonify({
            "ok": False,
            "message": f"Erro interno ao processar arquivos: {str(e)}"
        }), 500

    # Calcular resumo apenas dos arquivos que foram processados com sucesso
    arquivos_sucesso = [r for r in resultados if r.get("ok")]
    
    total_arquivos = len(arquivos_sucesso)
    qtde_vendas = sum(r.get("linhas", 0) for r in arquivos_sucesso if r.get("tipo") == "venda")
    qtde_recebimentos = sum(r.get("linhas", 0) for r in arquivos_sucesso if r.get("tipo") == "recebimento")
    
    # Calcular totais em R$ (somente dos arquivos com sucesso)
    total_valor_vendas = sum(
        sum(float(reg.get('valor_bruto') or reg.get('valor') or 0) 
            for reg in r.get('registros', []))
        for r in arquivos_sucesso if r.get("tipo") == "venda"
    )
    total_valor_recebimentos = sum(
        sum(float(reg.get('valor') or 0) 
            for reg in r.get('registros', []))
        for r in arquivos_sucesso if r.get("tipo") == "recebimento"
    )

    resumo = {
        "ok": True,
        "message": "Arquivos importados, analisados e salvos com sucesso.",
        "total_arquivos": total_arquivos,
        "qtde_vendas": qtde_vendas,
        "qtde_recebimentos": qtde_recebimentos,
        "total_vendas": f"{total_valor_vendas:.2f}",
        "total_recebimentos": f"{total_valor_recebimentos:.2f}",
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
    empresa_id = g.user.empresa_id
    page = request.args.get('page', 1, type=int)
    
    arquivos = listar_arquivos_importados(empresa_id, page=page, per_page=20)
    return render_template("arquivos_importados.html", arquivos=arquivos)

# ============================================================
# Tela: Detalhamento do Arquivo
# ============================================================
@operacoes_bp.route("/arquivo/<int:arquivo_id>")
@login_required
@empresa_required
def arquivo_detalhe_page(arquivo_id):
    import json

    empresa_id = g.user.empresa_id
    arquivo = buscar_arquivo_por_id(arquivo_id, empresa_id)

    if not arquivo:
        return render_template(
            "erro.html",
            mensagem="Arquivo não encontrado ou não pertence à sua empresa."
        )

    # Converter JSON armazenado (que na verdade é texto criptografado)
    try:
        from services.importer_db import descriptografar_conteudo
        registros = descriptografar_conteudo(arquivo.get("conteudo_json"))
    except Exception as e:
        logger.error(f"Erro ao descriptografar arquivo {arquivo_id}: {str(e)}")
        registros = []

    return render_template(
        "arquivo_detalhe.html",
        arquivo=arquivo,
        registros=registros
    )

# ============================================================
# API: Executar Conciliação
# ============================================================
@operacoes_bp.route("/api/processar_conciliacao", methods=["POST"])
@login_required
@empresa_required
def conciliar_api():
    empresa_id = g.user.empresa_id
    usuario_id = g.user.id

    try:
        from services.conciliacao import executar_conciliacao

        resultado = executar_conciliacao(empresa_id, usuario_id=usuario_id)

        return jsonify({
            "ok": True,
            "message": "Conciliação executada com sucesso.",
            "resultado": resultado
        })

    except Exception as e:
        logger.error(f"Erro na conciliação: {str(e)}", exc_info=True)
        return jsonify({
            "ok": False,
            "message": "Erro ao processar conciliação."
        }), 500

# ============================================================
# Telas / API: Detalhamento
# ============================================================
@operacoes_bp.route("/detalhado", methods=["GET"])
@login_required
@empresa_required
def detalhado_page():
    return render_template("detalhado.html")

@operacoes_bp.route("/api/detalhado", methods=["GET"])
@login_required
@empresa_required
def detalhado_api():
    empresa_id = g.user.empresa_id

    try:
        from services.detalhamento_service import gerar_detalhamento
        data = gerar_detalhamento(empresa_id)

        return jsonify({"ok": True, "dados": data})

    except Exception as e:
        logger.error(f"Erro ao gerar detalhamento: {str(e)}", exc_info=True)
        return jsonify({"ok": False, "message": "Erro ao gerar relatório detalhado."}), 500
