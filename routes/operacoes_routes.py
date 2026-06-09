# routes/operacoes_routes.py - VERSÃO CORRIGIDA E COMPLETA

from flask import Blueprint, render_template, request, jsonify, session, g, current_app, abort
from utils.auth_middleware import login_required, empresa_required
from services.importer import process_uploaded_files
from services.importer_db import listar_arquivos_importados, buscar_arquivo_por_id
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import logging
import re
import time

logger = logging.getLogger(__name__)

operacoes_bp = Blueprint("operacoes", __name__, url_prefix="/operacoes")

# ============================================================
# CONFIGURAÇÕES DE SEGURANÇA
# ============================================================
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB por arquivo
ALLOWED_EXTENSIONS = {'.csv', '.txt', '.xlsx', '.xls', '.ofx'}
RATE_LIMIT_WINDOW = 60  # segundos
RATE_LIMIT_MAX_UPLOADS = 5  # uploads por minuto por usuário

_upload_rate_limit_cache = {}

def check_upload_rate_limit(user_id: str) -> bool:
    """Verifica rate limiting para uploads"""
    now = time.time()
    key = f"upload:{user_id}"
    
    _upload_rate_limit_cache[key] = [
        t for t in _upload_rate_limit_cache.get(key, [])
        if now - t < RATE_LIMIT_WINDOW
    ]
    
    if len(_upload_rate_limit_cache.get(key, [])) >= RATE_LIMIT_MAX_UPLOADS:
        return False
    
    _upload_rate_limit_cache.setdefault(key, []).append(now)
    return True

def allowed_file(filename: str) -> bool:
    """Verifica se a extensão do arquivo é permitida"""
    return any(filename.lower().endswith(ext) for ext in ALLOWED_EXTENSIONS)

def validar_csrf_token():
    """Valida token CSRF manualmente para formulários"""
    token_form = request.form.get('csrf_token')
    token_header = request.headers.get('X-CSRF-Token')
    session_token = g.get('csrf_token')
    
    token = token_form or token_header
    if not token or not session_token or token != session_token:
        logger.warning("CSRF token inválido ou ausente")
        return False
    return True

# ============================================================
# Tela de IMPORTAÇÃO (GET)
# ============================================================
@operacoes_bp.route("/importar", methods=["GET"])
@login_required
@empresa_required
def importar_page():
    return render_template(
        "importar.html",
        allowed_extensions=ALLOWED_EXTENSIONS,
        max_file_size_mb=MAX_FILE_SIZE // (1024 * 1024)
    )

# ============================================================
# Upload com salvamento no banco (CORRIGIDO)
# ============================================================
@operacoes_bp.route("/upload", methods=["POST"])
@login_required
@empresa_required
def upload_arquivos():
    # ✅ Rate limiting
    if not check_upload_rate_limit(str(g.user.id)):
        return jsonify({
            "ok": False, 
            "message": "Muitos uploads. Aguarde alguns segundos antes de tentar novamente."
        }), 429
    
    # ✅ Validar CSRF
    if not validar_csrf_token():
        return jsonify({
            "ok": False,
            "message": "Erro de segurança. Recarregue a página."
        }), 403
    
    files = request.files.getlist("files")
    if not files:
        return jsonify({"ok": False, "message": "Nenhum arquivo enviado."}), 400

    # ✅ Validar empresa_id explicitamente
    usuario = g.user
    empresa_id = getattr(usuario, 'empresa_id', None)
    usuario_id = getattr(usuario, 'id', None)
    
    if not empresa_id:
        logger.error(f"❌ Upload bloqueado: usuario_id={usuario_id} não tem empresa_id vinculado")
        return jsonify({
            "ok": False, 
            "message": "Usuário não está vinculado a uma empresa. Contate o administrador."
        }), 403

    # ✅ Validar arquivos antes de processar
    for file in files:
        if file.filename and not allowed_file(file.filename):
            return jsonify({
                "ok": False,
                "message": f"Arquivo '{file.filename}' não é permitido. Extensões aceitas: {', '.join(ALLOWED_EXTENSIONS)}"
            }), 400
        
        # Verificar tamanho
        file.seek(0, 2)
        size = file.tell()
        file.seek(0)
        if size > MAX_FILE_SIZE:
            return jsonify({
                "ok": False,
                "message": f"Arquivo '{file.filename}' excede {MAX_FILE_SIZE // (1024*1024)}MB"
            }), 400

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
    
    # ✅ CORREÇÃO: Usar Decimal para precisão monetária
    total_valor_vendas = Decimal("0")
    total_valor_recebimentos = Decimal("0")
    
    for r in arquivos_sucesso:
        if r.get("tipo") == "venda":
            for reg in r.get('registros', []):
                try:
                    valor = reg.get('valor_bruto') or reg.get('valor') or 0
                    total_valor_vendas += Decimal(str(valor))
                except (InvalidOperation, ValueError, TypeError):
                    pass
        elif r.get("tipo") == "recebimento":
            for reg in r.get('registros', []):
                try:
                    valor = reg.get('valor') or 0
                    total_valor_recebimentos += Decimal(str(valor))
                except (InvalidOperation, ValueError, TypeError):
                    pass

    resumo = {
        "ok": True,
        "message": "Arquivos importados, analisados e salvos com sucesso.",
        "total_arquivos": total_arquivos,
        "qtde_vendas": qtde_vendas,
        "qtde_recebimentos": qtde_recebimentos,
        "total_vendas": str(total_valor_vendas),  # ✅ String para precisão
        "total_recebimentos": str(total_valor_recebimentos),
        "result": resultados
    }

    logger.info(f"✅ Upload concluído: usuario={usuario_id}, empresa={empresa_id}, arquivos={total_arquivos}")
    
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
# Tela: Arquivos Importados (COM BUSCA E FILTROS)
# ============================================================
@operacoes_bp.route("/arquivos", methods=["GET"])
@login_required
@empresa_required
def arquivos_importados_page():
    empresa_id = g.user.empresa_id
    page = max(1, request.args.get('page', 1, type=int))
    per_page = min(request.args.get('per_page', 20, type=int), 100)
    search = request.args.get('search', '').strip()
    tipo = request.args.get('tipo', '').strip()  # 'venda' ou 'recebimento'
    
    arquivos = listar_arquivos_importados(
        empresa_id, 
        page=page, 
        per_page=per_page
    )
    
    return render_template(
        "arquivos_importados.html", 
        arquivos=arquivos,
        page=page,
        per_page=per_page
    )

