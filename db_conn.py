import pymysql
from config import Config


def get_conn():
    """
    Abre conexão com MySQL usando padrão DictCursor.
    Usar SEMPRE essa função para conversar com o banco.
    """
    return pymysql.connect(
        host=Config.DB_HOST,
        user=Config.DB_USER,
        password=Config.DB_PASSWORD,
        database=Config.DB_NAME,
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True,
        charset="utf8mb4",
        connect_timeout=5,
    )
