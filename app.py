from flask import Flask, g, request, redirect, url_for, session
from config import Config
from models.base import db
from routes import register_blueprints
from datetime import datetime, timezone
from flask_migrate import Migrate
from flask_login import LoginManager, current_user
import logging
from logging.handlers import RotatingFileHandler
import os
import sentry_sdk
from sentry_sdk.integrations.flask import FlaskIntegration

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Sentry (produção)
    if os.getenv("SENTRY_DSN"):
        sentry_sdk.init(
            dsn=os.getenv("SENTRY_DSN"),
            integrations=[FlaskIntegration()],
            traces_sample_rate=0.1,
            environment=os.getenv("FLASK_ENV", "production")
        )

    # Inicializa banco
    db.init_app(app)
    migrate = Migrate(app, db)

    # Flask-Login
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = "auth.login_page"

    @login_manager.user_loader
    def load_user(user_id):
        from models import Usuario
        return Usuario.query.get(int(user_id))

    # Registra rotas e APIs
    register_blueprints(app)

    # ---------------------------------------------------------
    # DISPONIBILIZA O USUÁRIO PARA TODOS TEMPLATES
    # ---------------------------------------------------------
    @app.context_processor
    def inject_user():
        return {
            "usuario": getattr(g, "user", None),
            "is_authenticated": hasattr(g, "user") and g.user is not None,
            "is_master": getattr(g, "user", None) and getattr(g.user, "master", False),
            "is_admin": getattr(g, "user", None) and getattr(g.user, "admin", False),
        }

    # ---------------------------------------------------------
    # DISPONIBILIZA VARIÁVEIS GLOBAIS
    # ---------------------------------------------------------
    @app.context_processor
    def inject_globals():
        return {
            "current_year": datetime.now(timezone.utc).year
        }

    # ---------------------------------------------------------
    # HEALTH CHECK
    # ---------------------------------------------------------
    @app.route("/health")
    def health_check():
        try:
            db.session.execute("SELECT 1")
            db_status = "ok"
        except:
            db_status = "fail"
        
        return {
            "status": "ok" if db_status == "ok" else "degraded",
            "app": "NousCard",
            "database": db_status,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }, 200 if db_status == "ok" else 503

    # ---------------------------------------------------------
    # FORCE HTTPS (produção)
    # ---------------------------------------------------------
    @app.before_request
    def force_https():
        if not request.is_secure and os.getenv("FLASK_ENV") == "production":
            url = request.url.replace('http://', 'https://', 1)
            return redirect(url, code=301)

    # ---------------------------------------------------------
    # SECURITY HEADERS
    # ---------------------------------------------------------
    @app.after_request
    def add_security_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline';"
        return response

    # ---------------------------------------------------------
    # LOGGING
    # ---------------------------------------------------------
    if not app.debug and not os.environ.get("WERKZEUG_RUN_MAIN"):
        if not os.path.exists('logs'):
            os.mkdir('logs')
        
        handler = RotatingFileHandler('logs/nouscard.log', maxBytes=10*1024*1024, backupCount=5)
        handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
        ))
        handler.setLevel(logging.INFO)
        app.logger.addHandler(handler)
        app.logger.setLevel(logging.INFO)
        app.logger.info("NousCard startup")

    # ---------------------------------------------------------
    # TEARDOWN
    # ---------------------------------------------------------
    @app.teardown_appcontext
    def shutdown_session(exception=None):
        db.session.remove()

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
