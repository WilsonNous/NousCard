# services/dashboard_service.py

from services.importer_db import listar_arquivos_importados, buscar_arquivo_por_id

# ------------------------------------------------------------
# Detectar bandeira
# ------------------------------------------------------------
def detectar_bandeira(descricao: str):
    if not descricao:
        return "Outros"

    desc = descricao.lower()

    if "visa" in desc:
        return "Visa"
    if "master" in desc or "mc " in desc:
        return "Mastercard"
    if "elo" in desc:
        return "Elo"
    if "hiper" in desc:
        return "Hiper"
    if "amex" in desc:
        return "Amex"

    return "Outros"


# ------------------------------------------------------------
# Detectar adquirente
# ------------------------------------------------------------
def detectar_adquirente(descricao: str):
    if not descricao:
        return "Outros"

    desc = descricao.lower()

    if "cielo" in desc:
        return "Cielo"
    if "rede" in desc:
        return "Rede"
    if "getnet" in desc or "get net" in desc:
        return "Getnet"
    if "stone" in desc:
        return "Stone"
    if "santander" in desc:
        return "Santander"
    if "pagseguro" in desc or "pag seguro" in desc:
        return "PagSeguro"

    return "Outros"


# ------------------------------------------------------------
# Calcular todos KPIs + bandeiras + adquirentes
# ------------------------------------------------------------
def calcular_kpis(empresa_id):
    arquivos = listar_arquivos_importados(empresa_id)

    total_vendas = 0
    total_recebido = 0
    bandeiras = {}
    adquirentes = {}

    for arq in arquivos:
        arq_det = buscar_arquivo_por_id(arq["id"], empresa_id)
        registros = arq_det.get("registros", [])

        # VENDAS ----------------------------------------------------
        if arq["tipo"] == "venda":
            total_vendas += arq["total_valor"]

            for r in registros:
                descricao = r.get("descricao", "")
                valor = float(r.get("valor", 0))

                b = detectar_bandeira(descricao)
                bandeiras[b] = bandeiras.get(b, 0) + valor

                adq = detectar_adquirente(descricao)
                adquirentes[adq] = adquirentes.get(adq, 0) + valor

        # RECEBIMENTOS ----------------------------------------------
        elif arq["tipo"] == "recebimento":
            total_recebido += arq["total_valor"]

    diferenca = total_vendas - total_recebido

    return {
        "total_vendas": round(total_vendas, 2),
        "total_recebido": round(total_recebido, 2),
        "diferenca": round(diferenca, 2),
        "alertas": 0,
        "bandeiras": bandeiras,
        "adquirentes": adquirentes,
    }
