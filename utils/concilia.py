# utils/concilia.py - VERSÃO CORRIGIDA COM SUPORTE AVANÇADO

from decimal import Decimal, InvalidOperation
import re
import logging
from typing import List, Dict, Any, Optional, Set
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# ==========================================
# CONFIGURAÇÕES
# ==========================================
TOLERANCIA_CENTAVOS_DEFAULT = Decimal("0.05")  # R$ 0,05
TOLERANCIA_DIAS_DEFAULT = 3  # dias de diferença permitida entre venda e recebimento

# ==========================================
# Helpers básicos
# ==========================================
def _to_decimal(valor) -> Decimal:
    """
    Converte valor para Decimal com suporte a formato brasileiro.
    Ex: "R$ 1.234,56" → Decimal("1234.56")
    """
    if valor is None:
        return Decimal("0")
    if isinstance(valor, (int, float, Decimal)):
        return Decimal(str(valor))
    
    s = str(valor).strip()
    s = s.replace("R$", "").replace(" ", "").replace("\xa0", "")
    
    # Formato brasileiro: milhar com ponto, decimal com vírgula
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".")
    
    try:
        return Decimal(s)
    except InvalidOperation:
        logger.warning(f"⚠️ Valor inválido para Decimal: '{valor}'")
        return Decimal("0")


def _extrair_nsu(descricao: str) -> Optional[str]:
    """
    Extrai um número longo (NSU) de uma descrição de extrato.
    Ex: 'RECEBIMENTO CIELO NSU 981273' -> '981273'
    """
    if not descricao:
        return None
    
    # Tenta padrões comuns de NSU
    patterns = [
        r"NSU[:\s]*(\d{5,})\b",
        r"NSU[:\s]*#?(\d{5,})\b", 
        r"(\d{8,})\b",  # NSU longo sem label
        r"COD[:\s]*(\d{5,})\b",
    ]
    
    for pattern in patterns:
        m = re.search(pattern, descricao, re.IGNORECASE)
        if m:
            return m.group(1)
    
    # Fallback: qualquer número longo
    m = re.search(r"\b(\d{6,})\b", descricao)
    if m:
        return m.group(1)
    
    return None


def _inferir_adquirente(descricao: str) -> Optional[str]:
    """Inferir adquirente a partir de palavras-chave na descrição"""
    if not descricao:
        return None
    
    desc = descricao.upper()
    
    # Mapeamento de keywords → adquirente
    mapping = {
        "CIELO": "CIELO",
        "REDE": "REDE", 
        "GETNET": "GETNET",
        "STONE": "STONE",
        "PAGSEGURO": "PAGSEGURO",
        "MERCADO PAGO": "MERCADOPAGO",
        "PICPAY": "PICPAY",
    }
    
    for keyword, adquirente in mapping.items():
        if keyword in desc:
            return adquirente
    
    return None


def _parse_data_br(data_str: str) -> Optional[datetime]:
    """Parse de data no formato brasileiro DD/MM/YYYY ou ISO"""
    if not data_str:
        return None
    
    data_str = str(data_str).strip()
    
    formatos = [
        "%Y-%m-%d",           # ISO
        "%d/%m/%Y",           # BR
        "%d-%m-%Y",
        "%Y/%m/%d",
        "%d/%m/%Y %H:%M:%S",  # BR com hora
        "%Y-%m-%d %H:%M:%S",  # ISO com hora
    ]
    
    for fmt in formatos:
        try:
            return datetime.strptime(data_str, fmt)
        except ValueError:
            continue
    
    logger.debug(f"⚠️ Data não parseada: '{data_str}'")
    return None


def _datas_proximas(data1: Optional[str], data2: Optional[str], tolerancia_dias: int = 3) -> bool:
    """Verifica se duas datas estão dentro da tolerância configurada"""
    if not data1 or not data2:
        return True  # Sem data → assume compatível
    
    d1 = _parse_data_br(data1)
    d2 = _parse_data_br(data2)
    
    if not d1 or not d2:
        return True  # Se não conseguiu parsear, assume compatível
    
    diff = abs((d1.date() - d2.date()).days)
    return diff <= tolerancia_dias


