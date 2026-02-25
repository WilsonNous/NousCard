from models import db, MovAdquirente, MovBanco, Adquirente
from sqlalchemy import func
from datetime import datetime, timedelta
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)

def calcular_kpis(empresa_id, periodo='mes', data_inicio=None, data_fim=None):
    """Calcula KPIs do dashboard"""
    
    # Definir período
    hoje = datetime.now().date()
    
    if periodo == 'personalizado' and data_inicio and data_fim:
        inicio = datetime.strptime(data_inicio, "%Y-%m-%d").date()
        fim = datetime.strptime(data_fim, "%Y-%m-%d").date()
    elif periodo == 'semana':
        inicio = hoje - timedelta(days=7)
        fim = hoje
    elif periodo == 'ano':
        inicio = hoje.replace(month=1, day=1)
        fim = hoje
    else:  # mes
        inicio = hoje.replace(day=1)
        fim = hoje
    
    # Total Vendas
    total_vendas = db.session.query(
        func.sum(MovAdquirente.valor_bruto)
    ).filter(
        MovAdquirente.empresa_id == empresa_id,
        MovAdquirente.data_venda >= inicio,
        MovAdquirente.data_venda <= fim
    ).scalar() or Decimal("0")
    
    # Total Recebido
    total_recebido = db.session.query(
        func.sum(MovBanco.valor)
    ).filter(
        MovBanco.empresa_id == empresa_id,
        MovBanco.data_movimento >= inicio,
        MovBanco.data_movimento <= fim,
        MovBanco.conciliado == True
    ).scalar() or Decimal("0")
    
    # Diferença
    diferenca = total_vendas - total_recebido
    
    # Totais por Adquirente
    adquirentes = db.session.query(
        Adquirente.nome,
        func.sum(MovAdquirente.valor_bruto).label('total_vendas'),
        func.sum(MovAdquirente.valor_liquido).label('total_liquido')
    ).join(
        MovAdquirente, Adquirente.id == MovAdquirente.adquirente_id
    ).filter(
        MovAdquirente.empresa_id == empresa_id,
        MovAdquirente.data_venda >= inicio
    ).group_by(Adquirente.nome).all()
    
    # Vendas por Bandeira
    bandeiras = db.session.query(
        MovAdquirente.bandeira,
        func.count().label('quantidade'),
        func.sum(MovAdquirente.valor_bruto).label('total')
    ).filter(
        MovAdquirente.empresa_id == empresa_id,
        MovAdquirente.data_venda >= inicio
    ).group_by(MovAdquirente.bandeira).all()
    
    return {
        "periodo": {
            "inicio": inicio.strftime("%d/%m/%Y"),
            "fim": fim.strftime("%d/%m/%Y")
        },
        "total_vendas": str(total_vendas),
        "total_recebido": str(total_recebido),
        "diferenca": str(diferenca),
        "adquirentes": [{
            "nome": a.nome,
            "total_vendas": str(a.total_vendas or 0),
            "total_liquido": str(a.total_liquido or 0)
        } for a in adquirentes],
        "bandeiras": [{
            "bandeira": b.bandeira or "Não identificada",
            "quantidade": b.quantidade,
            "total": str(b.total or 0)
        } for b in bandeiras]
    }

def tem_dados_cadastrados(empresa_id):
    """Verifica se empresa já tem dados"""
    from models import MovAdquirente
    return MovAdquirente.query.filter_by(empresa_id=empresa_id).count() > 0

def calcular_resumo_rapido(empresa_id):
    """Resumo rápido para header (cacheável)"""
    hoje = datetime.now().date()
    inicio_mes = hoje.replace(day=1)
    
    vendas_mes = db.session.query(
        func.sum(MovAdquirente.valor_bruto)
    ).filter(
        MovAdquirente.empresa_id == empresa_id,
        MovAdquirente.data_venda >= inicio_mes
    ).scalar() or Decimal("0")
    
    return {
        "vendas_mes": str(vendas_mes),
        "atualizado_em": datetime.now().isoformat()
    }
