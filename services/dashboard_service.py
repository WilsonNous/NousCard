# services/dashboard_service.py

from services.importer_db import listar_arquivos_importados
import re

# =====================================================================
# Identificação da bandeira com base na descrição
# =====================================================================
def detectar_bandeira(descricao: str):
    """
    Identifica bandeira analisando o texto da descrição (case-insensitive)
    """
    if not descricao:
        return "Outros"

    desc = descricao.lower()

    if "visa" in desc:
        return "Visa"
    if "master" in desc or "mastercard" in desc:
        return "Mastercard"
    if "elo" in desc:
        return "Elo"
    if "hiper" in desc:
        return "Hipercard"
    if "amex" in desc or "american express" in desc:
        return "Amex"
    if "pix" in desc:
        return "Pix"

    return "Outros"


# =====================================================================
# Cálculo de KPIs gerais + bandeiras
# =====================================================================
def calcular_kpis(empresa_id):
    arquivos = listar_arquivos_importados(empresa_id)

    total_vendas = 0
    total_recebido = 0

    # Bandeiras
    bandeiras = {}

    for arq in arquivos:

        # TOTALIZAÇÃO
        if arq["tipo"] == "venda":
            total_vendas += arq["total_valor"]
        elif arq["tipo"] == "recebimento":
            total_recebido += arq["total_valor"]

        # PROCESSAMENTO DE BANDEIRA
        if arq["tipo"] != "venda":
            continue

        # Recuperar registros detalhados
        registros = arq.get("registros", [])

        for row in registros:
            descricao = row.get("descricao", "")
            valor = float(row.get("valor", 0))

            bandeira = detectar_bandeira(descricao)

            bandeiras[bandeira] = bandeiras.get(bandeira, 0) + valor

    diferenca = round(total_vendas - total_recebido, 2)

    return {
        "total_vendas": round(total_vendas, 2),
        "total_recebido": round(total_recebido, 2),
        "diferenca": diferenca,
        "alertas": 0,
        "bandeiras": bandeiras  # 🔥 gráfico usa isso
    }
