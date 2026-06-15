# routes/operacoes_routes.py - VERSÃO FINAL CORRIGIDA

from flask import Blueprint, render_template, request, jsonify, session, g, current_app, abort, url_for
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
    
    session_token = g.get('csrf_token') or session.get('csrf_token')
    
    token_form = token_form.strip() if token_form else None
    token_header = token_header.strip() if token_header else None
    session_token = session_token.strip() if session_token else None
    
    logger.debug(f"🔍 CSRF Debug: form={'✅' if token_form else '❌'}, "
                f"header={'✅' if token_header else '❌'}, "
                f"session={'✅' if session_token else '❌'}")
    
    token = token_header or token_form
    
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
    
    # ✅ Função auxiliar para construir URLs de paginação
    def build_pagination_url(page_num):
        """Constrói URL de paginação mantendo parâmetros atuais"""
        params = request.args.to_dict()
        params['page'] = page_num
        params = {k: v for k, v in params.items() if v}
        return url_for('operacoes.arquivos_importados_page', **params)
    
    return render_template(
        "arquivos_importados.html", 
        arquivos=arquivos, 
        page=page, 
        per_page=per_page,
        build_pagination_url=build_pagination_url
    )

@operacoes_bp.route("/arquivo/<int:arquivo_id>")
@login_required
@empresa_required
def arquivo_detalhe_page(arquivo_id):
    """Página de detalhes de um arquivo importado"""
    logger.info(f"🔍 ════════════════════════════════════════════════════════════")
    logger.info(f"🔍 Acessando arquivo_id={arquivo_id} por usuario_id={g.user.id}, empresa_id={g.user.empresa_id}")
    logger.info(f"🔍 ════════════════════════════════════════════════════════════")
    
    try:
        empresa_id = g.user.empresa_id
        
        # ✅ Buscar arquivo com tratamento para objeto SQLAlchemy
        logger.info(f"🔍 Buscando arquivo {arquivo_id} no banco...")
        arquivo = buscar_arquivo_por_id(arquivo_id, empresa_id)
        
        if not arquivo:
            logger.warning(f"❌ Arquivo {arquivo_id} NÃO ENCONTRADO para empresa {empresa_id}")
            abort(404)
        
        # ✅ Normalizar acesso a atributos (objeto SQLAlchemy ou dict)
        logger.info(f"✅ Arquivo encontrado")
        
        # Helper para acessar atributos de forma segura
        def get_attr(obj, key, default=None):
            """Acessa atributo de objeto SQLAlchemy ou chave de dict"""
            if hasattr(obj, 'get'):
                return obj.get(key, default)  # É um dict
            return getattr(obj, key, default)  # É um objeto SQLAlchemy
        
        nome_arquivo = get_attr(arquivo, 'nome_arquivo', 'Desconhecido')
        tipo_arquivo = get_attr(arquivo, 'tipo', 'desconhecido')
        status_arquivo = get_attr(arquivo, 'status', 'unknown')
        conteudo_json = get_attr(arquivo, 'conteudo_json')
        total_registros = get_attr(arquivo, 'total_registros', 0)
        total_valor = get_attr(arquivo, 'total_valor', 0)
        
        logger.info(f"📄 Arquivo: {nome_arquivo} | Tipo: {tipo_arquivo} | Status: {status_arquivo}")
        
        # ✅ Descriptografar conteúdo com tratamento de erro
        registros = []
        if conteudo_json:
            try:
                logger.info(f"🔐 Tentando descriptografar conteúdo...")
                from services.importer_db import descriptografar_conteudo
                registros = descriptografar_conteudo(conteudo_json)
                logger.info(f"✅ Conteúdo descriptografado: {len(registros)} registros")
            except Exception as e:
                logger.error(f"❌ Erro ao descriptografar: {str(e)}", exc_info=True)
                flash("⚠️ Não foi possível carregar o conteúdo do arquivo.", "warning")
                registros = []
        else:
            logger.warning(f"⚠️ Arquivo {arquivo_id} não tem conteudo_json")
        
        # ✅ Calcular totais para o template
        total_entradas = Decimal("0")
        total_saidas = Decimal("0")
        
        for reg in registros:
            try:
                valor = Decimal(str(reg.get('valor', 0)))
                if valor > 0:
                    total_entradas += valor
                else:
                    total_saidas += abs(valor)
            except Exception as e:
                logger.debug(f"⚠️ Erro ao processar registro: {str(e)}")
                continue
        
        # ✅ Calcular totais por categoria
        categorias = {}
        for reg in registros:
            try:
                cat = reg.get('categoria', 'outros')
                valor = Decimal(str(reg.get('valor', 0)))
                if cat not in categorias:
                    categorias[cat] = Decimal("0")
                categorias[cat] += valor
            except:
                continue
        
        # ✅ Calcular totais por tipo_pagamento
        tipos_pagamento = {}
        for reg in registros:
            try:
                tipo = reg.get('tipo_pagamento', 'outros')
                valor = Decimal(str(reg.get('valor', 0)))
                if tipo not in tipos_pagamento:
                    tipos_pagamento[tipo] = Decimal("0")
                tipos_pagamento[tipo] += valor
            except:
                continue
        
        logger.info(f"✅ Dados calculados: {len(registros)} registros, R$ {total_entradas + total_saidas} total")
        
        # ✅ Verificar se template existe antes de renderizar
        template_name = "arquivo_detalhe.html"
        if not current_app.jinja_loader.get_source(current_app, template_name):
            logger.error(f"❌ Template {template_name} NÃO ENCONTRADO")
            return f"Erro: Template '{template_name}' não encontrado", 500
        
        logger.info(f"🎨 Renderizando template {template_name}")
        
        return render_template(
            template_name, 
            arquivo=arquivo,
            arquivo_nome=nome_arquivo,
            arquivo_tipo=tipo_arquivo,
            arquivo_status=status_arquivo,
            registros=registros,
            total_entradas=total_entradas,
            total_saidas=total_saidas,
            total_registros=len(registros),
            categorias=categorias,
            tipos_pagamento=tipos_pagamento
        )
        
    except Exception as e:
        logger.error(f"❌ ════════════════════════════════════════════════════════════")
        logger.error(f"❌ ERRO CRÍTICO ao acessar arquivo {arquivo_id}: {type(e).__name__}: {str(e)}")
        logger.error(f"❌ Traceback:", exc_info=True)
        logger.error(f"❌ ════════════════════════════════════════════════════════════")
        
        # Em produção, não mostrar detalhes do erro
        if current_app.debug:
            raise
        return render_template("errors/500.html", error_message="Erro ao carregar arquivo"), 500

