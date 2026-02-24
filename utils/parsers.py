import csv
import io
import re
import logging
from datetime import datetime, date
from decimal import Decimal, InvalidOperation
from openpyxl import load_workbook
from ofxparse import OfxParser
import chardet

logger = logging.getLogger(__name__)

# ============================================================
# CONFIGURAÇÕES
# ============================================================
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
MAX_ROWS = 10000

# ============================================================
# DETECTAR ENCODING
# ============================================================
def detectar_encoding(file_stream):
    """Detecta encoding do arquivo"""
    file_stream.seek(0)
    raw = file_stream.read(10000)
    file_stream.seek(0)
    result = chardet.detect(raw)
    return result['encoding'] or 'utf-8'

# ============================================================
# PARSE VALOR MONETÁRIO (DECIMAL)
# ============================================================
def parse_valor(value, raise_on_error=False):
    """Converte valor para Decimal de forma segura"""
    if value is None:
        return Decimal("0")
    
    if isinstance(value, Decimal):
        return value
    
    if isinstance(value, (int, float)):
        return Decimal(str(value))
    
    value = str(value).strip()
    value = value.replace("R$", "").replace(" ", "")
    
    # Formato brasileiro "1.234,56"
    if "," in value and "." in value:
        value = value.replace(".", "").replace(",", ".")
    elif "," in value:
        value = value.replace(",", ".")
    
    try:
        return Decimal(value)
    except (InvalidOperation, ValueError) as e:
        logger.warning(f"Valor inválido: {value}, erro: {str(e)}")
        if raise_on_error:
            raise
        return Decimal("0")

# ============================================================
# PARSE DATA
# ============================================================
def parse_data(value):
    """Converte valor para date de forma segura"""
    if not value:
        return None
    
    if isinstance(value, (datetime, date)):
        return value if isinstance(value, date) else value.date()
    
    value = str(value).strip()
    
    formatos = [
        "%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y",
        "%Y/%m/%d", "%m/%d/%Y", "%Y-%m-%d %H:%M:%S"
    ]
    
    for fmt in formatos:
        try:
            return datetime.strptime(value, fmt).date()
        except:
            pass
    
    logger.warning(f"Data inválida: {value}")
    return None

# ============================================================
# SANITIZAR CÉLULA (CSV/EXCEL INJECTION)
# ============================================================
def sanitizar_celula(value):
    """Previne CSV/Excel injection"""
    if not value:
        return ""
    
    value = str(value).strip()
    
    # Caracteres que iniciam fórmulas perigosas
    if value and value[0] in ('=', '+', '-', '@', '\t', '\r'):
        value = "'" + value
    
    # Remove caracteres de controle
    value = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F]', '', value)
    
    # Limitar tamanho
    if len(value) > 1000:
        value = value[:1000]
    
    return value

# ============================================================
# NORMALIZAR ROW
# ============================================================
def normalize_row(row: dict):
    """Normaliza uma linha de dados"""
    new = {}
    valor_alternativo = None
    
    for key, value in row.items():
        if key is None:
            continue
        
        k = str(key).strip().lower()
        
        # 1) Colunas de valor definitivas
        if k in ("valor", "amount", "valor_bruto", "vlr", "price"):
            new["valor"] = parse_valor(value)
        
        # 2) Nomes alternativos para valor
        elif k in ("entrada", "creditado", "credito", "valor_liquido", 
                   "vlr_liq", "valor_liq", "lancado"):
            valor_alternativo = parse_valor(value)
        
        # 3) Detecção por regex
        elif re.search(r"valor|liq|credit", k):
            valor_alternativo = parse_valor(value)
        
        # 4) Datas
        elif k in ("data", "date", "dt", "transaction_date"):
            new["data"] = parse_data(value)
        elif re.search(r"data|date", k):
            new["data"] = parse_data(value)
        
        # 5) Descrição (sanitizada!)
        elif k in ("descricao", "desc", "memo", "historico", "detalhe"):
            new["descricao"] = sanitizar_celula(value)
        
        # 6) Outros campos
        else:
            new[k] = sanitizar_celula(value) if value else ""
    
    # Garantir valor
    if "valor" not in new or new["valor"] == Decimal("0"):
        if valor_alternativo is not None:
            new["valor"] = valor_alternativo
        else:
            new["valor"] = Decimal("0")
    
    # Garantir descrição
    if "descricao" not in new:
        new["descricao"] = ""
    
    return new

