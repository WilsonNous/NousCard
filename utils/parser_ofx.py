from ofxparse import OfxParser

def parse_ofx_file(file_storage):
    """
    Lê arquivo OFX e devolve lista de lançamentos básicos.
    """
    ofx = OfxParser.parse(file_storage.stream)
    lancamentos = []

    for account in ofx.accounts:
        for tx in account.statement.transactions:
            lancamentos.append({
                "data": tx.date,
                "valor": tx.amount,
                "id": tx.id,
                "memo": tx.memo,
            })

    # Volta o ponteiro
    file_storage.stream.seek(0)
    return lancamentos
