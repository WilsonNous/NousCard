import hashlib
import logging
from decimal import Decimal, InvalidOperation
from typing import Union, Optional

logger = logging.getLogger(__name__)

# ============================================================
# CONFIGURAÇÕES
# ============================================================
MAX_FILE_SIZE_MB = 50
HASH_CHUNK_SIZE = 8192  # 8KB por chunk

# ============================================================
# HASH DE ARQUIVO
# ============================================================
def gerar_hash_arquivo(
    file_storage,
    algorithm: str = "sha256",
    max_size_mb: int = MAX_FILE_SIZE_MB
) -> str:
    """
    Gera hash de arquivo em chunks para evitar estouro de memória.
    """
    # Validar objeto
    if not hasattr(file_storage, 'read') or not hasattr(file_storage, 'seek'):
        raise TypeError("file_storage deve ter métodos read() e seek()")
    
    # Validar algoritmo
    if algorithm not in ("sha256", "sha512", "md5"):
        logger.warning(f"Algoritmo {algorithm} não suportado, usando sha256")
        algorithm = "sha256"
    
    # Garantir ponteiro no início
    file_storage.seek(0)
    
    # Validar tamanho
    file_storage.seek(0, 2)
    size = file_storage.tell()
    file_storage.seek(0)
    
    max_size = max_size_mb * 1024 * 1024
    if size > max_size:
        raise ValueError(f"Arquivo excede {max_size_mb}MB (tamanho: {size/1024/1024:.2f}MB)")
    
    # Hash em chunks
    hasher = hashlib.new(algorithm)
    try:
        for chunk in iter(lambda: file_storage.read(HASH_CHUNK_SIZE), b""):
            hasher.update(chunk)
    except Exception as e:
        logger.error(f"Erro ao gerar hash: {str(e)}")
        raise
    
    # Resetar ponteiro para uso posterior
    file_storage.seek(0)
    
    return hasher.hexdigest()

# ============================================================
# FORMATAÇÃO DE MOEDA
# ============================================================
def format_currency_br(
    value: Union[int, float, Decimal, str, None],
    show_cents: bool = True
) -> str:
    """
    Formata valor monetário para padrão brasileiro (R$ 1.234,56).
    """
    try:
        if value is None:
            return "R$ 0,00"
        
        # Converter para Decimal (precisão preservada)
        if isinstance(value, Decimal):
            decimal_value = value
        elif isinstance(value, (int, float)):
            decimal_value = Decimal(str(value))
        elif isinstance(value, str):
            cleaned = str(value).strip().replace("R$", "").replace(" ", "")
            if "," in cleaned and "." in cleaned:
                cleaned = cleaned.replace(".", "").replace(",", ".")
            elif "," in cleaned:
                cleaned = cleaned.replace(",", ".")
            decimal_value = Decimal(cleaned)
        else:
            logger.warning(f"Tipo não suportado: {type(value)}")
            return "R$ 0,00"
        
        # Formatar
        sinal = "-" if decimal_value < 0 else ""
        abs_value = abs(decimal_value)
        
        if show_cents:
            inteiro = int(abs_value)
            centavos = int(round((abs_value - inteiro) * 100))
            if centavos >= 100:
                inteiro += 1
                centavos = 0
            return f"{sinal}R$ {inteiro:,}.{centavos:02d}".replace(",", "X").replace(".", ",").replace("X", ".")
        else:
            inteiro = int(round(abs_value))
            return f"{sinal}R$ {inteiro:,}".replace(",", ".")
            
    except (InvalidOperation, ValueError, TypeError) as e:
        logger.warning(f"Valor inválido para formatação: {value}, erro: {str(e)}")
        return "R$ 0,00"

# ============================================================
# HELPERS ADICIONAIS
# ============================================================
def parse_currency_br(value: str) -> Decimal:
    """Parse de string formatada em BR para Decimal."""
    if not value:
        return Decimal("0")
    
    try:
        cleaned = str(value).strip().replace("R$", "").replace(" ", "")
        cleaned = cleaned.replace(".", "").replace(",", ".")
        return Decimal(cleaned)
    except (InvalidOperation, ValueError):
        logger.warning(f"Não foi possível parsear moeda: {value}")
        return Decimal("0")

def mask_sensitive_data(data: str, visible_chars: int = 4) -> str:
    """Mascara dados sensíveis (CPF, CNPJ, cartão, etc.)."""
    if not data or len(data) <= visible_chars:
        return "*" * len(data) if data else ""
    
    return "*" * (len(data) - visible_chars) + data[-visible_chars:]
