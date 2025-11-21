from services.importer_db import listar_arquivos_importados

def executar_conciliacao(empresa_id):
    """
    Versão mínima da conciliação.
    Apenas retorna totas somas de vendas x recebimentos.
    """

    arquivos = listar_arquivos_importados(empresa_id)

    total_vendas = 0
    total_recebimentos = 0

    for arq in arquivos:
        if arq["tipo"] == "venda":
            total_vendas += arq["total_valor"]
        elif arq["tipo"] == "recebimento":
            total_recebimentos += arq["total_valor"]

    return {
        "total_vendas": round(total_vendas, 2),
        "total_recebimentos": round(total_recebimentos, 2),
        "diferenca": round(total_vendas - total_recebimentos, 2),
        "arquivos_processados": len(arquivos)
    }
