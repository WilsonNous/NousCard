#!/usr/bin/env python3
# scripts/normalizar_categorias.py
# Script para normalizar categorias de despesas em todos os registros processados

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from models import db, Normalizacao, MovBanco, MovAdquirente
from sqlalchemy import or_, and_
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================================
# MAPEAMENTO DE CATEGORIAS ANTIGAS → NOVAS (PADRONIZADAS)
# ============================================================
MAPEAMENTO_CATEGORIAS = {
    # Transporte/Combustível
    'transporte_combustivel': 'transporte_combustivel',  # já correto
    'combustivel': 'transporte_combustivel',
    'posto': 'transporte_combustivel',
    'gasolina': 'transporte_combustivel',
    'uber': 'transporte_combustivel',
    '99': 'transporte_combustivel',
    'taxi': 'transporte_combustivel',
    'estacionamento': 'transporte_combustivel',
    'pedagio': 'transporte_combustivel',
    'frete': 'transporte_combustivel',
    
    # Transferências enviadas → Fornecedores ou Outras
    'transferencia_enviada_outros': 'fornecedores_servicos',  # padrão
    'pix_emitido': 'fornecedores_servicos',
    'pix_fornecedores': 'fornecedores_servicos',
    
    # Energia/Água/Telecom
    'energia_agua_telecom': 'energia_agua_telecom',  # já correto
    'energia': 'energia_agua_telecom',
    'agua': 'energia_agua_telecom',
    'esgoto': 'energia_agua_telecom',
    'telefone': 'energia_agua_telecom',
    'celular': 'energia_agua_telecom',
    'internet': 'energia_agua_telecom',
    'netflix': 'energia_agua_telecom',  # assinatura digital
    'claro': 'energia_agua_telecom',
    'vivo': 'energia_agua_telecom',
    
    # Impostos
    'impostos_tributos': 'impostos_tributos',  # já correto
    'tributos': 'impostos_tributos',
    'das': 'impostos_tributos',
    'darf': 'impostos_tributos',
    'simples': 'impostos_tributos',
    'rfb': 'impostos_tributos',
    'iptu': 'impostos_tributos',
    'iss': 'impostos_tributos',
    
    # Tarifas bancárias
    'tarifas_bancarias': 'tarifas_bancarias',  # já correto
    'tarifa_bancaria': 'tarifas_bancarias',
    'tarifa': 'tarifas_bancarias',
    'manutencao': 'tarifas_bancarias',
    'pacote': 'tarifas_bancarias',
    'ted': 'tarifas_bancarias',
    'doc': 'tarifas_bancarias',
    'iof': 'tarifas_bancarias',
    
    # Outras despesas → tentar classificar por descrição
    'outras_despesas': 'outras_despesas',  # fallback
}

# Palavras-chave para classificar "outras_despesas" automaticamente
PALAVRAS_CHAVE_DESPESA = {
    'alimentacao': 'outras_despesas',
    'restaurante': 'outras_despesas',
    'lanches': 'outras_despesas',
    'mercado': 'fornecedores_mercadoria',
    'compra': 'fornecedores_mercadoria',
    'estoque': 'fornecedores_mercadoria',
    'material': 'fornecedores_mercadoria',
    'equipamento': 'equipamentos_manutencao',
    'manutencao': 'equipamentos_manutencao',
    'reparo': 'equipamentos_manutencao',
    'software': 'fornecedores_servicos',
    'assinatura': 'fornecedores_servicos',
    'hospedagem': 'fornecedores_servicos',
    'dominio': 'fornecedores_servicos',
    'marketing': 'marketing_publicidade',
    'anuncio': 'marketing_publicidade',
    'google': 'marketing_publicidade',
    'facebook': 'marketing_publicidade',
    'instagram': 'marketing_publicidade',
    'salario': 'salarios_encargos',
    'pro-labore': 'salarios_encargos',
    'inss': 'salarios_encargos',
    'fgts': 'salarios_encargos',
    'aluguel': 'aluguel_condominio',
    'condominio': 'aluguel_condominio',
    'iptu': 'aluguel_condominio',
    'seguro': 'seguros',
    'plano saude': 'saude_bem_estar',
    'medico': 'saude_bem_estar',
    'farmacia': 'saude_bem_estar',
    'viagem': 'viagens_hospedagem',
    'hotel': 'viagens_hospedagem',
    'passagem': 'viagens_hospedagem',
}


