# routes/dashboard_routes.py - VERSÃO FINAL CORRIGIDA

from flask import Blueprint, render_template, g, request, make_response, redirect, url_for, current_app, abort, session
from utils.auth_middleware import login_required, empresa_required
from datetime import datetime, timezone
from sqlalchemy import func
import logging
import time

logger = logging.getLogger(__name__)

dashboard_bp = Blueprint("dashboard", __name__)

# ============================================================
# CONFIGURAÇÕES DE SEGURANÇA
# ============================================================
RATE_LIMIT_WINDOW = 60
RATE_LIMIT_MAX_REQUESTS = 60
_dashboard_rate_limit_cache = {}

def check_dashboard_rate_limit(user_id: str) -> bool:
    """Verifica rate limiting para acesso ao dashboard"""
    now = time.time()
    key = f"dashboard:{user_id}"
    
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
    
    # Rate limiting
    if not check_dashboard_rate_limit(str(usuario.id)):
        logger.warning(f"Rate limit aproximado: usuario={usuario.id}")
    
    # Verificação robusta de empresa_id
    if not empresa_id:
        logger.error(f"❌ Usuário {usuario.id} não tem empresa_id vinculado")
        return redirect(url_for('operacoes.importar_page'))
    
    # Verificar se empresa está ativa
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
    
    # Log de auditoria
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
        logger.debug(f"⚠️ Erro ao logar acesso ao dashboard (não crítico): {str(e)}")
    
    # Onboarding com queries separadas
    try:
        from models import MovAdquirente, ArquivoImportado
        
        tem_vendas = MovAdquirente.query.filter_by(
            empresa_id=empresa_id
        ).limit(1).count() > 0
        
        tem_arquivos = ArquivoImportado.query.filter_by(
            empresa_id=empresa_id
        ).limit(1).count() > 0
        
        logger.debug(f"🔍 Onboarding: empresa={empresa_id}, tem_vendas={tem_vendas}, tem_arquivos={tem_arquivos}")
        
        if not tem_vendas and not tem_arquivos:
            logger.info(f"🔄 Onboarding: empresa {empresa_id} sem dados, redirecionando para importar")
            return redirect(url_for('operacoes.importar_page'))
            
    except Exception as e:
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
        # ✅ SEGURO: CSRF token apenas de session/g (não de cookie)
        "csrf_token": getattr(g, 'csrf_token', '') or session.get('csrf_token', ''),
        "tipos_pagamento_disponiveis": ["todos", "cartao", "pix", "boleto", "outros"],
    }
    
    # Renderizar com cache control
    try:
        html = render_template("dashboard.html", **contexto)
        response = make_response(html)
        
        # Prevenir cache de página sensível
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        
        # Security headers
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        
        return response
        
    except Exception as e:
        logger.error(f"❌ Erro ao renderizar dashboard: {str(e)}", exc_info=True)
        abort(500)
