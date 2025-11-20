import io
import pandas as pd

def parse_csv_generic(file_storage):
    """
    Lê CSV/XLS/XLSX usando pandas e devolve lista de dicionários.
    """
    filename = file_storage.filename.lower()
    content = file_storage.read()

    # Volta o ponteiro se precisar reutilizar depois
    file_storage.stream.seek(0)

    if filename.endswith(".csv") or filename.endswith(".txt"):
        df = pd.read_csv(io.BytesIO(content), sep=None, engine="python")
    else:
        df = pd.read_excel(io.BytesIO(content))

    return df.to_dict(orient="records")