# ==========================================
# Normalização de VENDAS
# ==========================================
def normalizar_registros_vendas(
    rows: List[Dict[str, Any]], 
    fonte_arquivo: str,
    mapeamento_colunas: Optional[Dict[str, str]] = None
) -> List[Dict[str, Any]]:
    """
    Normaliza linhas de vendas vindas de CSV (Cielo, Rede, Getnet...).
    
    Args:
        rows: Lista de dicts com dados crus
        fonte_arquivo: Nome do arquivo de origem (para logging)
        mapeamento_colunas: Dict opcional para mapear nomes de colunas personalizados
                           Ex: {"data_pagamento": "DATA_VENDA", "vl_bruto": "VALOR_BRUTO"}
    
    Returns:
        Lista de dicts com chaves padrão:
        {nsu, data, valor, bandeira, adquirente, tipo, fonte, tipo_pagamento}
    """
    # Mapeamento default de colunas (case-insensitive)
    colunas_default = {
        "nsu": ["NSU", "COD_NSU", "NUMERO_NSU", "TRANSACTION_ID"],
        "data": ["DATA_VENDA", "DATA", "DT_VENDA", "DATA_PAGAMENTO"],
        "valor": ["VALOR_BRUTO", "VALOR", "VL_BRUTO", "GROSS_VALUE"],
        "bandeira": ["BANDEIRA", "FLAG", "CARD_FLAG", "BRAND"],
        "adquirente": ["ADQUIRENTE", "ORIGEM", "ACQUIRER", "OPERADORA"],
        "produto": ["PRODUTO", "TIPO_PAGAMENTO", "PAYMENT_TYPE", "PRODUCT"],
    }
    
    # Mesclar com mapeamento personalizado se fornecido
    if mapeamento_colunas:
        for chave, valores in colunas_default.items():
            if chave in mapeamento_colunas:
                if isinstance(mapeamento_colunas[chave], list):
                    valores.extend(mapeamento_colunas[chave])
                else:
                    valores.append(mapeamento_colunas[chave])
    
    vendas_norm = []

    for idx, row in enumerate(rows):
        # Normalizar chaves para upper case para busca case-insensitive
        r = {str(k).strip().upper(): v for k, v in row.items()}
        
        # Helper para buscar valor com múltiplos nomes possíveis
        def _buscar_coluna(chave: str) -> Any:
            possiveis = colunas_default.get(chave, [chave])
            for nome in possiveis:
                if nome in r:
                    return r[nome]
            return None
        
        nsu = _buscar_coluna("nsu")
        data = _buscar_coluna("data")
        valor = _buscar_coluna("valor")
        bandeira = _buscar_coluna("bandeira")
        adquirente = _buscar_coluna("adquirente")
        produto = _buscar_coluna("produto")
        
        # Inferir tipo_pagamento a partir do produto/bandeira
        tipo_pagamento = _inferir_tipo_pagamento(produto, bandeira)
        
        if not nsu:
            logger.debug(f"⚠️ Venda linha {idx+1} sem NSU, pulando: {row}")
            continue
        
        vendas_norm.append(
            {
                "tipo": "venda",
                "nsu": str(nsu).strip(),
                "data": str(data).strip() if data else None,
                "valor": _to_decimal(valor),
                "bandeira": (bandeira or "").strip() if bandeira else None,
                "adquirente": (adquirente or "").strip() if adquirente else None,
                "produto": (produto or "").strip() if produto else None,
                "tipo_pagamento": tipo_pagamento,
                "fonte": fonte_arquivo,
                "linha_origem": idx + 1,  # Para debug
            }
        )
    
    logger.info(f"✅ Normalizadas {len(vendas_norm)} vendas de {fonte_arquivo}")
    return vendas_norm


