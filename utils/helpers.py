import hashlib

def gerar_hash_arquivo(file_storage):
    conteudo = file_storage.read()
    file_storage.seek(0)  # reset para permitir leitura depois
    return hashlib.sha256(conteudo).hexdigest()
    
def format_currency_br(value: float) -> str:
    try:
        value = float(value)
        return f"R$ {value:,.2f}".replace(",", "v").replace(".", ",").replace("v", ".")
    except (TypeError, ValueError):
        return "R$ 0,00"
