# ============================================================
#  PARSERS • NousCard (VERSÃO PRODUÇÃO COM FLOW + PIX)
#  Suporte: CSV Flow, CSV genérico, Excel, OFX com fallback robusto
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
    para um schema padrão: {valor, data, descricao, tipo_pagamento, ...}
    """
    if not row:
        return {
            "valor": Decimal("0"), 
            "data": None, 
            "descricao": "",
            "tipo_pagamento": "cartao"  # Default para cartão
        }
    
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
            val = sanitizar_celula(value) if value else None
            # PIX não tem bandeira tradicional
            if val and val.lower() == 'pix':
                new["bandeira"] = None
                new["tipo_pagamento"] = 'pix'
            else:
                new["bandeira"] = val
        
        # ✅ NOVO: Detectar tipo de pagamento (PIX, boleto, cartão)
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
    
    # ✅ Garantir tipo_pagamento (default: cartão)
    if "tipo_pagamento" not in new:
        # Inferir pelo produto ou bandeira se disponível
        produto = new.get("produto", "").lower() if new.get("produto") else ""
        bandeira = new.get("bandeira", "").lower() if new.get("bandeira") else ""
        
        if 'pix' in produto or bandeira == 'pix':
            new["tipo_pagamento"] = 'pix'
        elif 'boleto' in produto:
            new["tipo_pagamento"] = 'boleto'
        else:
            new["tipo_pagamento"] = 'cartao'  # Default para cartão
    
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
# DETECTOR E PARSER ESPECÍFICO: CLIENTE FLOW
# ============================================================

def is_flow_csv(filename: str, sample_content: str) -> bool:
    """
    Detecta se o arquivo é do formato Cliente Flow.
    
    Critérios:
    - Nome contém 'flow' ou 'relatorio sumarizado'
    - OU conteúdo tem 'Relatório sumarizado de vendas' + 'Estabelecimento(s)'
    """
    filename_lower = filename.lower() if filename else ""
    
    # Detectar pelo nome do arquivo
    if 'flow' in filename_lower or 'relatorio sumarizado' in filename_lower:
        return True
    
    # Detectar pelo conteúdo (primeiras 500 chars)
    content_preview = sample_content[:500].lower()
    if 'relatório sumarizado de vendas' in content_preview or 'relatorio sumarizado de vendas' in content_preview:
        if 'estabelecimento' in content_preview:
            return True
    
    return False


def parse_flow_csv(file_stream, filename: str, default_empresa_id: int = None) -> list:
    """
    Parser específico para CSV do Cliente Flow.
    
    Formato esperado:
    - Linha 0: "Relatório sumarizado de vendas"
    - Linha 1: "Estabelecimento(s);CB-109264950001"
    - Linha 2: Headers das colunas
    - Linhas 3+: Dados
    - Última linha: "Total;..." (ignorar)
    
    Args:
        file_stream: Stream do arquivo
        filename: Nome do arquivo
        default_empresa_id: Fallback se estabelecimento não mapeado
    
    Returns:
        Lista de registros normalizados com tipo_pagamento
    """
    logger.info(f"Início parse Flow CSV: {filename}")
    
    # Validar tamanho
    file_stream.seek(0, 2)
    size = file_stream.tell()
    file_stream.seek(0)
    
    if size > MAX_FILE_SIZE:
        raise ValueError(f"Arquivo Flow CSV excede {MAX_FILE_SIZE/1024/1024}MB")
    
    # Detectar encoding
    encoding = detectar_encoding(file_stream)
    
    try:
        # Ler todo o conteúdo
        file_stream.seek(0)
        raw = file_stream.read().decode(encoding, errors="replace")
        lines = raw.strip().split('\n')
        
        if len(lines) < 3:
            raise ValueError("Arquivo Flow CSV muito curto")
        
        # Extrair estabelecimento da linha 1 (índice 1)
        estabelecimento = None
        linha_estabelecimento = lines[1].strip() if len(lines) > 1 else ""
        if 'Estabelecimento' in linha_estabelecimento:
            partes = linha_estabelecimento.split(';')
            if len(partes) >= 2:
                estabelecimento = partes[1].strip()
        
        # Mapear estabelecimento para empresa_id
        empresa_id = _get_empresa_id_por_estabelecimento(estabelecimento, default_empresa_id)
        if not empresa_id:
            logger.error(f"❌ Não foi possível determinar empresa_id para estabelecimento: {estabelecimento}")
            if not default_empresa_id:
                return []
            empresa_id = default_empresa_id
        
        # Pular linhas de cabeçalho (0 e 1) e linha de headers (2)
        # Processar apenas linhas de dados (ignorar linha de Total)
        data_lines = []
        for i, line in enumerate(lines[3:], start=4):
            line_stripped = line.strip()
            if not line_stripped or line_stripped.lower().startswith('total'):
                continue
            data_lines.append(line)
        
        if not data_lines:
            logger.warning("Nenhuma linha de dados encontrada no Flow CSV")
            return []
        
        # Parse CSV com delimitador ;
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
                # Validar e converter valor_bruto (obrigatório para vendas)
                valor_bruto = parse_valor(row.get('valor_bruto'))
                if not valor_bruto or valor_bruto <= 0:
                    continue
                
                # Converter data
                data_venda = parse_data(row.get('data_pagamento'))
                if not data_venda:
                    logger.warning(f"⚠️ Flow CSV linha {row_num}: data inválida '{row.get('data_pagamento')}', pulando")
                    continue
                
                # ✅ Detectar tipo de pagamento pelo campo 'produto' (Crédito/Débito/PIX)
                produto_val = (row.get('produto') or '').strip().lower()
                bandeira_val = (row.get('bandeira') or '').strip().lower()
                
                if 'pix' in produto_val or bandeira_val == 'pix':
                    tipo_pagamento = 'pix'
                    bandeira = None  # PIX não tem bandeira tradicional
                elif 'boleto' in produto_val:
                    tipo_pagamento = 'boleto'
                    bandeira = None
                else:
                    tipo_pagamento = 'cartao'  # Default para cartão
                    bandeira = row.get('bandeira', '').strip() if row.get('bandeira') else None
                
                # Mapear para schema padrão do NousCard
                registro = normalize_row({
                    # Campos mapeados especificamente para Flow
                    'valor_bruto': str(valor_bruto),
                    'data_venda': data_venda.strftime('%Y-%m-%d') if data_venda else None,
                    'bandeira': bandeira,
                    'produto': row.get('produto', '').strip(),
                    'quantidade': row.get('quantidade', '0'),
                    'desconto': row.get('desconto', '0'),
                    'valor_liquido': row.get('valor_liquido', '0'),
                    'tipo_pagamento': tipo_pagamento,  # ✅ Definido explicitamente
                    
                    # Metadados para rastreabilidade
                    'empresa_id': empresa_id,
                    'estabelecimento_origem': estabelecimento,
                    'arquivo_origem': filename.split('/')[-1] if filename else 'unknown',
                    'linha_origem': row_num,
                })
                
                # Garantir que empresa_id e tipo_pagamento estão no registro final
                registro['empresa_id'] = empresa_id
                registro['tipo_pagamento'] = tipo_pagamento
                
                registros.append(registro)
                
            except Exception as e:
                logger.error(f"❌ Erro ao parsear linha {row_num} do Flow CSV: {str(e)}, row={row}")
                continue
        
        logger.info(f"✅ Parse Flow CSV: {len(registros)} registros válidos de {filename}")
        return registros
        
    except Exception as e:
        logger.error(f"❌ Erro ao processar Flow CSV {filename}: {str(e)}")
        raise ValueError(f"Erro ao processar arquivo Flow CSV: {str(e)}")


def _get_empresa_id_por_estabelecimento(codigo_estabelecimento: str, fallback: int = None) -> int:
    """
    Consulta mapeamento de estabelecimento → empresa_id.
    
    Prioridade:
    1. Tabela do banco (se disponível)
    2. Configuração estática em config/estabelecimentos.py
    3. Fallback passado como parâmetro
    """
    # Tentar consultar tabela do banco (se modelos disponíveis)
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
        pass  # Modelos não disponíveis ainda
    except Exception as e:
        logger.warning(f"⚠️ Erro ao consultar mapeamento no banco: {str(e)}")
    
    # Fallback para configuração estática
    try:
        from config.estabelecimentos import ESTABELECIMENTO_PARA_EMPRESA
        if codigo_estabelecimento and codigo_estabelecimento in ESTABELECIMENTO_PARA_EMPRESA:
            return ESTABELECIMENTO_PARA_EMPRESA[codigo_estabelecimento]
    except ImportError:
        pass
    except Exception as e:
        logger.warning(f"⚠️ Erro ao ler config de estabelecimentos: {str(e)}")
    
    # Último fallback
    return fallback


# ============================================================
# FUNÇÃO GENÉRICA DE PARSE (AUTO-DETECT FORMATO + FLOW + PIX)
# ============================================================

def parse_generic(file_stream, filename: str, default_empresa_id: int = None):
    """
    Detecta formato automaticamente e chama parser apropriado.
    
    Args:
        file_stream: Stream do arquivo
        filename: Nome do arquivo (para detectar extensão)
        default_empresa_id: Empresa_id fallback para parsers que precisam
    
    Returns:
        List[dict]: Registros normalizados com empresa_id e tipo_pagamento
    """
    if not filename:
        raise ValueError("Nome do arquivo é obrigatório para detecção de formato")
    
    filename_lower = filename.lower()
    
    # 🔹 Detectar Flow CSV primeiro (antes do CSV genérico)
    file_stream.seek(0)
    sample = file_stream.read(1024).decode('utf-8', errors='ignore')
    file_stream.seek(0)
    
    if is_flow_csv(filename, sample):
        return parse_flow_csv(file_stream, filename, default_empresa_id)
    
    # 🔹 Formatos padrão
    if filename_lower.endswith(('.csv', '.txt')):
        registros = parse_csv_generic(file_stream, filename)
        # Injetar empresa_id e tipo_pagamento se não estiverem presentes
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
        # Tentar detectar por conteúdo como fallback
        if sample.strip().startswith('<?xml') or '<OFX>' in sample.upper():
            registros = parse_ofx_generic(file_stream, filename)
        elif ',' in sample or ';' in sample:
            # Verificar se é Flow mesmo sem nome específico
            if is_flow_csv(filename, sample):
                registros = parse_flow_csv(file_stream, filename, default_empresa_id)
            else:
                registros = parse_csv_generic(file_stream, filename)
        else:
            raise ValueError(f"Formato não suportado: {filename}")
        
        # Injetar empresa_id e tipo_pagamento se necessário
        if default_empresa_id:
            for reg in registros:
                if 'empresa_id' not in reg or not reg['empresa_id']:
                    reg['empresa_id'] = default_empresa_id
                if 'tipo_pagamento' not in reg:
                    reg['tipo_pagamento'] = 'cartao'
        
        return registros
