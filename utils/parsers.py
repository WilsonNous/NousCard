# utils/parsers.py - VERSÃO FINAL COMPLETA COM TODAS AS FUNÇÕES

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

# ============================================================
# ENCODING
# ============================================================
def detectar_encoding(file_stream):
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
# PARSE VALOR
# ============================================================
def parse_valor(value, raise_on_error=False):
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
        logger.warning(f"Valor inválido: '{value}', erro: {str(e)}")
        if raise_on_error:
            raise
        return Decimal("0")

# ============================================================
# PARSE DATA
# ============================================================
def parse_data(value):
    if not value:
        return None
    if isinstance(value, (datetime, date)):
        return value if isinstance(value, date) else value.date()
    try:
        value = str(value).strip()
        # Remove timezone se presente
        if '[' in value:
            value = value.split('[')[0]
        formatos = [
            "%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d",
            "%m/%d/%Y", "%Y-%m-%d %H:%M:%S", "%d/%m/%Y %H:%M:%S", "%Y%m%d",
            "%Y%m%d%H%M%S",
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
        return None
    except Exception as e:
        logger.warning(f"Erro ao parsear data '{value}': {str(e)}")
        return None

# ============================================================
# SANITIZAR
# ============================================================
def sanitizar_celula(value):
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
        logger.warning(f"Erro ao sanitizar: {str(e)}")
        return ""

# ============================================================
# CATEGORIZAÇÃO AUTOMÁTICA DE TRANSAÇÕES
# ============================================================
def categorizar_transacao(descricao: str, name: str, valor: Decimal, trntype: str = None) -> str:
    """Categoriza automaticamente a transação baseada em palavras-chave."""
    texto = f"{descricao} {name}".upper()
    eh_credito = valor > 0 or trntype == 'CREDIT'
    
    if eh_credito:
        # Vendas via Maquininha (SIPAG/adquirentes)
        if any(kw in texto for kw in ['CR COMPRAS', 'SIPAG', 'CRED.COMPRAS']):
            if 'MASTERCARD' in texto:
                return 'vendas_mastercard'
            elif 'VISA' in texto and 'ELECTRON' not in texto:
                return 'vendas_visa'
            elif 'MAESTRO' in texto:
                return 'vendas_maestro'
            elif 'ELECTRON' in texto:
                return 'vendas_visa_electron'
            elif 'ELO' in texto:
                return 'vendas_elo'
            else:
                return 'vendas_cartao'
        
        if 'PIX RECEBIDO' in texto or ('RECEBIMENTO' in texto and 'PIX' in texto):
            return 'pix_recebido'
        
        if 'DEVOLUÇÃO' in texto or 'DEVOLUCAO' in texto:
            return 'devolucao_pix'
        
        if any(kw in texto for kw in ['TRANSF.RECEBIDA', 'CRED.TRANSF', 'REM.:']):
            return 'transferencia_recebida'
        
        if 'RESGATE' in texto:
            return 'resgate_investimento'
        
        if 'CRÉDITO EM CONTA' in texto or 'CREDITO EM CONTA' in texto:
            return 'credito_conta'
        
        return 'outras_receitas'
    
    else:
        if 'PIX EMITIDO' in texto or ('PAGAMENTO' in texto and 'PIX' in texto):
            if 'MESMA TIT' in texto:
                return 'pix_transferencia_propria'
            return 'pix_fornecedores'
        
        if any(kw in texto for kw in ['TRANSF.REALIZADA', 'DÉB.TRANSF', 'DEB.TRANSF', 'FAV.:']):
            return 'transferencia_enviada'
        
        if 'EMPRÉSTIMO' in texto or 'EMPRESTIMO' in texto:
            return 'emprestimo'
        
        if any(kw in texto for kw in ['TRIBUTOS', 'DAS-', 'DAS ', 'IMPOSTO', 'RFB', 'COMPE']):
            if 'SIMPLES' in texto or 'DAS-' in texto:
                return 'tributos_simples'
            return 'tributos'
        
        if any(kw in texto for kw in ['BOLETO', 'TÍTULO', 'TIT.COMPE']):
            return 'boleto'
        
        if any(kw in texto for kw in ['SEGURO', 'ALLIANZ']):
            return 'seguro'
        
        if any(kw in texto for kw in ['PACOTE SERVIÇOS', 'TARIFA', 'TARIFAS', 'MANUTENÇÃO']):
            return 'tarifa_bancaria'
        
        if any(kw in texto for kw in ['APLICAÇÃO', 'APLICACAO', 'RDC', 'CDB']):
            return 'aplicacao_investimento'
        
        if 'DÉB.CONV' in texto or 'DEB.CONV' in texto:
            return 'debito_cartao'
        
        return 'outras_despesas'

# ============================================================
# INFERIR TIPO PAGAMENTO
# ============================================================
def inferir_tipo_pagamento_ofx(registro):
    """Infere tipo_pagamento analisando descricao, name e trntype."""
    descricao = str(registro.get('descricao') or '').upper()
    name = str(registro.get('name') or '').upper()
    trntype = str(registro.get('trntype') or '').upper()
    texto = f"{descricao} {name}"
    
    if 'PIX' in texto:
        return 'pix'
    if any(kw in texto for kw in ['MASTERCARD', 'VISA', 'MAESTRO', 'ELO', 'SIPAG', 'CRED.COMPRAS', 'CR COMPRAS']):
        return 'cartao'
    if any(kw in texto for kw in ['DÉBITO', 'DEBITO', 'DEB._', 'VISA ELECTRON']):
        return 'debito'
    if any(kw in texto for kw in ['BOLETO', 'DAS-', 'DAS ', 'TRIBUTOS', 'COMPE', 'TÍTULO']):
        return 'boleto'
    if any(kw in texto for kw in ['TRANSF', 'TED', 'DOC', 'REM.:', 'FAV.:']):
        return 'transferencia'
    if 'EMPRÉSTIMO' in texto or 'EMPRESTIMO' in texto:
        return 'emprestimo'
    if any(kw in texto for kw in ['APLICAÇÃO', 'RESGATE', 'RDC', 'CDB']):
        return 'investimento'
    if any(kw in texto for kw in ['SEGURO', 'ALLIANZ']):
        return 'seguro'
    if any(kw in texto for kw in ['PACOTE SERVIÇOS', 'TARIFA']):
        return 'tarifa'
    return 'outros'

# ============================================================
# NORMALIZE ROW
# ============================================================
def normalize_row(row: dict):
    if not row:
        return {
            "valor": Decimal("0"), 
            "data": None, 
            "descricao": "",
            "tipo_pagamento": "outros",
            "categoria": "outros"
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
        elif k in ("name", "pagador", "beneficiario", "favorecido"):
            new["name"] = sanitizar_celula(value)
        elif k in ("trntype", "tipo_transacao"):
            new["trntype"] = sanitizar_celula(value)
        
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
    
    if "tipo_pagamento" not in new or new["tipo_pagamento"] in ("cartao", "outros"):
        new["tipo_pagamento"] = inferir_tipo_pagamento_ofx(new)
    
    new["categoria"] = categorizar_transacao(
        new.get("descricao", ""),
        new.get("name", ""),
        new.get("valor", Decimal("0")),
        new.get("trntype")
    )
    
    return new

# ============================================================
# PARSE CSV
# ============================================================
def parse_csv_generic(file_stream, filename=None):
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
        return registros
    except Exception as e:
        logger.error(f"❌ Erro ao parsear CSV: {str(e)}")
        raise ValueError(f"Erro ao processar CSV: {str(e)}")

# ============================================================
# PARSE EXCEL
# ============================================================
def parse_excel_generic(file_stream, filename=None):
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
            data_only=True, keep_links=False, read_only=True
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
        raise ValueError(f"Erro ao processar Excel: {str(e)}")

# ============================================================
# PARSER OFX
# ============================================================
def _extrair_tag_ofx(bloco: str, tag: str) -> str:
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
    inicio_total = time.time()
    logger.info(f"🏦 Início parse OFX: {filename}")
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
    
    stmttrn_positions = []
    search_start = 0
    while True:
        pos = content_upper.find('<STMTTRN>', search_start)
        if pos == -1:
            break
        stmttrn_positions.append(pos)
        search_start = pos + 1
    
    total_transacoes = len(stmttrn_positions)
    logger.info(f"🔍 {total_transacoes} transações no OFX")
    if total_transacoes == 0:
        return []
    
    registros = []
    for i, start_pos in enumerate(stmttrn_positions):
        if i + 1 < total_transacoes:
            end_pos = stmttrn_positions[i + 1]
        else:
            end_pos = len(content)
        bloco = content[start_pos:end_pos]
        
        dtposted = _extrair_tag_ofx(bloco, "DTPOSTED")
        trnamt = _extrair_tag_ofx(bloco, "TRNAMT")
        memo = _extrair_tag_ofx(bloco, "MEMO")
        name = _extrair_tag_ofx(bloco, "NAME")
        fitid = _extrair_tag_ofx(bloco, "FITID")
        trntype = _extrair_tag_ofx(bloco, "TRNTYPE")
        checknum = _extrair_tag_ofx(bloco, "CHECKNUM")
        refnum = _extrair_tag_ofx(bloco, "REFNUM")
        
        if not trnamt:
            continue
        
        data = None
        if dtposted:
            dtposted_clean = dtposted.split('[')[0] if '[' in dtposted else dtposted
            if len(dtposted_clean) >= 8:
                try:
                    data = datetime.strptime(dtposted_clean[:8], "%Y%m%d").date()
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
            "name": name,
            "trntype": trntype,
            "id": fitid or None,
            "checknum": checknum or None,
            "refnum": refnum or None,
            "tipo_ofx": None
        })
    
    tempo_total = time.time() - inicio_total
    logger.info(f"✅ OFX parseado: {len(registros)} registros em {tempo_total:.2f}s")
    return [normalize_row(r) for r in registros]

