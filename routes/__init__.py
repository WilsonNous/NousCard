# routes/__init__.py - VERSÃO FINAL COMPLETA

from .dashboard_routes import dashboard_bp
from .contrato_routes import contrato_bp
from .assistant_routes import assistant_bp
from .auth_routes import auth_bp
from .empresas_routes import empresas_bp
from .master_routes import master_bp
from .operacoes_routes import operacoes_bp
from .dashboard_api import dashboard_api
from .conciliacao_api import bp_conc
from .auditoria_routes import auditoria_bp  # ✅ NOVO: Registrar módulo de auditoria


def register_blueprints(app):
    """
    Registra todos os blueprints da aplicação.
    
    ✅ Ordem de registro (importante):
    1. Autenticação (público, necessário para login)
    2. Interface principal (dashboard, landing)
    3. Módulos de negócio (empresas, operações, etc.)
    4. APIs (versionadas, para frontend/mobile)
    5. Área administrativa (restrita)
    """
    
    # ---------------------------------------------------------
    # 1️⃣ AUTENTICAÇÃO (primeiro, para login/logout público)
    # ---------------------------------------------------------
    app.register_blueprint(auth_bp, url_prefix='/auth')
    # Rotas: /auth/login, /auth/logout, /auth/register
    
    # ---------------------------------------------------------
    # 2️⃣ INTERFACE PRINCIPAL (SEM url_prefix para rotas raiz)
    # ---------------------------------------------------------
    app.register_blueprint(dashboard_bp)
    # Rotas: /, /dashboard, /home
    
    # ---------------------------------------------------------
    # 3️⃣ MÓDULOS DE NEGÓCIO
    # ---------------------------------------------------------
    app.register_blueprint(empresas_bp, url_prefix='/empresas')
    # Rotas: /empresas/listar, /empresas/nova, etc.
    
    app.register_blueprint(contrato_bp, url_prefix='/contratos')
    # Rotas: /contratos/listar, /contratos/novo, etc.
    
    app.register_blueprint(operacoes_bp, url_prefix='/operacoes')
    # Rotas: /operacoes/importar, /operacoes/arquivos, /operacoes/conciliacao
    
    # ---------------------------------------------------------
    # 4️⃣ APIs (versionadas para frontend/mobile)
    # ---------------------------------------------------------
    app.register_blueprint(dashboard_api, url_prefix='/api/v1/dashboard')
    # Rotas: /api/v1/dashboard/kpis, /api/v1/dashboard/detalhamento
    
    # ✅ VERIFICAR: bp_conc deve ter url_prefix definido internamente
    # No arquivo conciliacao_api.py, deve haver:
    # bp_conc = Blueprint("conciliacao", __name__, url_prefix="/api/v1/conciliacao")
    app.register_blueprint(bp_conc)
    # Rotas: /api/v1/conciliacao/executar, /api/v1/conciliacao/detalhamento
    
    # ✅ NOVO: API de Auditoria
    app.register_blueprint(auditoria_bp, url_prefix='/api/v1/auditoria')
    # Rotas: /api/v1/auditoria/executar, /api/v1/auditoria/taxas
    
    # ---------------------------------------------------------
    # 5️⃣ ÁREA ADMINISTRATIVA (restrita, último para segurança)
    # ---------------------------------------------------------
    app.register_blueprint(master_bp, url_prefix='/master')
    # Rotas: /master/usuarios, /master/empresas, /master/config
    
    app.register_blueprint(assistant_bp, url_prefix='/assistant')
    # Rotas: /assistant/chat, /assistant/ajuda
    
    # ---------------------------------------------------------
    # ✅ LOG DE REGISTRO (opcional, útil para debug)
    # ---------------------------------------------------------
    # Descomente para ver quais rotas foram registradas:
    #
    # import logging
    # logger = logging.getLogger(__name__)
    # logger.info("Blueprints registrados:")
    # for rule in app.url_map.iter_rules():
    #     logger.info(f"  {rule.endpoint}: {rule.rule}")
