from datetime import timedelta
from sqlalchemy import func
from models import db, MovAdquirente, MovBanco, Conciliacao, Adquirente


# ============================================================
# 🔧 Funções utilitárias
# ============================================================

def normalizar(texto):
    """Deixa o texto consistente para comparação."""
    if not texto:
        return ""
    return texto.lower().replace(" ", "").replace("-", "").replace(".", "")


def identificar_adquirente_por_historico(historico, adquirentes):
    """
    Tenta identificar a origem (Cielo, Rede, Stone...) a partir
    do texto do lançamento bancário.
    """
    hist_norm = normalizar(historico)

    for adq in adquirentes:
        if adq.palavras_chave_extrato:
            for chave in adq.palavras_chave_extrato.split(","):
                if normalizar(chave) in hist_norm:
                    return adq.id

    return None



# ============================================================
# 🎯 Regras de matching
# ============================================================

TOLERANCIA_DIAS = 2  # sua escolha (opção B)


def datas_compatíveis(data_prevista, data_banco):
    """Verifica se a data do banco está dentro da tolerância."""
    if not data_prevista or not data_banco:
        return False

    return abs((data_prevista - data_banco).days) <= TOLERANCIA_DIAS



# ============================================================
# ⚙️ MATCHING PRINCIPAL
# ============================================================

def tentar_matching(venda, recebimentos):
    """
    Tenta conciliar uma venda com:
    1) Match exato
    2) Match parcial
    3) Match multivenda (várias vendas para 1 crédito)
    """

    # ---------------------------------------
    # 🔵 1. MATCH EXATO (valor igual)
    # ---------------------------------------
    for r in recebimentos:
        if float(r.valor) == float(venda.valor_liquido) and datas_compatíveis(venda.data_prevista_pagamento, r.data_movimento):
            return [(venda, r, float(r.valor))]  # lista com 1 vínculo

    # ---------------------------------------
    # 🟡 2. MATCH PARCIAL (valor menor que o previsto)
    # ---------------------------------------
    for r in recebimentos:
        if float(r.valor) < float(venda.valor_liquido) and datas_compatíveis(venda.data_prevista_pagamento, r.data_movimento):
            return [(venda, r, float(r.valor))]

    return None



# ============================================================
# 🔄 MULTIVENDA (crédito pagando várias vendas)
# ============================================================

def tentar_multivenda(recebimento, vendas):
    """
    Recebimento que pode pagar várias vendas.
    Ex: crédito consolidado da Cielo.
    """

    total = float(recebimento.valor)
    acumulado = 0
    vinculos = []

    for v in vendas:
        valor_prev = float(v.valor_liquido)

        if acumulado + valor_prev <= total:
            acumulado += valor_prev
            vinculos.append((v, recebimento, valor_prev))  # venda, recebimento, valor conciliado

        if acumulado == total:
            return vinculos

    return None  # não fechou exatamente



# ============================================================
# 📝 Gravação da conciliação
# ============================================================

def registrar_conciliacao(vinculos, empresa_id):
    """Grava os vínculos N–N na tabela conciliacoes."""

    for venda, recebimento, valor in vinculos:

        conc = Conciliacao(
            empresa_id=empresa_id,
            mov_adquirente_id=venda.id,
            mov_banco_id=recebimento.id,
            valor_previsto=venda.valor_liquido,
            valor_conciliado=valor,
            tipo="automatico",
            status="conciliado"
        )
        db.session.add(conc)

        # Atualiza a venda
        venda.valor_conciliado += valor
        venda.data_primeiro_recebimento = recebimento.data_movimento if not venda.data_primeiro_recebimento else venda.data_primeiro_recebimento
        venda.data_ultimo_recebimento = recebimento.data_movimento

        if float(venda.valor_conciliado) == float(venda.valor_liquido):
            venda.status_conciliacao = "conciliado"
        elif float(venda.valor_conciliado) > 0:
            venda.status_conciliacao = "parcial"

        # Atualiza o recebimento
        recebimento.valor_conciliado += valor
        recebimento.conciliado = (float(recebimento.valor_conciliado) == float(recebimento.valor))

    db.session.commit()



# ============================================================
# 🚀 Função principal chamada pelo endpoint
# ============================================================

def executar_conciliacao(empresa_id):
    """
    Conciliação avançada:
      ✔ Matching exato
      ✔ Matching parcial
      ✔ Matching multivenda
      ✔ Tolerância ±2 dias
    """

    vendas = MovAdquirente.query.filter_by(empresa_id=empresa_id).all()
    recebimentos = MovBanco.query.filter_by(empresa_id=empresa_id, conciliado=False).all()
    adquirentes = Adquirente.query.all()

    resultados = {
        "conciliados": 0,
        "parciais": 0,
        "multivendas": 0,
        "nao_conciliados": 0,
        "creditos_sem_origem": 0
    }

    # =========================================
    # 🔹 Primeira fase: match por venda
    # =========================================
    for venda in vendas:

        if venda.status_conciliacao == "conciliado":
            continue

        vinculos = tentar_matching(venda, recebimentos)

        if vinculos:
            registrar_conciliacao(vinculos, empresa_id)

            if sum([v[2] for v in vinculos]) == float(venda.valor_liquido):
                resultados["conciliados"] += 1
            else:
                resultados["parciais"] += 1

            continue

    # =========================================
    # 🔹 Segunda fase: multivenda
    # =========================================
    vendas_pendentes = [v for v in vendas if v.status_conciliacao == "pendente"]
    receb_pendentes = [r for r in recebimentos if not r.conciliado]

    for r in receb_pendentes:

        vinculos = tentar_multivenda(r, vendas_pendentes)

        if vinculos:
            registrar_conciliacao(vinculos, empresa_id)
            resultados["multivendas"] += 1

    # =========================================
    # 🔹 Pós-processamento
    # =========================================
    for v in vendas:
        if v.status_conciliacao == "pendente":
            resultados["nao_conciliados"] += 1

    for r in recebimentos:
        if not r.conciliado and float(r.valor) > 0:
            resultados["creditos_sem_origem"] += 1

    return resultados
