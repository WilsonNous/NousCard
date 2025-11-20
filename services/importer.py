# services/importer.py

import os
from utils.parsers import (
    parse_csv_generic,
    parse_excel_generic,
    parse_ofx_generic
)


def process_uploaded_files(files):
    """
    Processa todos os arquivos enviados.
    Retorna lista de resultados por arquivo.
    """

    resultados = []

    for file in files:
        nome = file.filename.lower()

        if nome.endswith(".csv"):
            data = parse_csv_generic(file)
            resultados.append({"arquivo": nome, "linhas": len(data)})

        elif nome.endswith(".xlsx") or nome.endswith(".xls"):
            data = parse_excel_generic(file)
            resultados.append({"arquivo": nome, "linhas": len(data)})

        elif nome.endswith(".ofx"):
            data = parse_ofx_generic(file)
            resultados.append({"arquivo": nome, "linhas": len(data)})

        else:
            resultados.append({
                "arquivo": nome,
                "erro": "Formato não suportado"
            })

    return resultados
