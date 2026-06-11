# routes/master_routes.py - VERSÃO CORRIGIDA E COMPLETA

from flask import Blueprint, render_template, request, redirect, url_for, flash, g, abort, jsonify, session
from utils.auth_middleware import master_required
from models import db, Empresa, Usuario, LogAuditoria, MovAdquirente, MovBanco
from datetime import datetime, timezone, timedelta
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy import or_, func
import logging
import re
import time
import secrets

logger = logging.getLogger(__name__)

master_bp = Blueprint("master", __name__, url_prefix="/master")

# ============================================================
# CONFIGURAÇÕES DE SEGURANÇA
# ============================================================
RATE_LIMIT_WINDOW = 60  # segundos
RATE_LIMIT_MAX_REQUESTS = 15  # por minuto para endpoints master (mais restritivo)
_master_rate_limit_cache = {}

def check_master_rate_limit(user_id: str, endpoint: str) -> bool:
    """Verifica rate limiting para endpoints master"""
    now = time.time()
    key = f"master:{user_id}:{endpoint}"
    
    _master_rate_limit_cache[key] = [
        t for t in _master_rate_limit_cache.get(key, [])
        if now - t < RATE_LIMIT_WINDOW
    ]
    
    if len(_master_rate_limit_cache.get(key, [])) >= RATE_LIMIT_MAX_REQUESTS:
        return False
    
    _master_rate_limit_cache.setdefault(key, []).append(now)
    return True

# ============================================================
# VALIDAÇÕES
# ============================================================
def validar_email(email: str) -> bool:
    """Valida formato de email com regex"""
    if not email:
        return False
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def validar_senha_forte(senha: str):
    """
    Valida força da senha para contas administrativas.
    Returns: (bool, mensagem)
    """
    if len(senha) < 8:
        return False, "Mínimo 8 caracteres"
    if not re.search(r"[A-Z]", senha):
        return False, "Precisa de letra maiúscula"
    if not re.search(r"[a-z]", senha):
        return False, "Precisa de letra minúscula"
    if not re.search(r"\d", senha):
        return False, "Precisa de número"
    if not re.search(r"[!@#$%^&*()_+\-=\[\]{};':\"\\|,.<>\/?]", senha):
        return False, "Precisa de caractere especial (!@#$%...)"
    return True, "Senha válida"

def validar_csrf_token():
    """Valida token CSRF manualmente para formulários master"""
    token_form = request.form.get('csrf_token')
    token_header = request.headers.get('X-CSRF-Token')
    session_token = g.get('csrf_token')
    
    token = token_form or token_header
    if not token or not session_token or token != session_token:
        logger.warning("CSRF token inválido ou ausente em ação master")
        return False
    return True

def log_acao_master(acao: str, detalhes: str, empresa_id=None):
    """
    Log centralizado para ações master.
    ⚠️ NÃO commita - deve ser commitado junto com a transação principal.
    """
    try:
        log = LogAuditoria(
            usuario_id=g.user.id,
            empresa_id=empresa_id,
            acao=acao,
            detalhes=detalhes,
            ip=request.remote_addr,
            criado_em=datetime.now(timezone.utc)
        )
        db.session.add(log)
        # NÃO commitar aqui - deixar para a transação principal
    except Exception as e:
        logger.error(f"Erro ao preparar log de auditoria master: {str(e)}")
        # Não falhar a operação principal por erro de log

# ============================================================
# LISTAR EMPRESAS (COM BUSCA E ORDENAÇÃO)
# ============================================================
@master_bp.route("/empresas")
@master_required
def empresas_listar():
    # ✅ Rate limiting
    if not check_master_rate_limit(str(g.user.id), "empresas_listar"):
        flash("Muitas requisições. Aguarde alguns segundos.", "warning")
        return redirect(url_for("master.empresas_listar"))
    
    # Parâmetros de paginação, busca e ordenação
    page = max(1, request.args.get('page', 1, type=int))
    per_page = min(request.args.get('per_page', 20, type=int), 100)
    search = request.args.get('search', '').strip()
    order_by = request.args.get('order_by', 'id')
    order_dir = request.args.get('order_dir', 'desc')
    
    # Query base
    query = Empresa.query
    
    # ✅ Aplicar busca por nome ou email
    if search:
        query = query.filter(
            or_(
                Empresa.nome.ilike(f"%{search}%"),
                Empresa.email.ilike(f"%{search}%")
            )
        )
    
    # ✅ Aplicar ordenação
    order_column = getattr(Empresa, order_by, Empresa.id)
    if order_dir == 'desc':
        query = query.order_by(order_column.desc())
    else:
        query = query.order_by(order_column.asc())
    
    # Paginar
    empresas = query.paginate(page=page, per_page=per_page, error_out=False)
    
    return render_template(
        "master/empresas_listar.html", 
        empresas=empresas,
        search=search,
        order_by=order_by,
        order_dir=order_dir,
        page=page,
        per_page=per_page
    )

