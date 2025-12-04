# services/importer_db.py

from models.base import db
from sqlalchemy import text
import json


# ============================================================
#  SALVAR ARQUIVO IMPORTADO
# ============================================================

def salvar_arquivo_importado(
    empresa_id,
    usuario_id,
    nome_arquivo,
    tipo,
    hash_arquivo,
    registros
):

    total_registros = len(registros)

    # Soma total
    total_valor = 0
    for r in registros:
        try:
            total_valor += float(r.get("valor", 0))
        except:
            pass

    conteudo_json = json.dumps(registros, ensure_ascii=False)

    sql = text("""
        INSERT INTO arquivos_importados
        (empresa_id, usuario_id, nome_arquivo, tipo, hash_arquivo,
         total_registros, total_valor, conteudo_json)
        VALUES
        (:empresa_id, :usuario_id, :nome_arquivo, :tipo, :hash_arquivo,
         :total_registros, :total_valor, :conteudo_json)
    """)

    result = db.session.execute(sql, {
        "empresa_id": empresa_id,
        "usuario_id": usuario_id,
        "nome_arquivo": nome_arquivo,
        "tipo": tipo,
        "hash_arquivo": hash_arquivo,
        "total_registros": total_registros,
        "total_valor": total_valor,
        "conteudo_json": conteudo_json
    })

    db.session.commit()

    # retorna ID do novo registro
    return result.lastrowid



# ============================================================
#  LISTAR ARQUIVOS IMPORTADOS
# ============================================================

def listar_arquivos_importados(empresa_id: int):
    sql = text("""
        SELECT
            id,
            nome_arquivo,
            tipo,
            hash_arquivo,
            total_registros,
            total_valor,
            created_at
        FROM arquivos_importados
        WHERE empresa_id = :empresa_id
        ORDER BY created_at DESC
    """)

    result = db.session.execute(sql, {"empresa_id": empresa_id})

    arquivos = []
    for row in result.mappings():
        arquivos.append({
            "id": row["id"],
            "nome_arquivo": row["nome_arquivo"],
            "tipo": row["tipo"],
            "hash": row["hash_arquivo"],
            "total_registros": row["total_registros"],
            "total_valor": float(row["total_valor"] or 0),
            "created_at": row["created_at"].strftime("%d/%m/%Y %H:%M"),
        })

    return arquivos
