# services/dashboard_service.py
from collections import defaultdict
import json

from services.importer_db import listar_arquivos_importados, buscar_arquivo_por_id


def calcular_kpis(empresa_id: int):
    """
    Calcula KPIs gerais do dashboard e monta:
      - totais de vendas / recebidos / diferença
      - totais por adquirente
      - detalhamento de vendas e recebimentos (linha a linha)
    """

    # Lista resumida de arquivos da empresa
    arquivos = listar_arquivos_importados(empresa_id)

    total_vendas = 0.0
    total_recebido = 0.0

    # Totais por adquirente
    vendas_acq = defaultdict(float)
    receb_acq = defaultdict(float)

    # Detalhamento linha a linha
    detalhamento_vendas = []
    detalhamento_recebidos = []

    for arq in arquivos:
        # Busca o arquivo com registros já decodificados
        detalhado = buscar_arquivo_por_id(arq["id"], empresa_id)
        if not detalhado:
            continue

        tipo = detalhado.get("tipo", "desconhecido")
        registros = detalhado.get("registros", [])

        for row in registros:
            adquirente = (row.get("adquirente") or "Outros").strip() or "Outros"
            valor = float(row.get("valor", 0) or 0)
            data = row.get("data", "") or ""
            desc = row.get("descricao", "") or ""
            banco = row.get("banco", "") or ""
            previsao = row.get("previsao", "") or ""
            data_receb = row.get("data_recebimento", "") or ""

            if tipo == "venda":
                total_vendas += valor
                vendas_acq[adquirente] += valor

                detalhamento_vendas.append({
                    "data": data,
                    "adquirente": adquirente,
                    "descricao": desc,
                    "valor": valor,
                    "previsao": previsao,
                    "banco": banco,
                    "data_recebimento": data_receb,
                    "tipo": "venda",
                })

            elif tipo == "recebimento":
                total_recebido += valor
                receb_acq[adquirente] += valor

                detalhamento_recebidos.append({
                    "data": data,
                    "adquirente": adquirente,
                    "descricao": desc,
                    "valor": valor,
                    "previsao": previsao,
                    "banco": banco,
                    "data_recebimento": data_receb,
                    "tipo": "recebimento",
                })

    diferenca = total_vendas - total_recebido

    # Monta mapa final por adquirente
    acquirers = {}
    for acq in set(list(vendas_acq.keys()) + list(receb_acq.keys())):
        v = vendas_acq.get(acq, 0.0)
        r = receb_acq.get(acq, 0.0)
        acquirers[acq] = {
            "vendas": round(v, 2),
            "recebidos": round(r, 2),
            "diferenca": round(v - r, 2),
        }

    return {
        "total_vendas": round(total_vendas, 2),
        "total_recebido": round(total_recebido, 2),
        "diferenca": round(diferenca, 2),
        "alertas": 0,  # mais pra frente podemos calcular
        "acquirers": acquirers,
        "detalhamento": {
            "vendas": detalhamento_vendas,
            "recebidos": detalhamento_recebidos,
        },
    }
