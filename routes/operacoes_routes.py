# routes/operacoes_routes.py - VERSÃO FINAL CORRIGIDA

from flask import Blueprint, render_template, request, jsonify, session, g, current_app, abort
from utils.auth_middleware import login_required, empresa_required
from services.importer import process_uploaded_files
from services.importer_db import listar_arquivos_importados, buscar_arquivo_por_id
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import logging
import time

logger = logging.getLogger(__name__)

operacoes_bp = Blueprint("operacoes", __name__, url_prefix="/operacoes")

# ============================================================
# CONFIGURAÇÕES
# ============================================================
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
ALLOWED_EXTENSIONS = {'.csv', '.txt', '.xlsx', '.xls', '.ofx'}
RATE_LIMIT_WINDOW = 60
RATE_LIMIT_MAX_UPLOADS = 5

_upload_rate_limit_cache = {}

def check_upload_rate_limit(user_id: str) -> bool:
    now = time.time()
    key = f"upload:{user_id}"
    _upload_rate_limit_cache[key] = [t for t in _upload_rate_limit_cache.get(key, []) if now - t < RATE_LIMIT_WINDOW]
    if len(_upload_rate_limit_cache.get(key, [])) >= RATE_LIMIT_MAX_UPLOADS:
        return False
    _upload_rate_limit_cache.setdefault(key, []).append(now)
    return True

def allowed_file(filename: str) -> bool:
    return any(filename.lower().endswith(ext) for ext in ALLOWED_EXTENSIONS)

def validar_csrf_token():
    """Valida token CSRF manualmente para formulários e AJAX"""
    token_form = request.form.get('csrf_token')
    token_header = request.headers.get('X-CSRF-Token')
    
    # ✅ SEGURO: Usar apenas session (não cookie)
    session_token = g.get('csrf_token') or session.get('csrf_token')
    
    # Normalizar
    token_form = token_form.strip() if token_form else None
    token_header = token_header.strip() if token_header else None
    session_token = session_token.strip() if session_token else None
    
    logger.debug(f"🔍 CSRF Debug: form={'✅' if token_form else '❌'}, "
                f"header={'✅' if token_header else '❌'}, "
                f"session={'✅' if session_token else '❌'}")
    
    # Token enviado: priorizar header (AJAX) sobre form
    token = token_header or token_form
    
    # Validações
    if not token:
        logger.warning("❌ CSRF token ausente (nem form nem header)")
        return False
    if not session_token:
        logger.warning("❌ CSRF token de sessão ausente")
        return False
    if token != session_token:
        logger.warning(f"❌ CSRF token mismatch: enviado={token[:20]}... vs sessão={session_token[:20]}...")
        return False
    
    logger.debug("✅ CSRF token válido")
    return True

# ============================================================
# ROTAS
# ============================================================

