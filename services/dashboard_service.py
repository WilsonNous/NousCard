# services/dashboard_service.py - VERSÃO CORRIGIDA

from models import db, MovAdquirente, MovBanco, Adquirente
from sqlalchemy import func, or_
from datetime import datetime, timedelta
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)

def calcular_kpis(empresa_id, periodo='todos', data_inicio=None, data_fim=None):
    """
    Calcula KPIs do dashboard.
    
    ✅ periodos suportados:
        - 'todos': Mostra TODOS os dados (sem filtro de data) ← NOVO
        - 'personalizado': Filtra por data_inicio e data_fim
        - 'semana': Últimos 7 dias
        - 'mes': Mês atual (padrão antigo)
        - 'ano': Ano atual
    """
    
    hoje = datetime.now().date()
    
    # ✅ CORREÇÃO: Definir datas com suporte a 'todos'
    if periodo == 'todos':
        # Sem filtro de data - mostra tudo
        inicio = None
        fim = None
    elif periodo == 'personalizado' and data_inicio and data_fim:
        inicio = datetime.strptime(data_inicio, "%Y-%m-%d").date()
        fim = datetime.strptime(data_fim, "%Y-%m-%d").date()
    elif periodo == 'semana':
        inicio = hoje - timedelta(days=7)
        fim = hoje
    elif periodo == 'ano':
        inicio = hoje.replace(month=1, day=1)
        fim = hoje
    else:  # mes (padrão antigo)
        inicio = hoje.replace(day=1)
        fim = hoje
    
    # ✅ Função auxiliar para aplicar filtro de data (trata NULLs)
    def aplicar_filtro_data(query, campo_data, inicio, fim):
        """Aplica filtro de data opcional, tratando NULLs"""
        if inicio is None and fim is None:
            # Sem filtro - retorna query original
            return query
        if inicio and fim:
            # Filtro completo: inclui registros com data no período OU data NULL (opcional)
            return query.filter(
                or_(
                    campo_data.between(inicio, fim),
                    campo_data == None  # ← Incluir NULLs? Remova se não quiser
                )
            )
        if inicio:
            return query.filter(
                or_(
                    campo_data >= inicio,
                    campo_data == None
                )
            )
        if fim:
            return query.filter(
                or_(
                    campo_data <= fim,
                    campo_data == None
                )
            )
        return query
    
    # ✅ Total Vendas (com filtro opcional)
    query_vendas = db.session.query(
        func.sum(MovAdquirente.valor_bruto)
    ).filter(
        MovAdquirente.empresa_id == empresa_id,
        MovAdquirente.ativo == True  # ← Garantir que só conta ativos
    )
    query_vendas = aplicar_filtro_data(query_vendas, MovAdquirente.data_venda, inicio, fim)
    total_vendas = query_vendas.scalar() or Decimal("0")
    
    # ✅ Total Recebido (com filtro opcional)
    query_recebido = db.session.query(
        func.sum(MovBanco.valor)
    ).filter(
        MovBanco.empresa_id == empresa_id,
        MovBanco.conciliado == True,
        MovBanco.ativo == True
    )
    query_recebido = aplicar_filtro_data(query_recebido, MovBanco.data_movimento, inicio, fim)
    total_recebido = query_recebido.scalar() or Decimal("0")
    
    # ✅ Diferença
    diferenca = total_vendas - total_recebido
    
    # ✅ Totais por Adquirente (com filtro opcional)
    query_adq = db.session.query(
        Adquirente.nome,
        func.sum(MovAdquirente.valor_bruto).label('total_vendas'),
        func.sum(MovAdquirente.valor_liquido).label('total_liquido')
    ).join(
        MovAdquirente, Adquirente.id == MovAdquirente.adquirente_id
    ).filter(
        MovAdquirente.empresa_id == empresa_id,
        MovAdquirente.ativo == True
    )
    query_adq = aplicar_filtro_data(query_adq, MovAdquirente.data_venda, inicio, fim)
    adquirentes = query_adq.group_by(Adquirente.nome).all()
    
    # ✅ Vendas por Bandeira (com filtro opcional)
    query_band = db.session.query(
        MovAdquirente.bandeira,
        func.count().label('quantidade'),
        func.sum(MovAdquirente.valor_bruto).label('total')
    ).filter(
        MovAdquirente.empresa_id == empresa_id,
        MovAdquirente.ativo == True
    )
    query_band = aplicar_filtro_data(query_band, MovAdquirente.data_venda, inicio, fim)
    bandeiras = query_band.group_by(MovAdquirente.bandeira).all()
    
    # ✅ Formatar resposta
    return {
        "periodo": {
            "inicio": inicio.strftime("%d/%m/%Y") if inicio else "todos",
            "fim": fim.strftime("%d/%m/%Y") if fim else "todos"
        },
        "total_vendas": str(total_vendas),
        "total_recebido": str(total_recebido),
        "diferenca": str(diferenca),
        "adquirentes": [{
            "nome": a.nome or "Não identificada",
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
    """Verifica se empresa já tem dados (ignora filtro de data)"""
    from models import MovAdquirente
    return MovAdquirente.query.filter_by(
        empresa_id=empresa_id,
        ativo=True
    ).count() > 0

def calcular_resumo_rapido(empresa_id):
    """Resumo rápido para header (sem filtro de data para ser cacheável)"""
    # ✅ Sem filtro de data - mostra total acumulado
    vendas_total = db.session.query(
        func.sum(MovAdquirente.valor_bruto)
    ).filter(
        MovAdquirente.empresa_id == empresa_id,
        MovAdquirente.ativo == True
    ).scalar() or Decimal("0")
    
    return {
        "vendas_total": str(vendas_total),
        "atualizado_em": datetime.now().isoformat()
    }
