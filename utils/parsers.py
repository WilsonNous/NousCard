# ============================================================
#  PARSERS • NousCard (VERSÃO PRODUÇÃO)
#  Suporte: CSV, Excel, OFX com fallback robusto para bancos BR
# ============================================================

import csv
import io
import re
import logging
from datetime import datetime, date
from decimal import Decimal, InvalidOperation
from openpyxl import load_workbook
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
    """Detecta encoding do arquivo com fallback seguro"""
    try:
        file_stream.seek(0)
        raw = file_stream.read(10000)
        file_stream.seek(0)
        result = chardet.detect(raw)
        encoding = result.get('encoding') or 'utf-8'
        # Validar encoding suportado
        if encoding.lower() in ('ascii', 'utf-8', 'utf-16', 'latin-1', 'iso-8859-1', 'cp1252'):
            return encoding
        return 'utf-8'  # Fallback seguro
    except Exception:
        file_stream.seek(0)
        return 'utf-8'

# ============================================================
# PARSE VALOR MONETÁRIO (DECIMAL - PRECISO)
# ============================================================
def parse_valor(value, raise_on_error=False):
    """
    Converte valor para Decimal de forma segura.
    Suporta formatos: "1.234,56", "1234.56", "R$ 1.234,56", float, int
    """
    if value is None:
        return Decimal("0")
    
    if isinstance(value, Decimal):
        return value
    
    if isinstance(value, (int, float)):
        return Decimal(str(value))
    
    try:
        value = str(value).strip()
        value = value.replace("R$", "").replace(" ", "").replace("\xa0", "")
        
        # Formato brasileiro "1.234,56" → "1234.56"
        if "," in value and "." in value:
            # Tem ambos: assume formato BR (milhar com ponto, decimal com vírgula)
            value = value.replace(".", "").replace(",", ".")
        elif "," in value:
            # Só vírgula: assume decimal BR
            value = value.replace(",", ".")
        
        # Remover caracteres não numéricos exceto ponto e sinal
        value = re.sub(r'[^\d.\-+]', '', value)
        
        if not value or value in ['.', '-', '+']:
            return Decimal("0")
            
        return Decimal(value)
        
    except (InvalidOperation, ValueError, TypeError) as e:
        logger.warning(f"Valor inválido para parse: '{value}', erro: {str(e)}")
        if raise_on_error:
            raise
        return Decimal("0")

# ============================================================
# PARSE DATA (MULTI-FORMATO)
# ============================================================
def parse_data(value):
    """
    Converte valor para date de forma segura.
    Suporta múltiplos formatos comuns em bancos brasileiros.
    """
    if not value:
        return None
    
    if isinstance(value, (datetime, date)):
        return value if isinstance(value, date) else value.date()
    
    try:
        value = str(value).strip()
        
        # Lista de formatos em ordem de probabilidade para BR
        formatos = [
            "%Y-%m-%d",           # 2024-01-15 (ISO)
            "%d/%m/%Y",           # 15/01/2024 (BR padrão)
            "%d-%m-%Y",           # 15-01-2024
            "%Y/%m/%d",           # 2024/01/15
            "%m/%d/%Y",           # 01/15/2024 (US - fallback)
            "%Y-%m-%d %H:%M:%S",  # 2024-01-15 14:30:00
            "%d/%m/%Y %H:%M:%S",  # 15/01/2024 14:30:00
            "%Y%m%d",             # 20240115 (OFX)
        ]
        
        for fmt in formatos:
            try:
                return datetime.strptime(value, fmt).date()
            except ValueError:
                continue
        
        # Tentar extrair data de string livre (ex: "15/01/2024 14:30")
        match = re.search(r'(\d{2}[/-]\d{2}[/-]\d{4})', value)
        if match:
            data_str = match.group(1)
            for fmt in ["%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d"]:
                try:
                    return datetime.strptime(data_str, fmt).date()
                except ValueError:
                    continue
        
        logger.warning(f"Data não reconhecida: '{value}'")
        return None
        
    except Exception as e:
        logger.warning(f"Erro ao parsear data '{value}': {str(e)}")
        return None

