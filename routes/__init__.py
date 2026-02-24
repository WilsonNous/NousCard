from .dashboard_routes import dashboard_bp
from .contrato_routes import contrato_bp
from .assistant_routes import assistant_bp
from .auth_routes import auth_bp
from .empresas_routes import empresas_bp
from .master_routes import master_bp
from .operacoes_routes import operacoes_bp
from .dashboard_api import dashboard_api
from .conciliacao_api import bp_conc


def register_blueprints(app):
    """
    Registra todos os blueprints da aplicação.
    Ordem importa: rotas mais específicas devem vir depois das gerais.
    """
    
    # ---------------------------------------------------------
    # AUTENTICAÇÃO (primeiro, para login/logout público)
    # ---------------------------------------------------------
    app.register_blueprint(auth_bp, url_prefix='/auth')
    
    # ---------------------------------------------------------
    # INTERFACE PRINCIPAL
    # ---------------------------------------------------------
    app.register_blueprint(dashboard_bp, url_prefix='/')
    
    # ---------------------------------------------------------
    # MÓDULOS DE NEGÓCIO
    # ---------------------------------------------------------
    app.register_blueprint(empresas_bp, url_prefix='/empresas')
    app.register_blueprint(contrato_bp, url_prefix='/contratos')
    app.register_blueprint(operacoes_bp, url_prefix='/operacoes')
    
    # ---------------------------------------------------------
    # APIs (versionadas)
    # ---------------------------------------------------------
    app.register_blueprint(dashboard_api, url_prefix='/api/v1/dashboard')
    app.register_blueprint(bp_conc, url_prefix='/api/v1/conciliacao')
    
    # ---------------------------------------------------------
    # ÁREA ADMINISTRATIVA (restrita)
    # ---------------------------------------------------------
    app.register_blueprint(master_bp, url_prefix='/master')
    app.register_blueprint(assistant_bp, url_prefix='/assistant')