@operacoes_bp.route("/importar", methods=["GET"])
@login_required
@empresa_required
def importar_page():
    return render_template("importar.html", allowed_extensions=ALLOWED_EXTENSIONS, max_file_size_mb=MAX_FILE_SIZE // (1024 * 1024))

@operacoes_bp.route("/upload", methods=["POST"])
@login_required
@empresa_required
def upload_arquivos():
    if not check_upload_rate_limit(str(g.user.id)):
        return jsonify({"ok": False, "message": "Muitos uploads. Aguarde alguns segundos."}), 429
    
    if not validar_csrf_token():
        logger.warning(f"❌ CSRF falhou para usuario={g.user.id if hasattr(g, 'user') else 'anon'}")
        return jsonify({
            "ok": False,
            "message": "Erro de segurança. Recarregue a página."
        }), 403
    
    files = request.files.getlist("files")
    
    if not files or all(f.filename == '' for f in files):
        logger.warning(f"⚠️ Upload recebido sem arquivos: files={files}")
        return jsonify({"ok": False, "message": "Nenhum arquivo válido enviado."}), 400

    usuario = g.user
    empresa_id = getattr(usuario, 'empresa_id', None)
    usuario_id = getattr(usuario, 'id', None)
    
    if not empresa_id:
        logger.error(f"❌ Upload bloqueado: usuario_id={usuario_id} sem empresa_id")
        return jsonify({"ok": False, "message": "Usuário não vinculado a uma empresa."}), 403

    # Validar arquivos
    for file in files:
        if file.filename and not allowed_file(file.filename):
            return jsonify({"ok": False, "message": f"Arquivo '{file.filename}' não permitido. Extensões: {', '.join(ALLOWED_EXTENSIONS)}"}), 400
        file.seek(0, 2)
        size = file.tell()
        file.seek(0)
        if size > MAX_FILE_SIZE:
            return jsonify({"ok": False, "message": f"Arquivo '{file.filename}' excede 10MB"}), 400

    try:
        resultados = process_uploaded_files(files, empresa_id, usuario_id)
    except Exception as e:
        logger.error(f"❌ Erro ao processar upload: {str(e)}", exc_info=True)
        return jsonify({"ok": False, "message": f"Erro interno: {str(e)}"}), 500

    # Resumo
    arquivos_sucesso = [r for r in resultados if r.get("ok")]
    total_arquivos = len(arquivos_sucesso)
    qtde_vendas = sum(r.get("linhas", 0) for r in arquivos_sucesso if r.get("tipo") == "venda")
    qtde_recebimentos = sum(r.get("linhas", 0) for r in arquivos_sucesso if r.get("tipo") == "recebimento")
    
    total_valor_vendas = Decimal("0")
    total_valor_recebimentos = Decimal("0")
    
    for r in arquivos_sucesso:
        if r.get("tipo") == "venda":
            for reg in r.get('registros', []):
                try:
                    valor = reg.get('valor_bruto') or reg.get('valor') or 0
                    total_valor_vendas += Decimal(str(valor))
                except: pass
        elif r.get("tipo") == "recebimento":
            for reg in r.get('registros', []):
                try:
                    valor = reg.get('valor') or 0
                    total_valor_recebimentos += Decimal(str(valor))
                except: pass

    return jsonify({
        "ok": True,
        "message": "Arquivos processados com sucesso.",
        "total_arquivos": total_arquivos,
        "qtde_vendas": qtde_vendas,
        "qtde_recebimentos": qtde_recebimentos,
        "total_vendas": str(total_valor_vendas),
        "total_recebimentos": str(total_valor_recebimentos),
        "result": resultados
    })

@operacoes_bp.route("/conciliacao", methods=["GET"])
@login_required
@empresa_required
def conciliar_page():
    return render_template("conciliacao.html")

@operacoes_bp.route("/arquivos", methods=["GET"])
@login_required
@empresa_required
def arquivos_importados_page():
    empresa_id = g.user.empresa_id
    page = max(1, request.args.get('page', 1, type=int))
    per_page = min(request.args.get('per_page', 20, type=int), 100)
    
    arquivos = listar_arquivos_importados(empresa_id, page=page, per_page=per_page)
    
    return render_template("arquivos_importados.html", arquivos=arquivos, page=page, per_page=per_page)

@operacoes_bp.route("/arquivo/<int:arquivo_id>")
@login_required
@empresa_required
def arquivo_detalhe_page(arquivo_id):
    empresa_id = g.user.empresa_id
    arquivo = buscar_arquivo_por_id(arquivo_id, empresa_id)
    if not arquivo:
        abort(404)
    try:
        from services.importer_db import descriptografar_conteudo
        registros = descriptografar_conteudo(arquivo.get("conteudo_json"))
    except Exception as e:
        logger.error(f"Erro ao descriptografar: {str(e)}")
        registros = []
    return render_template("arquivo_detalhe.html", arquivo=arquivo, registros=registros)

# ❌ REMOVIDO: Rota duplicada /api/processar_conciliacao
# ✅ Use /api/v1/conciliacao/processar do conciliacao_api.py

@operacoes_bp.route("/api/ultimos-uploads", methods=["GET"])
@login_required
@empresa_required
def ultimos_uploads_api():
    """Retorna últimos 5 arquivos importados"""
    try:
        empresa_id = g.user.empresa_id
        arquivos = listar_arquivos_importados(empresa_id, page=1, per_page=5)
        
        uploads = []
        for a in arquivos:
            data_iso = None
            if a.get("data_importacao"):
                try:
                    data_iso = a["data_importacao"].isoformat() if hasattr(a["data_importacao"], 'isoformat') else str(a["data_importacao"])
                except:
                    data_iso = str(a["data_importacao"])
            
            uploads.append({
                "id": a.get("id"),
                "nome": a.get("nome_arquivo") or "Desconhecido",
                "data": data_iso,
                "status": a.get("status") or "unknown",
                "total_valor": str(a.get("total_valor") or 0),
                "tipo": a.get("tipo_arquivo") or a.get("tipo") or "unknown"
            })
        
        return jsonify({"ok": True, "uploads": uploads, "timestamp": datetime.now(timezone.utc).isoformat()})
    except Exception as e:
        logger.error(f"❌ Erro API ultimos-uploads: {str(e)}")
        return jsonify({"ok": False, "error": "Erro ao carregar uploads"}), 500

@operacoes_bp.route("/detalhado", methods=["GET"])
@login_required
@empresa_required
def detalhado_page():
    return render_template("detalhado.html", tipos_pagamento=["todos", "cartao", "pix", "boleto", "outros"])

@operacoes_bp.route("/api/detalhado", methods=["GET"])
@login_required
@empresa_required
def detalhado_api():
    empresa_id = g.user.empresa_id
    page = max(1, request.args.get('page', 1, type=int))
    per_page = min(request.args.get('per_page', 50, type=int), 100)
    status = request.args.get('status')
    tipo_pagamento = request.args.get('tipo_pagamento')
    data_inicio = request.args.get('data_inicio')
    data_fim = request.args.get('data_fim')

    try:
        from services.detalhamento_service import gerar_detalhamento
        data = gerar_detalhamento(empresa_id, page=page, per_page=per_page, status=status, tipo_pagamento=tipo_pagamento, data_inicio=data_inicio, data_fim=data_fim)
        return jsonify({"ok": True, "dados": data, "timestamp": datetime.now(timezone.utc).isoformat()})
    except Exception as e:
        logger.error(f"❌ Erro ao gerar detalhamento: {str(e)}", exc_info=True)
        return jsonify({"ok": False, "message": "Erro ao gerar relatório."}), 500
