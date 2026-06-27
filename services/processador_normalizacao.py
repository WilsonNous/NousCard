# services/processador_normalizacao.py
# Processa normalizações e salva nas tabelas finais

from models import db, Normalizacao
from services.importer_db_movimento import salvar_vendas, salvar_recebimentos
import logging

logger = logging.getLogger(__name__)

# ============================================================
# CATEGORIAS FINANCEIRAS
# ============================================================

CATEGORIAS_RECEITA = {
    "venda",
    "recebimento",
    "deposito",
    "pix_recebido",
    "credito",
    "estorno_credito",
    "transferencia_entrada"
}

CATEGORIAS_DESPESA = {
    "fornecedor",
    "salario",
    "folha",
    "imposto",
    "energia",
    "agua",
    "internet",
    "telefone",
    "combustivel",
    "alimentacao",
    "aluguel",
    "tarifa_bancaria",
    "tarifa",
    "pix_enviado",
    "ted",
    "doc",
    "boleto",
    "transferencia_saida",
    "saque",
    "despesa",
    "investimento"
}

# ============================================================
# NORMALIZAÇÃO FINANCEIRA
# ============================================================

def normalizar_valor_financeiro(valor, categoria):
    """
    Garante que receitas sejam POSITIVAS e despesas NEGATIVAS.
    
    Args:
        valor: Valor bruto (float ou string)
        categoria: Categoria da transação (string)
    
    Returns:
        float: Valor normalizado (+ para receita, - para despesa)
    """
    valor = abs(float(valor))
    categoria = (categoria or "").lower().strip()
    
    # Despesas → sempre negativo
    if categoria in CATEGORIAS_DESPESA:
        return -valor
    
    # Receitas → sempre positivo
    if categoria in CATEGORIAS_RECEITA:
        return valor
    
    # Categoria desconhecida → mantém o valor original
    return float(valor)


# ============================================================
# PROCESSAMENTO PRINCIPAL
# ============================================================

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


# ============================================================
# CONVERSORES
# ============================================================

def _converter_para_venda(norm: Normalizacao) -> dict:
    """Converte Normalizacao para formato de venda"""
    try:
        if not norm.valor_bruto or norm.valor_bruto <= 0:
            logger.warning(f"⚠️ Normalizacao {norm.id} sem valor_bruto válido")
            return None
        
        if not norm.data_movimento:
            logger.warning(f"⚠️ Normalizacao {norm.id} sem data_movimento")
            return None
        
        # ✅ Normalizar valor financeiro (vendas são receitas → positivo)
        valor_normalizado = normalizar_valor_financeiro(
            norm.valor_bruto,
            norm.categoria or "venda"
        )
        valor_liquido = normalizar_valor_financeiro(
            norm.valor_liquido if norm.valor_liquido else norm.valor_bruto,
            norm.categoria or "venda"
        )
        
        return {
            "adquirente": norm.adquirente_nome or "Flow",
            "nsu": norm.nsu,
            "data_venda": norm.data_venda or norm.data_movimento,
            "valor_bruto": valor_normalizado,
            "valor_liquido": valor_liquido,
            "desconto": float(norm.valor_taxa) if norm.valor_taxa else 0,
            "bandeira": norm.bandeira,
            "produto": norm.produto,
            "tipo_pagamento": norm.tipo_pagamento or "cartao",
            "observacoes": norm.descricao,
            "empresa_id": norm.empresa_id,
        }
    except Exception as e:
        logger.error(f"❌ Erro ao converter normalizacao {norm.id} para venda: {str(e)}", exc_info=True)
        return None


def _converter_para_recebimento(norm: Normalizacao) -> dict:
    """
    Converte Normalizacao para formato de recebimento.
    ✅ Aplica normalização financeira: receitas +, despesas -
    """
    try:
        if not norm.valor_bruto:
            logger.warning(f"⚠️ Normalizacao {norm.id} sem valor_bruto")
            return None
        
        # ✅ FALLBACK: Se não tem categoria, gerar agora
        categoria = norm.categoria
        if not categoria or categoria in ['outros', '']:
            from utils.parsers import categorizar_transacao
            trntype = 'DEBIT' if norm.valor_bruto < 0 else 'CREDIT'
            categoria = categorizar_transacao(
                descricao=norm.descricao or '',
                name=norm.estabelecimento or '',
                valor=norm.valor_bruto,
                trntype=trntype
            )
            logger.debug(f"🏷️ Categoria gerada para recebimento {norm.id}: {categoria}")
        
        # ✅ NORMALIZAÇÃO FINANCEIRA (CORREÇÃO PRINCIPAL)
        valor_normalizado = normalizar_valor_financeiro(
            norm.valor_bruto,
            categoria
        )
        
        logger.debug(
            f"💰 Normalização financeira: "
            f"valor_bruto={norm.valor_bruto}, "
            f"categoria={categoria}, "
            f"valor_normalizado={valor_normalizado}"
        )
        
        return {
            "data": norm.data_movimento,
            "valor": valor_normalizado,  # ✅ Valor normalizado
            "descricao": norm.descricao,
            "nsu": norm.nsu,
            "tipo_pagamento": norm.tipo_pagamento,
            "categoria": categoria,
            "empresa_id": norm.empresa_id,
        }
    except Exception as e:
        logger.error(f"❌ Erro ao converter normalizacao {norm.id} para recebimento: {str(e)}", exc_info=True)
        return None