# services/importer.py

import os
from utils.parsers import (
    parse_csv_generic,
    parse_excel_generic,
    parse_ofx_generic
)

from utils.helpers import gerar_hash_arquivo
from services.importer_db import (
    salvar_arquivo_importado,
    listar_arquivos_importados
)

from models import db
import json



# ============================================================
#  IDENTIFICAR TIPO DO ARQUIVO
# ============================================================

def identificar_tipo(nome_arquivo: str) -> str:
    """Identifica automaticamente se o arquivo é de vendas ou recebimentos."""
    nome = nome_arquivo.lower()

    if "receb" in nome or "extrato" in nome or "ofx" in nome:
        return "recebimento"

    if "venda" in nome or "transacao" in nome or "movimento" in nome:
        return "venda"

    return "desconhecido"


# ============================================================
#  PROCESSAR UM ÚNICO ARQUIVO (SAFE)
# ============================================================

def process_file(file_storage):
    """
    Processa um único arquivo:
    - identifica tipo
    - executa parser correspondente
    - captura erros em OFX e formatos inválidos
    """

    nome = file_storage.filename.lower()

    try:
        # CSV / TXT
        if nome.endswith(".csv") or nome.endswith(".txt"):
            registros = parse_csv_generic(file_storage)

        # Excel
        elif nome.endswith(".xlsx") or nome.endswith(".xls"):
            registros = parse_excel_generic(file_storage)

        # OFX (proteção contra FITID ausente)
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
#  PROCESSAR MÚLTIPLOS ARQUIVOS + SALVAR NO BANCO
# ============================================================

def process_uploaded_files(files, empresa_id, usuario_id):
    """
    Processa todos os arquivos enviados,
    salva no banco,
    retorna um resumo geral para exibição no frontend.
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

        # Gera hash único
        hash_arquivo = gerar_hash_arquivo(file_storage)

        # Salva no banco de dados
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


# ============================================================
#  EXPORTAR LISTAGEM — FACILITA USO EM ROTAS
# ============================================================

def listar_importados(empresa_id: int):
    return listar_arquivos_importados(empresa_id)


def salvar_arquivo_importado(
    empresa_id,
    usuario_id,
    nome_arquivo,
    tipo,
    hash_arquivo,
    registros,
):
    total_registros = len(registros)
    total_valor = sum(float(r.get("valor", 0)) for r in registros)

    # 🔥 Corrigido: converter lista de dicts para JSON serializável
    conteudo_json = json.dumps(registros, ensure_ascii=False)

    db.session.execute("""
        INSERT INTO arquivos_importados
        (empresa_id, usuario_id, nome_arquivo, tipo, hash_arquivo, total_registros, total_valor, conteudo_json)
        VALUES
        (:empresa_id, :usuario_id, :nome_arquivo, :tipo, :hash_arquivo, :total_registros, :total_valor, :conteudo_json)
    """, {
        "empresa_id": empresa_id,
        "usuario_id": usuario_id,
        "nome_arquivo": nome_arquivo,
        "tipo": tipo,
        "hash_arquivo": hash_arquivo,
        "total_registros": total_registros,
        "total_valor": total_valor,
        "conteudo_json": conteudo_json,
    })

    db.session.commit()
