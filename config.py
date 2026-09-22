import os
import secrets
import logging
from datetime import timedelta
from pathlib import Path

from sqlalchemy.engine import URL

logger = logging.getLogger(__name__)


class Config:
    # -------------------------------------------------
    # Ambiente
    # -------------------------------------------------
    FLASK_ENV = os.getenv("FLASK_ENV", "development")
    FLASK_DEBUG = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    LOG_LEVEL = os.getenv(
        "LOG_LEVEL",
        "DEBUG" if FLASK_DEBUG else "INFO"
    )

    # -------------------------------------------------
    # Chave de sessão
    # -------------------------------------------------
    @staticmethod
    def _get_secret_key():
        key = os.getenv("SECRET_KEY")

        if key:
            return key

        if os.getenv("FLASK_ENV", "development") == "production":
            raise RuntimeError(
                "SECRET_KEY não configurada para produção! "
                "Defina via variável de ambiente."
            )

        dev_key_file = Path(".flask_secret_key")

        if dev_key_file.exists():
            try:
                key = dev_key_file.read_text().strip()

                if key:
                    return key

            except Exception as e:
                logger.warning(
                    f"⚠️ Não foi possível ler SECRET_KEY "
                    f"de {dev_key_file}: {e}"
                )

        key = secrets.token_hex(32)

        try:
            dev_key_file.write_text(key)
            logger.info(
                f"🔑 SECRET_KEY gerada para dev "
                f"e salva em {dev_key_file}"
            )

        except Exception as e:
            logger.warning(
                f"⚠️ Não foi possível salvar SECRET_KEY "
                f"em arquivo: {e}"
            )

        return key

    SECRET_KEY = _get_secret_key()

    # -------------------------------------------------
    # Banco de dados
    #
    # PRIORIDADE:
    # 1 - DB_HOST / DB_USER / DB_PASSWORD / DB_NAME
    # 2 - DATABASE_URL
    # 3 - SQLite somente em desenvolvimento
    # -------------------------------------------------
    @staticmethod
    def _build_database_uri():

        host = os.getenv("DB_HOST")
        user = os.getenv("DB_USER")
        password = os.getenv("DB_PASSWORD")
        name = os.getenv("DB_NAME")
        port = os.getenv("DB_PORT", "3306")

        # ---------------------------------------------
        # OPÇÃO 1 - Variáveis separadas
        # ---------------------------------------------
        if all([host, user, password, name]):

            try:
                port = int(port)

            except ValueError:
                raise RuntimeError(
                    f"DB_PORT inválida: {port}"
                )

            logger.info(
                f"🗄️ Banco configurado via DB_* "
                f"({host}:{port}/{name})"
            )

            #
            # URL.create trata corretamente senhas com:
            #
            # @
            # #
            # %
            # :
            # /
            #
            # Não precisamos usar quote_plus().
            #
            return URL.create(
                drivername="mysql+pymysql",
                username=user,
                password=password,
                host=host,
                port=port,
                database=name,
                query={
                    "charset": "utf8mb4"
                },
            )

        # ---------------------------------------------
        # OPÇÃO 2 - DATABASE_URL
        # Mantida por compatibilidade
        # ---------------------------------------------
        db_url = os.getenv("DATABASE_URL")

        if db_url:

            if db_url.startswith("postgres://"):
                db_url = db_url.replace(
                    "postgres://",
                    "postgresql://",
                    1
                )

                logger.info(
                    "🔄 Corrigido protocolo "
                    "postgres:// → postgresql://"
                )

            elif db_url.startswith("mysql://"):
                db_url = db_url.replace(
                    "mysql://",
                    "mysql+pymysql://",
                    1
                )

                logger.info(
                    "🔄 Corrigido protocolo "
                    "mysql:// → mysql+pymysql://"
                )

            logger.info(
                "🗄️ Banco configurado via DATABASE_URL"
            )

            return db_url

        # ---------------------------------------------
        # Nenhuma configuração encontrada
        # ---------------------------------------------
        if os.getenv(
            "FLASK_ENV",
            "development"
        ) == "production":

            raise RuntimeError(
                "Configurações do banco incompletas! "
                "Defina DB_HOST, DB_USER, DB_PASSWORD, "
                "DB_NAME e DB_PORT ou DATABASE_URL."
            )

        logger.warning(
            "⚠️ Banco não configurado. "
            "Usando SQLite em memória apenas para desenvolvimento."
        )

        return "sqlite:///:memory:"

    SQLALCHEMY_DATABASE_URI = _build_database_uri()

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    SQLALCHEMY_ECHO = (
        os.getenv(
            "FLASK_DEBUG",
            "false"
        ).lower() == "true"
    )

    # -------------------------------------------------
    # Pool de conexões
    # -------------------------------------------------
    #
    # IMPORTANTE:
    # As opções abaixo são adequadas para MySQL/PostgreSQL.
    #
    # Como produção obrigatoriamente deve ter banco configurado,
    # não teremos mais o problema anterior do SQLite + pool_size.
    #
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 300,
        "pool_size": int(
            os.getenv(
                "DATABASE_POOL_SIZE",
                10
            )
        ),
        "max_overflow": int(
            os.getenv(
                "DATABASE_MAX_OVERFLOW",
                20
            )
        ),
        "pool_timeout": int(
            os.getenv(
                "DATABASE_POOL_TIMEOUT",
                30
            )
        ),
    }

    # -------------------------------------------------
    # Segurança de sessão
    # -------------------------------------------------
    PERMANENT_SESSION_LIFETIME = timedelta(
        seconds=int(
            os.getenv(
                "PERMANENT_SESSION_LIFETIME",
                28800
            )
        )
    )

    _is_prod = (
        os.getenv(
            "FLASK_ENV",
            "development"
        ) == "production"
    )

    SESSION_COOKIE_SECURE = (
        os.getenv(
            "SESSION_COOKIE_SECURE",
            "true" if _is_prod else "false"
        ).lower() == "true"
    )

    SESSION_COOKIE_HTTPONLY = (
        os.getenv(
            "SESSION_COOKIE_HTTPONLY",
            "true"
        ).lower() == "true"
    )

    SESSION_COOKIE_SAMESITE = os.getenv(
        "SESSION_COOKIE_SAMESITE",
        "Lax"
    )

    SERVER_NAME = os.getenv("SERVER_NAME")

    # -------------------------------------------------
    # Upload
    # -------------------------------------------------
    MAX_CONTENT_LENGTH = int(
        os.getenv(
            "MAX_CONTENT_LENGTH",
            52428800
        )
    )

    UPLOAD_FOLDER = os.getenv(
        "UPLOAD_FOLDER",
        os.path.join(
            os.path.dirname(
                os.path.abspath(__file__)
            ),
            "uploads"
        )
    )

    Path(
        UPLOAD_FOLDER
    ).mkdir(
        parents=True,
        exist_ok=True
    )

    # -------------------------------------------------
    # CSRF
    # -------------------------------------------------
    WTF_CSRF_ENABLED = (
        os.getenv(
            "WTF_CSRF_ENABLED",
            "true"
        ).lower() == "true"
    )

    WTF_CSRF_TIME_LIMIT = None

    WTF_CSRF_SSL_STRICT = _is_prod

    # -------------------------------------------------
    # Criptografia
    # -------------------------------------------------
    ENCRYPTION_KEY = os.getenv(
        "ENCRYPTION_KEY"
    )

    if (
        not ENCRYPTION_KEY
        and FLASK_ENV == "production"
    ):
        raise RuntimeError(
            "ENCRYPTION_KEY não configurada "
            "para produção!"
        )

    if (
        not ENCRYPTION_KEY
        and FLASK_ENV != "production"
    ):
        ENCRYPTION_KEY = secrets.token_hex(16)

        logger.warning(
            "⚠️ ENCRYPTION_KEY temporária "
            "gerada para desenvolvimento."
        )

    # -------------------------------------------------
    # Rate Limiting
    # -------------------------------------------------
    RATELIMIT_ENABLED = (
        os.getenv(
            "RATELIMIT_ENABLED",
            "true"
        ).lower() == "true"
    )

    RATELIMIT_DEFAULT = os.getenv(
        "RATELIMIT_DEFAULT",
        "100 per hour"
    )

    RATELIMIT_STORAGE_URL = os.getenv(
        "RATELIMIT_STORAGE_URL",
        "memory://"
    )

    # -------------------------------------------------
    # Email
    # -------------------------------------------------
    MAIL_SERVER = os.getenv(
        "MAIL_SERVER"
    )

    MAIL_PORT = int(
        os.getenv(
            "MAIL_PORT",
            587
        )
    )

    MAIL_USE_TLS = (
        os.getenv(
            "MAIL_USE_TLS",
            "true"
        ).lower() == "true"
    )

    MAIL_USERNAME = os.getenv(
        "MAIL_USERNAME"
    )

    MAIL_PASSWORD = os.getenv(
        "MAIL_PASSWORD"
    )

    MAIL_DEFAULT_SENDER = os.getenv(
        "MAIL_DEFAULT_SENDER",
        "noreply@nouscard.com.br"
    )

    # -------------------------------------------------
    # Sentry
    # -------------------------------------------------
    SENTRY_DSN = os.getenv(
        "SENTRY_DSN"
    )

    # -------------------------------------------------
    # Feature Flags
    # -------------------------------------------------
    FEATURE_PIX_ENABLED = (
        os.getenv(
            "FEATURE_PIX_ENABLED",
            "true"
        ).lower() == "true"
    )

    FEATURE_CONCIL_AUTO = (
        os.getenv(
            "FEATURE_CONCIL_AUTO",
            "true"
        ).lower() == "true"
    )

    FEATURE_AUDITORIA_AVANCADA = (
        os.getenv(
            "FEATURE_AUDITORIA_AVANCADA",
            "false"
        ).lower() == "true"
    )
