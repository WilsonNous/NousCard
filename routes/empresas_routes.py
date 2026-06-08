# routes/empresas_routes.py - VERSÃO CORRIGIDA E COMPLETA

from flask import Blueprint, render_template, request, redirect, url_for, flash, g, abort
from models import db, Empresa, Usuario, LogAuditoria
from utils.auth_middleware import master_required
from datetime import datetime, timezone
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy import or_
import logging
import re
import time

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
    """Valida token CSRF manualmente para formulários"""
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
# NOVA EMPRESA
# ============================================================
@empresas_bp.route("/nova", methods=["GET", "POST"])
@master_required
def nova_empresa():
    # ✅ Rate limiting
    if not check_admin_rate_limit(str(g.user.id), "nova_empresa"):
        flash("Muitas tentativas. Aguarde.", "warning")
        return redirect(url_for("empresas.nova_empresa"))
    
    if request.method == "GET":
        return render_template("empresas_form.html", empresa=None)
    
    # ✅ Validar CSRF
    if not validar_csrf_token():
        flash("Erro de segurança. Recarregue a página.", "error")
        return redirect(url_for("empresas.nova_empresa"))
    
    # Coletar e sanitizar dados
    nome = (request.form.get("nome") or "").strip()
    documento = (request.form.get("documento") or "").strip().replace('.', '').replace('-', '').replace('/', '')
    
    # Validações
    if not nome or len(nome) > 150:
        flash("Nome deve ter entre 1 e 150 caracteres", "error")
        return render_template("empresas_form.html", empresa=None)
    
    if documento:
        if len(documento) > 14:  # CNPJ tem 14 dígitos
            flash("Documento muito longo", "error")
            return render_template("empresas_form.html", empresa=None)
        if not validar_cnpj(documento):
            flash("CNPJ inválido", "error")
            return render_template("empresas_form.html", empresa=None)
        
        # Verificar duplicidade
        if Empresa.query.filter_by(documento=documento).first():
            flash("Documento já cadastrado em outra empresa", "error")
            return render_template("empresas_form.html", empresa=None)
    
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
        flash("Erro: documento já existe", "error")
        return render_template("empresas_form.html", empresa=None)
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error(f"❌ Erro de banco ao criar empresa: {str(e)}")
        flash("Erro interno. Tente novamente.", "error")
        return render_template("empresas_form.html", empresa=None)

# ============================================================
# EDITAR EMPRESA
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
        return render_template("empresas_form.html", empresa=empresa)
    
    # ✅ Validar CSRF
    if not validar_csrf_token():
        flash("Erro de segurança. Recarregue a página.", "error")
        return redirect(url_for("empresas.editar_empresa", empresa_id=empresa_id))
    
    # Coletar e sanitizar dados
    nome = (request.form.get("nome") or "").strip()
    documento = (request.form.get("documento") or "").strip().replace('.', '').replace('-', '').replace('/', '')
    ativa = request.form.get("ativa") == "on"
    
    # Validações
    if not nome or len(nome) > 150:
        flash("Nome deve ter entre 1 e 150 caracteres", "error")
        return render_template("empresas_form.html", empresa=empresa)
    
    if documento:
        if len(documento) > 14:
            flash("Documento muito longo", "error")
            return render_template("empresas_form.html", empresa=empresa)
        if not validar_cnpj(documento):
            flash("CNPJ inválido", "error")
            return render_template("empresas_form.html", empresa=empresa)
        
        # Verificar duplicidade (excluindo esta empresa)
        existente = Empresa.query.filter(
            Empresa.documento == documento,
            Empresa.id != empresa_id
        ).first()
        if existente:
            flash("Documento já cadastrado em outra empresa", "error")
            return render_template("empresas_form.html", empresa=empresa)
    
    # ✅ Verificar desativação com confirmação explícita
    if not ativa and empresa.ativo:
        # Verificar se admin confirmou a desativação
        confirmar_desativacao = request.form.get("confirmar_desativacao")
        if confirmar_desativacao != "sim":
            usuarios_ativos = Usuario.query.filter_by(empresa_id=empresa_id, ativo=True).count()
            flash(f"⚠️ Para desativar, marque 'Confirmar desativação'. {usuarios_ativos} usuários serão afetados.", "warning")
            return render_template("empresas_form.html", empresa=empresa, requer_confirmacao=True)
    
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
        return render_template("empresas_form.html", empresa=empresa)

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
# DETALHES DA EMPRESA (NOVO - ÚTIL PARA AUDITORIA)
# ============================================================
@empresas_bp.route("/<int:empresa_id>")
@master_required
def detalhes_empresa(empresa_id):
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
