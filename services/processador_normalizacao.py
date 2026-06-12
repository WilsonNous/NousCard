# services/processador_normalizacao.py
# Processa normalizações e salva nas tabelas finais

from models import db, Normalizacao
from services.importer_db_movimento import salvar_vendas, salvar_recebimentos
import logging

logger = logging.getLogger(__name__)


def processar_normalizacoes(empresa_id: int, arquivo_id: int = None):
    """
    Processa normalizações validadas e salva nas tabelas finais.
    """
    logger.info(f"🔄 Processando normalizações para empresa {empresa_id}")
    
    # Buscar normalizações validadas
    query = Normalizacao.query.filter_by(
        empresa_id=empresa_id,
        status="validado"
    )
    
    if arquivo_id:
        query = query.filter_by(arquivo_origem_id=arquivo_id)
    
    normalizacoes = query.all()
    
    if not normalizacoes:
        logger.info("ℹ️ Nenhuma normalização para processar")
        return {"vendas": 0, "recebimentos": 0}
    
    logger.info(f"📦 {len(normalizacoes)} normalizações para processar")
    
    # Separar por tipo
    vendas = []
    recebimentos = []
    
    for norm in normalizacoes:
        try:
            if norm.tipo_movimento == "venda":
                vendas.append(_converter_para_venda(norm))
            elif norm.tipo_movimento in ["recebimento", "pagamento"]:
                recebimentos.append(_converter_para_recebimento(norm))
            
            # Marcar como processado
            norm.status = "processado"
            
        except Exception as e:
            logger.error(f"❌ Erro ao processar normalizacao {norm.id}: {str(e)}")
            norm.status = "erro"
            norm.erro_mensagem = str(e)
    
    # Salvar nas tabelas finais
    stats_vendas = {"sucesso": 0}
    stats_recebimentos = {"sucesso": 0}
    
    if vendas:
        logger.info(f"💳 Salvando {len(vendas)} vendas")
        stats_vendas = salvar_vendas(vendas, empresa_id, arquivo_id)
    
    if recebimentos:
        logger.info(f"🏦 Salvando {len(recebimentos)} recebimentos")
        stats_recebimentos = salvar_recebimentos(recebimentos, empresa_id, arquivo_id)
    
    db.session.commit()
    
    logger.info(
        f"✅ Processamento concluído: "
        f"{stats_vendas.get('sucesso', 0)} vendas, "
        f"{stats_recebimentos.get('sucesso', 0)} recebimentos"
    )
    
    return {
        "vendas": stats_vendas,
        "recebimentos": stats_recebimentos
    }


def _converter_para_venda(norm: Normalizacao) -> dict:
    """Converte Normalizacao para formato de venda"""
    return {
        "adquirente": norm.adquirente_nome,
        "nsu": norm.nsu,
        "data_venda": norm.data_venda or norm.data_movimento,
        "valor_bruto": float(norm.valor_bruto),
        "valor_liquido": float(norm.valor_liquido) if norm.valor_liquido else None,
        "desconto": float(norm.valor_taxa) if norm.valor_taxa else None,
        "bandeira": norm.bandeira,
        "produto": norm.produto,
        "tipo_pagamento": norm.tipo_pagamento or "cartao",
        "observacoes": norm.descricao,
        "empresa_id": norm.empresa_id,
    }


def _converter_para_recebimento(norm: Normalizacao) -> dict:
    """Converte Normalizacao para formato de recebimento"""
    return {
        "data": norm.data_movimento,
        "valor": float(norm.valor_bruto),
        "descricao": norm.descricao,
        "nsu": norm.nsu,
        "tipo_pagamento": norm.tipo_pagamento,
        "categoria": norm.categoria,
        "empresa_id": norm.empresa_id,
    }