# ============================================================
# EXTRAIR DADOS DA CONTA
# ============================================================
def extrair_dados_conta_ofx(content: str) -> dict:
    dados = {"banco": None, "agencia": None, "conta": None, "tipo": "corrente", "nome": None}
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
        tipo_map = {"CHECKING": "corrente", "SAVINGS": "poupanca", "MONEYMRKT": "investimento", "CREDITLINE": "credito"}
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

# ============================================================
# DIVIDIR OFX
# ============================================================
def dividir_ofx_em_partes(content: str, max_transacoes: int = 30) -> list:
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
    if total_transacoes == 0 or total_transacoes <= max_transacoes:
        return [content]
    
    transacoes = []
    for i, pos_inicio in enumerate(posicoes_inicio):
        if i + 1 < len(posicoes_inicio):
            pos_fim = posicoes_inicio[i + 1]
        else:
            pos_fim = len(bloco_transacoes)
        transacoes.append(bloco_transacoes[pos_inicio:pos_fim].strip())
    
    partes = []
    num_partes = (total_transacoes + max_transacoes - 1) // max_transacoes
    for i in range(num_partes):
        inicio_idx = i * max_transacoes
        fim_idx = min((i + 1) * max_transacoes, total_transacoes)
        ofx_parte = header + '\n' + '\n'.join(transacoes[inicio_idx:fim_idx]) + '\n' + footer
        partes.append(ofx_parte)
    
    logger.info(f"✅ OFX dividido: {total_transacoes} transações em {len(partes)} partes")
    return partes

