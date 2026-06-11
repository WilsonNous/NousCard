# routes/__init__.py - VERSÃO FINAL COMPLETA E ROBUSTA

import os  
import logging
import time
from flask import Flask

logger = logging.getLogger(__name__)

# ============================================================
# IMPORTAÇÃO DE BLUEPRINTS (COM FALLBACK SEGURO)
# ============================================================

def _import_blueprint(module_path: str, blueprint_name: str):
    """
    Importa blueprint com fallback seguro para testes/ambientes mínimos.
    
    Args:
        module_path: Caminho do módulo (ex: '.dashboard_routes')
        blueprint_name: Nome da variável do blueprint (ex: 'dashboard_bp')
    
    Returns:
        Blueprint object ou None se falhar
    """
    try:
        module = __import__(module_path, fromlist=[blueprint_name])
        return getattr(module, blueprint_name)
    except ImportError as e:
        # Em produção, falhar é melhor que silenciar
        if os.getenv('FLASK_ENV') == 'production':
            logger.error(f"❌ Falha crítica ao importar {blueprint_name}: {e}")
            raise
        # Em dev/teste, permitir continuar com warning
        logger.warning(f"⚠️ Blueprint {blueprint_name} não disponível: {e}")
        return None
    except AttributeError as e:
        logger.error(f"❌ Blueprint {blueprint_name} não encontrado em {module_path}: {e}")
        raise


# Importações diretas (padrão para produção)
from .dashboard_routes import dashboard_api_bp
from .contrato_routes import contrato_bp
from .assistant_routes import assistant_bp
from .auth_routes import auth_bp
from .empresas_routes import empresas_bp
from .master_routes import master_bp
from .operacoes_routes import operacoes_bp
from .dashboard_api import dashboard_api
from .conciliacao_api import bp_conc
from .auditor_routes import auditor_bp  
from routes.debug_routes import debug_bp

