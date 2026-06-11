# routes/dashboard_routes.py
# API de Dashboard Financeiro Inteligente

from flask import Blueprint, jsonify, request, g
from models import db, MovBanco, MovAdquirente
from sqlalchemy import func, extract, and_
from datetime import datetime, timedelta
from decimal import Decimal

# ✅ CORRETO (nome diferente)
dashboard_api_bp = Blueprint('dashboard_api', __name__)


def get_periodo_datas(periodo):
    """Retorna data_inicio e data_fim baseado no período selecionado"""
    hoje = datetime.now().date()
    
    if periodo == 'atual':  # Este mês
        data_inicio = hoje.replace(day=1)
        data_fim = hoje
    elif periodo == 'anterior':  # Mês anterior
        if hoje.month == 1:
            data_inicio = hoje.replace(year=hoje.year-1, month=12, day=1)
            data_fim = hoje.replace(year=hoje.year-1, month=12, day=31)
        else:
            data_inicio = hoje.replace(month=hoje.month-1, day=1)
            data_fim = hoje.replace(month=hoje.month-1, day=31)
    elif periodo == 'todos':  # Últimos 3 meses
        data_fim = hoje
        data_inicio = hoje - timedelta(days=90)
    else:
        data_inicio = hoje.replace(day=1)
        data_fim = hoje
    
    return data_inicio, data_fim


def calcular_kpis_financeiros(empresa_id, data_inicio, data_fim):
    """
    Calcula todos os KPIs financeiros baseados em MovBanco.
    Retorna dicionário com todos os valores.
    """
    # Filtrar movimentos do período
    query_base = MovBanco.query.filter(
        MovBanco.empresa_id == empresa_id,
        MovBanco.data_movimento >= data_inicio,
        MovBanco.data_movimento <= data_fim,
        MovBanco.ativo == True
    )
    
    # Total de entradas (valores positivos)
    total_entradas = query_base.filter(MovBanco.valor > 0).with_entities(
        func.sum(MovBanco.valor)
    ).scalar() or Decimal('0')
    
    # Total de saídas (valores negativos - valor absoluto)
    total_saidas = query_base.filter(MovBanco.valor < 0).with_entities(
        func.sum(func.abs(MovBanco.valor))
    ).scalar() or Decimal('0')
    
    # Saldo do período
    saldo = total_entradas - total_saidas
    
    # Vendas no cartão (SIPAG/Adquirente)
    vendas_cartao = query_base.filter(
        MovBanco.categoria.in_(['vendas_cartao', 'vendas_mastercard', 'vendas_visa', 'vendas_maestro', 'vendas_visa_electron'])
    ).with_entities(
        func.sum(MovBanco.valor)
    ).scalar() or Decimal('0')
    
    # PIX Recebido
    pix_recebido = query_base.filter(
        MovBanco.categoria == 'pix_recebido'
    ).with_entities(
        func.sum(MovBanco.valor)
    ).scalar() or Decimal('0')
    
    # Transferências Recebidas
    transferencias_recebidas = query_base.filter(
        MovBanco.categoria == 'transferencia_recebida'
    ).with_entities(
        func.sum(MovBanco.valor)
    ).scalar() or Decimal('0')
    
    # Fornecedores (PIX emitido + boletos)
    fornecedores = query_base.filter(
        MovBanco.categoria.in_(['pix_fornecedores', 'boleto'])
    ).with_entities(
        func.sum(func.abs(MovBanco.valor))
    ).scalar() or Decimal('0')
    
    # Impostos e Tributos
    impostos = query_base.filter(
        MovBanco.categoria == 'tributos'
    ).with_entities(
        func.sum(func.abs(MovBanco.valor))
    ).scalar() or Decimal('0')
    
    # Outras despesas (tarifas, empréstimos, etc.)
    outras_despesas = query_base.filter(
        MovBanco.categoria.in_(['tarifa_bancaria', 'emprestimo', 'aplicacao_investimento', 'seguro', 'outras_despesas'])
    ).with_entities(
        func.sum(func.abs(MovBanco.valor))
    ).scalar() or Decimal('0')
    
    # Total de registros
    total_registros = query_base.count()
    
    return {
        'saldo': float(saldo),
        'entradas': float(total_entradas),
        'saidas': float(total_saidas),
        'vendas_cartao': float(vendas_cartao),
        'receitas': {
            'cartao': float(vendas_cartao),
            'pix': float(pix_recebido),
            'transferencias': float(transferencias_recebidas)
        },
        'despesas': {
            'fornecedores': float(fornecedores),
            'impostos': float(impostos),
            'outras': float(outras_despesas)
        },
        'total_registros': total_registros
    }