# ============================================================
# CRIAR EMPRESA
# ============================================================
@master_bp.route("/empresa/nova", methods=["GET", "POST"])
@master_required
def empresa_nova():
    # ✅ Rate limiting
    if not check_master_rate_limit(str(g.user.id), "empresa_nova"):
        flash("Muitas tentativas. Aguarde.", "warning")
        return redirect(url_for("master.empresa_nova"))
    
    if request.method == "GET":
        return render_template("master/empresa_nova.html")
    
    # ✅ Validar CSRF
    if not validar_csrf_token():
        flash("Erro de segurança. Recarregue a página.", "error")
        return redirect(url_for("master.empresa_nova"))
    
    # Coletar e sanitizar dados
    nome = (request.form.get("nome") or "").strip()
    admin_nome = (request.form.get("admin_nome") or "").strip()
    email = (request.form.get("email") or "").lower().strip()
    senha = request.form.get("senha")
    
    # Validações
    if not all([nome, admin_nome, email, senha]):
        flash("Preencha todos os campos obrigatórios", "error")
        return render_template("master/empresa_nova.html")
    
    if not validar_email(email):
        flash("Formato de email inválido", "error")
        return render_template("master/empresa_nova.html")
    
    valido, msg = validar_senha_forte(senha)
    if not valido:
        flash(msg, "error")
        return render_template("master/empresa_nova.html")
    
    # Verificar email duplicado
    if Usuario.query.filter_by(email=email).first():
        flash("Email já cadastrado em outra empresa", "error")
        return render_template("master/empresa_nova.html")
    
    try:
        # Criar empresa
        empresa = Empresa(
            nome=nome,
            documento="",
            email=email,
            ativo=True,
            criado_em=datetime.now(timezone.utc)
        )
        db.session.add(empresa)
        db.session.flush()  # Gera ID sem commit
        
        # Criar usuário admin
        usuario = Usuario(
            empresa_id=empresa.id,
            nome=admin_nome,
            email=email,
            admin=True,
            master=False,
            ativo=True,
            tentativas_login_falhas=0
        )
        usuario.set_password(senha)
        db.session.add(usuario)
        
        # Log de auditoria (mesma transação)
        log_acao_master("master_criou_empresa", f"Empresa: {nome}, Admin: {email}", empresa.id)
        
        db.session.commit()
        
        flash(f"Empresa '{nome}' criada com sucesso!", "success")
        logger.info(f"✅ Master criou empresa: {nome}, admin={email}")
        
        return redirect(url_for("master.empresas_listar"))
        
    except IntegrityError as e:
        db.session.rollback()
        logger.error(f"⚠️ Erro de integridade ao criar empresa: {str(e)}")
        flash("Erro ao criar. Email já existe?", "error")
        return render_template("master/empresa_nova.html")
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error(f"❌ Erro de banco ao criar empresa: {str(e)}")
        flash("Erro interno. Tente novamente.", "error")
        return render_template("master/empresa_nova.html")

# ============================================================
# VER EMPRESA + USUÁRIOS (COM PAGINAÇÃO)
# ============================================================
@master_bp.route("/empresa/<int:empresa_id>")
@master_required
def empresa_ver(empresa_id):
    # ✅ Rate limiting
    if not check_master_rate_limit(str(g.user.id), "empresa_ver"):
        flash("Muitas requisições. Aguarde.", "warning")
        return redirect(url_for("master.empresas_listar"))
    
    empresa = Empresa.query.get_or_404(empresa_id)
    
    # ✅ Paginação para lista de usuários
    page = max(1, request.args.get('page', 1, type=int))
    per_page = min(request.args.get('per_page', 50, type=int), 100)
    
    usuarios_pagination = Usuario.query.filter_by(empresa_id=empresa_id)\
        .order_by(Usuario.nome.asc())\
        .paginate(page=page, per_page=per_page, error_out=False)
    
    # Contagens úteis para auditoria
    total_vendas = MovAdquirente.query.filter_by(empresa_id=empresa_id).count()
    total_recebimentos = MovBanco.query.filter_by(empresa_id=empresa_id).count()
    
    return render_template(
        "master/empresa_ver.html", 
        empresa=empresa, 
        usuarios=usuarios_pagination.items,
        usuarios_pagination=usuarios_pagination,
        total_vendas=total_vendas,
        total_recebimentos=total_recebimentos,
        page=page,
        per_page=per_page
    )

