import os
import secrets
from datetime import timedelta
from urllib.parse import quote_plus

class Config:
    # -------------------------------------------------
    # Chave de sessão (OBRIGATÓRIA em produção)
    # -------------------------------------------------
    @staticmethod
    def _get_secret_key():
        key = os.getenv("SECRET_KEY")
        if not key:
            if os.getenv("FLASK_ENV") == "production":
                raise RuntimeError("SECRET_KEY não configurada para produção!")
            return secrets.token_hex(32)
        return key
    
    SECRET_KEY = _get_secret_key()

    # -------------------------------------------------
    # Config MySQL (prioriza DATABASE_URL do Render)
    # -------------------------------------------------
    @staticmethod
    def _build_database_uri():
        if os.getenv("DATABASE_URL"):
            return os.getenv("DATABASE_URL")
        
        host = os.getenv("DB_HOST")
        user = os.getenv("DB_USER")
        password = os.getenv("DB_PASSWORD")
        name = os.getenv("DB_NAME")
        
        if not all([host, user, password, name]):
            if os.getenv("FLASK_ENV") == "production":
                raise RuntimeError("Configurações do banco incompletas!")
            return None
        
        pwd_encoded = quote_plus(password)
        return f"mysql+pymysql://{user}:{pwd_encoded}@{host}/{name}"

    SQLALCHEMY_DATABASE_URI = _build_database_uri()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Pool de conexões
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 300,
        "pool_size": int(os.getenv("DATABASE_POOL_SIZE", 10)),
    }

    # -------------------------------------------------
    # Segurança de Sessão
    # -------------------------------------------------
    PERMANENT_SESSION_LIFETIME = timedelta(
        seconds=int(os.getenv("PERMANENT_SESSION_LIFETIME", 28800))
    )
    SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "true").lower() == "true"
    SESSION_COOKIE_HTTPONLY = os.getenv("SESSION_COOKIE_HTTPONLY", "true").lower() == "true"
    SESSION_COOKIE_SAMESITE = os.getenv("SESSION_COOKIE_SAMESITE", "Lax")
    
    # -------------------------------------------------
    # Upload
    # -------------------------------------------------
    MAX_CONTENT_LENGTH = int(os.getenv("MAX_CONTENT_LENGTH", 52428800))  # 50MB
    
    # -------------------------------------------------
    # CSRF
    # -------------------------------------------------
    WTF_CSRF_ENABLED = os.getenv("WTF_CSRF_ENABLED", "true").lower() == "true"
    WTF_CSRF_TIME_LIMIT = None
    
    # -------------------------------------------------
    # Ambiente
    # -------------------------------------------------
    FLASK_ENV = os.getenv("FLASK_ENV", "development")
    FLASK_DEBUG = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    
    # -------------------------------------------------
    # Criptografia
    # -------------------------------------------------
    ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY")
    if not ENCRYPTION_KEY and FLASK_ENV == "production":
        raise RuntimeError("ENCRYPTION_KEY não configurada para produção!")