# ============================================================
# ✅ DIVIDIR CSV (NOVA FUNÇÃO)
# ============================================================
def dividir_csv_em_partes(content: str, max_linhas: int = 100) -> list:
    """Divide arquivo CSV em partes menores, mantendo o header em cada parte."""
    lines = content.split('\n')
    
    if len(lines) <= max_linhas + 1:
        return [content]
    
    header = lines[0]
    data_lines = lines[1:]
    data_lines = [line for line in data_lines if line.strip()]
    
    total_linhas = len(data_lines)
    logger.info(f"📊 CSV com {total_linhas} linhas de dados")
    
    partes = []
    num_partes = (total_linhas + max_linhas - 1) // max_linhas
    
    for i in range(num_partes):
        inicio_idx = i * max_linhas
        fim_idx = min((i + 1) * max_linhas, total_linhas)
        linhas_parte = data_lines[inicio_idx:fim_idx]
        csv_parte = header + '\n' + '\n'.join(linhas_parte)
        partes.append(csv_parte)
    
    logger.info(f"✅ CSV dividido: {total_linhas} linhas em {len(partes)} partes")
    return partes

# ============================================================
# ✅ FLOW CSV - DETECTOR
# ============================================================
def is_flow_csv(filename: str, sample_content: str) -> bool:
    """
    Detecta se o arquivo é do formato Flow baseando-se APENAS no conteúdo.
    Formato real: cada linha tem 8 campos separados por ;
    CB-XXXXXXX;DD/MM/YYYY;Bandeira;Produto;Qtd;R$ X;R$ Y;R$ Z
    """
    if not sample_content:
        return False
    
    lines = [l.strip() for l in sample_content.split('\n') if l.strip()]
    if not lines:
        return False
    
    # Testar as primeiras linhas para ver se batem com o padrão Flow
    matches = 0
    for line in lines[:5]:
        parts = line.split(';')
        if len(parts) == 8:
            # Campo 1: estabelecimento (começa com CB- ou similar)
            # Campo 2: data DD/MM/YYYY
            # Campo 3: bandeira (Visa, Mastercard, Elo, etc.)
            # Campo 6,7,8: valores com R$
            if (len(parts[0]) >= 5 and 
                '/' in parts[1] and 
                parts[2].strip() in ['Visa', 'Mastercard', 'Elo', 'Amex', 'Hipercard', 'Alelo', 'VR'] and
                'R$' in parts[5]):
                matches += 1
    
    if matches >= 2:
        logger.info(f"✅ CSV Flow detectado pelo padrão de dados ({matches} linhas compatíveis)")
        return True
    
    # Fallback: detecção pelo título (caso tenha)
    content_lower = sample_content.lower()
    if ('relatório sumarizado de vendas' in content_lower or 
        'relatorio sumarizado de vendas' in content_lower):
        if 'estabelecimento' in content_lower:
            logger.info(f"✅ CSV Flow detectado pelo título")
            return True
    
    return False