# ============================================================
# CRIAR USUÁRIO
# ============================================================
@master_bp.route("/empresa/<int:empresa_id>/usuario/novo", methods=["GET", "POST"])
@master_required
def usuario_novo(empresa_id):
    # ✅ Rate limiting
    if not check_master_rate_limit(str(g.user.id), "usuario_novo"):
        flash("Muitas tentativas. Aguarde.", "warning")
        return redirect(url_for("master.empresa_ver", empresa_id=empresa_id))
    
    empresa = Empresa.query.get_or_404(empresa_id)
    
    if request.method == "GET":
        return render_template("master/usuario_novo.html", empresa=empresa)
    
    # ✅ Validar CSRF
    if not validar_csrf_token():
        flash("Erro de segurança. Recarregue a página.", "error")
        return redirect(url_for("master.usuario_novo", empresa_id=empresa_id))
    
    # Coletar e sanitizar dados
    nome = (request.form.get("nome") or "").strip()
    email = (request.form.get("email") or "").lower().strip()
    senha = request.form.get("senha")
    admin_flag = 1 if request.form.get("admin") else 0
    
    # Validações
    if not all([nome, email, senha]):
        flash("Preencha todos os campos obrigatórios", "error")
        return render_template("master/usuario_novo.html", empresa=empresa)
    
    if not validar_email(email):
        flash("Formato de email inválido", "error")
        return render_template("master/usuario_novo.html", empresa=empresa)
    
    valido, msg = validar_senha_forte(senha)
    if not valido:
        flash(msg, "error")
        return render_template("master/usuario_novo.html", empresa=empresa)
    
    # Verificar email duplicado
    if Usuario.query.filter_by(email=email).first():
        flash("Email já cadastrado", "error")
        return render_template("master/usuario_novo.html", empresa=empresa)
    
    try:
        usuario = Usuario(
            empresa_id=empresa_id,
            nome=nome,
            email=email,
            admin=bool(admin_flag),
            master=False,
            ativo=True,
            tentativas_login_falhas=0,
            criado_em=datetime.now(timezone.utc)
        )
        usuario.set_password(senha)
        db.session.add(usuario)
        
        # Log de auditoria (mesma transação)
        log_acao_master("master_criou_usuario", f"Usuário: {email}, Empresa: {empresa.nome}", empresa_id)
        
        db.session.commit()
        
        flash(f"Usuário '{nome}' criado com sucesso!", "success")
        logger.info(f"✅ Master criou usuário: {email}, empresa={empresa_id}")
        
        return redirect(url_for("master.empresa_ver", empresa_id=empresa_id))
        
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error(f"❌ Erro ao criar usuário: {str(e)}")
        flash("Erro ao criar usuário", "error")
        return render_template("master/usuario_novo.html", empresa=empresa)

