# routes/empresas_routes.py - VERSÃO COMPLETA E CORRIGIDA

from flask import Blueprint, render_template, request, redirect, url_for, flash, g, abort, jsonify
from models import db, Empresa, Usuario, LogAuditoria
from utils.auth_middleware import master_required
from datetime import datetime, timezone
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy import or_, func
import logging
import re
import time
import os
import secrets
import requests  # Para consulta BrasilAPI

logger = logging.getLogger(__name__)

empresas_bp = Blueprint("empresas", __name__, url_prefix="/empresas")

# ============================================================
# CONFIGURAÇÕES DE SEGURANÇA
# ============================================================
RATE_LIMIT_WINDOW = 60  # segundos
RATE_LIMIT_MAX_REQUESTS = 20  # por minuto para endpoints admin
_admin_rate_limit_cache = {}

def check_admin_rate_limit(user_id: str, endpoint: str) -> bool:
    """Verifica rate limiting para endpoints administrativos"""
    now = time.time()
    key = f"admin:{user_id}:{endpoint}"
    
    _admin_rate_limit_cache[key] = [
        t for t in _admin_rate_limit_cache.get(key, [])
        if now - t < RATE_LIMIT_WINDOW
    ]
    
    if len(_admin_rate_limit_cache.get(key, [])) >= RATE_LIMIT_MAX_REQUESTS:
        return False
    
    _admin_rate_limit_cache.setdefault(key, []).append(now)
    return True

# ============================================================
# VALIDAÇÕES
# ============================================================
def validar_cnpj(cnpj: str) -> bool:
    """
    Valida CNPJ brasileiro com dígitos verificadores.
    Retorna True se válido ou vazio (opcional).
    """
    if not cnpj:
        return True  # Campo opcional
    
    # Remover caracteres não numéricos
    cnpj = re.sub(r'\D', '', cnpj)
    
    if len(cnpj) != 14:
        return False
    
    # Verificar sequências inválidas (ex: 11111111111111)
    if cnpj == cnpj[0] * 14:
        return False
    
    # Calcular primeiro dígito verificador
    pesos_1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    soma_1 = sum(int(cnpj[i]) * pesos_1[i] for i in range(12))
    digito_1 = 11 - (soma_1 % 11)
    digito_1 = 0 if digito_1 >= 10 else digito_1
    
    # Calcular segundo dígito verificador
    pesos_2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    soma_2 = sum(int(cnpj[i]) * pesos_2[i] for i in range(13))
    digito_2 = 11 - (soma_2 % 11)
    digito_2 = 0 if digito_2 >= 10 else digito_2
    
    # Validar dígitos calculados
    return int(cnpj[12]) == digito_1 and int(cnpj[13]) == digito_2

def validar_csrf_token():
    """Valida token CSRF manualmente para formulários e APIs"""
    token_form = request.form.get('csrf_token')
    token_header = request.headers.get('X-CSRF-Token')
    session_token = g.get('csrf_token')
    
    token = token_form or token_header
    if not token or not session_token or token != session_token:
        logger.warning("CSRF token inválido ou ausente")
        return False
    return True

def log_acao_empresa(acao: str, empresa, detalhes_extra: str = ""):
    """
    Log centralizado para ações em empresas.
    ⚠️ Não commita - deve ser commitado junto com a transação principal.
    """
    try:
        log = LogAuditoria(
            usuario_id=g.user.id,
            empresa_id=empresa.id if empresa else None,
            acao=acao,
            detalhes=f"Nome: {empresa.nome if empresa else 'N/A'}, {detalhes_extra}",
            ip=request.remote_addr,
            criado_em=datetime.now(timezone.utc)
        )
        db.session.add(log)
        # NÃO commitar aqui - deixar para a transação principal
    except Exception as e:
        logger.error(f"Erro ao preparar log de auditoria: {str(e)}")
        # Não falhar a operação principal por erro de log

# ============================================================
# HELPER: CALCULAR ESTATÍSTICAS DA EMPRESA
# ============================================================
def calcular_stats_empresa(empresa):
    """Calcula estatísticas úteis para exibição no template"""
    try:
        # Importar modelos apenas se necessário (evitar circular import)
        from models import MovAdquirente
        
        return {
            "total_usuarios": Usuario.query.filter_by(empresa_id=empresa.id).count(),
            "total_vendas": MovAdquirente.query.filter_by(empresa_id=empresa.id).count(),
            "total_valor_vendas": db.session.query(func.sum(MovAdquirente.valor))
                .filter_by(empresa_id=empresa.id)
                .scalar() or 0
        }
    except ImportError:
        # Fallback se modelo não estiver disponível
        return {
            "total_usuarios": Usuario.query.filter_by(empresa_id=empresa.id).count(),
            "total_vendas": 0,
            "total_valor_vendas": 0
        }

