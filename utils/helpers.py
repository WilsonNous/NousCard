# utils/helpers.py - VERSÃO CORRIGIDA E COMPLETA

import hashlib
import logging
import os
import re
import secrets
from decimal import Decimal, InvalidOperation
from typing import Union, Optional
from datetime import datetime, date

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
    
    Args:
        file_storage: Objeto com métodos read() e seek()
        algorithm: "sha256", "sha512" ou "md5"
        max_size_mb: Tamanho máximo em MB
    
    Returns:
        Hash hexadecimal do arquivo
    
    Raises:
        TypeError: Se file_storage não tiver read()/seek()
        ValueError: Se arquivo exceder tamanho máximo
    """
    # Validar objeto
    if not hasattr(file_storage, 'read') or not hasattr(file_storage, 'seek'):
        raise TypeError("file_storage deve ter métodos read() e seek()")
    
    # Validar algoritmo
    if algorithm not in ("sha256", "sha512", "md5"):
        logger.warning(f"⚠️ Algoritmo {algorithm} não suportado, usando sha256")
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
        logger.error(f"❌ Erro ao gerar hash: {str(e)}")
        raise
    
    # Resetar ponteiro para uso posterior
    file_storage.seek(0)
    
    return hasher.hexdigest()


def gerar_hash_arquivo_path(
    file_path: str,
    algorithm: str = "sha256",
    max_size_mb: int = MAX_FILE_SIZE_MB
) -> str:
    """
    Gera hash de arquivo a partir de path.
    
    Args:
        file_path: Caminho absoluto do arquivo
        algorithm: "sha256", "sha512" ou "md5"
        max_size_mb: Tamanho máximo em MB
    
    Returns:
        Hash hexadecimal do arquivo
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Arquivo não encontrado: {file_path}")
    
    size = os.path.getsize(file_path)
    max_size = max_size_mb * 1024 * 1024
    
    if size > max_size:
        raise ValueError(f"Arquivo excede {max_size_mb}MB (tamanho: {size/1024/1024:.2f}MB)")
    
    hasher = hashlib.new(algorithm)
    
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(HASH_CHUNK_SIZE), b""):
            hasher.update(chunk)
    
    return hasher.hexdigest()

# ============================================================
# FORMATAÇÃO DE MOEDA (CORRIGIDO)
# ============================================================
def format_currency_br(
    value: Union[int, float, Decimal, str, None],
    show_cents: bool = True,
    include_symbol: bool = True
) -> str:
    """
    Formata valor monetário para padrão brasileiro (R$ 1.234,56).
    
    ✅ Usa Decimal para precisão
    ✅ Handle valores negativos corretamente
    ✅ Formatação robusta sem replace chain frágil
    
    Args:
        value: Valor a formatar
        show_cents: Mostrar centavos (padrão: True)
        include_symbol: Incluir "R$" (padrão: True)
    
    Returns:
        String formatada ex: "R$ 1.234,56" ou "1.234,56"
    """
    try:
        if value is None:
            return "R$ 0,00" if include_symbol else "0,00"
        
        # Converter para Decimal (precisão preservada)
        if isinstance(value, Decimal):
            decimal_value = value
        elif isinstance(value, (int, float)):
            decimal_value = Decimal(str(value))
        elif isinstance(value, str):
            decimal_value = parse_currency_br(value)
        else:
            logger.warning(f"⚠️ Tipo não suportado: {type(value)}")
            return "R$ 0,00" if include_symbol else "0,00"
        
        # Separar sinal e valor absoluto
        is_negative = decimal_value < 0
        abs_value = abs(decimal_value)
        
        # Formatar com 2 casas decimais
        if show_cents:
            # Usar formatação string com separadores corretos
            formatted = f"{abs_value:.2f}"
            # Separar parte inteira e decimal
            inteiro, centavos = formatted.split(".")
            # Adicionar separador de milhar
            inteiro_formatado = "{:,}".format(int(inteiro)).replace(",", ".")
            result = f"{inteiro_formatado},{centavos}"
        else:
            inteiro = int(round(abs_value))
            result = "{:,}".format(inteiro).replace(",", ".")
        
        # Adicionar sinal se negativo
        sinal = "-" if is_negative else ""
        
        # Adicionar símbolo
        if include_symbol:
            return f"{sinal}R$ {result}"
        else:
            return f"{sinal}{result}"
            
    except (InvalidOperation, ValueError, TypeError) as e:
        logger.warning(f"⚠️ Valor inválido para formatação: {value}, erro: {str(e)}")
        return "R$ 0,00" if include_symbol else "0,00"


