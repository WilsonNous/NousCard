import os
import secrets
import logging
from datetime import timedelta
from urllib.parse import quote_plus
from pathlib import Path

logger = logging.getLogger(__name__)

class Config:
    # -------------------------------------------------
    # Chave de sessão (OBRIGATÓRIA em produção)
    # -------------------------------------------------
    @staticmethod
    def _get_secret_key():
        key = os.getenv("SECRET_KEY")
        if not key:
            if os.getenv("FLASK_ENV") == "production":
                raise RuntimeError("SECRET_KEY não configurada para produção! Defina via variável de ambiente.")
            # Em dev: gerar uma chave e salvar em arquivo para reuso (evita logout a cada restart)
            dev_key_file = Path(".flask_secret_key")
            if dev_key_file.exists():
                try:
                    key = dev_key_file.read_text().strip()
                    if key:
                        return key
                except Exception as e:
                    logger.warning(f"⚠️ Não foi possível ler SECRET_KEY de {dev_key_file}: {e}")
            # Gerar nova chave
            key = secrets.token_hex(32)
            try:
                dev_key_file.write_text(key)
                logger.info(f"🔑 SECRET_KEY gerada para dev e salva em {dev_key_file}")
            except Exception as e:
                logger.warning(f"⚠️ Não foi possível salvar SECRET_KEY em arquivo: {e}")
            return key
        return key
    
    SECRET_KEY = _get_secret_key()

    # -------------------------------------------------
    # Config MySQL (prioriza DATABASE_URL do Render)
    # -------------------------------------------------
    @staticmethod
    def _build_database_uri():
        # ✅ Priorizar DATABASE_URL (formato padrão do Render/Heroku)
        if os.getenv("DATABASE_URL"):
            db_url = os.getenv("DATABASE_URL")
            # Corrigir protocolo se necessário (Render usa postgres://, mas SQLAlchemy precisa postgresql://)
            if db_url.startswith("postgres://"):
                db_url = db_url.replace("postgres://", "postgresql://", 1)
                logger.info("🔄 Corrigido protocolo postgres:// → postgresql://")
            elif db_url.startswith("mysql://"):
                db_url = db_url.replace("mysql://", "mysql+pymysql://", 1)
                logger.info("🔄 Corrigido protocolo mysql:// → mysql+pymysql://")
            return db_url
        
        # Fallback: construir URI manual
        host = os.getenv("DB_HOST")
        user = os.getenv("DB_USER")
        password = os.getenv("DB_PASSWORD")
        name = os.getenv("DB_NAME")
        port = os.getenv("DB_PORT", "3306")
        
        if not all([host, user, password, name]):
            if os.getenv("FLASK_ENV") == "production":
                raise RuntimeError("Configurações do banco incompletas! Defina DATABASE_URL ou DB_HOST/DB_USER/DB_PASSWORD/DB_NAME.")
            # Em dev, permitir SQLite como fallback para testes
            logger.warning("⚠️ Configurações de banco incompletas; usando SQLite em memória para dev")
            return "sqlite:///:memory:"
        
        try:
            pwd_encoded = quote_plus(password)
            return f"mysql+pymysql://{user}:{pwd_encoded}@{host}:{port}/{name}?charset=utf8mb4"
        except Exception as e:
            logger.error(f"❌ Erro ao construir DATABASE_URI: {str(e)}")
            if os.getenv("FLASK_ENV") == "production":
                raise
            logger.warning("⚠️ Usando SQLite em memória como fallback")
            return "sqlite:///:memory:"

    SQLALCHEMY_DATABASE_URI = _build_database_uri()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # ✅ Debug de queries em desenvolvimento
    SQLALCHEMY_ECHO = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    
    # Pool de conexões
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,          # Verifica conexão antes de usar
        "pool_recycle": 300,            # Recicla conexões a cada 5min
        "pool_size": int(os.getenv("DATABASE_POOL_SIZE", 10)),
        "max_overflow": int(os.getenv("DATABASE_MAX_OVERFLOW", 20)),
        "pool_timeout": int(os.getenv("DATABASE_POOL_TIMEOUT", 30)),
    }

    # -------------------------------------------------
    # Segurança de Sessão
    # -------------------------------------------------
    PERMANENT_SESSION_LIFETIME = timedelta(
        seconds=int(os.getenv("PERMANENT_SESSION_LIFETIME", 28800))  # 8 horas padrão
    )
    # ✅ Padrão seguro: false em dev, true em produção
    _is_prod = os.getenv("FLASK_ENV") == "production"
    SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "false" if not _is_prod else "true").lower() == "true"
    SESSION_COOKIE_HTTPONLY = os.getenv("SESSION_COOKIE_HTTPONLY", "true").lower() == "true"
    SESSION_COOKIE_SAMESITE = os.getenv("SESSION_COOKIE_SAMESITE", "Lax")
    
    # ✅ Opcional: configurar SERVER_NAME para subdomínios
    SERVER_NAME = os.getenv("SERVER_NAME")  # Ex: "nouscard.com.br"
    
    # -------------------------------------------------
    # Upload
    # -------------------------------------------------
    MAX_CONTENT_LENGTH = int(os.getenv("MAX_CONTENT_LENGTH", 52428800))  # 50MB padrão
    
    # ✅ Pasta para uploads temporários (criada automaticamente)
    UPLOAD_FOLDER = os.getenv("UPLOAD_FOLDER", os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads"))
    Path(UPLOAD_FOLDER).mkdir(parents=True, exist_ok=True)
    
    # -------------------------------------------------
    # CSRF
    # -------------------------------------------------
    WTF_CSRF_ENABLED = os.getenv("WTF_CSRF_ENABLED", "true").lower() == "true"
    WTF_CSRF_TIME_LIMIT = None  # Tokens não expiram, renovados por request
    # Relaxar validação SSL em dev para localhost
    WTF_CSRF_SSL_STRICT = os.getenv("FLASK_ENV") == "production"
    
    # -------------------------------------------------
    # Ambiente
    # -------------------------------------------------
    FLASK_ENV = os.getenv("FLASK_ENV", "development")
    FLASK_DEBUG = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    LOG_LEVEL = os.getenv("LOG_LEVEL", "DEBUG" if FLASK_DEBUG else "INFO")
    
    # -------------------------------------------------
    # Criptografia
    # -------------------------------------------------
    ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY")
    if not ENCRYPTION_KEY and FLASK_ENV == "production":
        raise RuntimeError("ENCRYPTION_KEY não configurada para produção! Gere uma chave de 32 bytes e defina via variável de ambiente.")
    
    # ✅ Em dev: gerar chave temporária com warning
    if not ENCRYPTION_KEY and FLASK_ENV != "production":
        ENCRYPTION_KEY = secrets.token_hex(16)  # 128 bits para Fernet
        logger.warning(f"⚠️ ENCRYPTION_KEY gerada temporariamente para dev: {ENCRYPTION_KEY[:10]}... (NÃO USE EM PRODUÇÃO)")
    
    # -------------------------------------------------
    # Rate Limiting (opcional, se usar Flask-Limiter)
    # -------------------------------------------------
    RATELIMIT_ENABLED = os.getenv("RATELIMIT_ENABLED", "true").lower() == "true"
    RATELIMIT_DEFAULT = os.getenv("RATELIMIT_DEFAULT", "100 per hour")
    RATELIMIT_STORAGE_URL = os.getenv("RATELIMIT_STORAGE_URL", "memory://")
    
    # -------------------------------------------------
    # Email (para recuperação de senha, notificações)
    # -------------------------------------------------
    MAIL_SERVER = os.getenv("MAIL_SERVER")
    MAIL_PORT = int(os.getenv("MAIL_PORT", 587))
    MAIL_USE_TLS = os.getenv("MAIL_USE_TLS", "true").lower() == "true"
    MAIL_USERNAME = os.getenv("MAIL_USERNAME")
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD")
    MAIL_DEFAULT_SENDER = os.getenv("MAIL_DEFAULT_SENDER", "noreply@nouscard.com.br")
    
    # -------------------------------------------------
    # Sentry (monitoramento de erros)
    # -------------------------------------------------
    SENTRY_DSN = os.getenv("SENTRY_DSN")
    
    # -------------------------------------------------
    # Feature Flags (para habilitar/desabilitar recursos)
    # -------------------------------------------------
    FEATURE_PIX_ENABLED = os.getenv("FEATURE_PIX_ENABLED", "true").lower() == "true"
    FEATURE_CONCIL_AUTO = os.getenv("FEATURE_CONCIL_AUTO", "true").lower() == "true"
    FEATURE_AUDITORIA_AVANCADA = os.getenv("FEATURE_AUDITORIA_AVANCADA", "false").lower() == "true"