def _inferir_tipo_pagamento(produto: Any, bandeira: Any) -> str:
    """Inferir tipo de pagamento (cartao/pix/boleto) a partir de produto/bandeira"""
    produto_str = str(produto or "").lower()
    bandeira_str = str(bandeira or "").lower()
    
    if "pix" in produto_str or bandeira_str == "pix":
        return "pix"
    if "boleto" in produto_str or "billet" in produto_str:
        return "boleto"
    if any(kw in produto_str for kw in ["crédito", "credito", "débito", "debito", "credit", "debit"]):
        return "cartao"
    
    return "cartao"  # Default para adquirentes


# ==========================================
# Normalização de RECEBIMENTOS (extrato/OFX)
# ==========================================
def normalizar_registros_recebimentos(
    rows: List[Dict[str, Any]], 
    fonte_arquivo: str,
    mapeamento_colunas: Optional[Dict[str, str]] = None
) -> List[Dict[str, Any]]:
    """
    Normaliza linhas de extrato bancário (CSV/OFX).
    Espera colunas do tipo: DATA, DESCRICAO, VALOR/ENTRADA/SAIDA.
    """
    colunas_default = {
        "data": ["DATA", "DATA_MOVIMENTO", "DT", "TRANSACTION_DATE"],
        "descricao": ["DESCRICAO", "DESC", "MEMO", "HISTORICO", "DETAIL"],
        "valor": ["VALOR", "ENTRADA", "CREDITO", "TRNAMT", "AMOUNT"],
        "documento": ["DOCUMENTO", "DOC", "NSU", "REFERENCE", "COD_DOCUMENTO"],
    }
    
    if mapeamento_colunas:
        for chave, valores in colunas_default.items():
            if chave in mapeamento_colunas:
                if isinstance(mapeamento_colunas[chave], list):
                    valores.extend(mapeamento_colunas[chave])
                else:
                    valores.append(mapeamento_colunas[chave])
    
    rec_norm = []

    for idx, row in enumerate(rows):
        r = {str(k).strip().upper(): v for k, v in row.items()}
        
        def _buscar_coluna(chave: str) -> Any:
            possiveis = colunas_default.get(chave, [chave])
            for nome in possiveis:
                if nome in r:
                    return r[nome]
            return None
        
        data = _buscar_coluna("data")
        descricao = _buscar_coluna("descricao") or ""
        valor = _buscar_coluna("valor")
        documento = _buscar_coluna("documento")
        
        # Extrair NSU da descrição ou do campo documento
        nsu = _extrair_nsu(str(descricao)) or (str(documento).strip() if documento else None)
        adquirente = _inferir_adquirente(str(descricao))
        
        rec_norm.append(
            {
                "tipo": "recebimento",
                "nsu": nsu,
                "data": str(data).strip() if data else None,
                "valor": _to_decimal(valor),
                "bandeira": None,  # Normalmente não vem no extrato
                "adquirente": adquirente,
                "descricao": str(descricao).strip() if descricao else None,
                "fonte": fonte_arquivo,
                "linha_origem": idx + 1,
            }
        )
    
    logger.info(f"✅ Normalizados {len(rec_norm)} recebimentos de {fonte_arquivo}")
    return rec_norm


