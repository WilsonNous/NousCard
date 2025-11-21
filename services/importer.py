# services/importer.py

import os
from utils.parsers import (
    parse_csv_generic,
    parse_excel_generic,
    parse_ofx_generic
)

from utils.helpers import gerar_hash_arquivo
from services.importer_db import salvar_arquivo_importado


def identificar_tipo(nome_arquivo: str) -> str:
    """Identifica automaticamente se o arquivo é de vendas ou recebimentos."""
    nome = nome_arquivo.lower()

    if "receb" in nome or "extrato" in nome or "ofx" in nome:
        return "recebimento"

    if "venda" in nome or "transacao" in nome or "movimento" in nome:
        return "venda"

    return "desconhecido"


def process_file(file_storage):
    """
    Processa um único arquivo:
    - detecta o tipo
    - extrai dados
    - retorna registros normalizados
    """
    nome = file_storage.filename.lower()

    if nome.endswith(".csv"):
        registros = parse_csv_generic(file_storage)

    elif nome.endswith(".xlsx") or nome.endswith(".xls"):
        registros = parse_excel_generic(file_storage)

    elif nome.endswith(".ofx"):
        registros = parse_ofx_generic(file_storage)

    else:
        return {
            "ok": False,
            "arquivo": nome,
            "erro": "Formato não suportado"
        }

    tipo = identificar_tipo(nome)

    return {
        "ok": True,
        "arquivo": nome,
        "tipo": tipo,
        "registros": registros
    }


def process_uploaded_files(files, empresa_id, usuario_id):
    """
    Processa todos os arquivos enviados, salva no banco
    e retorna um resumo geral.
    """

    resultados = []

    for file_storage in files:

        resultado = process_file(file_storage)

        if not resultado["ok"]:
            resultados.append(resultado)
            continue

        nome = resultado["arquivo"]
        tipo = resultado["tipo"]
        registros = resultado["registros"]

        # Gera hash do arquivo
        hash_arquivo = gerar_hash_arquivo(file_storage)

        # Salva no banco
        salvar_arquivo_importado(
            empresa_id=empresa_id,
            usuario_id=usuario_id,
            nome_arquivo=nome,
            tipo=tipo,
            hash_arquivo=hash_arquivo,
            registros=registros
        )

        resultados.append({
            "ok": True,
            "arquivo": nome,
            "tipo": tipo,
            "linhas": len(registros),
            "hash": hash_arquivo
        })

    return resultados