# ============================================================
# Tela: Detalhamento do Arquivo
# ============================================================
@operacoes_bp.route("/arquivo/<int:arquivo_id>")
@login_required
@empresa_required
def arquivo_detalhe_page(arquivo_id):
    empresa_id = g.user.empresa_id
    arquivo = buscar_arquivo_por_id(arquivo_id, empresa_id)

    if not arquivo:
        abort(404)  # Ou renderizar template de erro amigável

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
# API: Executar Conciliação (CORRIGIDO)
# ============================================================
@operacoes_bp.route("/api/processar_conciliacao", methods=["POST"])
@login_required
@empresa_required
def conciliar_api():
    # ✅ Validar CSRF para API
    if not validar_csrf_token():
        return jsonify({
            "ok": False,
            "message": "Erro de segurança"
        }), 403
    
    empresa_id = g.user.empresa_id
    usuario_id = g.user.id
    
    # ✅ Obter parâmetros opcionais do JSON body
    data = request.get_json(silent=True) or {}
    tipo_pagamento = data.get('tipo_pagamento')  # 'pix', 'cartao', 'boleto', ou None

    try:
        # ✅ Import no topo do arquivo (melhor prática)
        from services.concilia import executar_conciliacao

        resultado = executar_conciliacao(
            empresa_id, 
            usuario_id=usuario_id,
            tipo_pagamento=tipo_pagamento  # ✅ Suporte a filtro por tipo
        )

        logger.info(f"✅ Conciliação executada: empresa={empresa_id}, tipo={tipo_pagamento or 'todos'}")

        return jsonify({
            "ok": True,
            "message": "Conciliação executada com sucesso.",
            "resultado": resultado,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })

    except Exception as e:
        logger.error(f"❌ Erro na conciliação: {str(e)}", exc_info=True)
        return jsonify({
            "ok": False,
            "message": "Erro ao processar conciliação. Tente novamente."
        }), 500

# ============================================================
# Telas / API: Detalhamento (COM PAGINAÇÃO E FILTROS)
# ============================================================
@operacoes_bp.route("/detalhado", methods=["GET"])
@login_required
@empresa_required
def detalhado_page():
    # Passar parâmetros de filtro para o template
    return render_template(
        "detalhado.html",
        tipos_pagamento=["todos", "cartao", "pix", "boleto", "outros"]
    )

@operacoes_bp.route("/api/detalhado", methods=["GET"])
@login_required
@empresa_required
def detalhado_api():
    empresa_id = g.user.empresa_id
    
    # ✅ Parâmetros de paginação e filtro
    page = max(1, request.args.get('page', 1, type=int))
    per_page = min(request.args.get('per_page', 50, type=int), 100)
    status = request.args.get('status')
    tipo_pagamento = request.args.get('tipo_pagamento')
    data_inicio = request.args.get('data_inicio')
    data_fim = request.args.get('data_fim')

    try:
        from services.detalhamento_service import gerar_detalhamento
        
        data = gerar_detalhamento(
            empresa_id,
            page=page,
            per_page=per_page,
            status=status,
            tipo_pagamento=tipo_pagamento,
            data_inicio=data_inicio,
            data_fim=data_fim
        )

        return jsonify({
            "ok": True, 
            "dados": data,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })

    except Exception as e:
        logger.error(f"❌ Erro ao gerar detalhamento: {str(e)}", exc_info=True)
        return jsonify({
            "ok": False, 
            "message": "Erro ao gerar relatório detalhado."
        }), 500

# routes/operacoes_routes.py - Adicionar esta nova rota

@operacoes_bp.route("/api/ultimos-uploads", methods=["GET"])
@login_required
@empresa_required
def ultimos_uploads_api():
    """Retorna últimos arquivos importados para a empresa"""
    from services.importer_db import listar_arquivos_importados
    
    empresa_id = g.user.empresa_id
    arquivos = listar_arquivos_importados(empresa_id, page=1, per_page=5)
    
    return jsonify({
        "ok": True,
        "uploads": [
            {
                "id": a["id"],
                "nome": a["nome_arquivo"],
                "data": a["data_importacao"].isoformat() if a.get("data_importacao") else None,
                "status": a["status"],
                "total_valor": str(a.get("total_valor", 0))
            }
            for a in arquivos
        ]
    })