# ============================================================
# LISTAR EMPRESAS (COM BUSCA E ORDENAÇÃO)
# ============================================================
@empresas_bp.route("/")
@master_required
def listar_empresas():
    # ✅ Rate limiting
    if not check_admin_rate_limit(str(g.user.id), "listar_empresas"):
        flash("Muitas requisições. Aguarde alguns segundos.", "warning")
        return redirect(url_for("empresas.listar_empresas"))
    
    # Parâmetros de paginação, busca e ordenação
    page = max(1, request.args.get('page', 1, type=int))
    per_page = min(request.args.get('per_page', 20, type=int), 100)
    search = request.args.get('search', '').strip()
    order_by = request.args.get('order_by', 'criado_em')
    order_dir = request.args.get('order_dir', 'desc')
    
    # Query base
    query = Empresa.query
    
    # ✅ Aplicar busca por nome ou documento
    if search:
        query = query.filter(
            or_(
                Empresa.nome.ilike(f"%{search}%"),
                Empresa.documento.ilike(f"%{search}%")
            )
        )
    
    # ✅ Aplicar ordenação
    order_column = getattr(Empresa, order_by, Empresa.criado_em)
    if order_dir == 'desc':
        query = query.order_by(order_column.desc())
    else:
        query = query.order_by(order_column.asc())
    
    # Paginar
    empresas = query.paginate(page=page, per_page=per_page, error_out=False)
    
    return render_template(
        "empresas_listar.html", 
        empresas=empresas,
        search=search,
        order_by=order_by,
        order_dir=order_dir,
        page=page,
        per_page=per_page
    )

# ============================================================
# NOVA EMPRESA (CORRIGIDO: contexto completo para o template)
# ============================================================
@empresas_bp.route("/nova", methods=["GET", "POST"])
@master_required
def nova_empresa():
    # ✅ Rate limiting
    if not check_admin_rate_limit(str(g.user.id), "nova_empresa"):
        flash("Muitas tentativas. Aguarde.", "warning")
        return redirect(url_for("empresas.nova_empresa"))
    
    if request.method == "GET":
        # ✅ Passar contexto completo: erros vazio, stats None (nova empresa)
        return render_template(
            "empresas_form.html", 
            empresa=None,
            erros={},  # ✅ Sempre passar dict, mesmo vazio
            stats=None  # ✅ Nova empresa não tem estatísticas
        )
    
    # ✅ Validar CSRF
    if not validar_csrf_token():
        flash("Erro de segurança. Recarregue a página.", "error")
        return redirect(url_for("empresas.nova_empresa"))
    
    # Coletar e sanitizar dados
    nome = (request.form.get("nome") or "").strip()
    documento = (request.form.get("documento") or "").strip().replace('.', '').replace('-', '').replace('/', '')
    
    # ✅ Preparar dict de erros para o template
    erros = {}
    
    # Validações
    if not nome or len(nome) > 150:
        erros['nome'] = "Nome deve ter entre 1 e 150 caracteres"
        flash(erros['nome'], "error")
        return render_template("empresas_form.html", empresa=None, erros=erros, stats=None)
    
    if documento:
        if len(documento) > 14:
            erros['documento'] = "Documento muito longo"
            flash(erros['documento'], "error")
            return render_template("empresas_form.html", empresa=None, erros=erros, stats=None)
        if not validar_cnpj(documento):
            erros['documento'] = "CNPJ inválido"
            flash(erros['documento'], "error")
            return render_template("empresas_form.html", empresa=None, erros=erros, stats=None)
        
        # Verificar duplicidade
        if Empresa.query.filter_by(documento=documento).first():
            erros['documento'] = "Documento já cadastrado em outra empresa"
            flash(erros['documento'], "error")
            return render_template("empresas_form.html", empresa=None, erros=erros, stats=None)
    
    try:
        empresa = Empresa(
            nome=nome,
            documento=documento,
            ativo=True,
            criado_em=datetime.now(timezone.utc)
        )
        db.session.add(empresa)
        
        # Log de auditoria (mesma transação)
        log_acao_empresa("master_criou_empresa", empresa)
        
        db.session.commit()
        
        flash("Empresa criada com sucesso", "success")
        logger.info(f"✅ Master criou empresa: {nome} (id={empresa.id})")
        
        return redirect(url_for("empresas.listar_empresas"))
        
    except IntegrityError as e:
        db.session.rollback()
        logger.error(f"⚠️ Erro de integridade ao criar empresa: {str(e)}")
        erros['documento'] = "Erro: documento já existe"
        flash(erros['documento'], "error")
        return render_template("empresas_form.html", empresa=None, erros=erros, stats=None)
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error(f"❌ Erro de banco ao criar empresa: {str(e)}")
        flash("Erro interno. Tente novamente.", "error")
        return render_template("empresas_form.html", empresa=None, erros=erros, stats=None)

