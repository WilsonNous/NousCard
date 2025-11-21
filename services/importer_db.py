from config import db

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
        "conteudo_json": registros,
    })

    db.session.commit()
