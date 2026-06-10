# utils/parsers.py - VERSÃO OTIMIZADA COM PERFORMANCE LOGS

import csv
import io
import re
import logging
import time
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
OFX_TIMEOUT_SECONDS = 10  # ✅ Timeout para parser OFX

# ============================================================
# DETECTAR ENCODING (mantém igual)
# ============================================================
def detectar_encoding(file_stream):
    """Detecta encoding do arquivo com fallback seguro"""
    try:
        file_stream.seek(0)
        raw = file_stream.read(10000)
        file_stream.seek(0)
        result = chardet.detect(raw)
        encoding = result.get('encoding') or 'utf-8'
        if encoding.lower() in ('ascii', 'utf-8', 'utf-16', 'latin-1', 'iso-8859-1', 'cp1252'):
            return encoding
        return 'utf-8'
    except Exception:
        file_stream.seek(0)
        return 'utf-8'

# ============================================================
# PARSE VALOR MONETÁRIO (mantém igual)
# ============================================================
def parse_valor(value, raise_on_error=False):
    """Converte valor para Decimal de forma segura."""
    if value is None:
        return Decimal("0")
    
    if isinstance(value, Decimal):
        return value
    
    if isinstance(value, (int, float)):
        return Decimal(str(value))
    
    try:
        value = str(value).strip()
        value = value.replace("R$", "").replace(" ", "").replace("\xa0", "")
        
        if "," in value and "." in value:
            value = value.replace(".", "").replace(",", ".")
        elif "," in value:
            value = value.replace(",", ".")
        
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
# PARSE DATA (mantém igual)
# ============================================================
def parse_data(value):
    """Converte valor para date de forma segura."""
    if not value:
        return None
    
    if isinstance(value, (datetime, date)):
        return value if isinstance(value, date) else value.date()
    
    try:
        value = str(value).strip()
        
        formatos = [
            "%Y-%m-%d",
            "%d/%m/%Y",
            "%d-%m-%Y",
            "%Y/%m/%d",
            "%m/%d/%Y",
            "%Y-%m-%d %H:%M:%S",
            "%d/%m/%Y %H:%M:%S",
            "%Y%m%d",
        ]
        
        for fmt in formatos:
            try:
                return datetime.strptime(value, fmt).date()
            except ValueError:
                continue
        
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
# SANITIZAR CÉLULA (mantém igual)
# ============================================================
def sanitizar_celula(value):
    """Previne CSV/Excel injection sanitizando valores de células."""
    if not value:
        return ""
    
    try:
        value = str(value).strip()
        
        if value and value[0] in ('=', '+', '-', '@', '\t', '\r', '\n'):
            value = "'" + value
        
        value = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', value)
        
        if len(value) > 1000:
            value = value[:1000] + "..."
        
        return value
        
    except Exception as e:
        logger.warning(f"Erro ao sanitizar célula: {str(e)}")
        return ""