# ============================================================
# PARSE CSV
# ============================================================
def parse_csv_generic(file_stream, filename=None):
    """Parse CSV com validações de segurança"""
    logger.info(f"Início parse CSV: {filename}")
    
    # Validar tamanho
    file_stream.seek(0, 2)
    size = file_stream.tell()
    file_stream.seek(0)
    
    if size > MAX_FILE_SIZE:
        raise ValueError(f"Arquivo excede {MAX_FILE_SIZE/1024/1024}MB")
    
    # Detectar encoding
    encoding = detectar_encoding(file_stream)
    logger.info(f"Encoding detectado: {encoding}")
    
    # Ler conteúdo
    raw = file_stream.read().decode(encoding, errors="replace")
    reader = csv.DictReader(io.StringIO(raw))
    
    # Parse com limite de linhas
    registros = []
    for i, row in enumerate(reader):
        if i >= MAX_ROWS:
            logger.warning(f"Limite de {MAX_ROWS} linhas atingido")
            break
        registros.append(normalize_row(dict(row)))
    
    logger.info(f"Fim parse CSV: {len(registros)} registros")
    
    return registros

# ============================================================
# PARSE EXCEL
# ============================================================
def parse_excel_generic(file_stream, filename=None):
    """Parse Excel com proteção XXE"""
    logger.info(f"Início parse Excel: {filename}")
    
    # Validar tamanho
    file_stream.seek(0, 2)
    size = file_stream.tell()
    file_stream.seek(0)
    
    if size > MAX_FILE_SIZE:
        raise ValueError(f"Arquivo excede {MAX_FILE_SIZE/1024/1024}MB")
    
    try:
        workbook = load_workbook(
            filename=io.BytesIO(file_stream.read()),
            data_only=True,
            keep_links=False  # Proteção XXE
        )
        sheet = workbook.active
        
        rows = list(sheet.rows)
        if not rows:
            return []
        
        headers = [str(c.value).strip() if c.value else "" for c in rows[0]]
        registros = []
        
        for i, row in enumerate(rows[1:]):
            if i >= MAX_ROWS:
                break
            row_dict = {}
            for j, cell in enumerate(row):
                if j < len(headers):
                    row_dict[headers[j]] = cell.value
            registros.append(normalize_row(row_dict))
        
        logger.info(f"Fim parse Excel: {len(registros)} registros")
        
        return registros
        
    except Exception as e:
        logger.error(f"Erro ao parsear Excel: {str(e)}")
        raise ValueError(f"Erro ao processar Excel: {str(e)}")

# ============================================================
# PARSE OFX
# ============================================================
def parse_ofx_generic(file_stream, filename=None):
    """Parse OFX com validação de estrutura"""
    logger.info(f"Início parse OFX: {filename}")
    
    # Validar tamanho
    file_stream.seek(0, 2)
    size = file_stream.tell()
    file_stream.seek(0)
    
    if size > MAX_FILE_SIZE:
        raise ValueError(f"Arquivo excede {MAX_FILE_SIZE/1024/1024}MB")
    
    try:
        ofx = OfxParser.parse(file_stream)
    except Exception as e:
        logger.error(f"Erro ao parsear OFX: {str(e)}")
        raise ValueError("Arquivo OFX inválido")
    
    if not ofx.accounts:
        logger.warning("OFX sem contas")
        return []
    
    registros = []
    for account in ofx.accounts:
        if not account.statement:
            continue
        if not account.statement.transactions:
            continue
        
        for tx in account.statement.transactions:
            try:
                registro = normalize_row({
                    "data": tx.date,
                    "valor": tx.amount,
                    "descricao": tx.memo,
                    "id": tx.id,
                    "tipo_ofx": tx.type
                })
                registros.append(registro)
            except Exception as e:
                logger.warning(f"Transação OFX inválida: {str(e)}")
                continue
    
    logger.info(f"Fim parse OFX: {len(registros)} registros")
    
    return registros
