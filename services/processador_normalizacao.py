# services/processador_normalizacao.py
# ✅ DEBUG PIPELINE: Normalizacao → conversão → salvar_vendas/salvar_recebimentos

from models import db, Normalizacao
from services.importer_db_movimento import salvar_vendas, salvar_recebimentos
from services.classificador_financeiro import classificador
import logging

logger = logging.getLogger(__name__)


def processar_normalizacoes(empresa_id: int, arquivo_id: int = None, dados_conta: dict = None):
    logger.info("🔄 [PROCESSADOR] INÍCIO processar_normalizacoes")
    logger.info(f"🧪 [PROCESSADOR] empresa_id={empresa_id}, arquivo_id={arquivo_id}, dados_conta={dados_conta}")

    query = Normalizacao.query.filter(
        Normalizacao.empresa_id == empresa_id,
        Normalizacao.status.in_(["importado", "validado"])
    )

    if arquivo_id:
        query = query.filter_by(arquivo_origem_id=arquivo_id)

    normalizacoes = query.all()

    logger.info(f"🧪 [PROCESSADOR] NORMALIZAÇÕES ENCONTRADAS: {len(normalizacoes)}")

    for n in normalizacoes[:10]:
        logger.info(
            f"🧪 [PROCESSADOR] NORMALIZACAO SAMPLE: "
            f"id={n.id}, arquivo_origem_id={getattr(n, 'arquivo_origem_id', None)}, "
            f"tipo_movimento={getattr(n, 'tipo_movimento', None)}, "
            f"tipo_origem={getattr(n, 'tipo_origem', None)}, "
            f"status={getattr(n, 'status', None)}, "
            f"valor_bruto={getattr(n, 'valor_bruto', None)}, "
            f"valor_liquido={getattr(n, 'valor_liquido', None)}, "
            f"categoria={getattr(n, 'categoria', None)}, "
            f"tipo_pagamento={getattr(n, 'tipo_pagamento', None)}, "
            f"data_movimento={getattr(n, 'data_movimento', None)}, "
            f"descricao={str(getattr(n, 'descricao', '') or '')[:120]}"
        )

    if not normalizacoes:
        logger.warning(
            f"⚠️ [PROCESSADOR] Nenhuma normalização encontrada para "
            f"empresa_id={empresa_id}, arquivo_id={arquivo_id}"
        )
        return {
            "vendas": {"sucesso": 0, "falhas": 0, "motivo": "nenhuma_normalizacao"},
            "recebimentos": {"sucesso": 0, "falhas": 0, "motivo": "nenhuma_normalizacao"}
        }

    vendas = []
    recebimentos = []

    contadores_tipo = {}

    for norm in normalizacoes:
        try:
            tipo_movimento = getattr(norm, "tipo_movimento", None)
            contadores_tipo[tipo_movimento] = contadores_tipo.get(tipo_movimento, 0) + 1

            logger.info(
                f"🧪 [PROCESSADOR] PROCESSANDO NORMALIZACAO: "
                f"id={norm.id}, tipo_movimento={tipo_movimento}, status={norm.status}"
            )

            if norm.status == "importado":
                try:
                    logger.info(f"🧪 [PROCESSADOR] Enriquecendo normalizacao id={norm.id}")
                    norm.enriquecer()
                except Exception as e:
                    logger.warning(
                        f"⚠️ [PROCESSADOR] Erro ao enriquecer id={norm.id}: {str(e)}",
                        exc_info=True
                    )

            if tipo_movimento == "venda":
                item = _converter_para_venda(norm)

                if item:
                    vendas.append(item)
                    norm.status = "processado"
                    logger.info(
                        f"✅ [PROCESSADOR] Venda convertida: "
                        f"id={norm.id}, nsu={item.get('nsu')}, valor={item.get('valor_bruto')}, "
                        f"categoria={item.get('categoria')}"
                    )
                else:
                    norm.status = "erro"
                    norm.erro_mensagem = "Falha na conversão para venda"
                    logger.error(f"❌ [PROCESSADOR] Falha conversão venda id={norm.id}")

            elif tipo_movimento in ["recebimento", "pagamento"]:
                item = _converter_para_recebimento(norm)

                if item:
                    recebimentos.append(item)
                    norm.status = "processado"
                    logger.info(
                        f"✅ [PROCESSADOR] Recebimento convertido: "
                        f"id={norm.id}, nsu={item.get('nsu')}, valor={item.get('valor')}, "
                        f"categoria={item.get('categoria')}, tipo_pagamento={item.get('tipo_pagamento')}"
                    )
                else:
                    norm.status = "erro"
                    norm.erro_mensagem = "Falha na conversão para recebimento"
                    logger.error(f"❌ [PROCESSADOR] Falha conversão recebimento id={norm.id}")

            else:
                norm.status = "erro"
                norm.erro_mensagem = f"Tipo de movimento não processável: {tipo_movimento}"
                logger.error(
                    f"❌ [PROCESSADOR] NORMALIZACAO IGNORADA: "
                    f"id={norm.id}, tipo_movimento={tipo_movimento}, arquivo_id={arquivo_id}"
                )

        except Exception as e:
            logger.error(f"❌ [PROCESSADOR] Erro normalização {norm.id}: {str(e)}", exc_info=True)
            norm.status = "erro"
            norm.erro_mensagem = str(e)

    logger.info(f"🧪 [PROCESSADOR] CONTADORES TIPO_MOVIMENTO: {contadores_tipo}")
    logger.info(f"🧪 [PROCESSADOR] VENDAS PARA SALVAR: {len(vendas)}")
    logger.info(f"🧪 [PROCESSADOR] RECEBIMENTOS PARA SALVAR: {len(recebimentos)}")
    logger.info(f"🧪 [PROCESSADOR] DADOS CONTA RECEBIDOS: {dados_conta}")
    logger.info(f"🧪 [PROCESSADOR] PRIMEIRA VENDA: {vendas[0] if vendas else None}")
    logger.info(f"🧪 [PROCESSADOR] PRIMEIRO RECEBIMENTO: {recebimentos[0] if recebimentos else None}")

    stats_vendas = {"sucesso": 0, "falhas": 0, "duplicados": 0}
    stats_recebimentos = {"sucesso": 0, "falhas": 0}

    if vendas:
        try:
            logger.info("💳 [PROCESSADOR] Chamando salvar_vendas")
            stats_vendas = salvar_vendas(vendas, empresa_id, arquivo_id)
            logger.info(f"🧪 [PROCESSADOR] STATS VENDAS: {stats_vendas}")
        except Exception as e:
            logger.error(f"❌ [PROCESSADOR] Erro ao salvar vendas: {str(e)}", exc_info=True)
            stats_vendas["erro"] = str(e)

    if recebimentos:
        try:
            logger.info("🏦 [PROCESSADOR] Chamando salvar_recebimentos")
            stats_recebimentos = salvar_recebimentos(
                recebimentos,
                empresa_id,
                arquivo_id,
                dados_conta=dados_conta
            )
            logger.info(f"🧪 [PROCESSADOR] STATS RECEBIMENTOS: {stats_recebimentos}")
        except Exception as e:
            logger.error(f"❌ [PROCESSADOR] Erro ao salvar recebimentos: {str(e)}", exc_info=True)
            stats_recebimentos["erro"] = str(e)

    try:
        db.session.commit()
        logger.info("✅ [PROCESSADOR] Commit final OK")
    except Exception as e:
        db.session.rollback()
        logger.error(f"❌ [PROCESSADOR] Commit final falhou: {str(e)}", exc_info=True)

    retorno = {
        "vendas": stats_vendas,
        "recebimentos": stats_recebimentos,
        "debug": {
            "empresa_id": empresa_id,
            "arquivo_id": arquivo_id,
            "normalizacoes_encontradas": len(normalizacoes),
            "tipos": contadores_tipo,
            "vendas_para_salvar": len(vendas),
            "recebimentos_para_salvar": len(recebimentos),
            "dados_conta_recebidos": dados_conta,
        }
    }

    logger.info(f"🏁 [PROCESSADOR] FIM processar_normalizacoes retorno={retorno}")

    return retorno