# ============================================================
# ✅ FLOW CSV - PARSER (FORMATO REAL SEM HEADERS)
# ============================================================
def parse_flow_csv(file_stream, filename: str, default_empresa_id: int = None) -> list:
    """
    Parser para CSV do Flow no formato REAL (sem headers).
    Formato: ESTABELECIMENTO;DATA;BANDEIRA;PRODUTO;QTD;VALOR_BRUTO;DESCONTO;VALOR_LIQUIDO
    """
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
        lines = [l.strip() for l in raw.strip().split('\n') if l.strip()]
        
        if not lines:
            raise ValueError("Arquivo Flow CSV vazio")
        
        # ✅ Detectar qual linha começar (pular headers se existirem)
        start_line = 0
        estabelecimento_principal = None
        
        for i, line in enumerate(lines):
            parts = line.split(';')
            if len(parts) == 8:
                # Verificar se é uma linha de dados válida
                if (len(parts[0]) >= 5 and 
                    '/' in parts[1] and 
                    parts[2].strip() in ['Visa', 'Mastercard', 'Elo', 'Amex', 'Hipercard', 'Alelo', 'VR', 'Débito', 'Crédito']):
                    start_line = i
                    estabelecimento_principal = parts[0].strip()
                    break
            elif 'Estabelecimento' in line or 'relatório' in line.lower():
                # Linha de header, pular
                continue
        
        logger.info(f"🏢 Estabelecimento detectado: {estabelecimento_principal}, iniciando na linha {start_line}")
        
        # Resolver empresa_id
        empresa_id = _get_empresa_id_por_estabelecimento(estabelecimento_principal, default_empresa_id)
        if not empresa_id:
            if not default_empresa_id:
                logger.error(f"❌ Estabelecimento não encontrado: {estabelecimento_principal}")
                return []
            empresa_id = default_empresa_id
        
        logger.info(f"🏢 empresa_id: {empresa_id}")
        
        # Processar linhas de dados
        registros = []
        nsu_counter = 0
        
        for row_num, line in enumerate(lines[start_line:], start=start_line):
            try:
                # Pular linha "Total" ou linhas vazias
                if line.lower().startswith('total') or not line.strip():
                    continue
                
                parts = line.split(';')
                if len(parts) != 8:
                    continue
                
                # Extrair campos
                estabelecimento = parts[0].strip()
                data_str = parts[1].strip()
                bandeira = parts[2].strip()
                produto = parts[3].strip()
                quantidade_str = parts[4].strip()
                valor_bruto_str = parts[5].strip()
                desconto_str = parts[6].strip()
                valor_liquido_str = parts[7].strip()
                
                # Parse data
                data_venda = parse_data(data_str)
                if not data_venda:
                    continue
                
                # Parse valores
                valor_bruto = parse_valor(valor_bruto_str.replace('R$', '').replace('.', '').replace(',', '.'))
                if not valor_bruto or valor_bruto <= 0:
                    continue
                
                desconto = parse_valor(desconto_str.replace('R$', '').replace('.', '').replace(',', '.'))
                valor_liquido = parse_valor(valor_liquido_str.replace('R$', '').replace('.', '').replace(',', '.'))
                
                # Gerar NSU único
                nsu_counter += 1
                nsu = f"FLOW-{estabelecimento or 'UNK'}-{data_venda.strftime('%Y%m%d')}-{nsu_counter:04d}"
                
                # Normalizar bandeira
                bandeira_map = {
                    'mastercard': 'Mastercard',
                    'visa': 'Visa',
                    'elo': 'Elo',
                    'amex': 'Amex',
                    'hipercard': 'Hipercard',
                }
                bandeira_final = bandeira_map.get(bandeira.lower().strip(), bandeira)
                
                # Normalizar produto
                produto_lower = produto.lower().strip()
                if 'pix' in produto_lower:
                    tipo_pagamento = 'pix'
                    produto_final = 'PIX'
                elif 'débito' in produto_lower or 'debito' in produto_lower:
                    tipo_pagamento = 'cartao'
                    produto_final = 'Débito'
                elif 'crédito' in produto_lower or 'credito' in produto_lower:
                    tipo_pagamento = 'cartao'
                    produto_final = 'Crédito'
                else:
                    tipo_pagamento = 'cartao'
                    produto_final = produto or 'Desconhecido'
                
                # Quantidade
                try:
                    quantidade = int(quantidade_str)
                except:
                    quantidade = 1
                
                # Gerar registro no formato correto para MovAdquirente
                registro = {
                    'adquirente': 'Flow',
                    'nsu': nsu,
                    'data_venda': data_venda.strftime('%Y-%m-%d'),
                    'valor_bruto': float(valor_bruto),
                    'valor_liquido': float(valor_liquido),
                    'desconto': float(desconto),
                    'bandeira': bandeira_final,
                    'produto': produto_final,
                    'tipo_pagamento': tipo_pagamento,
                    'observacoes': f"Flow {bandeira_final} {produto_final} - Qtd: {quantidade} - {data_venda.strftime('%d/%m/%Y')}",
                    'empresa_id': empresa_id,
                    'estabelecimento': estabelecimento,
                }
                
                registros.append(registro)
                
            except Exception as e:
                logger.error(f"❌ Erro linha {row_num}: {str(e)}", exc_info=True)
                continue
        
        tempo = time.time() - inicio
        logger.info(f"✅ Parse Flow CSV: {len(registros)} registros em {tempo:.2f}s")
        
        if registros:
            logger.info(f"📋 Exemplo de registro gerado: {registros[0]}")
        
        return registros
        
    except Exception as e:
        logger.error(f"❌ Erro Flow CSV: {str(e)}", exc_info=True)
        raise ValueError(f"Erro Flow CSV: {str(e)}")