def gerar_insight_inteligente(kpis, periodo):
    """
    Gera insights automáticos baseados nos dados financeiros.
    """
    insights = []
    
    # Insight sobre vendas no cartão
    if kpis['vendas_cartao'] > 0:
        percentual_cartao = (kpis['vendas_cartao'] / kpis['entradas'] * 100) if kpis['entradas'] > 0 else 0
        if percentual_cartao > 30:
            insights.append(f"Você recebeu R$ {kpis['vendas_cartao']:,.2f} via maquininha este período ({percentual_cartao:.1f}% das receitas). Verifique se as taxas da adquirente estão competitivas!")
    
    # Insight sobre PIX
    if kpis['receitas']['pix'] > 0:
        insights.append(f"PIX representa {kpis['receitas']['pix']/kpis['entradas']*100:.1f}% das suas receitas - ótima alternativa às taxas de cartão!")
    
    # Insight sobre fornecedores recorrentes
    if kpis['despesas']['fornecedores'] > kpis['entradas'] * 0.5:
        insights.append(f"Atenção: {kpis['despesas']['fornecedores']/kpis['entradas']*100:.1f}% da receita vai para fornecedores. Revise contratos!")
    
    # Insight sobre saldo
    if kpis['saldo'] < 0:
        insights.append("⚠️ Fluxo de caixa negativo neste período. Considere revisar despesas ou acelerar recebimentos.")
    elif kpis['saldo'] > kpis['entradas'] * 0.2:
        insights.append(f"✅ Excelente gestão! Você manteve {kpis['saldo']/kpis['entradas']*100:.1f}% de margem positiva.")
    
    # Insight sobre impostos
    if kpis['despesas']['impostos'] > 0:
        insights.append(f"Você pagou R$ {kpis['despesas']['impostos']:,.2f} em impostos. Mantenha a regularidade fiscal!")
    
    return insights[0] if insights else "Continue acompanhando seu fluxo de caixa regularmente para tomar melhores decisões financeiras."


@dashboard_api_bp.route('/api/v1/dashboard/kpis', methods=['GET'])
def get_dashboard_kpis():
    """
    API principal do dashboard.
    Query params: periodo (atual, anterior, todos)
    """
    try:
        # Obter período
        periodo = request.args.get('periodo', 'atual')
        
        # Obter empresa do usuário logado
        if not hasattr(g, 'user') or not g.user:
            return jsonify({'error': 'Usuário não autenticado'}), 401
        
        empresa_id = g.user.empresa_id
        
        if not empresa_id:
            return jsonify({'error': 'Usuário sem empresa vinculada'}), 403
        
        # Calcular datas do período
        data_inicio, data_fim = get_periodo_datas(periodo)
        
        # Calcular KPIs
        kpis = calcular_kpis_financeiros(empresa_id, data_inicio, data_fim)
        
        # Gerar insight inteligente
        insight = gerar_insight_inteligente(kpis, periodo)
        
        # Formatar resposta
        response = {
            'ok': True,
            'periodo': {
                'inicio': data_inicio.isoformat(),
                'fim': data_fim.isoformat(),
                'tipo': periodo
            },
            'saldo': round(kpis['saldo'], 2),
            'entradas': round(kpis['entradas'], 2),
            'saidas': round(kpis['saidas'], 2),
            'vendas_cartao': round(kpis['vendas_cartao'], 2),
            'receitas': {
                'cartao': round(kpis['receitas']['cartao'], 2),
                'pix': round(kpis['receitas']['pix'], 2),
                'transferencias': round(kpis['receitas']['transferencias'], 2)
            },
            'despesas': {
                'fornecedores': round(kpis['despesas']['fornecedores'], 2),
                'impostos': round(kpis['despesas']['impostos'], 2),
                'outras': round(kpis['despesas']['outras'], 2)
            },
            'insight': insight,
            'total_registros': kpis['total_registros']
        }
        
        return jsonify(response), 200
        
    except Exception as e:
        import logging
        logging.error(f"Erro ao calcular KPIs: {str(e)}", exc_info=True)
        return jsonify({
            'ok': False,
            'error': 'Erro ao processar dados do dashboard',
            'details': str(e)
        }), 500


@dashboard_api_bp.route('/api/v1/dashboard/resumo-mensal', methods=['GET'])
def get_resumo_mensal():
    """
    API para gráfico de evolução mensal (últimos 6 meses).
    """
    try:
        if not hasattr(g, 'user') or not g.user:
            return jsonify({'error': 'Usuário não autenticado'}), 401
        
        empresa_id = g.user.empresa_id
        hoje = datetime.now().date()
        
        # Últimos 6 meses
        meses = []
        for i in range(5, -1, -1):
            if hoje.month - i <= 0:
                mes = hoje.month - i + 12
                ano = hoje.year - 1
            else:
                mes = hoje.month - i
                ano = hoje.year
            
            data_inicio = hoje.replace(year=ano, month=mes, day=1)
            if mes == 12:
                data_fim = hoje.replace(year=ano, month=12, day=31)
            else:
                data_fim = hoje.replace(year=ano, month=mes+1, day=1) - timedelta(days=1)
            
            # Calcular saldo do mês
            saldo = MovBanco.query.filter(
                MovBanco.empresa_id == empresa_id,
                MovBanco.data_movimento >= data_inicio,
                MovBanco.data_movimento <= data_fim
            ).with_entities(
                func.sum(MovBanco.valor)
            ).scalar() or Decimal('0')
            
            meses.append({
                'mes': f'{mes:02d}/{ano}',
                'saldo': float(saldo),
                'label': f'{mes:02d}/{str(ano)[-2:]}'
            })
        
        return jsonify({'ok': True, 'meses': meses}), 200
        
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500