# ============================================================
# NORMALIZAR ROW (mantém igual)
# ============================================================
def normalize_row(row: dict):
    """Normaliza uma linha de dados mapeando nomes de colunas."""
    if not row:
        return {
            "valor": Decimal("0"), 
            "data": None, 
            "descricao": "",
            "tipo_pagamento": "cartao"
        }
    
    new = {}
    valor_alternativo = None
    
    for key, value in row.items():
        if key is None:
            continue
        
        k = str(key).strip().lower()
        
        if k in ("valor", "amount", "valor_bruto", "vlr", "price", "value"):
            new["valor"] = parse_valor(value)
        
        elif k in ("entrada", "creditado", "credito", "valor_liquido", 
                   "vlr_liq", "valor_liq", "lancado", "liquid_value"):
            valor_alternativo = parse_valor(value)
        
        elif re.search(r"valor|liq|credit|amount", k):
            valor_alternativo = parse_valor(value)
        
        elif k in ("data", "date", "dt", "transaction_date", "data_venda", "data_pagamento"):
            new["data"] = parse_data(value)
        elif re.search(r"data|date|dt", k):
            new["data"] = parse_data(value)
        
        elif k in ("descricao", "desc", "memo", "historico", "detalhe", "description", "note"):
            new["descricao"] = sanitizar_celula(value)
        
        elif k in ("nsu", "id", "transaction_id", "codigo"):
            new["nsu"] = sanitizar_celula(value) if value else None
        elif k in ("adquirente", "merchant", "estabelecimento"):
            new["adquirente"] = sanitizar_celula(value) if value else None
        elif k in ("bandeira", "card", "brand"):
            val = sanitizar_celula(value) if value else None
            if val and val.lower() == 'pix':
                new["bandeira"] = None
                new["tipo_pagamento"] = 'pix'
            else:
                new["bandeira"] = val
        
        elif k in ("tipo_pagamento", "forma_pagamento", "payment_method", "payment_type", "produto"):
            val = str(value).strip().lower()
            if 'pix' in val:
                new["tipo_pagamento"] = 'pix'
            elif 'boleto' in val or 'billet' in val:
                new["tipo_pagamento"] = 'boleto'
            elif 'cartao' in val or 'cartão' in val or 'credit' in val or 'debit' in val:
                new["tipo_pagamento"] = 'cartao'
            else:
                new["tipo_pagamento"] = 'outros'
        
        else:
            new[k] = sanitizar_celula(value) if value else ""
    
    if "valor" not in new or new["valor"] == Decimal("0"):
        if valor_alternativo is not None:
            new["valor"] = valor_alternativo
        else:
            new["valor"] = Decimal("0")
    
    if "descricao" not in new:
        new["descricao"] = ""
    
    if "data" not in new:
        new["data"] = None
    
    if "tipo_pagamento" not in new:
        produto = new.get("produto", "").lower() if new.get("produto") else ""
        bandeira = new.get("bandeira", "").lower() if new.get("bandeira") else ""
        
        if 'pix' in produto or bandeira == 'pix':
            new["tipo_pagamento"] = 'pix'
        elif 'boleto' in produto:
            new["tipo_pagamento"] = 'boleto'
        else:
            new["tipo_pagamento"] = 'cartao'
    
    return new

# ============================================================
# PARSE CSV (mantém igual)
# ============================================================
def parse_csv_generic(file_stream, filename=None):
    """Parse CSV com detecção automática de encoding."""
    inicio = time.time()
    logger.info(f"📄 Início parse CSV: {filename}")
    
    file_stream.seek(0, 2)
    size = file_stream.tell()
    file_stream.seek(0)
    
    if size > MAX_FILE_SIZE:
        raise ValueError(f"Arquivo CSV excede {MAX_FILE_SIZE/1024/1024}MB")
    
    encoding = detectar_encoding(file_stream)
    logger.info(f"🔍 Encoding detectado: {encoding}")
    
    try:
        raw = file_stream.read().decode(encoding, errors="replace")
        
        sample = raw[:4096]
        delimitador = ','
        if ';' in sample and sample.count(';') > sample.count(','):
            delimitador = ';'
        elif '|' in sample and sample.count('|') > sample.count(','):
            delimitador = '|'
        elif '\t' in sample:
            delimitador = '\t'
        
        reader = csv.DictReader(io.StringIO(raw), delimiter=delimitador)
        
        registros = []
        for i, row in enumerate(reader):
            if i >= MAX_ROWS:
                logger.warning(f"⚠️ Limite de {MAX_ROWS} linhas atingido")
                break
            if row:
                registros.append(normalize_row(dict(row)))
        
        tempo = time.time() - inicio
        logger.info(f"✅ Fim parse CSV: {len(registros)} registros em {tempo:.2f}s")
        return registros
        
    except UnicodeDecodeError as e:
        logger.error(f"Erro de encoding: {str(e)}")
        file_stream.seek(0)
        raw = file_stream.read().decode('latin-1', errors='replace')
        reader = csv.DictReader(io.StringIO(raw))
        registros = [normalize_row(dict(row)) for i, row in enumerate(reader) if i < MAX_ROWS and row]
        tempo = time.time() - inicio
        logger.info(f"✅ Fim parse CSV (fallback): {len(registros)} registros em {tempo:.2f}s")
        return registros
        
    except Exception as e:
        logger.error(f"❌ Erro ao parsear CSV: {str(e)}")
        raise ValueError(f"Erro ao processar arquivo CSV: {str(e)}")