# ==========================================
# Motor de conciliação AVANÇADO
# ==========================================
def conciliar(
    vendas: List[Dict[str, Any]], 
    recebimentos: List[Dict[str, Any]], 
    tolerancia_centavos: Decimal = TOLERANCIA_CENTAVOS_DEFAULT,
    tolerancia_dias: int = TOLERANCIA_DIAS_DEFAULT,
    permitir_multivenda: bool = True
) -> Dict[str, Any]:
    """
    Faz o casamento venda x recebimento com estratégias avançadas:
    
    1. Match exato por NSU + data próxima + valor compatível
    2. Match com tolerância de centavos
    3. (Opcional) Multi-venda: soma de vendas = 1 recebimento
    
    Args:
        vendas: Lista de vendas normalizadas
        recebimentos: Lista de recebimentos normalizados
        tolerancia_centavos: Diferença máxima em R$ para considerar match
        tolerancia_dias: Diferença máxima em dias para considerar data compatível
        permitir_multivenda: Se True, tenta combinar múltiplas vendas em 1 recebimento
    
    Returns:
        Dict com conciliados, pendentes e resumo estatístico
    """
    logger.info(f"🔍 Iniciando conciliação: {len(vendas)} vendas, {len(recebimentos)} recebimentos")
    
    # Índices para matching eficiente
    rec_por_nsu: Dict[str, List[Dict[str, Any]]] = {}
    for r in recebimentos:
        nsu = str(r.get("nsu") or "").strip()
        if nsu:
            rec_por_nsu.setdefault(nsu, []).append(r)
    
    # Track de itens já conciliados
    vendas_conciliadas: Set[str] = set()  # IDs ou NSU+data como chave única
    recebimentos_usados: Set[int] = set()  # Índices dos recebimentos usados
    
    conciliados = []
    pendentes_vendas = []
    
    # ==========================================
    # FASE 1: Match individual por NSU
    # ==========================================
    for v in vendas:
        nsu = str(v.get("nsu") or "").strip()
        chave_venda = f"{nsu}:{v.get('data')}:{v.get('valor')}"
        
        if chave_venda in vendas_conciliadas:
            continue  # Já processada
        
        if not nsu or nsu not in rec_por_nsu:
            pendentes_vendas.append(_criar_pendente_venda(v, "SEM_RECEBIMENTO_NSU"))
            continue
        
        # Encontrar melhor match entre recebimentos com mesmo NSU
        melhor_match = None
        melhor_score = -1
        
        for idx_rec, r in enumerate(rec_por_nsu[nsu]):
            if idx_rec in recebimentos_usados:
                continue
            
            # Calcular score de compatibilidade
            score = _calcular_score_match(v, r, tolerancia_centavos, tolerancia_dias)
            
            if score > melhor_score:
                melhor_score = score
                melhor_match = (idx_rec, r, score)
        
        if not melhor_match or melhor_score < 0.5:  # Threshold mínimo de confiança
            pendentes_vendas.append(_criar_pendente_venda(v, "SEM_MATCH_CONFIÁVEL"))
            continue
        
        # Processar match encontrado
        idx_rec, r, score = melhor_match
        recebimentos_usados.add(idx_rec)
        vendas_conciliadas.add(chave_venda)
        
        val_v = _to_decimal(v.get("valor"))
        val_r = _to_decimal(r.get("valor"))
        diff = val_r - val_v
        
        status = "OK" if abs(diff) <= tolerancia_centavos else "DIVERGENTE"
        
        conciliados.append({
            "nsu": nsu,
            "valor_venda": str(val_v),
            "valor_recebido": str(val_r),
            "diferenca": str(diff),
            "status": status,
            "score_match": round(melhor_score, 2),
            "data_venda": v.get("data"),
            "data_recebimento": r.get("data"),
            "bandeira": v.get("bandeira") or r.get("bandeira"),
            "adquirente": v.get("adquirente") or r.get("adquirente"),
            "tipo_pagamento": v.get("tipo_pagamento", "cartao"),
            "fonte_venda": v.get("fonte"),
            "fonte_recebimento": r.get("fonte"),
            "descricao_recebimento": r.get("descricao"),
        })
        
        if status != "OK":
            pendentes_vendas.append(_criar_pendente_venda(v, "VALOR_DIFERENTE"))
        
        logger.debug(f"✅ Match: NSU={nsu}, score={melhor_score:.2f}, status={status}")
    
    # ==========================================
    # FASE 2: Multi-venda (opcional)
    # ==========================================
    if permitir_multivenda:
        conciliados_mv, pendentes_vendas_mv = _tentar_multivenda(
            vendas, recebimentos, 
            vendas_conciliadas, recebimentos_usados,
            tolerancia_centavos, tolerancia_dias
        )
        conciliados.extend(conciliados_mv)
        pendentes_vendas.extend(pendentes_vendas_mv)
    
    # ==========================================
    # Recebimentos sobrantes
    # ==========================================
    pendentes_recebimentos = []
    for idx, r in enumerate(recebimentos):
        if idx in recebimentos_usados:
            continue
        pendentes_recebimentos.append({
            "nsu": r.get("nsu"),
            "data": r.get("data"),
            "valor": str(_to_decimal(r.get("valor"))),
            "adquirente": r.get("adquirente"),
            "descricao": r.get("descricao"),
            "fonte": r.get("fonte"),
            "motivo": "RECEBIMENTO_SEM_VENDA_CORRESPONDENTE",
        })
    
    # ==========================================
    # Resumo estatístico
    # ==========================================
    total_vendas = sum(_to_decimal(v.get("valor")) for v in vendas)
    total_recebimentos = sum(_to_decimal(r.get("valor")) for r in recebimentos)
    
    resumo = {
        "total_vendas": str(total_vendas),
        "total_recebimentos": str(total_recebimentos),
        "diferenca_geral": str(total_recebimentos - total_vendas),
        "qtd_vendas": len(vendas),
        "qtd_recebimentos": len(recebimentos),
        "qtd_conciliados_ok": len([c for c in conciliados if c["status"] == "OK"]),
        "qtd_conciliados_divergentes": len([c for c in conciliados if c["status"] != "OK"]),
        "qtd_pendentes_vendas": len(pendentes_vendas),
        "qtd_pendentes_recebimentos": len(pendentes_recebimentos),
        "taxa_conciliacao": round(
            len([c for c in conciliados if c["status"] == "OK"]) / max(len(vendas), 1) * 100, 
            2
        ),
    }
    
    logger.info(f"✅ Conciliação concluída: {resumo['qtd_conciliados_ok']}/{len(vendas)} conciliados ({resumo['taxa_conciliacao']}%)")
    
    return {
        "resumo": resumo,
        "conciliados": conciliados,
        "pendentes_vendas": pendentes_vendas,
        "pendentes_recebimentos": pendentes_recebimentos,
    }