# ============================================================
# REMOVER USUÁRIO (SOFT DELETE)
# ============================================================
@master_bp.route("/empresa/<int:empresa_id>/usuario/<int:user_id>/remover", methods=["POST"])
@master_required
def usuario_remover(empresa_id, user_id):
    # ✅ Rate limiting
    if not check_master_rate_limit(str(g.user.id), "usuario_remover"):
        flash("Muitas tentativas. Aguarde.", "warning")
        return redirect(url_for("master.empresa_ver", empresa_id=empresa_id))
    
    # ✅ Validar CSRF
    if not validar_csrf_token():
        flash("Erro de segurança", "error")
        return redirect(url_for("master.empresa_ver", empresa_id=empresa_id))
    
    usuario = Usuario.query.filter_by(id=user_id, empresa_id=empresa_id).first_or_404()
    
    # Não permitir auto-exclusão
    if usuario.id == g.user.id:
        flash("Não pode excluir a si mesmo", "error")
        return redirect(url_for("master.empresa_ver", empresa_id=empresa_id))
    
    # ✅ Verificar confirmação explícita para exclusão
    confirmar = request.form.get("confirmar_exclusao")
    if confirmar != "sim":
        flash("Para remover usuário, confirme digitando 'sim' no campo de confirmação", "warning")
        return redirect(url_for("master.empresa_ver", empresa_id=empresa_id))
    
    try:
        # ✅ Soft delete: marcar como inativo + registrar exclusão
        usuario.ativo = False
        usuario.nome = f"[EXCLUÍDO] {usuario.nome}"
        usuario.excluido_em = datetime.now(timezone.utc)
        usuario.excluido_por = g.user.id
        
        # Log de auditoria (mesma transação)
        log_acao_master("master_excluiu_usuario", f"Usuário: {usuario.email}", empresa_id)
        
        db.session.commit()
        
        flash("Usuário removido com sucesso", "success")
        logger.info(f"✅ Master removeu usuário: {usuario.id}, empresa={empresa_id}")
        
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error(f"❌ Erro ao remover usuário: {str(e)}")
        flash("Erro ao remover usuário", "error")
    
    return redirect(url_for("master.empresa_ver", empresa_id=empresa_id))

# ============================================================
# REMOVER EMPRESA (SOFT DELETE COM VALIDAÇÃO REFORÇADA)
# ============================================================
@master_bp.route("/empresa/<int:empresa_id>/remover", methods=["POST"])
@master_required
def empresa_remover(empresa_id):
    # ✅ Rate limiting
    if not check_master_rate_limit(str(g.user.id), "empresa_remover"):
        flash("Muitas tentativas. Aguarde.", "warning")
        return redirect(url_for("master.empresas_listar"))
    
    # ✅ Validar CSRF
    if not validar_csrf_token():
        flash("Erro de segurança", "error")
        return redirect(url_for("master.empresas_listar"))
    
    empresa = Empresa.query.get_or_404(empresa_id)
    
    # ✅ Verificar confirmação explícita para exclusão de empresa
    confirmar = request.form.get("confirmar_exclusao_empresa")
    if confirmar != "sim":
        flash("Para excluir empresa, confirme digitando 'sim' no campo de confirmação", "warning")
        return redirect(url_for("master.empresas_listar"))
    
    # Verificar se tem dados financeiros
    tem_vendas = MovAdquirente.query.filter_by(empresa_id=empresa_id).count() > 0
    tem_recebimentos = MovBanco.query.filter_by(empresa_id=empresa_id).count() > 0
    
    if tem_vendas or tem_recebimentos:
        flash("Não é possível excluir empresa com dados financeiros. Contate o suporte.", "error")
        return redirect(url_for("master.empresas_listar"))
    
    try:
        # ✅ Soft delete: marcar como inativo + registrar exclusão
        empresa.ativo = False
        empresa.nome = f"[EXCLUÍDA] {empresa.nome}"
        empresa.excluido_em = datetime.now(timezone.utc)
        empresa.excluido_por = g.user.id
        
        # Desativar todos os usuários da empresa
        for usuario in Usuario.query.filter_by(empresa_id=empresa_id).all():
            usuario.ativo = False
            usuario.excluido_em = datetime.now(timezone.utc)
        
        # Log de auditoria (mesma transação)
        log_acao_master("master_excluiu_empresa", f"Empresa: {empresa.nome}", empresa_id)
        
        db.session.commit()
        
        flash("Empresa removida com sucesso", "success")
        logger.info(f"✅ Master removeu empresa: {empresa_id}")
        
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error(f"❌ Erro ao remover empresa: {str(e)}")
        flash("Erro ao remover empresa", "error")
    
    return redirect(url_for("master.empresas_listar"))

