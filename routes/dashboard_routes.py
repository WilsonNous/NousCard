# routes/dashboard_routes.py - VERSÃO APRIMORADA COM SEGURANÇA REFORÇADA

from flask import Blueprint, render_template, g, request, make_response, redirect, url_for, current_app, abort
from utils.auth_middleware import login_required, empresa_required
from datetime import datetime, timezone
from sqlalchemy import func, or_
import logging
import time

logger = logging.getLogger(__name__)

dashboard_bp = Blueprint("dashboard", __name__)

# ============================================================
# CONFIGURAÇÕES DE SEGURANÇA
# ============================================================
RATE_LIMIT_WINDOW = 60  # segundos
RATE_LIMIT_MAX_REQUESTS = 60  # por minuto para dashboard (mais flexível que API)
_dashboard_rate_limit_cache = {}

def check_dashboard_rate_limit(user_id: str) -> bool:
    """Verifica rate limiting para acesso ao dashboard"""
    now = time.time()
    key = f"dashboard:{user_id}"
    
    # Limpar entradas antigas
    _dashboard_rate_limit_cache[key] = [
        t for t in _dashboard_rate_limit_cache.get(key, [])
        if now - t < RATE_LIMIT_WINDOW
    ]
    
    if len(_dashboard_rate_limit_cache.get(key, [])) >= RATE_LIMIT_MAX_REQUESTS:
        return False
    
    _dashboard_rate_limit_cache.setdefault(key, []).append(now)
    return True

# ============================================================
# ROTAS PRINCIPAIS
# ============================================================
@dashboard_bp.route("/")
@dashboard_bp.route("/dashboard")
@login_required
@empresa_required
def dashboard():
    """
    Página principal do dashboard.
    Requer usuário logado e vinculado a uma empresa ativa.
    """
    
    usuario = g.user
    empresa_id = getattr(usuario, 'empresa_id', None)
    
    # ✅ Rate limiting (apenas log warning, não bloquear para não prejudicar UX)
    if not check_dashboard_rate_limit(str(usuario.id)):
        logger.warning(f"Rate limit aproximado: usuario={usuario.id}")
        # Não bloquear, apenas logar - dashboard é crítico para UX
    
    # ✅ Verificação robusta de empresa_id
    if not empresa_id:
        logger.error(f"❌ Usuário {usuario.id} não tem empresa_id vinculado")
        return redirect(url_for('operacoes.importar_page'))
    
    # ✅ Verificar se empresa está ativa (segurança adicional)
    try:
        from models import Empresa
        empresa = Empresa.query.filter_by(id=empresa_id, ativo=True).first()
        if not empresa:
            logger.warning(f"⚠️ Empresa {empresa_id} não encontrada ou inativa")
            return redirect(url_for('auth.logout'))
        empresa_nome = empresa.nome
    except Exception as e:
        logger.error(f"❌ Erro ao verificar empresa: {str(e)}")
        return redirect(url_for('auth.logout'))
    
    # ✅ Log de auditoria (não crítico - isolado em try/except)
    try:
        from models import LogAuditoria, db
        log = LogAuditoria(
            usuario_id=usuario.id,
            empresa_id=empresa_id,
            acao="dashboard_acesso",
            detalhes=f"User-Agent: {request.user_agent.string[:100]}",
            ip=request.remote_addr,
            criado_em=datetime.now(timezone.utc)
        )
        db.session.add(log)
        db.session.commit()
    except Exception as e:
        # Não falhar o dashboard por erro de log
        logger.debug(f"⚠️ Erro ao logar acesso ao dashboard (não crítico): {str(e)}")
    
    # ✅ Onboarding Inteligente: Verificar dados OU arquivos importados
    # ✅ Otimizado: 1 query em vez de 2 COUNTs separados
    try:
        from models import MovAdquirente, ArquivoImportado
        
        # Query única com OR para verificar se tem vendas OU arquivos
        tem_dados = db.session.query(
            func.count(MovAdquirente.id).label('vendas'),
            func.count(ArquivoImportado.id).label('arquivos')
        ).filter(
            or_(
                MovAdquirente.empresa_id == empresa_id,
                ArquivoImportado.empresa_id == empresa_id
            )
        ).first()
        
        tem_vendas = tem_dados.vendas > 0 if tem_dados else False
        tem_arquivos = tem_dados.arquivos > 0 if tem_dados else False
        
        logger.debug(f"🔍 Onboarding: empresa={empresa_id}, tem_vendas={tem_vendas}, tem_arquivos={tem_arquivos}")
        
        # Só redireciona se NÃO tiver NENHUM dos dois
        if not tem_vendas and not tem_arquivos:
            logger.info(f"🔄 Onboarding: empresa {empresa_id} sem dados, redirecionando para importar")
            return redirect(url_for('operacoes.importar_page'))
            
    except Exception as e:
        # Em caso de erro, NÃO redireciona - deixa o usuário ver o dashboard
        logger.debug(f"⚠️ Não foi possível verificar dados para onboarding: {str(e)}")
    
    # ✅ Preparar contexto completo para o template
    contexto = {
        "usuario": usuario,
        "empresa_id": empresa_id,
        "empresa_nome": empresa_nome,
        "is_admin": getattr(usuario, 'admin', False),
        "is_master": getattr(usuario, 'master', False),
        "current_year": datetime.now().year,
        "current_month": datetime.now().month,
        "page_title": "Dashboard - NousCard",
        # ✅ NOVO: CSRF token para formulários no template
        "csrf_token": request.cookies.get('csrf_token') or getattr(g, 'csrf_token', ''),
        # ✅ NOVO: Tipos de pagamento disponíveis para filtros no frontend
        "tipos_pagamento_disponiveis": ["todos", "cartao", "pix", "boleto", "outros"],
    }
    
    # ✅ Renderizar com cache control e tratamento de erro
    try:
        html = render_template("dashboard.html", **contexto)
        response = make_response(html)
        
        # Prevenir cache de página sensível
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        
        # ✅ NOVO: Security headers adicionais
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        
        return response
        
    except Exception as e:
        logger.error(f"❌ Erro ao renderizar dashboard: {str(e)}", exc_info=True)
        abort(500)