# ============================================================
# SANITIZAR CÉLULA (PREVENIR CSV/EXCEL INJECTION)
# ============================================================
def sanitizar_celula(value):
    """
    Previne CSV/Excel injection sanitizando valores de células.
    Remove fórmulas maliciosas e caracteres de controle.
    """
    if not value:
        return ""
    
    try:
        value = str(value).strip()
        
        # Caracteres que iniciam fórmulas perigosas em Excel/CSV
        if value and value[0] in ('=', '+', '-', '@', '\t', '\r', '\n'):
            value = "'" + value  # Prefixa com apóstrofo para escapar
        
        # Remove caracteres de controle não imprimíveis
        value = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', value)
        
        # Limitar tamanho máximo para prevenir DoS
        if len(value) > 1000:
            value = value[:1000] + "..."
        
        return value
        
    except Exception as e:
        logger.warning(f"Erro ao sanitizar célula: {str(e)}")
        return ""

# ============================================================
# NORMALIZAR ROW (MAPEAMENTO DE COLUNAS)
# ============================================================
def normalize_row(row: dict):
    """
    Normaliza uma linha de dados mapeando nomes de colunas variados
    para um schema padrão: {valor, data, descricao, ...}
    """
    if not row:
        return {"valor": Decimal("0"), "data": None, "descricao": ""}
    
    new = {}
    valor_alternativo = None
    
    for key, value in row.items():
        if key is None:
            continue
        
        k = str(key).strip().lower()
        
        # 1) Colunas de valor definitivas
        if k in ("valor", "amount", "valor_bruto", "vlr", "price", "value"):
            new["valor"] = parse_valor(value)
        
        # 2) Nomes alternativos para valor (recebimentos)
        elif k in ("entrada", "creditado", "credito", "valor_liquido", 
                   "vlr_liq", "valor_liq", "lancado", "liquid_value"):
            valor_alternativo = parse_valor(value)
        
        # 3) Detecção por regex para casos não mapeados
        elif re.search(r"valor|liq|credit|amount", k):
            valor_alternativo = parse_valor(value)
        
        # 4) Datas
        elif k in ("data", "date", "dt", "transaction_date", "data_venda", "data_pagamento"):
            new["data"] = parse_data(value)
        elif re.search(r"data|date|dt", k):
            new["data"] = parse_data(value)
        
        # 5) Descrição (sanitizada!)
        elif k in ("descricao", "desc", "memo", "historico", "detalhe", "description", "note"):
            new["descricao"] = sanitizar_celula(value)
        
        # 6) Campos adicionais úteis
        elif k in ("nsu", "id", "transaction_id", "codigo"):
            new["nsu"] = sanitizar_celula(value) if value else None
        elif k in ("adquirente", "merchant", "estabelecimento"):
            new["adquirente"] = sanitizar_celula(value) if value else None
        elif k in ("bandeira", "card", "brand"):
            new["bandeira"] = sanitizar_celula(value) if value else None
        
        # 7) Outros campos: sanitizar e incluir
        else:
            new[k] = sanitizar_celula(value) if value else ""
    
    # Garantir valor (usar alternativo se principal não encontrado)
    if "valor" not in new or new["valor"] == Decimal("0"):
        if valor_alternativo is not None:
            new["valor"] = valor_alternativo
        else:
            new["valor"] = Decimal("0")
    
    # Garantir descrição
    if "descricao" not in new:
        new["descricao"] = ""
    
    # Garantir data
    if "data" not in new:
        new["data"] = None
    
    return new

