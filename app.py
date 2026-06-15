# ============================================================
#  APP • NousCard (PRODUÇÃO)
#  Compatível com SQLAlchemy 1.4.x + Flask-SQLAlchemy 3.0.x
#  Garantindo instância única do db
# ============================================================

# app.py
from utils.context_processors import inject_global_vars
# ✅ NOVO: Helpers de timezone brasileiro
from utils.timezone_helpers import format_brazilia, format_brazilia_full, to_brazilia, agora_brasil

from flask import Flask, g, request, redirect, url_for, session, jsonify
from config import Config
from models.base import db, init_db, cleanup_session  # ✅ ÚNICO import do db
from routes import register_blueprints
from datetime import datetime, timezone, timedelta
from flask_migrate import Migrate
from flask_login import LoginManager
import logging
from logging.handlers import RotatingFileHandler
import os
import sys
import secrets

# Sentry (import condicional)
try:
    import sentry_sdk
    from sentry_sdk.integrations.flask import FlaskIntegration
    SENTRY_AVAILABLE = True
except ImportError:
    SENTRY_AVAILABLE = False


# Flag para garantir inicialização única
_db_initialized = False


def create_app(config_class=Config):
    """
    Factory pattern para criar a aplicação Flask.
    Garante que db.init_app() seja chamado apenas uma vez.
    """
    global _db_initialized
    
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    # ✅ VALIDAÇÃO CRÍTICA: SECRET_KEY em produção
    if os.getenv("FLASK_ENV") == "production" and not app.config.get("SECRET_KEY"):
        raise RuntimeError(
            "SECRET_KEY não definida em produção! "
            "Defina uma chave segura em config.py ou via variável de ambiente."
        )
    
    # ✅ CONFIGURAÇÕES DE SESSÃO SEGURA
    if os.getenv("FLASK_ENV") == "production":
        app.config.update(
            SESSION_COOKIE_SECURE=True,
            SESSION_COOKIE_HTTPONLY=True,
            SESSION_COOKIE_SAMESITE='Lax',
            PERMANENT_SESSION_LIFETIME=timedelta(hours=8),
            WTF_CSRF_ENABLED=True,
            WTF_CSRF_TIME_LIMIT=None
        )
    
    # Registrar context processor
    app.context_processor(inject_global_vars)
    
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
                send_default_pii=False,
                before_send=lambda event, hint: add_business_tags(event)
            )
            app.logger.info("Sentry initialized")
        except Exception as e:
            app.logger.warning(f"Sentry init failed: {str(e)}")
    
    def add_business_tags(event):
        """Adiciona tags de negócio para métricas no Sentry"""
        try:
            if hasattr(g, 'user') and g.user:
                event.setdefault('tags', {})['user_role'] = 'master' if g.user.master else 'admin' if g.user.admin else 'user'
                event['tags']['empresa_id'] = getattr(g.user, 'empresa_id', None)
        except:
            pass
        return event

    # ---------------------------------------------------------
    # BANCO DE DADOS (INICIALIZAÇÃO ÚNICA)
    # ---------------------------------------------------------
    
    if not _db_initialized:
        db.init_app(app)
        _db_initialized = True
    
    migrate = Migrate(app, db, render_as_batch=True)

    # ---------------------------------------------------------
    # FLASK-LOGIN (AUTENTICAÇÃO DE USUÁRIOS)
    # ---------------------------------------------------------
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = "auth.login_page"
    login_manager.login_message = "Por favor, faça login para acessar esta página."
    login_manager.login_message_category = "info"
    
    login_manager.remember_cookie_duration = timedelta(days=7)

    @login_manager.user_loader
    def load_user(user_id):
        """Carrega usuário pelo ID para Flask-Login"""
        try:
            from models import Usuario
            return Usuario.query.get(int(user_id))
        except Exception as e:
            app.logger.error(f"Erro ao carregar usuário {user_id}: {str(e)}")
            return None

    # ---------------------------------------------------------
    # REGISTRAR BLUEPRINTS (ROTAS E APIs)
    # ---------------------------------------------------------
    register_blueprints(app)

    # ✅ REGISTRAR FILTERS JINJA2 PERSONALIZADOS (PARA TEMPLATES)
    try:
        from utils.filters import register_filters
        register_filters(app)
        app.logger.info("✅ Custom Jinja2 filters registered")
    except ImportError as e:
        app.logger.warning(f"⚠️ Custom filters not loaded: {str(e)}")
    except Exception as e:
        app.logger.error(f"❌ Error registering filters: {str(e)}")

    # ✅ NOVO: FILTROS DE HORÁRIO BRASILEIRO (UTC-3)
    # ============================================================
    # Disponibiliza filtros em todos os templates:
    #   {{ data | hora_brasil }}         → "09/06/2026 19:30"
    #   {{ data | hora_brasil('%H:%M') }} → "19:30"
    #   {{ data | hora_brasil_full }}     → "Segunda, 09/06/2026 às 19:30"
    # ============================================================
    try:
        @app.template_filter('hora_brasil')
        def filter_hora_brasil(dt, fmt="%d/%m/%Y %H:%M"):
            """Formata datetime no fuso de Brasília (America/Sao_Paulo)"""
            return format_brazilia(dt, fmt)

        @app.template_filter('hora_brasil_full')
        def filter_hora_brasil_full(dt):
            """Formata datetime completo com dia da semana em Brasília"""
            return format_brazilia_full(dt)

        app.logger.info("✅ Filtros de horário brasileiro registrados (hora_brasil, hora_brasil_full)")
    except Exception as e:
        app.logger.error(f"❌ Erro ao registrar filtros de horário: {str(e)}")

    # ✅ FILTROS FINANCEIROS PARA TEMPLATES (BRL + COMPARAÇÕES)
    # ============================================================
    # Disponibiliza em todos os templates:
    #   {{ valor|format_brl }}      → "R$ 1.234,56"
    #   {{ valor|safe_float }}      → 1234.56 (para comparações)
    # ============================================================
    try:
        @app.template_filter('format_brl')
        def filter_format_brl(value):
            """
            Formata valor para BRL no template.
            Aceita: str, int, float, Decimal, None
            Exemplo: 1234.56 → "1.234,56"
            """
            from decimal import Decimal
            
            if value is None:
                return "0,00"
            try:
                # Converte para float se for string
                if isinstance(value, str):
                    # Remove R$, espaços e converte vírgula para ponto
                    value = value.replace("R$", "").replace(" ", "").replace(".", "").replace(",", ".")
                    num = float(value)
                elif isinstance(value, Decimal):
                    num = float(value)
                else:
                    num = float(value)
                
                # Formata para padrão brasileiro: 1234.56 → "1.234,56"
                return f"{num:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            except Exception as e:
                app.logger.debug(f"⚠️ format_brl fallback: {str(e)}")
                return "0,00"

        @app.template_filter('safe_float')
        def filter_safe_float(value):
            """
            Converte valor para float de forma segura para comparações no template.
            Exemplo: "R$ 1.234,56" → 1234.56
            """
            from decimal import Decimal
            
            if value is None:
                return 0.0
            try:
                if isinstance(value, str):
                    # Remove formatação BRL e converte
                    value = value.replace("R$", "").replace(" ", "").replace(".", "").replace(",", ".")
                if isinstance(value, Decimal):
                    return float(value)
                return float(value)
            except Exception as e:
                app.logger.debug(f"⚠️ safe_float fallback: {str(e)}")
                return 0.0

        app.logger.info("✅ Filtros financeiros registrados (format_brl, safe_float)")
    except Exception as e:
        app.logger.error(f"❌ Erro ao registrar filtros financeiros: {str(e)}")

    # ✅ Blueprint de Usuários (Gestão pelo Master)
    from routes.usuarios_routes import usuarios_bp
    app.register_blueprint(usuarios_bp)

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
            "app_version": "1.0.0",
            "csrf_token": session.get('csrf_token', ''),
        }

    # ✅ NOVO: CONTEXT PROCESSOR DE HORÁRIO BRASILEIRO
    # Disponibiliza 'agora_brasil' em TODOS os templates
    # Uso: {{ agora_brasil | hora_brasil }}
    @app.context_processor
    def inject_agora_brasil():
        """Injeta horário atual de Brasília em todos os templates"""
        return {
            'agora_brasil': agora_brasil()
        }
    
    # ✅ Helper para gerar token CSRF se não existir
    @app.before_request
    def ensure_csrf_token():
        """Garante que token CSRF exista na sessão"""
        if 'csrf_token' not in session:
            session['csrf_token'] = secrets.token_urlsafe(32)
            session.modified = True
        
        g.csrf_token = session['csrf_token']

    # ---------------------------------------------------------
    # HEALTH CHECK (MONITORAMENTO E LOAD BALANCER)
    # ---------------------------------------------------------
    @app.route("/health")
    def health_check():
        """Endpoint para verificar saúde da aplicação"""
        db_status = "fail"
        db_latency_ms = None
        
        try:
            from sqlalchemy import text
            start = datetime.now()
            result = db.session.execute(text("SELECT 1"))
            if result.scalar() == 1:
                db_status = "ok"
                db_latency_ms = (datetime.now() - start).total_seconds() * 1000
        except Exception as e:
            app.logger.error(f"Health check DB failed: {str(e)}")
            db_status = "fail"
        
        status_code = 200 if db_status == "ok" else 503
        
        if db_status == "fail":
            app.logger.warning(f"Health check degraded: db_latency={db_latency_ms}ms")
        
        return jsonify({
            "status": "ok" if db_status == "ok" else "degraded",
            "app": "NousCard",
            "version": "1.0.0",
            "database": db_status,
            "db_latency_ms": db_latency_ms,
            "python": sys.version.split()[0],
            "timestamp": datetime.now(timezone.utc).isoformat()
        }), status_code

    # ---------------------------------------------------------
    # FORCE HTTPS (REDIRECIONAMENTO EM PRODUÇÃO)
    # ---------------------------------------------------------
    @app.before_request
    def force_https():
        """Redireciona HTTP → HTTPS em produção"""
        if os.getenv("FLASK_ENV") != "production":
            return None
        
        if request.path == "/health":
            return None
            
        if not request.is_secure and request.headers.get("X-Forwarded-Proto") != "https":
            url = request.url.replace("http://", "https://", 1)
            return redirect(url, code=301)
        
        return None

    # ---------------------------------------------------------
    # SECURITY HEADERS (PROTEÇÃO CONTRA ATAQUES COMUNS)
    # ---------------------------------------------------------
    @app.after_request
    def add_security_headers(response):
        """Adiciona headers de segurança em todas as respostas"""
        
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        
        response.headers['Content-Security-Policy'] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' https: data:; "
            "font-src 'self' data:; "
            "connect-src 'self' https://cdn.jsdelivr.net;"
        )
        
        if request.path.startswith('/api/') or request.path.startswith('/auth/'):
            response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
            response.headers['Pragma'] = 'no-cache'
            response.headers['Expires'] = '0'
        
        return response

    # ---------------------------------------------------------
    # LOGGING CONFIGURATION (PRODUÇÃO)
    # ---------------------------------------------------------
    if not app.debug and os.getenv("FLASK_ENV") == "production":
        
        log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
        if not os.path.exists(log_dir):
            try:
                os.makedirs(log_dir)
            except OSError:
                log_dir = '/tmp/nouscard-logs'
                os.makedirs(log_dir, exist_ok=True)
        
        file_handler = RotatingFileHandler(
            os.path.join(log_dir, 'nouscard.log'),
            maxBytes=10 * 1024 * 1024,
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
        ))
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)
        
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(logging.Formatter('%(levelname)s: %(message)s'))
        console_handler.setLevel(logging.INFO)
        app.logger.addHandler(console_handler)
        
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
        cleanup_session(exception)

    # ---------------------------------------------------------
    # ERROR HANDLERS (PÁGINAS DE ERRO AMIGÁVEIS)
    # ---------------------------------------------------------
    
    @app.errorhandler(404)
    def not_found_error(error):
        """Handler para erro 404"""
        if request.path.startswith('/api/'):
            return jsonify({"error": "Recurso não encontrado", "status": 404}), 404
        
        try:
            from flask import render_template
            return render_template("erro.html", mensagem="Página não encontrada.", error_code=404), 404
        except Exception as e:
            app.logger.error(f"Erro ao renderizar 404: {str(e)}")
            return jsonify({"error": "Página não encontrada"}), 404

    @app.errorhandler(500)
    def internal_error(error):
        """Handler para erro 500"""
        db.session.rollback()
        app.logger.error(f"Internal error: {str(error)}", exc_info=True)
        
        if request.path.startswith('/api/'):
            return jsonify({"error": "Erro interno do servidor", "status": 500}), 500
        
        try:
            from flask import render_template
            return render_template("erro.html", mensagem="Ocorreu um erro interno. Tente novamente.", error_code=500), 500
        except Exception as e:
            app.logger.critical(f"Fallback error handler failed: {str(e)}")
            return jsonify({"error": "Erro crítico no servidor"}), 500

    @app.errorhandler(403)
    def forbidden_error(error):
        """Handler para erro 403"""
        if request.path.startswith('/api/'):
            return jsonify({"error": "Acesso negado", "status": 403}), 403
        try:
            from flask import render_template
            return render_template("erro.html", mensagem="Acesso negado.", error_code=403), 403
        except:
            return jsonify({"error": "Acesso negado"}), 403

    # ---------------------------------------------------------
    # SHELL CONTEXT (PARA flask shell)
    # ---------------------------------------------------------
    @app.shell_context_processor
    def make_shell_context():
        """Variáveis disponíveis no flask shell"""
        return {'db': db}

    return app


# ============================================================
# INSTÂNCIA DA APLICAÇÃO (PARA GUNICORN)
# ============================================================

app = create_app()


# ============================================================
# EXECUÇÃO DIRETA (DESENVOLVIMENTO)
# ============================================================

if __name__ == "__main__":
    print("🚀 Iniciando NousCard em modo desenvolvimento...")
    print(f"📍 Acesse: http://localhost:5000")
    
    app.run(
        debug=True,
        host="127.0.0.1",
        port=5000,
        use_reloader=False
    )