def normalizar_categoria(categoria_atual: str, descricao: str = None) -> str:
    """
    Normaliza uma categoria baseada no mapeamento e palavras-chave.
    """
    # 1. Tentar mapeamento direto
    if categoria_atual in MAPEAMENTO_CATEGORIAS:
        return MAPEAMENTO_CATEGORIAS[categoria_atual]
    
    # 2. Se for 'outras_despesas', tentar classificar por descrição
    if categoria_atual == 'outras_despesas' and descricao:
        descricao_lower = descricao.lower()
        for palavra, categoria in PALAVRAS_CHAVE_DESPESA.items():
            if palavra in descricao_lower:
                return categoria
    
    # 3. Fallback: manter categoria original
    return categoria_atual


def processar_tabela(tabela, campo_categoria, campo_descricao, campo_valor, campo_data, empresa_id=None, dry_run=True):
    """
    Processa uma tabela para normalizar categorias.
    
    Args:
        tabela: Modelo SQLAlchemy (Normalizacao, MovBanco, etc.)
        campo_categoria: Nome do campo de categoria
        campo_descricao: Nome do campo de descrição (para fallback)
        campo_valor: Nome do campo de valor
        campo_data: Nome do campo de data
        empresa_id: Filtrar por empresa (None = todas)
        dry_run: Se True, só mostra o que seria alterado
    """
    query = tabela.query
    
    if empresa_id:
        query = query.filter(tabela.empresa_id == empresa_id)
    
    # Filtrar apenas despesas (valor negativo ou categoria de despesa)
    query = query.filter(
        or_(
            getattr(tabela, campo_valor) < 0,
            getattr(tabela, campo_categoria).in_([
                'pix_emitido', 'transferencia_enviada_outros', 'outras_despesas',
                'transporte_combustivel', 'energia_agua_telecom', 'tarifas_bancarias'
            ])
        )
    )
    
    registros = query.all()
    atualizados = 0
    
    for reg in registros:
        categoria_atual = getattr(reg, campo_categoria)
        descricao = getattr(reg, campo_descricao, None) if campo_descricao else None
        
        nova_categoria = normalizar_categoria(categoria_atual, descricao)
        
        if nova_categoria != categoria_atual:
            atualizados += 1
            if dry_run:
                logger.info(f"🔄 [{tabela.__name__}] ID={reg.id}: '{categoria_atual}' → '{nova_categoria}'")
            else:
                setattr(reg, campo_categoria, nova_categoria)
    
    if not dry_run and atualizados > 0:
        db.session.commit()
        logger.info(f"✅ {atualizados} categorias atualizadas em {tabela.__name__}")
    
    return atualizados


def main():
    """Executa a normalização de categorias"""
    app = create_app()
    
    with app.app_context():
        dry_run = '--execute' not in sys.argv
        
        if dry_run:
            logger.info("🔍 MODO DRY-RUN: Mostrando alterações sem salvar")
            logger.info("💡 Use 'python scripts/normalizar_categorias.py --execute' para aplicar")
        else:
            logger.info("⚠️ MODO EXECUÇÃO: Alterações serão SALVAS no banco")
            confirm = input("Confirma a execução? (sim/N): ").strip().lower()
            if confirm != 'sim':
                logger.info("❌ Cancelado pelo usuário")
                return
        
        total_atualizados = 0
        
        # 1. Normalizar em tous_normalizacao (prioridade)
        logger.info("\n📋 Processando tous_normalizacao...")
        total_atualizados += processar_tabela(
            Normalizacao,
            campo_categoria='categoria',
            campo_descricao='descricao',
            campo_valor='valor_bruto',
            campo_data='data_movimento',
            dry_run=dry_run
        )
        
        # 2. Normalizar em MovBanco
        logger.info("\n📋 Processando MovBanco...")
        total_atualizados += processar_tabela(
            MovBanco,
            campo_categoria='categoria',
            campo_descricao='descricao',
            campo_valor='valor',
            campo_data='data_movimento',
            dry_run=dry_run
        )
        
        # 3. Normalizar em MovAdquirente (se houver despesas)
        logger.info("\n📋 Processando MovAdquirente...")
        total_atualizados += processar_tabela(
            MovAdquirente,
            campo_categoria='categoria',
            campo_descricao='observacoes',
            campo_valor='valor_bruto',
            campo_data='data_venda',
            dry_run=dry_run
        )
        
        logger.info(f"\n{'='*60}")
        if dry_run:
            logger.info(f"📊 TOTAL DE ALTERAÇÕES IDENTIFICADAS: {total_atualizados}")
            logger.info("💡 Execute com --execute para aplicar as mudanças")
        else:
            logger.info(f"✅ TOTAL DE CATEGORIAS NORMALIZADAS: {total_atualizados}")
        logger.info(f"{'='*60}")


if __name__ == '__main__':
    main()