def register_blueprints(app: Flask):
    """
    Registra todos os blueprints da aplicação com validação e logging.
    
    ✅ Ordem de registro (importante):
    1. Autenticação (público, necessário para login)
    2. Interface principal (dashboard, landing)
    3. Módulos de negócio (empresas, operações, etc.)
    4. APIs (versionadas, para frontend/mobile)
    5. Área administrativa (restrita)
    
    Args:
        app: Instância Flask configurada
    """
    
    # Configurar logging apenas em debug
    is_debug = app.debug or os.getenv('FLASK_ENV') == 'development'
    
    if is_debug:
        logger.info("🔄 Iniciando registro de blueprints...")
        start_time = time.time()
    
    # Lista de blueprints para registro (ordem importante)
    blueprints = [
        # 1️⃣ AUTENTICAÇÃO (primeiro, para login/logout público)
        {
            'blueprint': auth_bp,
            'prefix': '/auth',
            'description': 'Autenticação (login, registro, logout)',
            'access': 'public',
            'required': True
        },
        
        # 2️⃣ INTERFACE PRINCIPAL (SEM url_prefix para rotas raiz)
        {
            'blueprint': dashboard_bp,
            'prefix': None,  # Rotas raiz: /, /dashboard
            'description': 'Interface principal (dashboard, landing)',
            'access': 'authenticated',
            'required': True
        },
        
        # 3️⃣ MÓDULOS DE NEGÓCIO
        {
            'blueprint': empresas_bp,
            'prefix': '/empresas',
            'description': 'Gestão de empresas',
            'access': 'authenticated',
            'required': True
        },
        {
            'blueprint': contrato_bp,
            'prefix': '/contratos',
            'description': 'Gestão de contratos de taxas',
            'access': 'authenticated',
            'required': True
        },
        {
            'blueprint': operacoes_bp,
            'prefix': '/operacoes',
            'description': 'Operações (importar, conciliar, detalhar)',
            'access': 'authenticated',
            'required': True
        },
        
        # 4️⃣ APIs (versionadas para frontend/mobile)
        {
            'blueprint': dashboard_api,
            'prefix': '/api/v1/dashboard',
            'description': 'API de dashboard (KPIs, gráficos)',
            'access': 'authenticated',
            'required': True
        },
        {
            'blueprint': bp_conc,
            'prefix': '/api/v1/conciliacao',  # ✅ Explícito, não depender do interno
            'description': 'API de conciliação',
            'access': 'authenticated',
            'required': True
        },
        {
            'blueprint': auditor_bp,
            'prefix': '/api/v1/auditoria',
            'description': 'API de auditoria de taxas',
            'access': 'authenticated',
            'required': False,  # ✅ Feature flag: pode ser desabilitado
            'feature_flag': 'FEATURE_AUDITORIA_ENABLED'
        },
        
        # 5️⃣ ÁREA ADMINISTRATIVA (restrita, último para segurança)
        {
            'blueprint': master_bp,
            'prefix': '/master',
            'description': 'Área administrativa (restrita a master)',
            'access': 'master_only',
            'required': True
        },
        {
            'blueprint': assistant_bp,
            'prefix': '/assistant',
            'description': 'Assistente virtual e ajuda',
            'access': 'authenticated',
            'required': False,
            'feature_flag': 'FEATURE_ASSISTANT_ENABLED'
        },
        # ✅ 6️⃣ DEBUG/DIAGNÓSTICO (apenas master, para troubleshooting)
        {
            'blueprint': debug_bp,
            'prefix': '/debug',  # ← Prefixo aqui
            'description': 'Rotas de debug e diagnóstico',
            'access': 'master_only',
            'required': False,
            'feature_flag': 'FEATURE_DEBUG_ENABLED'
        },
    ]
    
    # Registrar cada blueprint com validação
    registered = 0
    skipped = 0
    
    for bp_config in blueprints:
        blueprint = bp_config['blueprint']
        prefix = bp_config['prefix']
        description = bp_config['description']
        access_level = bp_config['access']
        required = bp_config.get('required', True)
        feature_flag = bp_config.get('feature_flag')
        
        # ✅ Verificar feature flag se configurado
        if feature_flag and not app.config.get(feature_flag, True):
            if is_debug:
                logger.info(f"⏭️ Blueprint '{description}' pulado (feature flag: {feature_flag}=False)")
            skipped += 1
            continue
              
        try:
            # ✅ Timing do registro
            bp_start = time.time()
            app.register_blueprint(blueprint, url_prefix=prefix)
            bp_duration = (time.time() - bp_start) * 1000  # em ms
            
            if is_debug:
                logger.info(f"✅ Registrado: {description} ({prefix or '/'}) [{bp_duration:.1f}ms] [{access_level}]")
            registered += 1
            
        except Exception as e:
            error_msg = f"❌ Falha ao registrar {description}: {str(e)}"
            if required:
                logger.error(error_msg)
                raise
            else:
                logger.warning(f"⚠️ {error_msg} (blueprint opcional, continuando)")
                skipped += 1
    
    # ✅ Log final de resumo
    if is_debug:
        total_time = (time.time() - start_time) * 1000
        logger.info(f"🎯 Registro concluído: {registered} blueprints, {skipped} pulados [{total_time:.1f}ms total]")
        
        # ✅ Listar rotas registradas (opcional, pode ser pesado)
        if app.config.get('DEBUG_LIST_ROUTES', False):
            logger.info("📋 Rotas registradas:")
            for rule in sorted(app.url_map.iter_rules(), key=lambda r: r.rule):
                if rule.endpoint != 'static':
                    methods = ', '.join(sorted(m for m in rule.methods if m not in ['HEAD', 'OPTIONS']))
                    logger.info(f"  {rule.rule:40s} [{methods:10s}] → {rule.endpoint}")
    
    # ✅ Expor lista de blueprints para testes (injeção de dependência)
    app.config['_REGISTERED_BLUEPRINTS'] = [bp['blueprint'].name for bp in blueprints if bp['blueprint']]
