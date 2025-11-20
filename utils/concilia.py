# utils/concilia.py
from decimal import Decimal, InvalidOperation
import re
from typing import List, Dict, Any


# ==========================================
# Helpers básicos
# ==========================================
def _to_decimal(valor) -> Decimal:
    if valor is None:
        return Decimal("0")
    if isinstance(valor, (int, float, Decimal)):
        return Decimal(str(valor))
    s = str(valor).strip()
    s = s.replace("R$", "").replace(" ", "")
    # troca vírgula por ponto (padrão BR)
    s = s.replace(".", "").replace(",", ".") if "," in s and "." in s else s.replace(",", ".")
    try:
        return Decimal(s)
    except InvalidOperation:
        return Decimal("0")


def _extrair_nsu(descricao: str) -> str | None:
    """
    Extrai um número longo (NSU) de uma descrição de extrato.
    Ex: 'RECEBIMENTO CIELO NSU 981273' -> '981273'
    """
    if not descricao:
        return None
    m = re.search(r"(\d{5,})\b", descricao)
    if m:
        return m.group(1)
    return None


def _inferir_adquirente(descricao: str) -> str | None:
    if not descricao:
        return None
    desc = descricao.upper()
    if "CIELO" in desc:
        return "CIELO"
    if "REDE" in desc:
        return "REDE"
    if "GETNET" in desc:
        return "GETNET"
    return None


# ==========================================
# Normalização de VENDAS
# ==========================================
def normalizar_registros_vendas(rows: List[Dict[str, Any]], fonte_arquivo: str) -> List[Dict[str, Any]]:
    """
    Normaliza linhas de vendas vindas de CSV (Cielo, Rede, Getnet...).
    Retorna uma lista de dicts com chaves padrão:
    nsu, data, valor, bandeira, adquirente, tipo, fonte
    """
    vendas_norm = []

    for row in rows:
        # Garantir que as chaves sejam tratadas de forma case-insensitive
        r = {str(k).upper(): v for k, v in row.items()}

        nsu = r.get("NSU")
        data = r.get("DATA_VENDA") or r.get("DATA")
        valor = r.get("VALOR") or r.get("VALOR_BRUTO")
        bandeira = r.get("BANDEIRA") or r.get("CARTAO")
        adquirente = r.get("ADQUIRENTE") or r.get("ORIGEM") or "DESCONHECIDO"

        if not nsu:
            # sem NSU é difícil conciliar – pulamos
            continue

        vendas_norm.append(
            {
                "tipo": "venda",
                "nsu": str(nsu).strip(),
                "data": str(data).strip() if data else None,
                "valor": _to_decimal(valor),
                "bandeira": (bandeira or "").strip() if bandeira else None,
                "adquirente": (adquirente or "").strip(),
                "fonte": fonte_arquivo,
            }
        )

    return vendas_norm


# ==========================================
# Normalização de RECEBIMENTOS (extrato/OFX)
# ==========================================
def normalizar_registros_recebimentos(rows: List[Dict[str, Any]], fonte_arquivo: str) -> List[Dict[str, Any]]:
    """
    Normaliza linhas de extrato bancário (CSV/OFX).
    Espera colunas do tipo: DATA, DESCRICAO, VALOR/ENTRADA/SAIDA.
    """
    rec_norm = []

    for row in rows:
        r = {str(k).upper(): v for k, v in row.items()}

        data = r.get("DATA")
        descricao = r.get("DESCRICAO") or ""
        valor = r.get("VALOR") or r.get("ENTRADA") or r.get("CREDITO") or r.get("TRNAMT")

        nsu = _extrair_nsu(str(descricao))
        adquirente = _inferir_adquirente(str(descricao))

        rec_norm.append(
            {
                "tipo": "recebimento",
                "nsu": nsu,  # pode ser None; alguns recebimentos ficarão sem vínculo
                "data": str(data).strip() if data else None,
                "valor": _to_decimal(valor),
                "bandeira": None,  # normalmente não vem no extrato
                "adquirente": adquirente,
                "descricao": descricao,
                "fonte": fonte_arquivo,
            }
        )

    return rec_norm