def parse_currency_br(value: str) -> Decimal:
    """
    Parse de string formatada em BR para Decimal.
    
    ✅ Detecta automaticamente formato BR vs US
    ✅ Handle múltiplos formatos: "1.234,56", "1234.56", "R$ 1.234,56"
    
    Args:
        value: String no formato brasileiro ou americano
    
    Returns:
        Decimal value
    """
    if not value:
        return Decimal("0")
    
    try:
        cleaned = str(value).strip().replace("R$", "").replace(" ", "").replace("\xa0", "")
        
        # Detectar formato
        has_comma = "," in cleaned
        has_dot = "." in cleaned
        
        if has_comma and has_dot:
            # Tem ambos: determinar qual é decimal
            # Se vírgula vem depois do último ponto → formato BR (1.234,56)
            last_comma_pos = cleaned.rfind(",")
            last_dot_pos = cleaned.rfind(".")
            
            if last_comma_pos > last_dot_pos:
                # Formato BR: milhar com ponto, decimal com vírgula
                cleaned = cleaned.replace(".", "").replace(",", ".")
            else:
                # Formato US: milhar com vírgula, decimal com ponto
                cleaned = cleaned.replace(",", "")
        elif has_comma:
            # Só vírgula: assume decimal BR (1234,56)
            cleaned = cleaned.replace(",", ".")
        # elif has_dot:
        # # Só ponto: assume decimal US (1234.56) - já está correto
        
        # Remover caracteres não numéricos exceto ponto e sinal
        cleaned = re.sub(r'[^\d.\-+]', '', cleaned)
        
        if not cleaned or cleaned in ['.', '-', '+']:
            return Decimal("0")
        
        return Decimal(cleaned)
        
    except (InvalidOperation, ValueError) as e:
        logger.warning(f"⚠️ Não foi possível parsear moeda: {value}, erro: {str(e)}")
        return Decimal("0")

# ============================================================
# FORMATAÇÃO DE DATA
# ============================================================
def format_date_br(
    date_value: Union[date, datetime, str, None],
    format_string: str = "%d/%m/%Y"
) -> str:
    """
    Formata data para padrão brasileiro.
    
    Args:
        date_value: date, datetime ou string ISO
        format_string: Formato de saída (padrão: "%d/%m/%Y")
    
    Returns:
        String formatada ex: "24/04/2026"
    """
    if not date_value:
        return "-"
    
    try:
        if isinstance(date_value, (date, datetime)):
            return date_value.strftime(format_string)
        elif isinstance(date_value, str):
            # Tentar parsear string ISO
            parsed = parse_date_br(date_value)
            if parsed:
                return parsed.strftime(format_string)
            return date_value  # Retorna original se não conseguir parsear
        else:
            logger.warning(f"⚠️ Tipo de data não suportado: {type(date_value)}")
            return "-"
    except Exception as e:
        logger.warning(f"⚠️ Erro ao formatar data: {str(e)}")
        return "-"


def parse_date_br(date_string: str) -> Optional[date]:
    """
    Parse de string para date, suportando formatos BR e ISO.
    
    Args:
        date_string: String no formato "24/04/2026" ou "2026-04-24"
    
    Returns:
        date object ou None se não conseguir parsear
    """
    if not date_string:
        return None
    
    formatos = [
        "%d/%m/%Y",           # BR: 24/04/2026
        "%Y-%m-%d",           # ISO: 2026-04-24
        "%d-%m-%Y",           # 24-04-2026
        "%Y/%m/%d",           # 2026/04/24
        "%d/%m/%Y %H:%M:%S",  # BR com hora
        "%Y-%m-%d %H:%M:%S",  # ISO com hora
    ]
    
    date_string = str(date_string).strip()
    
    for fmt in formatos:
        try:
            parsed = datetime.strptime(date_string, fmt)
            return parsed.date()
        except ValueError:
            continue
    
    logger.debug(f"⚠️ Não foi possível parsear data: {date_string}")
    return None

# ============================================================
# SEGURANÇA E SANITIZAÇÃO
# ============================================================
def gerar_csrf_token() -> str:
    """
    Gera token CSRF seguro para formulários.
    
    Returns:
        Token URL-safe de 32 bytes
    """
    return secrets.token_urlsafe(32)


def validar_csrf_token(token_provided: str, token_session: str) -> bool:
    """
    Valida token CSRF com comparação constante-time.
    
    Args:
        token_provided: Token enviado pelo cliente
        token_session: Token armazenado na sessão
    
    Returns:
        True se válido, False caso contrário
    """
    if not token_provided or not token_session:
        return False
    
    # Comparação constante-time para prevenir timing attacks
    return secrets.compare_digest(
        token_provided.encode(),
        token_session.encode()
    )