# ============================================================
# NOVO: DASHBOARD MASTER (RESUMO DO SISTEMA)
# ============================================================
@master_bp.route("/")
@master_required
def dashboard_master():
    """Dashboard com resumo do sistema para master"""
    
    # Contagens globais (otimizadas)
    total_empresas = Empresa.query.count()
    empresas_ativas = Empresa.query.filter_by(ativo=True).count()
    total_usuarios = Usuario.query.count()
    usuarios_ativos = Usuario.query.filter_by(ativo=True).count()
    total_vendas = MovAdquirente.query.count()
    total_recebimentos = MovBanco.query.count()
    
    # Empresas criadas nos últimos 7 dias
    from datetime import timedelta
    sete_dias_atras = datetime.now(timezone.utc) - timedelta(days=7)
    empresas_recentes = Empresa.query.filter(Empresa.criado_em >= sete_dias_atras).count()
    
    # Logs recentes de auditoria
    logs_recentes = LogAuditoria.query.filter_by(acao__in=[
        "master_criou_empresa",
        "master_excluiu_empresa",
        "master_criou_usuario",
        "master_excluiu_usuario"
    ]).order_by(LogAuditoria.criado_em.desc()).limit(10).all()
    
    return render_template(
        "master/dashboard.html",
        total_empresas=total_empresas,
        empresas_ativas=empresas_ativas,
        empresas_recentes=empresas_recentes,
        total_usuarios=total_usuarios,
        usuarios_ativos=usuarios_ativos,
        total_vendas=total_vendas,
        total_recebimentos=total_recebimentos,
        logs_recentes=logs_recentes
    )


# ============================================================
# 🧪 TESTE OFX - DIAGNÓSTICO INTEGRADO
# ============================================================

@master_bp.route("/teste-ofx", methods=["GET"])
@master_required
def teste_ofx_page():
    """Página de teste de upload OFX para diagnóstico"""
    # Garantir CSRF token
    if 'csrf_token' not in session:
        session['csrf_token'] = secrets.token_urlsafe(32)
    
    return render_template("master/teste_ofx.html")


@master_bp.route("/teste-ofx/processar", methods=["POST"])
@master_required
def teste_ofx_processar():
    """Processa arquivo OFX em etapas com logs detalhados"""
    inicio_total = time.time()
    resultados = {"etapas": [], "total_tempo": 0}
    
    try:
        # ETAPA 1: Receber arquivo
        inicio = time.time()
        if 'file' not in request.files:
            return jsonify({"erro": "Nenhum arquivo enviado"}), 400
        
        file = request.files['file']
        if not file.filename:
            return jsonify({"erro": "Arquivo sem nome"}), 400
        
        content = file.read()
        file_size = len(content)
        tempo_receber = time.time() - inicio
        
        resultados["etapas"].append({
            "nome": "1. Receber arquivo",
            "tempo": f"{tempo_receber:.3f}s",
            "tempo_num": tempo_receber,
            "detalhes": f"Tamanho: {file_size/1024:.1f} KB",
            "ok": True
        })
        
        # ETAPA 2: Decodificar
        inicio = time.time()
        try:
            text = content.decode('utf-8', errors='replace')
        except:
            text = content.decode('latin-1', errors='replace')
        tempo_decode = time.time() - inicio
        
        resultados["etapas"].append({
            "nome": "2. Decodificar",
            "tempo": f"{tempo_decode:.3f}s",
            "tempo_num": tempo_decode,
            "detalhes": f"Chars: {len(text)}",
            "ok": True
        })
        
        # ETAPA 3: Contar transações
        inicio = time.time()
        total_transacoes = text.upper().count('<STMTTRN>')
        tempo_contar = time.time() - inicio
        
        resultados["etapas"].append({
            "nome": "3. Contar transações",
            "tempo": f"{tempo_contar:.3f}s",
            "tempo_num": tempo_contar,
            "detalhes": f"Total: {total_transacoes} transações",
            "ok": True
        })
        
        # ETAPA 4: Parser OFX
        inicio = time.time()
        try:
            from utils.parsers import parse_ofx_generic
            from io import BytesIO
            
            stream = BytesIO(content)
            registros = parse_ofx_generic(stream, file.filename)
            tempo_parser = time.time() - inicio
            
            resultados["etapas"].append({
                "nome": "4. Parser OFX",
                "tempo": f"{tempo_parser:.2f}s",
                "tempo_num": tempo_parser,
                "detalhes": f"Registros parseados: {len(registros)}",
                "ok": True
            })
            
            # Amostra dos primeiros 3 registros
            if registros:
                resultados["amostra"] = [
                    {
                        "data": str(r.get('data')),
                        "valor": str(r.get('valor')),
                        "descricao": (r.get('descricao') or '')[:50]
                    }
                    for r in registros[:3]
                ]
            
        except Exception as e:
            tempo_parser = time.time() - inicio
            resultados["etapas"].append({
                "nome": "4. Parser OFX",
                "tempo": f"{tempo_parser:.2f}s",
                "tempo_num": tempo_parser,
                "detalhes": f"ERRO: {str(e)}",
                "ok": False
            })
            import traceback
            resultados["traceback"] = traceback.format_exc()
            registros = []
        
        # ETAPA 5: Salvamento no banco (SOMENTE SE TIVER REGISTROS)
        if registros:
            inicio = time.time()
            try:
                from services.importer_db_movimento import salvar_recebimentos
                from models import db, Empresa
                
                # Pegar a primeira empresa ativa para teste
                empresa_teste = Empresa.query.filter_by(ativo=True).first()
                if not empresa_teste:
                    raise Exception("Nenhuma empresa ativa encontrada para teste")
                
                stats = salvar_recebimentos(registros, empresa_teste.id, None)
                tempo_save = time.time() - inicio
                
                resultados["etapas"].append({
                    "nome": "5. Salvamento no banco",
                    "tempo": f"{tempo_save:.2f}s",
                    "tempo_num": tempo_save,
                    "detalhes": stats,
                    "ok": True
                })
                
                # ROLLBACK - não salvar dados de teste
                db.session.rollback()
                
            except Exception as e:
                from models import db
                db.session.rollback()
                tempo_save = time.time() - inicio
                resultados["etapas"].append({
                    "nome": "5. Salvamento no banco",
                    "tempo": f"{tempo_save:.2f}s",
                    "tempo_num": tempo_save,
                    "detalhes": f"ERRO: {str(e)}",
                    "ok": False
                })
                import traceback
                resultados["traceback_save"] = traceback.format_exc()
        
        resultados["total_tempo"] = f"{time.time() - inicio_total:.2f}s"
        resultados["total_tempo_num"] = time.time() - inicio_total
        resultados["arquivo"] = file.filename
        resultados["total_transacoes"] = total_transacoes
        resultados["total_registros"] = len(registros) if registros else 0
        
    except Exception as e:
        resultados["erro_geral"] = str(e)
        import traceback
        resultados["traceback_geral"] = traceback.format_exc()
    
    return jsonify(resultados), 200

