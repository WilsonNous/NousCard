import csv
import io
from openpyxl import load_workbook
from ofxparse import OfxParser


# ============================================================
# PARSER CSV — Leitura 100% baseada em csv.DictReader
# ============================================================
def parse_csv_generic(file_stream):
    """
    Lê CSV genérico e retorna lista de dicionários.
    Funciona para qualquer arquivo com cabeçalho.
    """
    raw = file_stream.read().decode("utf-8", errors="ignore")
    reader = csv.DictReader(io.StringIO(raw))
    return [dict(row) for row in reader]


# ============================================================
# PARSER XLSX — Leitura baseada em openpyxl
# ============================================================
def parse_excel_generic(file_stream):
    """
    Lê arquivos Excel XLSX de forma simples, converte a primeira
    planilha em lista de dicionários.
    """
    workbook = load_workbook(filename=io.BytesIO(file_stream.read()), data_only=True)
    sheet = workbook.active

    rows = list(sheet.rows)

    if not rows:
        return []

    headers = [str(cell.value).strip() if cell.value else "" for cell in rows[0]]

    data = []
    for row in rows[1:]:
        row_dict = {}
        for i, cell in enumerate(row):
            row_dict[headers[i]] = cell.value
        data.append(row_dict)

    return data


# ============================================================
# PARSER OFX — Leitura simples e limpa
# ============================================================
def parse_ofx_generic(file_stream):
    """
    Lê arquivo OFX usando ofxparse e retorna lista de transações.
    """
    ofx = OfxParser.parse(file_stream)
    result = []

    for account in ofx.accounts:
        for tx in account.statement.transactions:
            result.append({
                "date": tx.date,
                "amount": float(tx.amount),
                "id": tx.id,
                "memo": tx.memo,
                "type": tx.type,
            })

    return result
