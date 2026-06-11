# utils/parsers.py - VERSÃO FINAL COM EXTRAÇÃO DE NAME + DIVISÃO AUTOMÁTICA

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

MAX_FILE_SIZE = 10 * 1024 * 1024
MAX_ROWS = 10000

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

def parse_data(value):
    """Converte valor para date de forma segura."""
    if not value:
        return None
    
    if isinstance(value, (datetime, date)):
        return value if isinstance(value, date) else value.date()
    
    try:
        value = str(value).strip()
        
        formatos = [
            "%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d",
            "%m/%d/%Y", "%Y-%m-%d %H:%M:%S", "%d/%m/%Y %H:%M:%S", "%Y%m%d",
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

def sanitizar_celula(value):
    """Previne CSV/Excel injection."""
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

def normalize_row(row: dict):
    """Normaliza uma linha de dados mapeando nomes de colunas."""
    if not row:
        return {
            "valor": Decimal("0"), 
            "data": None, 
            "descricao": "",
            "tipo_pagamento": "outros"
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
        
        # ✅ NOVO: Extrair NAME (pagador/recebedor)
        elif k in ("name", "pagador", "beneficiario", "favorecido"):
            new["name"] = sanitizar_celula(value)
        
        elif k in ("nsu", "id", "transaction_id", "codigo", "fitid"):
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
    
    # ✅ MELHORADO: Inferir tipo_pagamento analisando descricao e name
    if "tipo_pagamento" not in new or new["tipo_pagamento"] == "cartao":
        new["tipo_pagamento"] = inferir_tipo_pagamento_ofx(new)
    
    return new


def inferir_tipo_pagamento_ofx(registro):
    """
    Infere o tipo de pagamento analisando descricao, name e outros campos.
    ✅ Versão melhorada para OFX de bancos brasileiros
    """
    descricao = str(registro.get('descricao') or '').strip().upper()
    name = str(registro.get('name') or '').strip().upper()
    texto_completo = f"{descricao} {name}"
    
    # ✅ PIX (prioridade máxima)
    if 'PIX' in texto_completo:
        return 'pix'
    
    # ✅ Cartão de Crédito (vendas maquininha)
    if any(kw in texto_completo for kw in [
        'MASTERCARD', 'VISA', 'MAESTRO', 'ELO', 'SIPAG', 
        'CRED.COMPRAS', 'CR COMPRAS'
    ]):
        return 'cartao'
    
    # ✅ Débito
    if any(kw in texto_completo for kw in ['DÉBITO', 'DEBITO', 'DEB._']):
        return 'debito'
    
    # ✅ Boleto/Tributos
    if any(kw in texto_completo for kw in [
        'BOLETO', 'DAS-', 'DAS ', 'TRIBUTOS', 'COMPE', 'TÍTULO'
    ]):
        return 'boleto'
    
    # ✅ Transferência
    if any(kw in texto_completo for kw in [
        'TRANSF', 'TED', 'DOC', 'REM.:', 'FAV.:'
    ]):
        return 'transferencia'
    
    # ✅ Empréstimo
    if 'EMPRÉSTIMO' in texto_completo or 'EMPRESTIMO' in texto_completo:
        return 'emprestimo'
    
    # ✅ Investimento
    if any(kw in texto_completo for kw in ['APLICAÇÃO', 'RESGATE', 'RDC', 'CDB']):
        return 'investimento'
    
    # ✅ Seguro
    if any(kw in texto_completo for kw in ['SEGURO', 'ALLIANZ']):
        return 'seguro'
    
    # Default
    return 'outros'


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
                break
            if row:
                registros.append(normalize_row(dict(row)))
        
        tempo = time.time() - inicio
        logger.info(f"✅ Fim parse CSV: {len(registros)} registros em {tempo:.2f}s")
        return registros
        
    except UnicodeDecodeError:
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
            return []
        
        rows = list(sheet.rows)
        if not rows:
            return []
        
        headers = [str(c.value).strip() if c.value is not None else "" for c in rows[0]]
        if not any(headers):
            return []
        
        registros = []
        for i, row in enumerate(rows[1:], start=1):
            if i > MAX_ROWS:
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

def _extrair_tag_ofx(bloco: str, tag: str) -> str:
    """Extrai valor de uma tag OFX de forma ultra-rápida usando find()."""
    tag_upper = tag.upper()
    bloco_upper = bloco.upper()
    
    start_tag = f"<{tag_upper}>"
    end_tag = f"</{tag_upper}>"
    
    start_idx = bloco_upper.find(start_tag)
    if start_idx == -1:
        return ""
    
    start_idx += len(start_tag)
    
    end_idx = bloco_upper.find(end_tag, start_idx)
    if end_idx == -1:
        next_tag = bloco.find('<', start_idx)
        if next_tag == -1:
            return bloco[start_idx:].strip()
        return bloco[start_idx:next_tag].strip()
    
    return bloco[start_idx:end_idx].strip()


def parse_ofx_generic(file_stream, filename=None):
    """Parser OFX ULTRA-RÁPIDO usando split de string."""
    inicio_total = time.time()
    logger.info(f"🏦 Início parse OFX (split rápido): {filename}")
    
    file_stream.seek(0, 2)
    size = file_stream.tell()
    file_stream.seek(0)
    
    if size > MAX_FILE_SIZE:
        raise ValueError(f"Arquivo OFX excede {MAX_FILE_SIZE/1024/1024}MB")
    
    file_stream.seek(0)
    raw_content = file_stream.read()
    
    encoding = detectar_encoding(io.BytesIO(raw_content))
    try:
        content = raw_content.decode(encoding, errors='replace')
    except Exception:
        content = raw_content.decode('utf-8', errors='replace')
    
    content_upper = content.upper()
    
    logger.info(f"🔍 Arquivo lido: {len(content)} chars, encoding={encoding}")
    
    inicio_split = time.time()
    
    stmttrn_positions = []
    search_start = 0
    while True:
        pos = content_upper.find('<STMTTRN>', search_start)
        if pos == -1:
            break
        stmttrn_positions.append(pos)
        search_start = pos + 1
    
    total_transacoes = len(stmttrn_positions)
    logger.info(f"🔍 Encontradas {total_transacoes} transações no OFX")
    
    if total_transacoes == 0:
        logger.warning("⚠️ Nenhuma transação encontrada no OFX")
        return []
    
    tempo_split = time.time() - inicio_split
    logger.info(f"⏱️ Split inicial: {tempo_split:.3f}s")
    
    registros = []
    timeout_seconds = 10
    inicio_parse = time.time()
    
    max_transacoes = min(total_transacoes, 5000)
    
    for i in range(max_transacoes):
        if i % 100 == 0 and i > 0:
            if time.time() - inicio_parse > timeout_seconds:
                logger.warning(f"⚠️ Timeout atingido após {i} transações")
                break
        
        try:
            start_pos = stmttrn_positions[i]
            
            if i + 1 < total_transacoes:
                end_pos = stmttrn_positions[i + 1]
            else:
                end_pos = len(content)
            
            bloco = content[start_pos:end_pos]
            
            # ✅ Extrair campos incluindo NAME
            dtposted = _extrair_tag_ofx(bloco, "DTPOSTED")
            trnamt = _extrair_tag_ofx(bloco, "TRNAMT")
            memo = _extrair_tag_ofx(bloco, "MEMO")
            name = _extrair_tag_ofx(bloco, "NAME")  # ✅ NOVO
            fitid = _extrair_tag_ofx(bloco, "FITID")
            
            if not trnamt:
                continue
            
            data = None
            if dtposted and len(dtposted) >= 8:
                try:
                    data = datetime.strptime(dtposted[:8], "%Y%m%d").date()
                except ValueError:
                    pass
            
            try:
                valor_str = trnamt
                if ',' in valor_str and '.' in valor_str:
                    valor_str = valor_str.replace('.', '').replace(',', '.')
                elif ',' in valor_str:
                    valor_str = valor_str.replace(',', '.')
                valor = Decimal(valor_str)
            except (InvalidOperation, ValueError):
                continue
            
            # ✅ Combinar MEMO e NAME para descrição completa
            descricao_parts = []
            if memo:
                descricao_parts.append(memo)
            if name and name != memo:
                descricao_parts.append(name)
            descricao = " - ".join(descricao_parts) if descricao_parts else ""
            
            registros.append({
                "data": data,
                "valor": valor,
                "descricao": descricao,
                "name": name,  # ✅ NOVO: pagador/recebedor
                "id": fitid or None,
                "tipo_ofx": None
            })
            
        except Exception as e:
            logger.debug(f"⚠️ Erro ao parsear transação {i}: {str(e)}")
            continue
    
    tempo_parse = time.time() - inicio_parse
    tempo_total = time.time() - inicio_total
    
    logger.info(f"✅ OFX parseado: {len(registros)}/{total_transacoes} registros em {tempo_total:.2f}s")
    
    return [normalize_row(r) for r in registros]


def extrair_dados_conta_ofx(content: str) -> dict:
    """Extrai dados da conta bancária do arquivo OFX."""
    dados = {
        "banco": None,
        "agencia": None,
        "conta": None,
        "tipo": "corrente",
        "nome": None
    }
    
    content_upper = content.upper()
    
    bankid_match = re.search(r'<BANKID>([^<]+)</BANKID>', content_upper)
    if bankid_match:
        dados["banco"] = bankid_match.group(1).strip()
    
    branchid_match = re.search(r'<BRANCHID>([^<]+)</BRANCHID>', content_upper)
    if branchid_match:
        dados["agencia"] = branchid_match.group(1).strip()
    
    acctid_match = re.search(r'<ACCTID>([^<]+)</ACCTID>', content_upper)
    if acctid_match:
        dados["conta"] = acctid_match.group(1).strip()
    
    accttype_match = re.search(r'<ACCTTYPE>([^<]+)</ACCTTYPE>', content_upper)
    if accttype_match:
        tipo_raw = accttype_match.group(1).strip().upper()
        tipo_map = {
            "CHECKING": "corrente",
            "SAVINGS": "poupanca",
            "MONEYMRKT": "investimento",
            "CREDITLINE": "credito"
        }
        dados["tipo"] = tipo_map.get(tipo_raw, "corrente")
    
    if dados["banco"] or dados["agencia"] or dados["conta"]:
        partes = []
        if dados["banco"]:
            partes.append(f"Banco {dados['banco']}")
        if dados["agencia"]:
            partes.append(f"Ag {dados['agencia']}")
        if dados["conta"]:
            partes.append(f"CC {dados['conta']}")
        dados["nome"] = " - ".join(partes)
    else:
        dados["nome"] = "Conta Extraída do OFX"
    
    return dados


def dividir_ofx_em_partes(content: str, max_transacoes: int = 30) -> list:
    """Divide arquivo OFX em partes menores usando find() (NUNCA regex)."""
    content_upper = content.upper()
    
    banktranlist_start = content_upper.find('<BANKTRANLIST>')
    if banktranlist_start == -1:
        return [content]
    
    banktranlist_end = content_upper.find('</BANKTRANLIST>')
    if banktranlist_end == -1:
        return [content]
    
    header = content[:banktranlist_start + len('<BANKTRANLIST>')]
    footer = content[banktranlist_end:]
    
    bloco_transacoes = content[banktranlist_start + len('<BANKTRANLIST>'):banktranlist_end]
    bloco_upper = bloco_transacoes.upper()
    
    posicoes_inicio = []
    search_start = 0
    while True:
        pos = bloco_upper.find('<STMTTRN>', search_start)
        if pos == -1:
            break
        posicoes_inicio.append(pos)
        search_start = pos + 1
    
    total_transacoes = len(posicoes_inicio)
    
    if total_transacoes == 0:
        return [content]
    
    if total_transacoes <= max_transacoes:
        return [content]
    
    transacoes = []
    for i, pos_inicio in enumerate(posicoes_inicio):
        if i + 1 < len(posicoes_inicio):
            pos_fim = posicoes_inicio[i + 1]
        else:
            pos_fim = len(bloco_transacoes)
        
        transacao = bloco_transacoes[pos_inicio:pos_fim].strip()
        transacoes.append(transacao)
    
    partes = []
    num_partes = (total_transacoes + max_transacoes - 1) // max_transacoes
    
    for i in range(num_partes):
        inicio_idx = i * max_transacoes
        fim_idx = min((i + 1) * max_transacoes, total_transacoes)
        
        transacoes_parte = transacoes[inicio_idx:fim_idx]
        ofx_parte = header + '\n' + '\n'.join(transacoes_parte) + '\n' + footer
        partes.append(ofx_parte)
    
    logger.info(f"✅ OFX dividido: {total_transacoes} transações em {len(partes)} partes")
    
    return partes


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
    except:
        pass
    
    try:
        from config.estabelecimentos import ESTABELECIMENTO_PARA_EMPRESA
        if codigo_estabelecimento and codigo_estabelecimento in ESTABELECIMENTO_PARA_EMPRESA:
            return ESTABELECIMENTO_PARA_EMPRESA[codigo_estabelecimento]
    except:
        pass
    
    return fallback


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
        return registros
    
    elif filename_lower.endswith(('.xlsx', '.xls')):
        registros = parse_excel_generic(file_stream, filename)
        if default_empresa_id:
            for reg in registros:
                if 'empresa_id' not in reg or not reg['empresa_id']:
                    reg['empresa_id'] = default_empresa_id
        return registros
    
    elif filename_lower.endswith('.ofx'):
        registros = parse_ofx_generic(file_stream, filename)
        if default_empresa_id:
            for reg in registros:
                if 'empresa_id' not in reg or not reg['empresa_id']:
                    reg['empresa_id'] = default_empresa_id
        return registros
    
    else:
        raise ValueError(f"Formato não suportado: {filename}")
