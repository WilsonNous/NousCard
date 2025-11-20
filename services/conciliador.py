def executar_conciliacao_simples():
    """
    MVP: aqui depois vamos buscar os dados no banco e fazer a conciliação real.
    Por enquanto, devolve um resumo estático.
    """
    resumo = {
        "total_vendas": 0.00,
        "total_recebido": 0.00,
        "diferenca": 0.00,
        "vendas_sem_recebimento": 0,
        "recebimentos_sem_venda": 0,
        "taxas_acima_contrato": 0,
        "mensagem": "Conciliação executada (MVP). Em breve, resultados reais aparecerão aqui."
    }
    return resumo