# ============================================================
# PARSE EXCEL (mantém igual)
# ============================================================
def parse_excel_generic(file_stream, filename=None):
    """Parse Excel com proteção XXE."""
    inicio = time.time()
    logger.info(f"📊 Início parse Excel: {filename}")
    
    file_stream.seek(0, 2)
    size = file_stream.tell()
    file_stream.seek(0)
    
    if size > MAX_FILE_SIZE:
        raise ValueError(f"Arquivo Excel excede {MAX_FILE_SIZE/1024/1024}MB")
    
    try:
        workbook = load_workbook(
            filename=io.BytesIO(file_stream.read()),
            data_only=True,
            keep_links=False,
            read_only=True
        )
        
        sheet = workbook.active
        if not sheet:
            logger.warning("Excel sem sheet ativa")
            return []
        
        rows = list(sheet.rows)
        if not rows:
            return []
        
        headers = [str(c.value).strip() if c.value is not None else "" for c in rows[0]]
        if not any(headers):
            logger.warning("Excel sem headers válidos")
            return []
        
        registros = []
        for i, row in enumerate(rows[1:], start=1):
            if i > MAX_ROWS:
                logger.warning(f"⚠️ Limite de {MAX_ROWS} linhas atingido")
                break
            
            row_dict = {}
            for j, cell in enumerate(row):
                if j < len(headers) and headers[j]:
                    val = cell.value
                    if val is not None:
                        row_dict[headers[j]] = val
            
            if row_dict:
                registros.append(normalize_row(row_dict))
        
        workbook.close()
        tempo = time.time() - inicio
        logger.info(f"✅ Fim parse Excel: {len(registros)} registros em {tempo:.2f}s")
        return registros
        
    except Exception as e:
        logger.error(f"❌ Erro ao parsear Excel: {str(e)}")
        raise ValueError(f"Erro ao processar arquivo Excel: {str(e)}")

# ============================================================
# PRÉ-PROCESSAMENTO DE OFX (mantém igual)
# ============================================================
def _preprocess_ofx(content: str) -> str:
    """Corrige problemas comuns em arquivos OFX de bancos brasileiros."""
    if content.startswith('\ufeff'):
        content = content[1:]
    
    content = content.replace('', '')
    
    content = re.sub(r'<(/?)([a-zA-Z][a-zA-Z0-9_]*)>', 
                     lambda m: f"<{m.group(1)}{m.group(2).upper()}>", 
                     content)
    
    content = re.sub(r'\n{3,}', '\n\n', content)
    
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
# ✅ FALLBACK PARSER OFX OTIMIZADO (COM TIMEOUT)
# ============================================================
def _parse_ofx_fallback_otimizado(content: str, timeout_seconds=10) -> list:
    """
    Fallback OFX otimizado com timeout e regex eficiente.
    
    ✅ Melhorias:
    - Timeout de 10 segundos
    - Regex pré-compilado (mais rápido)
    - Logs de performance
    - Limite de transações
    """
    inicio = time.time()
    logger.info(f"🔍 Iniciando fallback OFX otimizado (timeout={timeout_seconds}s)")
    
    registros = []
    
    # ✅ Regex pré-compilado (MUITO mais rápido)
    stmttrn_pattern = re.compile(r'<STMTTRN>(.*?)</STMTTRN>', re.DOTALL | re.IGNORECASE)
    data_pattern = re.compile(r'<DTPOSTED>(\d{8})', re.IGNORECASE)
    valor_pattern = re.compile(r'<TRNAMT>(-?[\d.,]+)', re.IGNORECASE)
    memo_pattern = re.compile(r'<MEMO>(.*?)</MEMO>', re.DOTALL | re.IGNORECASE)
    name_pattern = re.compile(r'<NAME>(.*?)</NAME>', re.DOTALL | re.IGNORECASE)
    
    # Encontrar todas as transações
    matches = stmttrn_pattern.findall(content)
    total_matches = len(matches)
    logger.info(f"🔍 Encontradas {total_matches} transações no OFX")
    
    # ✅ Limitar processamento para não travar
    max_transacoes = min(total_matches, 5000)
    
    for i, block in enumerate(matches[:max_transacoes]):
        # ✅ Verificar timeout a cada 100 transações
        if i % 100 == 0:
            if time.time() - inicio > timeout_seconds:
                logger.warning(f"⚠️ Timeout atingido após {i} transações ({time.time() - inicio:.2f}s)")
                break
        
        try:
            # Extrair campos
            data_match = data_pattern.search(block)
            valor_match = valor_pattern.search(block)
            memo_match = memo_pattern.search(block)
            name_match = name_pattern.search(block)
            
            if not valor_match:
                continue
            
            # Parse de data
            data = None
            if data_match:
                try:
                    dt_str = data_match.group(1)
                    data = datetime.strptime(dt_str[:8], "%Y%m%d").date()
                except ValueError:
                    pass
            
            # Parse de valor
            try:
                valor_str = valor_match.group(1)
                if ',' in valor_str and '.' in valor_str:
                    valor_str = valor_str.replace('.', '').replace(',', '.')
                elif ',' in valor_str:
                    valor_str = valor_str.replace(',', '.')
                valor = Decimal(valor_str)
            except (InvalidOperation, ValueError):
                continue
            
            # Descrição
            descricao = ""
            if memo_match:
                descricao = memo_match.group(1).strip()
            elif name_match:
                descricao = name_match.group(1).strip()
            
            registros.append({
                "data": data,
                "valor": valor,
                "descricao": descricao,
                "id": None,
                "tipo_ofx": None
            })
            
        except Exception as e:
            logger.debug(f"⚠️ Erro ao parsear transação {i}: {str(e)}")
            continue
    
    tempo = time.time() - inicio
    logger.info(f"✅ Fallback OFX: {len(registros)} registros em {tempo:.2f}s")
    
    return registros

