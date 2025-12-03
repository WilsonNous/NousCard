from .dashboard_routes import dashboard_bp
from .contrato_routes import contrato_bp
from .assistant_routes import assistant_bp
from .auth_routes import auth_bp
from .empresas_routes import empresas_bp
from .master_routes import master_bp
from .operacoes_routes import operacoes_bp
from .dashboard_api import dashboard_api


def register_blueprints(app):
    # Interface principal
    app.register_blueprint(dashboard_bp)

    # Módulos adicionais
    app.register_blueprint(contrato_bp)         # já tem prefixo interno
    app.register_blueprint(assistant_bp)        # já tem prefixo interno
    app.register_blueprint(auth_bp)             # login e auth
    app.register_blueprint(empresas_bp)         # gestão de empresas
    app.register_blueprint(master_bp)           # área master

    # Operações
    app.register_blueprint(operacoes_bp)        # já tem prefixo /operacoes

    # API do dashboard
    app.register_blueprint(dashboard_api)       # já tem prefixo /api/dashboard