def mask_sensitive_data(
    data: str,
    visible_chars: int = 4,
    mask_char: str = "*"
) -> str:
    """
    Mascara dados sensíveis (CPF, CNPJ, cartão, etc.).
    
    Args:
        data: Dado a mascarar
        visible_chars: Quantos caracteres manter visíveis no final
        mask_char: Caractere para máscara
    
    Returns:
        Dado mascarado ex: "***********1234"
    """
    if not data:
        return ""
    
    if not isinstance(data, str):
        logger.warning(f"⚠️ mask_sensitive_data espera string, recebeu {type(data)}")
        data = str(data)
    
    data = data.strip()
    
    if len(data) <= visible_chars:
        return mask_char * len(data)
    
    return mask_char * (len(data) - visible_chars) + data[-visible_chars:]


def sanitizar_string(
    value: str,
    max_length: int = 255,
    allow_html: bool = False
) -> str:
    """
    Sanitiza string para prevenir XSS e injection.
    
    Args:
        value: String a sanitizar
        max_length: Tamanho máximo
        allow_html: Permitir tags HTML (padrão: False)
    
    Returns:
        String sanitizada
    """
    if not value:
        return ""
    
    if not isinstance(value, str):
        value = str(value)
    
    # Trim whitespace
    value = value.strip()
    
    # Remover tags HTML se não permitido
    if not allow_html:
        value = re.sub(r'<[^>]+>', '', value)
    
    # Remover caracteres de controle
    value = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', value)
    
    # Limitar tamanho
    if len(value) > max_length:
        value = value[:max_length] + "..."
    
    return value

# ============================================================
# VALIDAÇÕES
# ============================================================
def validar_cnpj(cnpj: str) -> bool:
    """
    Valida CNPJ brasileiro com dígitos verificadores.
    
    Args:
        cnpj: CNPJ formatado ou não
    
    Returns:
        True se válido, False caso contrário
    """
    if not cnpj:
        return False
    
    # Remover caracteres não numéricos
    cnpj = re.sub(r'\D', '', cnpj)
    
    if len(cnpj) != 14:
        return False
    
    # Verificar sequências inválidas
    if cnpj == cnpj[0] * 14:
        return False
    
    # Calcular primeiro dígito verificador
    pesos_1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    soma_1 = sum(int(cnpj[i]) * pesos_1[i] for i in range(12))
    digito_1 = 11 - (soma_1 % 11)
    digito_1 = 0 if digito_1 >= 10 else digito_1
    
    # Calcular segundo dígito verificador
    pesos_2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    soma_2 = sum(int(cnpj[i]) * pesos_2[i] for i in range(13))
    digito_2 = 11 - (soma_2 % 11)
    digito_2 = 0 if digito_2 >= 10 else digito_2
    
    return int(cnpj[12]) == digito_1 and int(cnpj[13]) == digito_2


def validar_cpf(cpf: str) -> bool:
    """
    Valida CPF brasileiro com dígitos verificadores.
    
    Args:
        cpf: CPF formatado ou não
    
    Returns:
        True se válido, False caso contrário
    """
    if not cpf:
        return False
    
    cpf = re.sub(r'\D', '', cpf)
    
    if len(cpf) != 11:
        return False
    
    if cpf == cpf[0] * 11:
        return False
    
    # Calcular primeiro dígito
    pesos_1 = list(range(10, 1, -1))
    soma_1 = sum(int(cpf[i]) * pesos_1[i] for i in range(9))
    digito_1 = 11 - (soma_1 % 11)
    digito_1 = 0 if digito_1 >= 10 else digito_1
    
    # Calcular segundo dígito
    pesos_2 = list(range(11, 1, -1))
    soma_2 = sum(int(cpf[i]) * pesos_2[i] for i in range(10))
    digito_2 = 11 - (soma_2 % 11)
    digito_2 = 0 if digito_2 >= 10 else digito_2
    
    return int(cpf[9]) == digito_1 and int(cpf[10]) == digito_2

# ============================================================
# UTILITÁRIOS DIVERSOS
# ============================================================
def truncate_text(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """Trunca texto com sufixo."""
    if not text or len(text) <= max_length:
        return text or ""
    return text[:max_length - len(suffix)] + suffix


def slugify(text: str) -> str:
    """Converte texto para slug URL-safe."""
    if not text:
        return ""
    
    # Lowercase
    text = text.lower()
    
    # Remover acentos
    import unicodedata
    text = ''.join(
        c for c in unicodedata.normalize('NFD', text)
        if unicodedata.category(c) != 'Mn'
    )
    
    # Substituir espaços e caracteres especiais por hífen
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_]+', '-', text)
    
    # Remover hífens múltiplos
    text = re.sub(r'-+', '-', text)
    
    return text.strip('-')