@operacoes_bp.route("/api/ultimos-uploads", methods=["GET"])
@login_required
@empresa_required
def ultimos_uploads_api():
    """Retorna últimos 5 arquivos importados"""
    try:
        empresa_id = g.user.empresa_id
        resultado = listar_arquivos_importados(empresa_id, page=1, per_page=5)
        
        arquivos_lista = resultado.get("arquivos", [])
        
        uploads = []
        for a in arquivos_lista:
            data_iso = None
            created_at = a.get("created_at") or a.get("data_importacao")
            if created_at:
                try:
                    data_iso = created_at.isoformat() if hasattr(created_at, 'isoformat') else str(created_at)
                except:
                    data_iso = str(created_at)
            
            uploads.append({
                "id": a.get("id"),
                "nome": a.get("nome_arquivo") or "Desconhecido",
                "data": data_iso,
                "status": a.get("status") or "unknown",
                "total_valor": str(a.get("total_valor") or 0),
                "tipo": a.get("tipo") or a.get("tipo_arquivo") or "unknown"
            })
        
        return jsonify({"ok": True, "uploads": uploads, "timestamp": datetime.now(timezone.utc).isoformat()})
    except Exception as e:
        logger.error(f"❌ Erro API ultimos-uploads: {str(e)}", exc_info=True)
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