# ============================================================
# EDITAR EMPRESA (CORRIGIDO: contexto completo + stats calculados)
# ============================================================
@empresas_bp.route("/<int:empresa_id>/editar", methods=["GET", "POST"])
@master_required
def editar_empresa(empresa_id):
    # ✅ Rate limiting
    if not check_admin_rate_limit(str(g.user.id), "editar_empresa"):
        flash("Muitas tentativas. Aguarde.", "warning")
        return redirect(url_for("empresas.listar_empresas"))
    
    empresa = Empresa.query.get_or_404(empresa_id)
    
    if request.method == "GET":
        # ✅ Passar contexto completo: empresa, erros vazio, stats calculados
        return render_template(
            "empresas_form.html", 
            empresa=empresa,
            erros={},  # ✅ Sempre passar dict, mesmo vazio
            stats=calcular_stats_empresa(empresa)  # ✅ Estatísticas calculadas
        )
    
    # ✅ Validar CSRF
    if not validar_csrf_token():
        flash("Erro de segurança. Recarregue a página.", "error")
        return redirect(url_for("empresas.editar_empresa", empresa_id=empresa_id))
    
    # Coletar e sanitizar dados
    nome = (request.form.get("nome") or "").strip()
    documento = (request.form.get("documento") or "").strip().replace('.', '').replace('-', '').replace('/', '')
    ativa = request.form.get("ativa") == "on"
    
    # ✅ Preparar dict de erros para o template
    erros = {}
    
    # Validações
    if not nome or len(nome) > 150:
        erros['nome'] = "Nome deve ter entre 1 e 150 caracteres"
        flash(erros['nome'], "error")
        return render_template("empresas_form.html", empresa=empresa, erros=erros, stats=calcular_stats_empresa(empresa))
    
    if documento:
        if len(documento) > 14:
            erros['documento'] = "Documento muito longo"
            flash(erros['documento'], "error")
            return render_template("empresas_form.html", empresa=empresa, erros=erros, stats=calcular_stats_empresa(empresa))
        if not validar_cnpj(documento):
            erros['documento'] = "CNPJ inválido"
            flash(erros['documento'], "error")
            return render_template("empresas_form.html", empresa=empresa, erros=erros, stats=calcular_stats_empresa(empresa))
        
        # Verificar duplicidade (excluindo esta empresa)
        existente = Empresa.query.filter(
            Empresa.documento == documento,
            Empresa.id != empresa_id
        ).first()
        if existente:
            erros['documento'] = "Documento já cadastrado em outra empresa"
            flash(erros['documento'], "error")
            return render_template("empresas_form.html", empresa=empresa, erros=erros, stats=calcular_stats_empresa(empresa))
    
    # ✅ Verificar desativação com confirmação explícita
    if not ativa and empresa.ativo:
        confirmar_desativacao = request.form.get("confirmar_desativacao")
        if confirmar_desativacao != "sim":
            usuarios_ativos = Usuario.query.filter_by(empresa_id=empresa_id, ativo=True).count()
            flash(f"⚠️ Para desativar, marque 'Confirmar desativação'. {usuarios_ativos} usuários serão afetados.", "warning")
            return render_template(
                "empresas_form.html", 
                empresa=empresa, 
                erros=erros, 
                stats=calcular_stats_empresa(empresa),
                requer_confirmacao=True
            )
    
    try:
        # Atualizar campos
        empresa.nome = nome
        empresa.documento = documento or None
        empresa.ativo = ativa
        empresa.atualizado_em = datetime.now(timezone.utc)
        
        # Log de auditoria (mesma transação)
        log_acao_empresa("master_editou_empresa", empresa, f"Ativa: {ativa}")
        
        db.session.commit()
        
        flash("Empresa atualizada com sucesso", "success")
        logger.info(f"✅ Master editou empresa: {empresa_id}")
        
        return redirect(url_for("empresas.listar_empresas"))
        
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error(f"❌ Erro ao editar empresa {empresa_id}: {str(e)}")
        flash("Erro ao atualizar empresa", "error")
        return render_template("empresas_form.html", empresa=empresa, erros=erros, stats=calcular_stats_empresa(empresa))

