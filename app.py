# ============================================================
#  APP • NousCard (PRODUÇÃO)
#  Compatível com: SQLAlchemy 1.4.50 + Flask-SQLAlchemy 3.0.5 + Python 3.11
# ============================================================

from flask import Flask, g, request, redirect, url_for, session
from config import Config
from models.base import db, init_db, cleanup_session  # ✅ Importa helpers
from routes import register_blueprints
from datetime import datetime, timezone
from flask_migrate import Migrate
from flask_login import LoginManager, current_user
import logging
from logging.handlers import RotatingFileHandler
import os
import sys

# Sentry (import condicional para evitar erro se não instalado)
try:
    import sentry_sdk
    from sentry_sdk.integrations.flask import FlaskIntegration
    SENTRY_AVAILABLE = True
except ImportError:
    SENTRY_AVAILABLE = False


def create_app():
    """Factory pattern para criar a aplicação Flask"""
    
    app = Flask(__name__)
    app.config.from_object(Config)

    # ---------------------------------------------------------
    # SENTRY (MONITORAMENTO DE ERROS - PRODUÇÃO)
    # ---------------------------------------------------------
    if SENTRY_AVAILABLE and os.getenv("SENTRY_DSN"):
        try:
            sentry_sdk.init(
                dsn=os.getenv("SENTRY_DSN"),
                integrations=[FlaskIntegration()],
                traces_sample_rate=0.1,
                environment=os.getenv("FLASK_ENV", "production"),
                send_default_pii=False  # Não enviar dados pessoais
            )
            app.logger.info("Sentry initialized")
        except Exception as e:
            app.logger.warning(f"Sentry init failed: {str(e)}")

    # ---------------------------------------------------------
    # BANCO DE DADOS (SQLAlchemy 1.4 + Flask-SQLAlchemy 3.0)
    # ---------------------------------------------------------
    db.init_app(app)
    
    # Inicializar com helper (cria tabelas em dev, migrações em prod)
    init_db(app)
    
    # Flask-Migrate para versionamento de schema
    migrate = Migrate(app, db, render_as_batch=True)  # ✅ render_as_batch para SQLite compat

    # ---------------------------------------------------------
    # FLASK-LOGIN (AUTENTICAÇÃO DE USUÁRIOS)
    # ---------------------------------------------------------
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = "auth.login_page"
    login_manager.login_message = "Por favor, faça login para acessar esta página."
    login_manager.login_message_category = "info"

    @login_manager.user_loader
    def load_user(user_id):
        """Carrega usuário pelo ID para Flask-Login"""
        try:
            from models import Usuario
            # SQLAlchemy 1.4: .get() retorna None se não encontrar (não lança erro)
            return Usuario.query.get(int(user_id))
        except Exception as e:
            app.logger.error(f"Erro ao carregar usuário {user_id}: {str(e)}")
            return None

    # ---------------------------------------------------------
    # REGISTRAR BLUEPRINTS (ROTAS E APIs)
    # ---------------------------------------------------------
    register_blueprints(app)

    # ---------------------------------------------------------
    # CONTEXT PROCESSORS (VARIÁVEIS GLOBAIS PARA TEMPLATES)
    # ---------------------------------------------------------
    
    @app.context_processor
    def inject_user():
        """Disponibiliza dados do usuário para todos os templates"""
        return {
            "usuario": getattr(g, "user", None),
            "is_authenticated": hasattr(g, "user") and g.user is not None,
            "is_master": getattr(g, "user", None) and getattr(g.user, "master", False),
            "is_admin": getattr(g, "user", None) and getattr(g.user, "admin", False),
        }

    @app.context_processor
    def inject_globals():
        """Variáveis globais úteis para templates"""
        return {
            "current_year": datetime.now(timezone.utc).year,
            "app_version": "1.0.0",  # Útil para cache busting
        }

    # ---------------------------------------------------------
    # HEALTH CHECK (MONITORAMENTO E LOAD BALANCER)
    # ---------------------------------------------------------
    @app.route("/health")
    def health_check():
        """Endpoint para verificar saúde da aplicação"""
        db_status = "fail"
        
        try:
            # SQLAlchemy 1.4: usar text() para queries raw
            from sqlalchemy import text
            result = db.session.execute(text("SELECT 1"))
            if result.scalar() == 1:
                db_status = "ok"
        except Exception as e:
            app.logger.error(f"Health check DB failed: {str(e)}")
            db_status = "fail"
        
        status_code = 200 if db_status == "ok" else 503
        
        return {
            "status": "ok" if db_status == "ok" else "degraded",
            "app": "NousCard",
            "version": "1.0.0",
            "database": db_status,
            "python": sys.version.split()[0],
            "timestamp": datetime.now(timezone.utc).isoformat()
        }, status_code

    # ---------------------------------------------------------
    # FORCE HTTPS (REDIRECIONAMENTO EM PRODUÇÃO)
    # ---------------------------------------------------------
    @app.before_request
    def force_https():
        """Redireciona HTTP → HTTPS em produção"""
        # Não redirecionar em desenvolvimento ou para health check
        if os.getenv("FLASK_ENV") != "production":
            return None
        
        if request.path == "/health":
            return None
            
        if not request.is_secure and not request.headers.get("X-Forwarded-Proto") == "https":
            url = request.url.replace("http://", "https://", 1)
            return redirect(url, code=301)
        
        return None

    # ---------------------------------------------------------
    # SECURITY HEADERS (PROTEÇÃO CONTRA ATAQUES COMUNS)
    # ---------------------------------------------------------
    @app.after_request
    def add_security_headers(response):
        """Adiciona headers de segurança em todas as respostas"""
        
        # Prevenir MIME type sniffing
        response.headers['X-Content-Type-Options'] = 'nosniff'
        
        # Prevenir clickjacking
        response.headers['X-Frame-Options'] = 'DENY'
        
        # XSS protection (ainda útil em browsers antigos)
        response.headers['X-XSS-Protection'] = '1; mode=block'
        
        # Controlar referer em links externos
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        
        # Content Security Policy (CSP) - ajustar conforme necessidade
        response.headers['Content-Security-Policy'] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https:; "
            "font-src 'self' data:; "
            "connect-src 'self';"
        )
        
        # Prevenir caching de páginas sensíveis
        if request.path.startswith('/api/') or request.path.startswith('/auth/'):
            response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
            response.headers['Pragma'] = 'no-cache'
            response.headers['Expires'] = '0'
        
        return response

    # ---------------------------------------------------------
    # LOGGING CONFIGURATION (PRODUÇÃO)
    # ---------------------------------------------------------
    if not app.debug and os.getenv("FLASK_ENV") == "production":
        
        # Criar diretório de logs se não existir
        log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
        if not os.path.exists(log_dir):
            try:
                os.makedirs(log_dir)
            except OSError:
                # Fallback para /tmp se não tiver permissão
                log_dir = '/tmp/nouscard-logs'
                os.makedirs(log_dir, exist_ok=True)
        
        # Handler para arquivo com rotação
        file_handler = RotatingFileHandler(
            os.path.join(log_dir, 'nouscard.log'),
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
        ))
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)
        
        # Handler para console (útil para logs do Render)
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(logging.Formatter(
            '%(levelname)s: %(message)s'
        ))
        console_handler.setLevel(logging.INFO)
        app.logger.addHandler(console_handler)
        
        # Nível global de logging
        app.logger.setLevel(logging.INFO)
        app.logger.info("=== NousCard startup ===")
        app.logger.info(f"Environment: {os.getenv('FLASK_ENV')}")
        app.logger.info(f"Python: {sys.version.split()[0]}")

    # ---------------------------------------------------------
    # TEARDOWN: LIMPEZA DE SESSÃO APÓS CADA REQUEST
    # ---------------------------------------------------------
    @app.teardown_appcontext
    def shutdown_session(exception=None):
        """Remove sessão do banco para prevenir vazamento de conexões"""
        # Usar helper do base.py (ou manter lógica inline)
        cleanup_session(exception)

    # ---------------------------------------------------------
    # ERROR HANDLERS (PÁGINAS DE ERRO AMIGÁVEIS)
    # ---------------------------------------------------------
    
    @app.errorhandler(404)
    def not_found_error(error):
        """Handler para erro 404"""
        if request.path.startswith('/api/'):
            return {"error": "Recurso não encontrado", "status": 404}, 404
        return render_template("erro.html", mensagem="Página não encontrada."), 404

    @app.errorhandler(500)
    def internal_error(error):
        """Handler para erro 500"""
        db.session.rollback()  # Garantir rollback em caso de erro
        app.logger.error(f"Internal error: {str(error)}")
        
        if request.path.startswith('/api/'):
            return {"error": "Erro interno do servidor", "status": 500}, 500
        return render_template("erro.html", mensagem="Ocorreu um erro interno. Tente novamente."), 500

    @app.errorhandler(403)
    def forbidden_error(error):
        """Handler para erro 403"""
        if request.path.startswith('/api/'):
            return {"error": "Acesso negado", "status": 403}, 403
        return render_template("erro.html", mensagem="Acesso negado."), 403

    # ---------------------------------------------------------
    # SHELL CONTEXT (PARA flask shell)
    # ---------------------------------------------------------
    @app.shell_context_processor
    def make_shell_context():
        """Variáveis disponíveis no flask shell"""
        return {
            'db': db,
            'Usuario': None,  # Será importado dinamicamente
            'Empresa': None,
        }

    return app


# ============================================================
# INSTÂNCIA DA APLICAÇÃO
# ============================================================

app = create_app()


# ============================================================
# EXECUÇÃO DIRETA (DESENVOLVIMENTO)
# ============================================================

if __name__ == "__main__":
    # Apenas para desenvolvimento local
    print("🚀 Iniciando NousCard em modo desenvolvimento...")
    print(f"📍 Acesse: http://localhost:5000")
    
    # Desabilitar reload para evitar problemas com SQLAlchemy
    app.run(
        debug=True,
        host="127.0.0.1",
        port=5000,
        use_reloader=False  # ✅ Importante para SQLAlchemy + dev server
    )
