from .dashboard_routes import dashboard_bp
from .contrato_routes import contrato_bp
from .assistant_routes import assistant_bp
from .auth_routes import auth_bp
from .empresas_routes import empresas_bp
from .master_routes import master_bp
from .operacoes_routes import operacoes_bp
from .dashboard_api import dashboard_api



def register_blueprints(app):
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(contrato_bp, url_prefix="/contratos")
    app.register_blueprint(assistant_bp, url_prefix="/assistant")
    app.register_blueprint(auth_bp)
    app.register_blueprint(empresas_bp)
    app.register_blueprint(master_bp)
    app.register_blueprint(operacoes_bp, url_prefix="/operacoes")
    app.register_blueprint(dashboard_api
