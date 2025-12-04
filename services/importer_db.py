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
    registros,
):
    total_registros = len(registros)

    # Alguns arquivos podem não ter coluna valor → garantir "0"
    total_valor = 0
    for r in registros:
        try:
            total_valor += float(r.get("valor", 0))
        except:
            pass

    # Salva registros como JSON no banco
    conteudo_json = json.dumps(registros, ensure_ascii=False)

    sql = text("""
        INSERT INTO arquivos_importados
        (empresa_id, usuario_id, nome_arquivo, tipo, hash_arquivo,
         total_registros, total_valor, conteudo_json)
        VALUES
        (:empresa_id, :usuario_id, :nome_arquivo, :tipo, :hash_arquivo,
         :total_registros, :total_valor, :conteudo_json)
    """)

    db.session.execute(sql, {
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


# ============================================================
#  BUSCAR ARQUIVO POR ID (usado nas rotas)
# ============================================================
def buscar_arquivo_por_id(arquivo_id, empresa_id):
    sql = text("""
        SELECT
            id,
            nome_arquivo,
            tipo,
            total_registros,
            total_valor,
            conteudo_json,
            created_at
        FROM arquivos_importados
        WHERE id = :id
          AND empresa_id = :empresa_id
        LIMIT 1
    """)

    row = db.session.execute(sql, {
        "id": arquivo_id,
        "empresa_id": empresa_id
    }).mappings().first()

    if not row:
        return None

    # Tratar JSON armazenado
    conteudo_str = row["conteudo_json"]
    try:
        registros = json.loads(conteudo_str) if conteudo_str else []
    except Exception:
        registros = []

    return {
        "id": row["id"],
        "nome_arquivo": row["nome_arquivo"],
        "tipo": row["tipo"],
        "total_registros": row["total_registros"],
        "total_valor": float(row["total_valor"] or 0),
        "created_at": row["created_at"].strftime("%d/%m/%Y %H:%M") if row["created_at"] else "",
        "conteudo_json": conteudo_str,
        "registros": registros,
    }