# ============================================================
# ✅ PARSE OFX OTIMIZADO (COM TIMEOUT E LOGS)
# ============================================================
def parse_ofx_generic(file_stream, filename=None):
    """
    Parse OFX otimizado com timeout e logs de performance.
    
    ✅ Melhorias:
    - Timeout de 10s no fallback
    - Logs de performance em cada etapa
    - Regex otimizado
    """
    inicio_total = time.time()
    logger.info(f"🏦 Início parse OFX: {filename}")
    
    # Validar tamanho
    file_stream.seek(0, 2)
    size = file_stream.tell()
    file_stream.seek(0)
    
    if size > MAX_FILE_SIZE:
        raise ValueError(f"Arquivo OFX excede {MAX_FILE_SIZE/1024/1024}MB")
    
    # Ler conteúdo
    file_stream.seek(0)
    raw_content = file_stream.read()
    
    inicio_decode = time.time()
    encoding = detectar_encoding(io.BytesIO(raw_content))
    try:
        content = raw_content.decode(encoding, errors='replace')
    except Exception:
        content = raw_content.decode('utf-8', errors='replace')
    
    tempo_decode = time.time() - inicio_decode
    logger.info(f"⏱️ Decode OFX: {tempo_decode:.2f}s (encoding={encoding})")
    
    # Tentar ofxparse oficial
    inicio_ofxparse = time.time()
    try:
        from ofxparse import OfxParser
        
        content_fixed = _preprocess_ofx(content)
        ofx = OfxParser.parse(io.BytesIO(content_fixed.encode('utf-8', errors='ignore')))
        
        tempo_ofxparse = time.time() - inicio_ofxparse
        logger.info(f"✅ ofxparse bem-sucedido em {tempo_ofxparse:.2f}s")
        
    except ImportError:
        logger.error("❌ ofxparse não instalado")
        raise ValueError("Suporte a OFX não disponível. Use CSV ou Excel.")
        
    except Exception as e:
        tempo_ofxparse = time.time() - inicio_ofxparse
        logger.warning(f"⚠️ ofxparse falhou em {tempo_ofxparse:.2f}s: {str(e)}")
        logger.info("🔄 Tentando fallback regex otimizado...")
        
        # ✅ Usar fallback otimizado com timeout
        try:
            registros = _parse_ofx_fallback_otimizado(content, timeout_seconds=OFX_TIMEOUT_SECONDS)
            if registros:
                tempo_total = time.time() - inicio_total
                logger.info(f"✅ OFX parseado com fallback: {len(registros)} registros em {tempo_total:.2f}s")
                return [normalize_row(r) for r in registros]
        except Exception as fallback_err:
            logger.error(f"❌ Fallback OFX também falhou: {str(fallback_err)}")
        
        raise ValueError(f"Arquivo OFX inválido ou não suportado: {str(e)}")
    
    # Processar contas e transações
    inicio_process = time.time()
    
    if not ofx.accounts:
        logger.warning("⚠️ OFX sem contas encontradas")
        return []
    
    registros = []
    for account in ofx.accounts:
        if not account.statement or not account.statement.transactions:
            continue
        
        for tx in account.statement.transactions:
            try:
                registro = normalize_row({
                    "data": getattr(tx, 'date', None),
                    "valor": getattr(tx, 'amount', None),
                    "descricao": getattr(tx, 'memo', '') or getattr(tx, 'payee', ''),
                    "id": getattr(tx, 'id', None),
                    "tipo_ofx": getattr(tx, 'type', None)
                })
                registros.append(registro)
                
            except Exception as e:
                logger.warning(f"⚠️ Transação OFX ignorada: {str(e)}")
                continue
    
    tempo_process = time.time() - inicio_process
    tempo_total = time.time() - inicio_total
    
    logger.info(f"✅ OFX processado: {len(registros)} registros em {tempo_total:.2f}s (parse={tempo_ofxparse:.2f}s, process={tempo_process:.2f}s)")
    
    return registros

