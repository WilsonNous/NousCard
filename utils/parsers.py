import csv
import io
import re
from datetime import datetime
from openpyxl import load_workbook
from ofxparse import OfxParser

# ============================================================
# FUNÇÃO AUXILIAR — Normalizar valores monetários
# ============================================================
def parse_valor(value):
    if value is None:
        return 0.0

    if isinstance(value, (int, float)):
        return float(value)

    value = str(value).strip()

    # Remove "R$", espaços, etc.
    value = value.replace("R$", "").replace(" ", "")

    # Corrige formatos brasileiros "1.234,56"
    if "," in value and "." in value:
        value = value.replace(".", "").replace(",", ".")

    # Corrige "120,00"
    elif "," in value:
        value = value.replace(",", ".")

    try:
        return float(value)
    except:
        return 0.0


# ============================================================
# FUNÇÃO AUXILIAR — Normalizar datas
# ============================================================
def parse_data(value):
    if not value:
        return ""

    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d")

    value = str(value).strip()

    formatos = [
        "%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y",
        "%Y/%m/%d", "%m/%d/%Y"
    ]

    for fmt in formatos:
        try:
            return datetime.strptime(value, fmt).strftime("%Y-%m-%d")
        except:
            pass

    return value


# ============================================================
# Normalização genérica de colunas
# ============================================================
def normalize_row(row: dict):
    new = {}
    for key, value in row.items():
        k = key.strip().lower()

        # Detectar coluna de valor
        if k in ("valor", "amount", "valor_bruto", "vlr", "price"):
            new["valor"] = parse_valor(value)

        # Detectar coluna de entrada (Itaú)
        elif k in ("entrada", "credit", "credito"):
            new["valor"] = parse_valor(value)

        # Detectar coluna de data
        elif k in ("data", "date", "dt", "transaction date"):
            new["data"] = parse_data(value)

        elif re.search(r"valor", k):
            new["valor"] = parse_valor(value)

        elif re.search(r"data", k):
            new["data"] = parse_data(value)

        # Descrição
        elif k in ("descricao", "desc", "memo", "historico"):
            new["descricao"] = str(value).strip() if value else ""

        else:
            new[k] = value

    # Garantir campos obrigatórios
    if "valor" not in new:
        new["valor"] = 0.0

    if "descricao" not in new:
        new["descricao"] = ""

    return new

# ============================================================
# PARSER CSV
# ============================================================
def parse_csv_generic(file_stream):
    raw = file_stream.read().decode("utf-8", errors="ignore")
    reader = csv.DictReader(io.StringIO(raw))
    return [normalize_row(dict(row)) for row in reader]


# ============================================================
# PARSER XLSX
# ============================================================
def parse_excel_generic(file_stream):
    workbook = load_workbook(filename=io.BytesIO(file_stream.read()), data_only=True)
    sheet = workbook.active

    rows = list(sheet.rows)
    if not rows:
        return []

    headers = [str(c.value).strip() if c.value else "" for c in rows[0]]
    registros = []

    for row in rows[1:]:
        row_dict = {}
        for i, cell in enumerate(row):
            row_dict[headers[i]] = cell.value
        registros.append(normalize_row(row_dict))

    return registros


# ============================================================
# PARSER OFX
# ============================================================
def parse_ofx_generic(file_stream):
    ofx = OfxParser.parse(file_stream)
    registros = []

    for account in ofx.accounts:
        for tx in account.statement.transactions:
            registros.append(normalize_row({
                "data": tx.date,
                "valor": tx.amount,
                "descricao": tx.memo,
                "id": tx.id,
                "tipo_ofx": tx.type
            }))

    return registros
