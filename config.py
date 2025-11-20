import os

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-nouscard")

    SQLALCHEMY_DATABASE_URI = (
        "mysql+pymysql://noust785_nouscard_user:n0usc%40rd@108.167.132.58/noust785_nouscard_db"
    )

    SQLALCHEMY_TRACK_MODIFICATIONS = False