# ============================================================
# DETECTOR E PARSER FLOW (mantém igual)
# ============================================================

def is_flow_csv(filename: str, sample_content: str) -> bool:
    """Detecta se o arquivo é do formato Cliente Flow."""
    filename_lower = filename.lower() if filename else ""
    
    if 'flow' in filename_lower or 'relatorio sumarizado' in filename_lower:
        return True
    
    content_preview = sample_content[:500].lower()
    if 'relatório sumarizado de vendas' in content_preview or 'relatorio sumarizado de vendas' in content_preview:
        if 'estabelecimento' in content_preview:
            return True
    
    return False


def parse_flow_csv(file_stream, filename: str, default_empresa_id: int = None) -> list:
    """Parser específico para CSV do Cliente Flow."""
    inicio = time.time()
    logger.info(f"📄 Início parse Flow CSV: {filename}")
    
    file_stream.seek(0, 2)
    size = file_stream.tell()
    file_stream.seek(0)
    
    if size > MAX_FILE_SIZE:
        raise ValueError(f"Arquivo Flow CSV excede {MAX_FILE_SIZE/1024/1024}MB")
    
    encoding = detectar_encoding(file_stream)
    
    try:
        file_stream.seek(0)
        raw = file_stream.read().decode(encoding, errors="replace")
        lines = raw.strip().split('\n')
        
        if len(lines) < 3:
            raise ValueError("Arquivo Flow CSV muito curto")
        
        estabelecimento = None
        linha_estabelecimento = lines[1].strip() if len(lines) > 1 else ""
        if 'Estabelecimento' in linha_estabelecimento:
            partes = linha_estabelecimento.split(';')
            if len(partes) >= 2:
                estabelecimento = partes[1].strip()
        
        empresa_id = _get_empresa_id_por_estabelecimento(estabelecimento, default_empresa_id)
        if not empresa_id:
            logger.error(f"❌ Não foi possível determinar empresa_id: {estabelecimento}")
            if not default_empresa_id:
                return []
            empresa_id = default_empresa_id
        
        data_lines = []
        for i, line in enumerate(lines[3:], start=4):
            line_stripped = line.strip()
            if not line_stripped or line_stripped.lower().startswith('total'):
                continue
            data_lines.append(line)
        
        if not data_lines:
            logger.warning("⚠️ Nenhuma linha de dados encontrada")
            return []
        
        reader = csv.DictReader(
            data_lines,
            delimiter=';',
            fieldnames=[
                'estabelecimento', 'data_pagamento', 'bandeira',
                'produto', 'quantidade', 'valor_bruto',
                'desconto', 'valor_liquido'
            ]
        )
        
        registros = []
        for row_num, row in enumerate(reader, start=4):
            try:
                valor_bruto = parse_valor(row.get('valor_bruto'))
                if not valor_bruto or valor_bruto <= 0:
                    continue
                
                data_venda = parse_data(row.get('data_pagamento'))
                if not data_venda:
                    logger.warning(f"⚠️ Flow CSV linha {row_num}: data inválida")
                    continue
                
                produto_val = (row.get('produto') or '').strip().lower()
                bandeira_val = (row.get('bandeira') or '').strip().lower()
                
                if 'pix' in produto_val or bandeira_val == 'pix':
                    tipo_pagamento = 'pix'
                    bandeira = None
                elif 'boleto' in produto_val:
                    tipo_pagamento = 'boleto'
                    bandeira = None
                else:
                    tipo_pagamento = 'cartao'
                    bandeira = row.get('bandeira', '').strip() if row.get('bandeira') else None
                
                registro = normalize_row({
                    'valor_bruto': str(valor_bruto),
                    'data_venda': data_venda.strftime('%Y-%m-%d') if data_venda else None,
                    'bandeira': bandeira,
                    'produto': row.get('produto', '').strip(),
                    'quantidade': row.get('quantidade', '0'),
                    'desconto': row.get('desconto', '0'),
                    'valor_liquido': row.get('valor_liquido', '0'),
                    'tipo_pagamento': tipo_pagamento,
                    'empresa_id': empresa_id,
                    'estabelecimento_origem': estabelecimento,
                    'arquivo_origem': filename.split('/')[-1] if filename else 'unknown',
                    'linha_origem': row_num,
                })
                
                registro['empresa_id'] = empresa_id
                registro['tipo_pagamento'] = tipo_pagamento
                
                registros.append(registro)
                
            except Exception as e:
                logger.error(f"❌ Erro ao parsear linha {row_num}: {str(e)}")
                continue
        
        tempo = time.time() - inicio
        logger.info(f"✅ Parse Flow CSV: {len(registros)} registros em {tempo:.2f}s")
        return registros
        
    except Exception as e:
        logger.error(f"❌ Erro ao processar Flow CSV: {str(e)}")
        raise ValueError(f"Erro ao processar arquivo Flow CSV: {str(e)}")