def _texto_norm(norm):
    return (
        getattr(norm, "descricao", None)
        or getattr(norm, "historico", None)
        or getattr(norm, "estabelecimento", None)
        or ""
    )


def _classificar(norm, valor):
    descricao = _texto_norm(norm)
    trntype = getattr(norm, "trntype", None)

    logger.info(
        f"🧪 [PROCESSADOR] Classificando: "
        f"id={getattr(norm, 'id', None)}, valor={valor}, trntype={trntype}, "
        f"descricao={str(descricao)[:120]}"
    )

    resultado = classificador.classificar(
        descricao=descricao,
        valor=float(valor or 0),
        trntype=trntype
    )

    logger.info(
        f"🧪 [PROCESSADOR] Resultado classificação: "
        f"id={getattr(norm, 'id', None)}, resultado={resultado}"
    )

    return resultado


def _converter_para_venda(norm: Normalizacao) -> dict:
    try:
        logger.info(f"🧪 [PROCESSADOR] _converter_para_venda id={norm.id}")

        if not norm.valor_bruto or norm.valor_bruto <= 0:
            logger.warning(
                f"⚠️ [PROCESSADOR] Venda inválida sem valor positivo: "
                f"id={norm.id}, valor_bruto={norm.valor_bruto}"
            )
            return None

        if not norm.data_movimento:
            logger.warning(f"⚠️ [PROCESSADOR] Venda inválida sem data_movimento: id={norm.id}")
            return None

        resultado = _classificar(norm, norm.valor_bruto)

        item = {
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

        logger.info(f"🧪 [PROCESSADOR] Venda item convertido id={norm.id}: {item}")
        return item

    except Exception as e:
        logger.error(f"❌ [PROCESSADOR] Erro ao converter venda {norm.id}: {str(e)}", exc_info=True)
        return None


def _converter_para_recebimento(norm: Normalizacao) -> dict:
    try:
        logger.info(f"🧪 [PROCESSADOR] _converter_para_recebimento id={norm.id}")

        if norm.valor_bruto is None:
            logger.warning(f"⚠️ [PROCESSADOR] Recebimento inválido sem valor_bruto: id={norm.id}")
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

        item = {
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

        logger.info(f"🧪 [PROCESSADOR] Recebimento item convertido id={norm.id}: {item}")
        return item

    except Exception as e:
        logger.error(f"❌ [PROCESSADOR] Erro ao converter recebimento {norm.id}: {str(e)}", exc_info=True)
        return None