# ==========================================
# Motor de conciliação
# ==========================================
def conciliar(vendas: List[Dict[str, Any]], recebimentos: List[Dict[str, Any]], tolerancia_centavos: int = 5) -> Dict[str, Any]:
    """
    Faz o casamento venda x recebimento por NSU, com tolerância em centavos.
    Estrutura esperada:
      vendas[i] = { nsu, data, valor, bandeira, adquirente, ... }
      recebimentos[i] = { nsu, data, valor, adquirente, descricao, ... }
    """
    tol = Decimal(tolerancia_centavos) / Decimal(100)

    # Totais globais
    total_vendas = sum(_to_decimal(v.get("valor")) for v in vendas)
    total_recebimentos = sum(_to_decimal(r.get("valor")) for r in recebimentos)

    # Índice de recebimentos por NSU
    rec_por_nsu: Dict[str, List[Dict[str, Any]]] = {}
    for r in recebimentos:
        nsu = r.get("nsu")
        if not nsu:
            # recebimento sem NSU – só entra nos pendentes depois
            continue
        rec_por_nsu.setdefault(str(nsu), []).append(r)

    conciliados = []
    pendentes_vendas = []

    for v in vendas:
        nsu = str(v.get("nsu") or "").strip()
        if not nsu or nsu not in rec_por_nsu:
            pendentes_vendas.append(
                {
                    "nsu": nsu or None,
                    "data": v.get("data"),
                    "valor": float(_to_decimal(v.get("valor"))),
                    "bandeira": v.get("bandeira"),
                    "adquirente": v.get("adquirente"),
                    "fonte": v.get("fonte"),
                    "motivo": "SEM_RECEBIMENTO",
                }
            )
            continue

        # há 1+ recebimentos para esse NSU – pega o primeiro
        r = rec_por_nsu[nsu].pop(0)
        if not rec_por_nsu[nsu]:
            del rec_por_nsu[nsu]

        val_v = _to_decimal(v.get("valor"))
        val_r = _to_decimal(r.get("valor"))
        diff = val_r - val_v

        status = "OK" if abs(diff) <= tol else "DIVERGENTE"

        conciliados.append(
            {
                "nsu": nsu,
                "valor_venda": float(val_v),
                "valor_recebido": float(val_r),
                "diferenca": float(diff),
                "status": status,
                "data_venda": v.get("data"),
                "data_recebimento": r.get("data"),
                "bandeira": v.get("bandeira") or r.get("bandeira"),
                "adquirente": v.get("adquirente") or r.get("adquirente"),
                "fonte_venda": v.get("fonte"),
                "fonte_recebimento": r.get("fonte"),
                "descricao_recebimento": r.get("descricao"),
            }
        )

        if status != "OK":
            pendentes_vendas.append(
                {
                    "nsu": nsu,
                    "data": v.get("data"),
                    "valor": float(val_v),
                    "bandeira": v.get("bandeira"),
                    "adquirente": v.get("adquirente"),
                    "fonte": v.get("fonte"),
                    "motivo": "VALOR_DIFERENTE",
                }
            )

    # Recebimentos que sobraram sem venda
    pendentes_recebimentos = []
    for nsu, lista in rec_por_nsu.items():
        for r in lista:
            pendentes_recebimentos.append(
                {
                    "nsu": nsu,
                    "data": r.get("data"),
                    "valor": float(_to_decimal(r.get("valor"))),
                    "adquirente": r.get("adquirente"),
                    "descricao": r.get("descricao"),
                    "fonte": r.get("fonte"),
                    "motivo": "RECEBIMENTO_SEM_VENDA",
                }
            )

    resumo = {
        "total_vendas": float(total_vendas),
        "total_recebimentos": float(total_recebimentos),
        "diferenca": float(total_recebimentos - total_vendas),
        "qtd_vendas": len(vendas),
        "qtd_recebimentos": len(recebimentos),
        "qtd_conciliados": len([c for c in conciliados if c["status"] == "OK"]),
        "qtd_divergentes": len([c for c in conciliados if c["status"] != "OK"]),
        "qtd_pendentes_vendas": len(pendentes_vendas),
        "qtd_pendentes_recebimentos": len(pendentes_recebimentos),
        "conciliados": conciliados,
        "pendentes_vendas": pendentes_vendas,
        "pendentes_recebimentos": pendentes_recebimentos,
    }

    return resumo