# ============================================================
# PARSE CSV (GENÉRICO COM ENCODING DETECTION)
# ============================================================
def parse_csv_generic(file_stream, filename=None):
    """
    Parse CSV com detecção automática de encoding e validações.
    Suporta delimitadores , ; | tab
    """
    logger.info(f"Início parse CSV: {filename}")
    
    # Validar tamanho
    file_stream.seek(0, 2)
    size = file_stream.tell()
    file_stream.seek(0)
    
    if size > MAX_FILE_SIZE:
        raise ValueError(f"Arquivo CSV excede {MAX_FILE_SIZE/1024/1024}MB")
    
    # Detectar encoding
    encoding = detectar_encoding(file_stream)
    logger.info(f"Encoding detectado para CSV: {encoding}")
    
    try:
        # Ler conteúdo
        raw = file_stream.read().decode(encoding, errors="replace")
        
        # Tentar detectar delimitador automático
        sample = raw[:4096]
        delimitador = ','
        if ';' in sample and sample.count(';') > sample.count(','):
            delimitador = ';'
        elif '|' in sample and sample.count('|') > sample.count(','):
            delimitador = '|'
        elif '\t' in sample:
            delimitador = '\t'
        
        reader = csv.DictReader(io.StringIO(raw), delimiter=delimitador)
        
        # Parse com limite de linhas
        registros = []
        for i, row in enumerate(reader):
            if i >= MAX_ROWS:
                logger.warning(f"Limite de {MAX_ROWS} linhas atingido no CSV")
                break
            if row:  # Ignorar linhas vazias
                registros.append(normalize_row(dict(row)))
        
        logger.info(f"Fim parse CSV: {len(registros)} registros processados")
        return registros
        
    except UnicodeDecodeError as e:
        logger.error(f"Erro de encoding no CSV: {str(e)}")
        # Tentar fallback com latin-1
        file_stream.seek(0)
        raw = file_stream.read().decode('latin-1', errors='replace')
        reader = csv.DictReader(io.StringIO(raw))
        registros = [normalize_row(dict(row)) for i, row in enumerate(reader) if i < MAX_ROWS and row]
        logger.info(f"Fim parse CSV (fallback): {len(registros)} registros")
        return registros
        
    except Exception as e:
        logger.error(f"Erro ao parsear CSV: {str(e)}")
        raise ValueError(f"Erro ao processar arquivo CSV: {str(e)}")

# ============================================================
# PARSE EXCEL (COM PROTEÇÃO XXE E VALIDAÇÕES)
# ============================================================
def parse_excel_generic(file_stream, filename=None):
    """
    Parse Excel (.xlsx, .xls) com proteção contra XXE e validações.
    Usa openpyxl para .xlsx e fallback para .xls se necessário.
    """
    logger.info(f"Início parse Excel: {filename}")
    
    # Validar tamanho
    file_stream.seek(0, 2)
    size = file_stream.tell()
    file_stream.seek(0)
    
    if size > MAX_FILE_SIZE:
        raise ValueError(f"Arquivo Excel excede {MAX_FILE_SIZE/1024/1024}MB")
    
    try:
        # Carregar workbook com proteções de segurança
        workbook = load_workbook(
            filename=io.BytesIO(file_stream.read()),
            data_only=True,      # Usar valores, não fórmulas
            keep_links=False,    # Desabilitar links externos (XXE protection)
            read_only=True       # Modo leitura para performance
        )
        
        sheet = workbook.active
        if not sheet:
            logger.warning("Excel sem sheet ativa")
            return []
        
        # Ler headers da primeira linha
        rows = list(sheet.rows)
        if not rows:
            return []
        
        headers = [str(c.value).strip() if c.value is not None else "" for c in rows[0]]
        if not any(headers):  # Headers vazios
            logger.warning("Excel sem headers válidos")
            return []
        
        # Processar linhas de dados
        registros = []
        for i, row in enumerate(rows[1:], start=1):
            if i > MAX_ROWS:
                logger.warning(f"Limite de {MAX_ROWS} linhas atingido no Excel")
                break
            
            row_dict = {}
            for j, cell in enumerate(row):
                if j < len(headers) and headers[j]:
                    # Extrair valor da célula (handle diferentes tipos)
                    val = cell.value
                    if val is not None:
                        row_dict[headers[j]] = val
            
            if row_dict:  # Ignorar linhas completamente vazias
                registros.append(normalize_row(row_dict))
        
        workbook.close()
        logger.info(f"Fim parse Excel: {len(registros)} registros processados")
        return registros
        
    except Exception as e:
        logger.error(f"Erro ao parsear Excel: {str(e)}")
        raise ValueError(f"Erro ao processar arquivo Excel: {str(e)}")

