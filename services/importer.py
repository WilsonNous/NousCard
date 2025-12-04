# services/importer.py

import os
from utils.parsers import (
    parse_csv_generic,
    parse_excel_generic,
    parse_ofx_generic
)

from utils.helpers import gerar_hash_arquivo
from services.importer_db import salvar_arquivo_importado
from services.importer_db_movimento import (
    salvar_vendas,
    salvar_recebimentos
)

from models import db


# ============================================================
#  IDENTIFICAR TIPO DO ARQUIVO
# ============================================================

def identificar_tipo(nome_arquivo: str) -> str:
    nome = nome_arquivo.lower()

    if "receb" in nome or "extrato" in nome or "ofx" in nome:
        return "recebimento"

    if "venda" in nome or "transacao" in nome or "movimento" in nome:
        return "venda"

    return "desconhecido"


# ============================================================
#  PROCESSAR UM ARQUIVO
# ============================================================

def process_file(file_storage):
    nome = file_storage.filename.lower()

    try:
        if nome.endswith(".csv") or nome.endswith(".txt"):
            registros = parse_csv_generic(file_storage)

        elif nome.endswith(".xlsx") or nome.endswith(".xls"):
            registros = parse_excel_generic(file_storage)

        elif nome.endswith(".ofx"):
            try:
                registros = parse_ofx_generic(file_storage)
            except Exception as e:
                return {
                    "ok": False,
                    "arquivo": nome,
                    "erro": f"Erro ao interpretar OFX: {str(e)}"
                }

        else:
            return {
                "ok": False,
                "arquivo": nome,
                "erro": "Formato não suportado"
            }

    except Exception as e:
        return {
            "ok": False,
            "arquivo": nome,
            "erro": f"Erro ao processar arquivo: {str(e)}"
        }

    tipo = identificar_tipo(nome)

    return {
        "ok": True,
        "arquivo": nome,
        "tipo": tipo,
        "registros": registros
    }


# ============================================================
#  PROCESSAR MULTIPLOS ARQUIVOS
# ============================================================

def process_uploaded_files(files, empresa_id, usuario_id):

    resultados = []

    for file_storage in files:
        resultado = process_file(file_storage)

        if not resultado["ok"]:
            resultados.append(resultado)
            continue

        nome = resultado["arquivo"]
        tipo = resultado["tipo"]
        registros = resultado["registros"]

        # hash
        hash_arquivo = gerar_hash_arquivo(file_storage)

        # Salvar JSON + metadados
        arquivo_id = salvar_arquivo_importado(
            empresa_id=empresa_id,
            usuario_id=usuario_id,
            nome_arquivo=nome,
            tipo=tipo,
            hash_arquivo=hash_arquivo,
            registros=registros
        )

        # ============================
        # 🔥 SALVAR NAS TABELAS REAIS
        # ============================

        if tipo == "venda":
            salvar_vendas(registros, empresa_id, arquivo_id)

        elif tipo == "recebimento":
            salvar_recebimentos(registros, empresa_id, arquivo_id)

        resultados.append({
            "ok": True,
            "arquivo": nome,
            "tipo": tipo,
            "linhas": len(registros),
            "hash": hash_arquivo
        })

    return resultados


# ============================================================
#  LISTAR
# ============================================================

def listar_importados(empresa_id: int):
    from services.importer_db import listar_arquivos_importados
    return listar_arquivos_importados(empresa_id)