# ============================================================
# HELPER: Resolver empresa_id pelo código do estabelecimento
# ============================================================
def _get_empresa_id_por_estabelecimento(codigo_estabelecimento: str, fallback: int = None) -> int:
    """
    Resolve empresa_id a partir do código do estabelecimento (ex: CB-109264950001).
    Usa tabela de mapeamento ou config hardcoded.
    """
    if not codigo_estabelecimento:
        return fallback
    
    # Tentativa 1: Tabela EstabelecimentoMapeamento
    try:
        from models import EstabelecimentoMapeamento
        mapeamento = EstabelecimentoMapeamento.query.filter_by(
            codigo_estabelecimento=codigo_estabelecimento, ativo=True
        ).first()
        if mapeamento:
            logger.info(f"✅ Estabelecimento {codigo_estabelecimento} encontrado na tabela: empresa_id={mapeamento.empresa_id}")
            return mapeamento.empresa_id
    except Exception as e:
        logger.debug(f"⚠️ Tabela EstabelecimentoMapeamento não disponível: {str(e)}")
    
    # Tentativa 2: Config hardcoded
    try:
        from config.estabelecimentos import ESTABELECIMENTO_PARA_EMPRESA
        if codigo_estabelecimento in ESTABELECIMENTO_PARA_EMPRESA:
            empresa_id = ESTABELECIMENTO_PARA_EMPRESA[codigo_estabelecimento]
            logger.info(f"✅ Estabelecimento {codigo_estabelecimento} encontrado no config: empresa_id={empresa_id}")
            return empresa_id
    except Exception as e:
        logger.debug(f"⚠️ Config estabelecimentos não disponível: {str(e)}")
    
    # Fallback: usar o default
    logger.info(f"ℹ️ Estabelecimento {codigo_estabelecimento} não mapeado, usando fallback: {fallback}")
    return fallback