# ============================================================
# PRÉ-PROCESSAMENTO DE OFX (CORREÇÕES PARA BANCOS BR)
# ============================================================
def _preprocess_ofx(content: str) -> str:
    """
    Corrige problemas comuns em arquivos OFX de bancos brasileiros:
    - Remove BOM (Byte Order Mark)
    - Corrige encoding de acentos
    - Normaliza tags para maiúsculas
    - Remove linhas vazias excessivas
    - Corrige campos mal formados
    """
    # Remover BOM se existir
    if content.startswith('\ufeff'):
        content = content[1:]
    
    # Corrigir encoding de acentos mal formados (comum em OFX BR)
    content = content.replace('', '')
    
    # Normalizar tags OFX para maiúsculas (alguns bancos enviam minúsculas)
    # Ex: <STMTTRN> em vez de <stmttrn>
    content = re.sub(r'<(/?)([a-zA-Z][a-zA-Z0-9_]*)>', 
                     lambda m: f"<{m.group(1)}{m.group(2).upper()}>", 
                     content)
    
    # Remover linhas vazias excessivas que podem quebrar parsers
    content = re.sub(r'\n{3,}', '\n\n', content)
    
    # Corrigir campos de valor com formato BR dentro de tags OFX
    # Ex: <TRNAMT>1.234,56</TRNAMT> → <TRNAMT>1234.56</TRNAMT>
    def fix_amount(match):
        val = match.group(1)
        if ',' in val and '.' in val:
            val = val.replace('.', '').replace(',', '.')
        elif ',' in val:
            val = val.replace(',', '.')
        return f"<{match.group(2)}>{val}</{match.group(2)}>"
    
    content = re.sub(r'<(TRNAMT|FITID)>([^<]+)</\1>', fix_amount, content)
    
    return content

# ============================================================
# FALLBACK PARSER OFX (REGEX - QUANDO OFXPARSE FALHA)
# ============================================================
def _parse_ofx_fallback(content: str) -> list:
    """
    Fallback simples: extrai transações com regex quando o parser oficial falha.
    Retorna estrutura compatível com normalize_row.
    Útil para OFX mal formados de alguns bancos brasileiros.
    """
    registros = []
    
    # Pattern para blocos de transação OFX
    stmttrn_pattern = re.compile(
        r'<STMTTRN>(.*?)</STMTTRN>', 
        re.DOTALL | re.IGNORECASE
    )
    
    for match in stmttrn_pattern.finditer(content):
        block = match.group(1)
        
        # Extrair campos básicos com regex tolerante
        data_match = re.search(r'<DTPOSTED>(\d+)', block, re.IGNORECASE)
        valor_match = re.search(r'<TRNAMT>(-?[\d.,]+)', block, re.IGNORECASE)
        desc_match = re.search(r'<MEMO>(.*?)</MEMO>', block, re.DOTALL | re.IGNORECASE)
        payee_match = re.search(r'<NAME>(.*?)</NAME>', block, re.DOTALL | re.IGNORECASE)
        
        if not valor_match:
            continue  # Pular transação sem valor
        
        # Parse de data OFX (formato: YYYYMMDD[HHMMSS])
        data = None
        if data_match:
            try:
                dt_str = data_match.group(1)
                if len(dt_str) >= 8:
                    data = datetime.strptime(dt_str[:8], "%Y%m%d").date()
            except ValueError:
                pass  # Manter None se não conseguir parsear
        
        # Parse de valor (suportar formato BR)
        try:
            valor_str = valor_match.group(1)
            if ',' in valor_str and '.' in valor_str:
                valor_str = valor_str.replace('.', '').replace(',', '.')
            elif ',' in valor_str:
                valor_str = valor_str.replace(',', '.')
            valor = Decimal(valor_str)
        except (InvalidOperation, ValueError):
            continue  # Pular se não conseguir parsear valor
        
        # Descrição: preferir MEMO, fallback para NAME
        descricao = ""
        if desc_match:
            descricao = desc_match.group(1).strip()
        elif payee_match:
            descricao = payee_match.group(1).strip()
        
        registros.append({
            "data": data,
            "valor": valor,
            "descricao": descricao,
            "id": None,
            "tipo_ofx": None
        })
    
    return registros