def _calcular_score_match(
    venda: Dict, 
    recebimento: Dict, 
    tol_centavos: Decimal, 
    tol_dias: int
) -> float:
    """
    Calcula score de compatibilidade entre venda e recebimento (0.0 a 1.0).
    
    Fatores considerados:
    - Proximidade de valor (peso: 50%)
    - Proximidade de data (peso: 30%)
    - Match de adquirente/bandeira (peso: 20%)
    """
    score = 0.0
    
    # 1. Score por valor (0-0.5)
    val_v = _to_decimal(venda.get("valor"))
    val_r = _to_decimal(recebimento.get("valor"))
    diff_valor = abs(val_r - val_v)
    
    if diff_valor == 0:
        score += 0.5
    elif diff_valor <= tol_centavos:
        score += 0.4
    elif diff_valor <= tol_centavos * 2:
        score += 0.2
    # else: 0 pontos
    
    # 2. Score por data (0-0.3)
    if _datas_proximas(venda.get("data"), recebimento.get("data"), tol_dias):
        score += 0.3
    elif _datas_proximas(venda.get("data"), recebimento.get("data"), tol_dias * 2):
        score += 0.15
    
    # 3. Score por adquirente/bandeira (0-0.2)
    adq_v = (venda.get("adquirente") or "").upper()
    adq_r = (recebimento.get("adquirente") or "").upper()
    if adq_v and adq_r and adq_v == adq_r:
        score += 0.2
    elif adq_v and adq_r and (adq_v in adq_r or adq_r in adq_v):
        score += 0.1
    
    return score


