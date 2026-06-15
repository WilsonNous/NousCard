# services/categorizacao_service.py
# Serviço para refinamento manual de categorias

from models import db, Normalizacao
import logging

logger = logging.getLogger(__name__)


def refinar_categorias(empresa_id: int, regras_personalizadas: dict = None):
    """
    Aplica regras personalizadas de categorização para uma empresa.
    
    Args:
        empresa_id: ID da empresa
        regras_personalizadas: Dict com {palavra_chave: categoria}
    
    Returns:
        int: Número de registros atualizados
    """
    # Regras padrão (podem ser sobrescritas)
    regras = {
        # Exemplo de regras personalizadas por empresa
        # 'palavra-chave': 'categoria_destino'
    }
    
    if regras_personalizadas:
        regras.update(regras_personalizadas)
    
    if not regras:
        return 0
    
    atualizados = 0
    
    for palavra, categoria in regras.items():
        # Atualizar normalizações que contenham a palavra-chave
        resultados = Normalizacao.query.filter(
            Normalizacao.empresa_id == empresa_id,
            Normalizacao.descricao.ilike(f'%{palavra}%'),
            Normalizacao.categoria != categoria  # Só atualiza se for diferente
        ).all()
        
        for norm in resultados:
            norm.categoria = categoria
            norm.subcategoria = f"refinado_manual:{palavra}"
            atualizados += 1
        
        if resultados:
            logger.info(f"✅ Aplicada regra '{palavra}' → '{categoria}': {len(resultados)} registros")
    
    if atualizados > 0:
        db.session.commit()
        logger.info(f"🔄 {atualizados} categorias refinadas para empresa {empresa_id}")
    
    return atualizados


def sugerir_categorias(empresa_id: int, limite: int = 50):
    """
    Sugere categorias para transações não classificadas.
    
    Returns:
        list: Lista de sugestões {descricao, valor, sugestao}
    """
    # Buscar transações com categoria genérica
    nao_classificadas = Normalizacao.query.filter(
        Normalizacao.empresa_id == empresa_id,
        Normalizacao.categoria.in_(['outras_despesas', 'receitas_nao_classificadas']),
        Normalizacao.status == 'processado'
    ).order_by(Normalizacao.data_movimento.desc()).limit(limite).all()
    
    sugestoes = []
    
    for norm in nao_classificadas:
        # Analisar descrição para sugerir categoria
        texto = f"{norm.descricao or ''}".upper()
        
        sugestao = None
        
        # Lógica simples de sugestão
        if 'FORNECEDOR' in texto or 'COMPRA' in texto:
            sugestao = 'fornecedores_mercadoria'
        elif 'ENERGIA' in texto or 'LUZ' in texto or 'AGUA' in texto:
            sugestao = 'energia_agua_telecom'
        elif 'GOOGLE' in texto or 'FACEBOOK' in texto or 'ADS' in texto:
            sugestao = 'marketing_publicidade'
        elif 'ALUGUEL' in texto or 'CONDOMINIO' in texto:
            sugestao = 'aluguel_condominio'
        
        if sugestao and sugestao != norm.categoria:
            sugestoes.append({
                'id': norm.id,
                'descricao': norm.descricao[:100],
                'valor': float(norm.valor_bruto),
                'categoria_atual': norm.categoria,
                'sugestao': sugestao
            })
    
    return sugestoes
