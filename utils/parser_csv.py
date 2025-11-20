import io
import csv
from openpyxl import load_workbook

try:
    import xlrd  # necessário para XLS antigos
    XLS_SUPPORT = True
except ImportError:
    XLS_SUPPORT = False


def parse_csv_generic(file_storage):
    """
    Lê CSV/XLS/XLSX SEM pandas e devolve lista de dicionários.
    Mantém mesma interface e comportamento esperado.
    """
    filename = file_storage.filename.lower()
    content = file_storage.read()

    # reposiciona ponteiro
    file_storage.stream.seek(0)

    # -----------------------------------------
    # CSV / TXT
    # -----------------------------------------
    if filename.endswith(".csv") or filename.endswith(".txt"):
        content_str = content.decode("utf-8", errors="ignore")
        reader = csv.DictReader(io.StringIO(content_str))
        return list(reader)

    # -----------------------------------------
    # XLSX (OpenXML)
    # -----------------------------------------
    elif filename.endswith(".xlsx"):
        wb = load_workbook(io.BytesIO(content), data_only=True)
        sheet = wb.active

        rows = list(sheet.values)
        if not rows:
            return []

        headers = [str(h).strip() if h is not None else "" for h in rows[0]]
        data_rows = rows[1:]

        result = []
        for row in data_rows:
            row_dict = {headers[i]: row[i] for i in range(len(headers))}
            result.append(row_dict)

        return result

    # -----------------------------------------
    # XLS (antigo)
    # -----------------------------------------
    elif filename.endswith(".xls") and XLS_SUPPORT:
        wb = xlrd.open_workbook(file_contents=content)
        sheet = wb.sheet_by_index(0)

        headers = [str(sheet.cell_value(0, col)).strip() for col in range(sheet.ncols)]

        result = []
        for row_idx in range(1, sheet.nrows):
            row = {}
            for col_idx in range(sheet.ncols):
                row[headers[col_idx]] = sheet.cell_value(row_idx, col_idx)
            result.append(row)

        return result

    else:
        raise ValueError("Formato de arquivo não suportado.")
