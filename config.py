import os


class Config:
    # -------------------------------------------------
    # Chave de sessão
    # -------------------------------------------------
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-nouscard")

    # -------------------------------------------------
    # Config MySQL (padrão HostGator)
    # -------------------------------------------------
    DB_HOST = os.getenv("DB_HOST", "108.167.132.58")
    DB_USER = os.getenv("DB_USER", "noust785_nouscard_user")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "n0usc@rd")
    DB_NAME = os.getenv("DB_NAME", "noust785_nouscard_db")

    # -------------------------------------------------
    # SQLAlchemy (mantemos só pra não quebrar models)
    # Se quiser usar ORM no futuro, já está pronto.
    # -------------------------------------------------
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "SQLALCHEMY_DATABASE_URI",
        "mysql+pymysql://noust785_nouscard_user:n0usc%40rd@108.167.132.58/noust785_nouscard_db"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
