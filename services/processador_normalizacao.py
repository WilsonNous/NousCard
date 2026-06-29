# services/processador_normalizacao.py
# Processa normalizações e salva nas tabelas finais
# ✅ INTEGRADO com Classificador Financeiro

from models import db, Normalizacao
from services.importer_db_movimento import salvar_vendas, salvar_recebimentos
from services.classificador_financeiro import classificador
import logging

logger = logging.getLogger(__name__)


def processar_normalizacoes(empresa_id: int, arquivo_id: int = None):
    """Processa normalizações e salva nas tabelas finais"""
    logger.info(f"🔄 Processando normalizações para empresa {empresa_id}, arquivo {arquivo_id}")
    
    query = Normalizacao.query.filter(
        Normalizacao.empresa_id == empresa_id,
        Normalizacao.status.in_(["importado", "validado"])
    )
    
    if arquivo_id:
        query = query.filter_by(arquivo_origem_id=arquivo_id)
    
    normalizacoes = query.all()
    
    if not normalizacoes:
        logger.info("ℹ️ Nenhuma normalização para processar")
        return {"vendas": {"sucesso": 0}, "recebimentos": {"sucesso": 0}}
    
    logger.info(f"📦 {len(normalizacoes)} normalizações para processar")
    
    vendas = []
    recebimentos = []
    
    for norm in normalizacoes:
        try:
            # Enriquecer se ainda não foi enriquecido
            if norm.status == "importado":
                norm.enriquecer()
            
            if norm.tipo_movimento == "venda":
                venda_dict = _converter_para_venda(norm)
                if venda_dict:
                    vendas.append(venda_dict)
                    norm.status = "processado"
                else:
                    norm.status = "erro"
                    norm.erro_mensagem = "Falha na conversão para venda"
            
            elif norm.tipo_movimento in ["recebimento", "pagamento"]:
                recebimento_dict = _converter_para_recebimento(norm)
                if recebimento_dict:
                    recebimentos.append(recebimento_dict)
                    norm.status = "processado"
                else:
                    norm.status = "erro"
                    norm.erro_mensagem = "Falha na conversão para recebimento"
            
        except Exception as e:
            logger.error(f"❌ Erro ao processar normalizacao {norm.id}: {str(e)}", exc_info=True)
            norm.status = "erro"
            norm.erro_mensagem = str(e)
    
    # Salvar nas tabelas finais
    stats_vendas = {"sucesso": 0, "falhas": 0, "duplicados": 0}
    stats_recebimentos = {"sucesso": 0, "falhas": 0}
    
    if vendas:
        logger.info(f"💳 Salvando {len(vendas)} vendas")
        try:
            stats_vendas = salvar_vendas(vendas, empresa_id, arquivo_id)
            logger.info(f"✅ Vendas salvas: {stats_vendas}")
        except Exception as e:
            logger.error(f"❌ Erro ao salvar vendas: {str(e)}", exc_info=True)
            stats_vendas["erro"] = str(e)
    
    if recebimentos:
        logger.info(f"🏦 Salvando {len(recebimentos)} recebimentos")
        try:
            stats_recebimentos = salvar_recebimentos(recebimentos, empresa_id, arquivo_id)
            logger.info(f"✅ Recebimentos salvos: {stats_recebimentos}")
        except Exception as e:
            logger.error(f"❌ Erro ao salvar recebimentos: {str(e)}", exc_info=True)
            stats_recebimentos["erro"] = str(e)
    
    db.session.commit()
    
    logger.info(f"✅ Processamento concluído: {stats_vendas.get('sucesso', 0)} vendas, {stats_recebimentos.get('sucesso', 0)} recebimentos")
    
    return {
        "vendas": stats_vendas,
        "recebimentos": stats_recebimentos
    }


def _converter_para_venda(norm: Normalizacao) -> dict:
    """Converte Normalizacao para formato de venda"""
    try:
        if not norm.valor_bruto or norm.valor_bruto <= 0:
            logger.warning(f"⚠️ Normalizacao {norm.id} sem valor_bruto válido")
            return None
        
        if not norm.data_movimento:
            logger.warning(f"⚠️ Normalizacao {norm.id} sem data_movimento")
            return None
        
        # ✅ Classificar usando o novo motor
        resultado = classificador.classificar(
            descricao=norm.descricao or "",
            valor=float(norm.valor_bruto),
            trntype=getattr(norm, 'trntype', 'CREDIT')
        )
        
        return {
            "adquirente": norm.adquirente_nome or "Flow",
            "nsu": norm.nsu,
            "data_venda": norm.data_venda or norm.data_movimento,
            "valor_bruto": float(norm.valor_bruto),
            "valor_liquido": float(norm.valor_liquido) if norm.valor_liquido else float(norm.valor_bruto),
            "desconto": float(norm.valor_taxa) if norm.valor_taxa else 0,
            "bandeira": norm.bandeira,
            "produto": norm.produto,
            "tipo_pagamento": resultado["tipo_pagamento"],
            "categoria": resultado["categoria"],
            "observacoes": norm.descricao,
            "empresa_id": norm.empresa_id,
            "score_classificacao": resultado["score"],
            "origem_classificacao": "classificador_financeiro_v2",
            "regra_utilizada": resultado["categoria"]
        }
    except Exception as e:
        logger.error(f"❌ Erro ao converter normalizacao {norm.id} para venda: {str(e)}", exc_info=True)
        return None


def _converter_para_recebimento(norm: Normalizacao) -> dict:
    """
    Converte Normalizacao para formato de recebimento.
    ✅ Usa o Classificador Financeiro oficial.
    """
    try:
        if not norm.valor_bruto:
            logger.warning(f"⚠️ Normalizacao {norm.id} sem valor_bruto")
            return None
        
        # ✅ Usar o novo classificador financeiro
        resultado = classificador.classificar(
            descricao=norm.descricao or norm.historico or "",
            valor=float(norm.valor_bruto),
            trntype=getattr(norm, 'trntype', None)
        )
        
        categoria = resultado["categoria"]
        tipo_pagamento = resultado["tipo_pagamento"]
        natureza = resultado["natureza"]
        score = resultado["score"]
        
        # Aplicar normalização financeira
        valor_abs = abs(float(norm.valor_bruto))
        if natureza == "despesa":
            valor_normalizado = -valor_abs
        else:
            valor_normalizado = valor_abs
        
        logger.debug(
            f"💰 Classificação: '{str(norm.descricao)[:50]}' "
            f"→ {categoria} ({natureza}) score={score}"
        )
        
        return {
            "data": norm.data_movimento,
            "valor": valor_normalizado,
            "descricao": norm.descricao,
            "nsu": norm.nsu,
            "tipo_pagamento": tipo_pagamento,
            "categoria": categoria,
            "empresa_id": norm.empresa_id,
            "score_classificacao": score,
            "origem_classificacao": "classificador_financeiro_v2",
            "regra_utilizada": categoria
        }
    except Exception as e:
        logger.error(f"❌ Erro ao converter normalizacao {norm.id} para recebimento: {str(e)}", exc_info=True)
        return None