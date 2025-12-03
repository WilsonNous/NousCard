from sqlalchemy import text
from models.base import db

def calcular_kpis(empresa_id):

    sql = """
        SELECT tipo, SUM(total_valor) AS soma
        FROM arquivos_importados
        WHERE empresa_id = :empresa_id
        GROUP BY tipo
    """

    result = db.session.execute(text(sql), {"empresa_id": empresa_id}).mappings()

    total_vendas = 0.0
    total_recebido = 0.0

    for row in result:
        if row["tipo"] == "venda":
            total_vendas = float(row["soma"] or 0)
        elif row["tipo"] == "recebimento":
            total_recebido = float(row["soma"] or 0)

    diferenca = total_vendas - total_recebido

    return {
        "total_vendas": total_vendas,
        "total_recebido": total_recebido,
        "diferenca": diferenca,
        "alertas": 0,  # Depois calculamos divergências reais
    }
