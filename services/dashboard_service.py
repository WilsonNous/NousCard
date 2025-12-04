from services.importer_db import listar_arquivos_importados, buscar_arquivo_por_id
import json
import re

def detectar_bandeira(descricao):
    if not descricao:
        return "Outros"

    descricao = descricao.lower()

    if "visa" in descricao:
        return "Visa"
    if "master" in descricao or "mc" in descricao:
        return "Mastercard"
    if "elo" in descricao:
        return "Elo"
    if "amex" in descricao or "american" in descricao:
        return "Amex"
    if "hiper" in descricao:
        return "Hipercard"
    if "pix" in descricao:
        return "PIX"

    return "Outros"


def calcular_kpis(empresa_id):

    arquivos = listar_arquivos_importados(empresa_id)

    total_vendas = 0
    total_recebido = 0
    bandeiras = {}

    # --------------------------------------------------------------------
    # PERCORRE TODOS OS ARQUIVOS E SEUS REGISTROS
    # --------------------------------------------------------------------
    for arq in arquivos:
        arq_det = buscar_arquivo_por_id(arq["id"], empresa_id)
        registros = arq_det.get("registros", [])

        if arq["tipo"] == "venda":
            total_vendas += arq["total_valor"]

            # Agrupar bandeiras
            for r in registros:
                descricao = r.get("descricao", "")
                bandeira = detectar_bandeira(descricao)
                valor = float(r.get("valor", 0))

                bandeiras[bandeira] = bandeiras.get(bandeira, 0) + valor

        elif arq["tipo"] == "recebimento":
            total_recebido += arq["total_valor"]

    diferenca = total_vendas - total_recebido

    # --------------------------------------------------------------------
    # RETORNO FINAL COMPLETO PARA O FRONT-END
    # --------------------------------------------------------------------
    return {
        "total_vendas": round(total_vendas, 2),
        "total_recebido": round(total_recebido, 2),
        "diferenca": round(diferenca, 2),
        "alertas": 0,   # ainda vamos implementar
        "bandeiras": bandeiras,
    }