def _get_empresa_id_por_estabelecimento(codigo_estabelecimento: str, fallback: int = None) -> int:
    """Consulta mapeamento de estabelecimento → empresa_id."""
    try:
        from models import EstabelecimentoMapeamento
        if codigo_estabelecimento:
            mapeamento = EstabelecimentoMapeamento.query.filter_by(
                codigo_estabelecimento=codigo_estabelecimento,
                ativo=True
            ).first()
            if mapeamento:
                return mapeamento.empresa_id
    except ImportError:
        pass
    except Exception as e:
        logger.warning(f"⚠️ Erro ao consultar mapeamento: {str(e)}")
    
    try:
        from config.estabelecimentos import ESTABELECIMENTO_PARA_EMPRESA
        if codigo_estabelecimento and codigo_estabelecimento in ESTABELECIMENTO_PARA_EMPRESA:
            return ESTABELECIMENTO_PARA_EMPRESA[codigo_estabelecimento]
    except ImportError:
        pass
    except Exception as e:
        logger.warning(f"⚠️ Erro ao ler config: {str(e)}")
    
    return fallback


# ============================================================
# FUNÇÃO GENÉRICA (mantém igual)
# ============================================================

def parse_generic(file_stream, filename: str, default_empresa_id: int = None):
    """Detecta formato automaticamente e chama parser apropriado."""
    if not filename:
        raise ValueError("Nome do arquivo é obrigatório")
    
    filename_lower = filename.lower()
    
    file_stream.seek(0)
    sample = file_stream.read(1024).decode('utf-8', errors='ignore')
    file_stream.seek(0)
    
    if is_flow_csv(filename, sample):
        return parse_flow_csv(file_stream, filename, default_empresa_id)
    
    if filename_lower.endswith(('.csv', '.txt')):
        registros = parse_csv_generic(file_stream, filename)
        if default_empresa_id:
            for reg in registros:
                if 'empresa_id' not in reg or not reg['empresa_id']:
                    reg['empresa_id'] = default_empresa_id
                if 'tipo_pagamento' not in reg:
                    reg['tipo_pagamento'] = 'cartao'
        return registros
    
    elif filename_lower.endswith(('.xlsx', '.xls')):
        registros = parse_excel_generic(file_stream, filename)
        if default_empresa_id:
            for reg in registros:
                if 'empresa_id' not in reg or not reg['empresa_id']:
                    reg['empresa_id'] = default_empresa_id
                if 'tipo_pagamento' not in reg:
                    reg['tipo_pagamento'] = 'cartao'
        return registros
    
    elif filename_lower.endswith('.ofx'):
        registros = parse_ofx_generic(file_stream, filename)
        if default_empresa_id:
            for reg in registros:
                if 'empresa_id' not in reg or not reg['empresa_id']:
                    reg['empresa_id'] = default_empresa_id
                if 'tipo_pagamento' not in reg:
                    reg['tipo_pagamento'] = 'cartao'
        return registros
    
    else:
        if sample.strip().startswith('<?xml') or '<OFX>' in sample.upper():
            registros = parse_ofx_generic(file_stream, filename)
        elif ',' in sample or ';' in sample:
            if is_flow_csv(filename, sample):
                registros = parse_flow_csv(file_stream, filename, default_empresa_id)
            else:
                registros = parse_csv_generic(file_stream, filename)
        else:
            raise ValueError(f"Formato não suportado: {filename}")
        
        if default_empresa_id:
            for reg in registros:
                if 'empresa_id' not in reg or not reg['empresa_id']:
                    reg['empresa_id'] = default_empresa_id
                if 'tipo_pagamento' not in reg:
                    reg['tipo_pagamento'] = 'cartao'
        
        return registros
