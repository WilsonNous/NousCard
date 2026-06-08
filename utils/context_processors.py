# utils/context_processors.py - VERSÃO CORRIGIDA E COMPLETA

from datetime import datetime, timezone
from flask import g, session, current_app
import logging

logger = logging.getLogger(__name__)

def inject_global_vars():
    """
    Injeta variáveis globais em todos os templates Jinja2.
    
    ✅ Safe access: usa getattr/hasattr para evitar AttributeError
    ✅ CSRF ready: inclui token para formulários
    ✅ Debug friendly: logging opcional para desenvolvimento
    """
    
    # Obter usuário de forma segura
    usuario = getattr(g, 'user', None)
    
    # Extrair dados do usuário com fallbacks em cascata
    usuario_id = getattr(usuario, 'id', None) if usuario else None
    usuario_email = getattr(usuario, 'email', None) if usuario else None
    usuario_nome = getattr(usuario, 'nome', None) if usuario else None
    
    # Verificar permissões
    is_master = bool(getattr(usuario, 'master', False)) if usuario else False
    is_admin = bool(getattr(usuario, 'admin', False)) if usuario else False
    
    # Extrair dados da empresa com verificação aninhada segura
    empresa = getattr(usuario, 'empresa', None) if usuario else None
    empresa_id = getattr(usuario, 'empresa_id', None) if usuario else None
    empresa_nome = getattr(empresa, 'nome', None) if empresa else None
    empresa_nome = empresa_nome or 'Minha Empresa'  # Fallback amigável
    
    # ✅ Token CSRF para formulários (vem da sessão, gerado no login)
    csrf_token = session.get('csrf_token') if session else None
    
    # ✅ Variáveis de ambiente úteis para templates
    app_debug = current_app.debug if current_app else False
    app_name = current_app.config.get('APP_NAME', 'NousCard')
    
    # ✅ Feature flags (exemplo: habilitar/desabilitar recursos)
    feature_flags = {
        'pix_enabled': current_app.config.get('FEATURE_PIX_ENABLED', True),
        'conciliacao_auto': current_app.config.get('FEATURE_CONCIL_AUTO', True),
        'auditoria_avancada': current_app.config.get('FEATURE_AUDITORIA', False),
    }
    
    # ✅ Dados de tempo para templates
    now = datetime.now(timezone.utc)
    
    # Montar contexto
    contexto = {
        # Usuário
        'usuario_id': usuario_id,
        'usuario_email': usuario_email,
        'usuario_nome': usuario_nome,
        'is_master': is_master,
        'is_admin': is_admin,
        
        # Empresa
        'empresa_id': empresa_id,
        'empresa_nome': empresa_nome,
        
        # Segurança
        'csrf_token': csrf_token,
        
        # App
        'app_name': app_name,
        'app_debug': app_debug,
        
        # Feature flags
        'features': feature_flags,
        
        # Tempo
        'current_year': now.year,
        'current_month': now.month,
        'current_day': now.day,
        'timestamp_utc': now.isoformat(),
    }
    
    # ✅ Logging em modo debug para auditar contexto injetado
    if app_debug:
        logger.debug(f"🔍 Contexto injetado: usuario={usuario_id}, empresa={empresa_id}, csrf={'✓' if csrf_token else '✗'}")
    
    return contexto


def inject_flash_messages():
    """
    Injeta mensagens flash no contexto para exibição automática.
    Útil para não precisar repetir o bloco de flashes em cada template.
    """
    from flask import get_flashed_messages
    
    return {
        'flashed_messages': get_flashed_messages(with_categories=True)
    }


def inject_nav_context():
    """
    Injeta dados para navegação: menu ativo, breadcrumbs, etc.
    Pode ser expandido conforme necessidade.
    """
    from flask import request
    
    # Determinar seção ativa baseada na URL
    endpoint = request.endpoint or ''
    
    secao_ativa = None
    if endpoint.startswith('dashboard'):
        secao_ativa = 'dashboard'
    elif endpoint.startswith('operacoes'):
        secao_ativa = 'operacoes'
    elif endpoint.startswith('empresas') or endpoint.startswith('master'):
        secao_ativa = 'admin'
    elif endpoint.startswith('contrato'):
        secao_ativa = 'contratos'
    
    return {
        'secao_ativa': secao_ativa,
        'endpoint_atual': endpoint,
        'url_atual': request.path,
    }


# ============================================================
# REGISTRO NO APP (exemplo de uso em app.py)
# ============================================================
# 
# Em app.py, registrar os context processors:
#
# @app.context_processor
# def global_vars():
#     return inject_global_vars()
#
# @app.context_processor  
# def flash_msgs():
#     return inject_flash_messages()
#
# @app.context_processor
# def nav_ctx():
#     return inject_nav_context()
#
