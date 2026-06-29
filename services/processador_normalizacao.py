# services/processador_normalizacao.py

from models import db, Normalizacao
from services.importer_db_movimento import salvar_vendas, salvar_recebimentos
from services.classificador_financeiro import classificador
import logging

logger = logging.getLogger(__name__)


def processar_normalizacoes(empresa_id: int, arquivo_id: int = None, dados_conta: dict = None):
    logger.info(f"🔄 Processando normalizações: empresa={empresa_id}, arquivo={arquivo_id}")

    query = Normalizacao.query.filter(
        Normalizacao.empresa_id == empresa_id,
        Normalizacao.status.in_(["importado", "validado"])
    )

    if arquivo_id:
        query = query.filter_by(arquivo_origem_id=arquivo_id)

    normalizacoes = query.all()

    if not normalizacoes:
        return {"vendas": {"sucesso": 0}, "recebimentos": {"sucesso": 0}}

    vendas = []
    recebimentos = []

    for norm in normalizacoes:
        try:
            if norm.status == "importado":
                norm.enriquecer()

            if norm.tipo_movimento == "venda":
                item = _converter_para_venda(norm)
                if item:
                    vendas.append(item)
                    norm.status = "processado"
                else:
                    norm.status = "erro"
                    norm.erro_mensagem = "Falha na conversão para venda"

            elif norm.tipo_movimento in ["recebimento", "pagamento"]:
                item = _converter_para_recebimento(norm)
                if item:
                    recebimentos.append(item)
                    norm.status = "processado"
                else:
                    norm.status = "erro"
                    norm.erro_mensagem = "Falha na conversão para recebimento"

        except Exception as e:
            logger.error(f"❌ Erro normalização {norm.id}: {str(e)}", exc_info=True)
            norm.status = "erro"
            norm.erro_mensagem = str(e)

    stats_vendas = {"sucesso": 0, "falhas": 0, "duplicados": 0}
    stats_recebimentos = {"sucesso": 0, "falhas": 0}

    if vendas:
        stats_vendas = salvar_vendas(vendas, empresa_id, arquivo_id)

    if recebimentos:
        stats_recebimentos = salvar_recebimentos(
            recebimentos,
            empresa_id,
            arquivo_id,
            dados_conta=dados_conta
        )

    db.session.commit()

    return {
        "vendas": stats_vendas,
        "recebimentos": stats_recebimentos
    }


def _texto_norm(norm):
    return (
        getattr(norm, "descricao", None)
        or getattr(norm, "historico", None)
        or getattr(norm, "estabelecimento", None)
        or ""
    )


def _classificar(norm, valor):
    return classificador.classificar(
        descricao=_texto_norm(norm),
        valor=float(valor or 0),
        trntype=getattr(norm, "trntype", None)
    )


def _converter_para_venda(norm: Normalizacao) -> dict:
    try:
        if not norm.valor_bruto or norm.valor_bruto <= 0:
            return None

        if not norm.data_movimento:
            return None

        resultado = _classificar(norm, norm.valor_bruto)

        return {
            "adquirente": norm.adquirente_nome or "Flow",
            "nsu": norm.nsu,
            "data_venda": norm.data_venda or norm.data_movimento,
            "valor_bruto": float(norm.valor_bruto),
            "valor_liquido": float(norm.valor_liquido) if norm.valor_liquido else float(norm.valor_bruto),
            "desconto": float(norm.valor_taxa) if norm.valor_taxa else 0,
            "bandeira": norm.bandeira,
            "produto": norm.produto,
            "tipo_pagamento": resultado.get("tipo_pagamento") or norm.tipo_pagamento or "cartao",
            "categoria": resultado.get("categoria") or norm.categoria or "vendas_cartao",
            "observacoes": norm.descricao,
            "empresa_id": norm.empresa_id,
            "score_classificacao": resultado.get("score", 0),
            "categoria_principal": resultado.get("grupo"),
            "subcategoria": resultado.get("subgrupo"),
            "origem_classificacao": "classificador_financeiro_v2",
            "regra_utilizada": resultado.get("regra") or resultado.get("categoria"),
            "classificacao_automatica": True,
            "classificacao_manual": False,
        }

    except Exception as e:
        logger.error(f"❌ Erro ao converter venda {norm.id}: {str(e)}", exc_info=True)
        return None


def _converter_para_recebimento(norm: Normalizacao) -> dict:
    try:
        if norm.valor_bruto is None:
            return None

        resultado = _classificar(norm, norm.valor_bruto)

        categoria = resultado.get("categoria") or norm.categoria or "outros"
        tipo_pagamento = resultado.get("tipo_pagamento") or norm.tipo_pagamento or "outros"
        natureza = resultado.get("natureza")
        score = resultado.get("score", 0)

        valor_abs = abs(float(norm.valor_bruto))

        if natureza == "despesa":
            valor_normalizado = -valor_abs
        elif natureza == "receita":
            valor_normalizado = valor_abs
        else:
            valor_normalizado = float(norm.valor_bruto)

        return {
            "data": norm.data_movimento,
            "valor": valor_normalizado,
            "descricao": _texto_norm(norm),
            "nsu": norm.nsu,
            "tipo_pagamento": tipo_pagamento,
            "categoria": categoria,
            "empresa_id": norm.empresa_id,
            "score_classificacao": score,
            "categoria_principal": resultado.get("grupo"),
            "subcategoria": resultado.get("subgrupo"),
            "origem_classificacao": "classificador_financeiro_v2",
            "regra_utilizada": resultado.get("regra") or categoria,
            "classificacao_automatica": True,
            "classificacao_manual": False,
        }

    except Exception as e:
        logger.error(f"❌ Erro ao converter recebimento {norm.id}: {str(e)}", exc_info=True)
        return None