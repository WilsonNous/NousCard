from .dashboard_routes import dashboard_bp
from .upload_routes import upload_bp
from .conciliacao_routes import conciliacao_bp
from .contrato_routes import contrato_bp
from .assistant_routes import assistant_bp
from .auth_routes import auth_bp
from .empresas_routes import empresas_bp

def register_blueprints(app):
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(upload_bp, url_prefix="/upload")
    app.register_blueprint(conciliacao_bp, url_prefix="/conciliacao")
    app.register_blueprint(contrato_bp, url_prefix="/contratos")
    app.register_blueprint(assistant_bp, url_prefix="/assistant")
    app.register_blueprint(auth_bp)
    app.register_blueprint(empresas_bp)