# ============================================================
# EXCLUIR EMPRESA (SOFT DELETE COM CONFIRMAÇÃO)
# ============================================================
@empresas_bp.route("/<int:empresa_id>/excluir", methods=["POST"])
@master_required
def excluir_empresa(empresa_id):
    # ✅ Rate limiting
    if not check_admin_rate_limit(str(g.user.id), "excluir_empresa"):
        flash("Muitas tentativas. Aguarde.", "warning")
        return redirect(url_for("empresas.listar_empresas"))
    
    # ✅ Validar CSRF
    if not validar_csrf_token():
        flash("Erro de segurança", "error")
        return redirect(url_for("empresas.listar_empresas"))
    
    empresa = Empresa.query.get_or_404(empresa_id)
    
    # ✅ Verificar confirmação explícita para exclusão
    confirmar = request.form.get("confirmar_exclusao")
    if confirmar != "sim":
        flash("Para excluir, confirme digitando 'sim' no campo de confirmação", "warning")
        return redirect(url_for("empresas.editar_empresa", empresa_id=empresa_id))
    
    try:
        # ✅ Soft delete: marcar como inativo + registrar exclusão
        empresa.ativo = False
        empresa.excluido_em = datetime.now(timezone.utc)
        empresa.excluido_por = g.user.id
        
        # Log de auditoria
        log_acao_empresa("master_excluiu_empresa", empresa, "Soft delete")
        
        db.session.commit()
        
        flash("Empresa excluída com sucesso", "success")
        logger.info(f"✅ Master excluiu empresa: {empresa_id}")
        
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error(f"❌ Erro ao excluir empresa {empresa_id}: {str(e)}")
        flash("Erro ao excluir empresa", "error")
    
    return redirect(url_for("empresas.listar_empresas"))

# ============================================================
# ✅ DETALHES DA EMPRESA (CORRIGIDO: endpoint bate com template)
# ============================================================
@empresas_bp.route("/<int:empresa_id>", endpoint="empresa_detalhe")
@master_required
def empresa_detalhe(empresa_id):
    """Página de detalhe de uma empresa específica"""
    empresa = Empresa.query.get_or_404(empresa_id)
    
    # Contagens úteis para auditoria
    total_usuarios = Usuario.query.filter_by(empresa_id=empresa_id).count()
    usuarios_ativos = Usuario.query.filter_by(empresa_id=empresa_id, ativo=True).count()
    
    # Buscar logs recentes desta empresa
    logs_recentes = LogAuditoria.query.filter_by(empresa_id=empresa_id)\
        .order_by(LogAuditoria.criado_em.desc())\
        .limit(10).all()
    
    return render_template(
        "empresas_detalhes.html",
        empresa=empresa,
        total_usuarios=total_usuarios,
        usuarios_ativos=usuarios_ativos,
        logs_recentes=logs_recentes
    )

