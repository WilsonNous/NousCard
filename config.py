import os

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-nouscard")
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL",
        "mysql+pymysql://usuario:senha@host:3306/nouscard_db"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # Outros ajustes futuros (LOG_LEVEL, etc.)
