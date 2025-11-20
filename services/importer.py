from utils.parser_csv import parse_csv_generic
from utils.parser_ofx import parse_ofx_file

def process_uploaded_files(files):
    """
    Processa arquivos enviados.
    Neste MVP, apenas identifica tipo e conta linhas.
    """
    resultados = []

    for f in files:
        filename = f.filename.lower()
        if filename.endswith(".csv") or filename.endswith(".txt") or filename.endswith(".xls") or filename.endswith(".xlsx"):
            rows = parse_csv_generic(f)
            resultados.append({
                "arquivo": filename,
                "tipo": "tabela_cartao_ou_banco",
                "linhas": len(rows)
            })
        elif filename.endswith(".ofx"):
            lancamentos = parse_ofx_file(f)
            resultados.append({
                "arquivo": filename,
                "tipo": "extrato_banco_ofx",
                "linhas": len(lancamentos)
            })
        else:
            resultados.append({
                "arquivo": filename,
                "tipo": "desconhecido",
                "linhas": 0
            })

    return resultados