# ============================================================
# ✅ API: CONSULTAR CNPJ VIA BRASILAPI (NOVA)
# ============================================================
@empresas_bp.route("/api/consultar-cnpj", methods=["POST"])
@master_required
def api_consultar_cnpj():
    """
    API para consultar dados de empresa via CNPJ usando BrasilAPI (gratuito).
    
    Request JSON:
    { "cnpj": "00.000.000/0001-91" }
    
    Response JSON:
    {
        "ok": true,
        "dados": {
            "razao_social": "...",
            "nome_fantasia": "...",
            "logradouro": "...",
            ...
        }
    }
    """
    # ✅ Validar CSRF para API
    if not validar_csrf_token():
        return jsonify({"ok": False, "message": "Erro de segurança"}), 403
    
    data = request.get_json(silent=True) or {}
    cnpj = data.get('cnpj', '').strip()
    
    if not cnpj:
        return jsonify({"ok": False, "message": "CNPJ não informado"}), 400
    
    # Limpar CNPJ (só números)
    cnpj_limpo = re.sub(r'\D', '', cnpj)
    
    if len(cnpj_limpo) != 14:
        return jsonify({"ok": False, "message": "CNPJ deve ter 14 dígitos"}), 400
    
    try:
        # Consultar BrasilAPI (gratuito, sem autenticação)
        url = f"https://brasilapi.com.br/api/cnpj/v1/{cnpj_limpo}"
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            dados = response.json()
            # Retornar dados formatados para o frontend
            resultado = {
                "razao_social": dados.get('razao_social', ''),
                "nome_fantasia": dados.get('nome_fantasia', ''),
                "logradouro": dados.get('logradouro', ''),
                "numero": dados.get('numero', ''),
                "complemento": dados.get('complemento', ''),
                "bairro": dados.get('bairro', ''),
                "cep": dados.get('cep', ''),
                "municipio": dados.get('municipio', ''),
                "uf": dados.get('uf', ''),
                "telefone": dados.get('ddd_telefone_1', ''),
                "email": dados.get('email', ''),
                "situacao": dados.get('descricao_situacao_cadastral', '')
            }
            logger.info(f"✅ CNPJ consultado: {cnpj_limpo}")
            return jsonify({"ok": True, "dados": resultado})
        else:
            logger.warning(f"BrasilAPI retornou {response.status_code} para CNPJ {cnpj_limpo}")
            return jsonify({"ok": False, "message": "CNPJ não encontrado ou serviço indisponível"}), 404
            
    except requests.RequestException as e:
        logger.error(f"❌ Erro ao consultar BrasilAPI: {str(e)}")
        return jsonify({"ok": False, "message": "Erro de conexão ao consultar CNPJ"}), 500
    except Exception as e:
        logger.error(f"❌ Erro inesperado ao consultar CNPJ: {str(e)}")
        return jsonify({"ok": False, "message": "Erro interno ao consultar CNPJ"}), 500

# ============================================================
# ✅ API: UPLOAD DE LOGO DA EMPRESA (NOVA)
# ============================================================
@empresas_bp.route("/api/upload-logo", methods=["POST"])
@master_required
def api_upload_logo():
    """
    API para upload de logo da empresa.
    
    Request: multipart/form-data com fields:
    - empresa_id: ID da empresa
    - logo: arquivo de imagem (PNG/JPG/SVG, máx 2MB)
    
    Response JSON:
    { "ok": true, "logo_url": "/static/uploads/logos/..." }
    """
    # ✅ Validar CSRF para API
    if not validar_csrf_token():
        return jsonify({"ok": False, "message": "Erro de segurança"}), 403
    
    empresa_id = request.form.get('empresa_id')
    if not empresa_id:
        return jsonify({"ok": False, "message": "Empresa não informada"}), 400
    
    empresa = Empresa.query.get(empresa_id)
    if not empresa:
        return jsonify({"ok": False, "message": "Empresa não encontrada"}), 404
    
    if 'logo' not in request.files:
        return jsonify({"ok": False, "message": "Nenhum arquivo enviado"}), 400
    
    file = request.files['logo']
    if file.filename == '':
        return jsonify({"ok": False, "message": "Nome de arquivo vazio"}), 400
    
    # Validar extensão
    allowed_extensions = {'.png', '.jpg', '.jpeg', '.svg', '.webp'}
    ext = os.path.splitext(file.filename.lower())[1]
    if ext not in allowed_extensions:
        return jsonify({"ok": False, "message": f"Formato não permitido. Use: {', '.join(allowed_extensions)}"}), 400
    
    # Validar tamanho (2MB)
    file.seek(0, 2)
    size = file.tell()
    file.seek(0)
    if size > 2 * 1024 * 1024:
        return jsonify({"ok": False, "message": "Arquivo muito grande. Máximo: 2MB"}), 400
    
    try:
        # Gerar nome único para o arquivo
        filename = f"logo_{empresa_id}_{secrets.token_hex(8)}{ext}"
        
        # Criar diretório de upload se não existir
        upload_dir = os.path.join('static', 'uploads', 'logos')
        os.makedirs(upload_dir, exist_ok=True)
        
        # Salvar arquivo
        filepath = os.path.join(upload_dir, filename)
        file.save(filepath)
        
        # Atualizar empresa com URL da logo
        logo_url = f"/static/uploads/logos/{filename}"
        empresa.logo_url = logo_url
        empresa.atualizado_em = datetime.now(timezone.utc)
        
        # Log de auditoria
        log_acao_empresa("master_upload_logo", empresa, f"Logo: {filename}")
        
        db.session.commit()
        
        logger.info(f"✅ Logo salva para empresa {empresa_id}: {filename}")
        return jsonify({"ok": True, "logo_url": logo_url, "message": "Logo atualizada com sucesso"})
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"❌ Erro ao salvar logo: {str(e)}", exc_info=True)
        return jsonify({"ok": False, "message": "Erro ao salvar arquivo"}), 500