def _criar_pendente_venda(venda: Dict, motivo: str) -> Dict[str, Any]:
    """Cria registro padronizado para venda pendente"""
    return {
        "nsu": venda.get("nsu"),
        "data": venda.get("data"),
        "valor": str(_to_decimal(venda.get("valor"))),
        "bandeira": venda.get("bandeira"),
        "adquirente": venda.get("adquirente"),
        "tipo_pagamento": venda.get("tipo_pagamento", "cartao"),
        "fonte": venda.get("fonte"),
        "motivo": motivo,
    }


def _tentar_multivenda(
    vendas: List[Dict],
    recebimentos: List[Dict],
    vendas_conciliadas: Set[str],
    recebimentos_usados: Set[int],
    tol_centavos: Decimal,
    tol_dias: int
) -> tuple:
    """
    Tenta combinar múltiplas vendas pendentes em um único recebimento.
    Útil para depósitos em lote de adquirentes.
    
    Returns:
        (lista_conciliados_mv, lista_pendentes_mv)
    """
    conciliados = []
    pendentes = []
    
    # Recebimentos ainda não usados
    rec_disponiveis = [
        (idx, r) for idx, r in enumerate(recebimentos) 
        if idx not in recebimentos_usados and r.get("nsu")
    ]
    
    # Vendas ainda não conciliadas
    vendas_disponiveis = [
        v for v in vendas 
        if f"{v.get('nsu')}:{v.get('data')}:{v.get('valor')}" not in vendas_conciliadas
    ]
    
    for idx_rec, rec in rec_disponiveis:
        valor_rec = _to_decimal(rec.get("valor"))
        data_rec = rec.get("data")
        
        # Filtrar vendas compatíveis por data e adquirente
        candidatas = [
            v for v in vendas_disponiveis
            if _datas_proximas(v.get("data"), data_rec, tol_dias)
            and (not v.get("adquirente") or not rec.get("adquirente") 
                 or v["adquirente"].upper() == rec["adquirente"].upper())
        ]
        
        if not candidatas:
            continue
        
        # Algoritmo greedy: ordenar por valor (maior primeiro) e somar até bater
        candidatas.sort(key=lambda v: _to_decimal(v.get("valor")), reverse=True)
        
        soma = Decimal("0")
        combinacao = []
        
        for v in candidatas:
            val_v = _to_decimal(v.get("valor"))
            if soma + val_v <= valor_rec + tol_centavos:
                soma += val_v
                combinacao.append(v)
            
            # Parar se bateu exato ou passou do limite
            if abs(soma - valor_rec) <= tol_centavos:
                break
        
        # Se encontrou combinação válida
        if combinacao and abs(soma - valor_rec) <= tol_centavos:
            # Registrar conciliação multi-venda
            conciliados.append({
                "nsu": rec.get("nsu"),
                "valor_venda": str(soma),
                "valor_recebido": str(valor_rec),
                "diferenca": str(valor_rec - soma),
                "status": "OK" if abs(valor_rec - soma) <= tol_centavos else "DIVERGENTE",
                "tipo_match": "MULTIVENDA",
                "qtd_vendas": len(combinacao),
                "nsus_combinados": [v.get("nsu") for v in combinacao],
                "data_recebimento": rec.get("data"),
                "adquirente": rec.get("adquirente"),
                "fonte_recebimento": rec.get("fonte"),
                "descricao_recebimento": rec.get("descricao"),
            })
            
            # Marcar como usadas
            recebimentos_usados.add(idx_rec)
            for v in combinacao:
                chave = f"{v.get('nsu')}:{v.get('data')}:{v.get('valor')}"
                vendas_conciliadas.add(chave)
            
            logger.debug(f"✅ Multi-venda: {len(combinacao)} vendas → 1 recebimento, NSU={rec.get('nsu')}")
    
    return conciliados, pendentes