# ============================================================
# 🎯 DASHBOARD OPERACIONAL DO MASTER
# ============================================================

@master_bp.route("/dashboard-operacional")
@master_required
def dashboard_operacional_page():
    """Dashboard operacional do Master - visão geral do sistema"""
    return render_template("master/dashboard_operacional.html")


@master_bp.route("/api/dashboard-operacional")
@master_required
def dashboard_operacional_api():
    """API do dashboard operacional com KPIs completos"""
    try:
        from models import Lead, Empresa, Usuario, MovBanco, LogAuditoria
        
        hoje = datetime.now(timezone.utc)
        
        # ============================================================
        # KPI 1: TOTAL DE EMPRESAS
        # ============================================================
        total_empresas = Empresa.query.filter_by(ativo=True).count()
        empresas_ativas_30d = db.session.query(Empresa).filter(
            Empresa.ativo == True,
            Empresa.id.in_(
                db.session.query(MovBanco.empresa_id).filter(
                    MovBanco.data_movimento >= hoje.date() - timedelta(days=30)
                ).distinct()
            )
        ).count()
        
        # Empresas que já têm dados vs sem dados
        empresas_com_dados = db.session.query(Empresa).filter(
            Empresa.ativo == True,
            Empresa.id.in_(
                db.session.query(MovBanco.empresa_id).distinct()
            )
        ).count()
        empresas_sem_dados = total_empresas - empresas_com_dados
        
        # ============================================================
        # KPI 2: LEADS
        # ============================================================
        total_leads = Lead.query.count()
        leads_novos = Lead.query.filter_by(status='novo').count()
        leads_ultimos_7d = Lead.query.filter(
            Lead.criado_em >= hoje - timedelta(days=7)
        ).count()
        leads_convertidos = Lead.query.filter_by(status='cliente').count()
        
        # ============================================================
        # KPI 3: VOLUME DE TRANSAÇÕES
        # ============================================================
        transacoes_30d = db.session.query(
            func.count(MovBanco.id).label('total'),
            func.sum(func.abs(MovBanco.valor)).label('volume')
        ).filter(
            MovBanco.data_movimento >= hoje.date() - timedelta(days=30)
        ).first()
        
        transacoes_hoje = db.session.query(
            func.count(MovBanco.id).label('total'),
            func.sum(func.abs(MovBanco.valor)).label('volume')
        ).filter(
            MovBanco.data_movimento == hoje.date()
        ).first()
        
        # ============================================================
        # KPI 4: EMPRESAS MAIS ATIVAS (últimos 30 dias)
        # ============================================================
        empresas_top = db.session.query(
            Empresa.nome,
            func.count(MovBanco.id).label('total_transacoes'),
            func.sum(func.abs(MovBanco.valor)).label('volume_total')
        ).join(MovBanco).filter(
            MovBanco.data_movimento >= hoje.date() - timedelta(days=30),
            Empresa.ativo == True
        ).group_by(Empresa.id, Empresa.nome).order_by(
            func.sum(func.abs(MovBanco.valor)).desc()
        ).limit(10).all()
        
        # ============================================================
        # KPI 5: ÚLTIMOS ACESSOS DE USUÁRIOS
        # ============================================================
        ultimos_acessos = db.session.query(
            Usuario.nome,
            Usuario.email,
            Empresa.nome.label('empresa'),
            LogAuditoria.criado_em
        ).join(Usuario, LogAuditoria.usuario_id == Usuario.id)\
         .join(Empresa, Usuario.empresa_id == Empresa.id)\
         .filter(
             LogAuditoria.acao == 'dashboard_acesso',
             LogAuditoria.criado_em >= hoje - timedelta(days=7)
         ).order_by(LogAuditoria.criado_em.desc()).limit(20).all()
        
        # ============================================================
        # KPI 6: EVOLUÇÃO MENSAL (últimos 6 meses)
        # ============================================================
        evolucao_mensal = []
        for i in range(5, -1, -1):
            mes_atual = hoje.month - i
            ano_atual = hoje.year
            while mes_atual <= 0:
                mes_atual += 12
                ano_atual -= 1
            
            inicio_mes = datetime(ano_atual, mes_atual, 1, tzinfo=timezone.utc).date()
            if mes_atual == 12:
                fim_mes = datetime(ano_atual, 12, 31, tzinfo=timezone.utc).date()
            else:
                fim_mes = datetime(ano_atual, mes_atual + 1, 1, tzinfo=timezone.utc).date() - timedelta(days=1)
            
            stats = db.session.query(
                func.count(MovBanco.id).label('total'),
                func.sum(func.abs(MovBanco.valor)).label('volume')
            ).filter(
                MovBanco.data_movimento >= inicio_mes,
                MovBanco.data_movimento <= fim_mes
            ).first()
            
            evolucao_mensal.append({
                'mes': f'{mes_atual:02d}/{ano_atual}',
                'transacoes': stats[0] or 0,
                'volume': float(stats[1] or 0)
            })
        
        # ============================================================
        # KPI 7: NOVOS LEADS (lista detalhada)
        # ============================================================
        leads_recentes = Lead.query.order_by(
            Lead.criado_em.desc()
        ).limit(10).all()
        
        # ============================================================
        # MONTAR RESPOSTA
        # ============================================================
        response = {
            "ok": True,
            "kpis": {
                "empresas": {
                    "total": total_empresas,
                    "ativas_30d": empresas_ativas_30d,
                    "com_dados": empresas_com_dados,
                    "sem_dados": empresas_sem_dados
                },
                "leads": {
                    "total": total_leads,
                    "novos": leads_novos,
                    "ultimos_7d": leads_ultimos_7d,
                    "convertidos": leads_convertidos
                },
                "transacoes": {
                    "ultimos_30d": {
                        "total": transacoes_30d[0] or 0,
                        "volume": float(transacoes_30d[1] or 0)
                    },
                    "hoje": {
                        "total": transacoes_hoje[0] or 0,
                        "volume": float(transacoes_hoje[1] or 0)
                    }
                },
                "empresas_top": [
                    {
                        "nome": e[0],
                        "transacoes": e[1],
                        "volume": float(e[2] or 0)
                    } for e in empresas_top
                ],
                "ultimos_acessos": [
                    {
                        "usuario": a[0],
                        "email": a[1],
                        "empresa": a[2],
                        "data": a[3].isoformat() if a[3] else None
                    } for a in ultimos_acessos
                ],
                "evolucao_mensal": evolucao_mensal,
                "leads_recentes": [l.to_dict() for l in leads_recentes]
            }
        }
        
        return jsonify(response), 200
        
    except Exception as e:
        logger.error(f"❌ Erro no dashboard operacional: {str(e)}", exc_info=True)
        return jsonify({"ok": False, "error": str(e)}), 500