# ============================================================
# PARSE GENERIC (entry point principal)
# ============================================================
def parse_generic(file_stream, filename: str, default_empresa_id: int = None):
    """Dispatcher principal: detecta o tipo e delega para o parser correto."""
    if not filename:
        raise ValueError("Nome do arquivo é obrigatório")
    
    filename_lower = filename.lower()
    file_stream.seek(0)
    sample = file_stream.read(2048).decode('utf-8', errors='ignore')
    file_stream.seek(0)
    
    # 1. Detectar Flow CSV
    if is_flow_csv(filename, sample):
        return parse_flow_csv(file_stream, filename, default_empresa_id)
    
    # 2. CSV / TXT genérico
    if filename_lower.endswith(('.csv', '.txt')):
        registros = parse_csv_generic(file_stream, filename)
        if default_empresa_id:
            for reg in registros:
                if 'empresa_id' not in reg or not reg['empresa_id']:
                    reg['empresa_id'] = default_empresa_id
        return registros
    
    # 3. Excel
    elif filename_lower.endswith(('.xlsx', '.xls')):
        registros = parse_excel_generic(file_stream, filename)
        if default_empresa_id:
            for reg in registros:
                if 'empresa_id' not in reg or not reg['empresa_id']:
                    reg['empresa_id'] = default_empresa_id
        return registros
    
    # 4. OFX
    elif filename_lower.endswith('.ofx'):
        registros = parse_ofx_generic(file_stream, filename)
        if default_empresa_id:
            for reg in registros:
                if 'empresa_id' not in reg or not reg['empresa_id']:
                    reg['empresa_id'] = default_empresa_id
        return registros
    
    else:
        raise ValueError(f"Formato não suportado: {filename}")
