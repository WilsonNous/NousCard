from services.importer_db import listar_arquivos_importados, buscar_arquivo_por_id
from datetime import datetime

def gerar_detalhamento(empresa_id):

    arquivos = listar_arquivos_importados(empresa_id)

    vendas = []
    recebimentos = []

    # Carrega conteúdo completo dos arquivos
    for arq in arquivos:
        item = buscar_arquivo_por_id(arq["id"], empresa_id)
        if not item or "registros" not in item:
            continue

        for row in item["registros"]:
            if arq["tipo"] == "venda":
                vendas.append(row)
            elif arq["tipo"] == "recebimento":
                recebimentos.append(row)

    # Índice rápido de recebimentos por descrição + valor
    idx_receb = {}
    for r in recebimentos:
        chave = (r.get("descricao", ""), float(r.get("valor", 0)))
        idx_receb[chave] = r

    # Montagem da visão detalhada
    linhas = []

    for v in vendas:
        data_venda = v.get("data", "")
        valor = float(v.get("valor", 0))
        desc = v.get("descricao", "")

        adquirente = detectar_adquirente(desc)
        previsao = calcular_previsao(data_venda, adquirente)

        chave = (desc, valor)
        recebido = idx_receb.get(chave)

        linha = {
            "data_venda": data_venda,
            "adquirente": adquirente,
            "descricao": desc,
            "valor_venda": valor,
            "previsao": previsao,

            "recebido": float(recebido["valor"]) if recebido else 0.0,
            "data_recebimento": recebido.get("data") if recebido else "-",
            "banco": detectar_banco(recebido["descricao"]) if recebido else "-",

            "status": "Recebido" if recebido else "Pendente"
        }

        linhas.append(linha)

    # Ordena por data da venda
    linhas.sort(key=lambda x: x["data_venda"])

    return linhas


def detectar_adquirente(desc):
    desc = desc.lower()

    if "cielo" in desc: return "Cielo"
    if "rede" in desc: return "Rede"
    if "getnet" in desc: return "Getnet"
    if "stone" in desc: return "Stone"

    return "Desconhecida"


def detectar_banco(desc):
    desc = desc.lower()

    if "itau" in desc or "itaú" in desc: return "Itaú"
    if "bb" in desc or "brasil" in desc: return "Banco do Brasil"

    return "-"


def calcular_previsao(data_venda, adquirente):
    try:
        dv = datetime.strptime(data_venda, "%Y-%m-%d")
    except:
        return "-"

    # Prazos reais (podemos depois personalizar por empresa)
    dias = {
        "Cielo": 2,
        "Rede": 1,
        "Getnet": 2,
        "Stone": 1
    }.get(adquirente, 2)

    previsao = dv.replace(day=dv.day + dias)
    return previsao.strftime("%Y-%m-%d")
