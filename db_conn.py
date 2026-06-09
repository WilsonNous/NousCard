# utils/database.py
from contextlib import contextmanager
from sqlalchemy import text
from models.base import db
import logging

logger = logging.getLogger(__name__)


@contextmanager
def get_db_connection():
    """
    Context manager para conexão bruta com MySQL via SQLAlchemy.
    
    ✅ Vantagens:
    - Reutiliza pool de conexões do SQLAlchemy
    - Compatível com config.py (DATABASE_URL)
    - Auto-reconnect via pool_pre_ping
    - Cleanup automático no teardown
    
    Usage:
        with get_db_connection() as conn:
            result = conn.execute(text("SELECT * FROM usuarios"))
            rows = result.fetchall()
    """
    conn = None
    try:
        # ✅ Obter conexão bruta do engine do SQLAlchemy
        conn = db.engine.raw_connection()
        # Garantir que resultados venham como dict (compatível com código existente)
        conn.cursor = lambda: conn.connection.cursor(cursorclass='DictCursor')
        yield conn
        conn.commit()
    except Exception as e:
        logger.error(f"❌ Erro na conexão com banco: {str(e)}")
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            conn.close()


def execute_query(query: str, params: tuple = None):
    """
    Executa query SQL e retorna resultados como lista de dicts.
    
    Args:
        query: SQL com placeholders %(nome)s
        params: dict ou tuple de parâmetros
    
    Returns:
        Lista de dicts com resultados
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(query, params or {})
            if cursor.description:  # Query retorna dados (SELECT)
                columns = [desc[0] for desc in cursor.description]
                return [dict(zip(columns, row)) for row in cursor.fetchall()]
            return []  # Query sem retorno (INSERT/UPDATE/DELETE)
        finally:
            cursor.close()


def execute_update(query: str, params: tuple = None) -> int:
    """
    Executa query de atualização e retorna número de linhas afetadas.
    
    Args:
        query: SQL com placeholders %(nome)s
        params: dict ou tuple de parâmetros
    
    Returns:
        Número de linhas afetadas
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(query, params or {})
            return cursor.rowcount
        finally:
            cursor.close()