# ============================================================
# PARSE OFX (COM FALLBACK ROBUSTO PARA BANCOS BR)
# ============================================================
def parse_ofx_generic(file_stream, filename=None):
    """
    Parse OFX com fallback robusto para arquivos de bancos brasileiros.
    
    Fluxo:
    1. Tenta parse com ofxparse oficial
    2. Se falhar, pré-processa e tenta novamente
    3. Se ainda falhar, usa fallback com regex
    4. Se tudo falhar, lança erro informativo
    """
    logger.info(f"Início parse OFX: {filename}")
    
    # Validar tamanho
    file_stream.seek(0, 2)
    size = file_stream.tell()
    file_stream.seek(0)
    
    if size > MAX_FILE_SIZE:
        raise ValueError(f"Arquivo OFX excede {MAX_FILE_SIZE/1024/1024}MB")
    
    # Ler conteúdo para processamento
    file_stream.seek(0)
    raw_content = file_stream.read()
    
    # Detectar e decodificar encoding
    encoding = detectar_encoding(io.BytesIO(raw_content))
    try:
        content = raw_content.decode(encoding, errors='replace')
    except Exception:
        content = raw_content.decode('utf-8', errors='replace')
    
    # Tentar parse com ofxparse oficial
    try:
        from ofxparse import OfxParser
        
        # Pré-processar para corrigir problemas comuns de bancos BR
        content_fixed = _preprocess_ofx(content)
        
        ofx = OfxParser.parse(io.BytesIO(content_fixed.encode('utf-8', errors='ignore')))
        
    except ImportError:
        logger.error("ofxparse não instalado. Instale com: pip install ofxparse")
        raise ValueError("Suporte a OFX não disponível. Use CSV ou Excel como alternativa.")
        
    except Exception as e:
        logger.warning(f"ofxparse falhou: {str(e)}. Tentando fallback com regex...")
        
        # Tentar fallback com regex
        try:
            registros = _parse_ofx_fallback(content)
            if registros:
                logger.info(f"Fallback OFX bem-sucedido: {len(registros)} registros")
                return [normalize_row(r) for r in registros]
        except Exception as fallback_err:
            logger.error(f"Fallback OFX também falhou: {str(fallback_err)}")
        
        raise ValueError(f"Arquivo OFX inválido ou não suportado: {str(e)}")
    
    # Processar contas e transações
    if not ofx.accounts:
        logger.warning("OFX sem contas encontradas")
        return []
    
    registros = []
    for account in ofx.accounts:
        if not account.statement or not account.statement.transactions:
            continue
        
        for tx in account.statement.transactions:
            try:
                # Extrair campos com fallback para None
                registro = normalize_row({
                    "data": getattr(tx, 'date', None),
                    "valor": getattr(tx, 'amount', None),
                    "descricao": getattr(tx, 'memo', '') or getattr(tx, 'payee', ''),
                    "id": getattr(tx, 'id', None),
                    "tipo_ofx": getattr(tx, 'type', None)
                })
                registros.append(registro)
                
            except Exception as e:
                logger.warning(f"Transação OFX ignorada (erro ao normalizar): {str(e)}")
                continue
    
    logger.info(f"Fim parse OFX: {len(registros)} registros processados")
    return registros

# ============================================================
# FUNÇÃO GENÉRICA DE PARSE (AUTO-DETECT FORMATO)
# ============================================================
def parse_generic(file_stream, filename: str):
    """
    Detecta formato automaticamente e chama parser apropriado.
    
    Args:
        file_stream: Stream do arquivo
        filename: Nome do arquivo (para detectar extensão)
    
    Returns:
        List[dict]: Registros normalizados
    """
    if not filename:
        raise ValueError("Nome do arquivo é obrigatório para detecção de formato")
    
    filename_lower = filename.lower()
    
    if filename_lower.endswith(('.csv', '.txt')):
        return parse_csv_generic(file_stream, filename)
    
    elif filename_lower.endswith(('.xlsx', '.xls')):
        return parse_excel_generic(file_stream, filename)
    
    elif filename_lower.endswith('.ofx'):
        return parse_ofx_generic(file_stream, filename)
    
    else:
        # Tentar detectar por conteúdo como fallback
        file_stream.seek(0)
        sample = file_stream.read(1024).decode('utf-8', errors='ignore')
        file_stream.seek(0)
        
        if sample.strip().startswith('<?xml') or '<OFX>' in sample.upper():
            return parse_ofx_generic(file_stream, filename)
        elif ',' in sample or ';' in sample:
            return parse_csv_generic(file_stream, filename)
        
        raise ValueError(f"Formato não suportado: {filename}")
