# services/dashboard_service.py - VERSÃO CORRIGIDA

from models import db, MovAdquirente, MovBanco, Adquirente
from sqlalchemy import func, and_
from datetime import datetime, timedelta
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)

def calcular_kpis(empresa_id, periodo='todos', data_inicio=None, data_fim=None):
    """
    Calcula KPIs do dashboard.
    
    ✅ Filtra por 'ativo' apenas em tabelas que têm essa coluna.
    """
    
    try:
        hoje = datetime.now().date()
        
        # Definir datas com suporte a 'todos'
        if periodo == 'todos':
            inicio = None
            fim = None
        elif periodo == 'personalizado' and data_inicio and data_fim:
            try:
                inicio = datetime.strptime(data_inicio, "%Y-%m-%d").date()
                fim = datetime.strptime(data_fim, "%Y-%m-%d").date()
            except ValueError as e:
                logger.error(f"❌ Data inválida: {e}")
                raise ValueError("Formato de data inválido. Use YYYY-MM-DD.")
        elif periodo == 'semana':
            inicio = hoje - timedelta(days=7)
            fim = hoje
        elif periodo == 'ano':
            inicio = hoje.replace(month=1, day=1)
            fim = hoje
        else:  # mes
            inicio = hoje.replace(day=1)
            fim = hoje
        
        logger.info(f"🔍 Calcular KPIs: empresa={empresa_id}, periodo={periodo}, inicio={inicio}, fim={fim}")
        
        # ✅ Query para VENDAS (MovAdquirente TEM coluna 'ativo')
        query_vendas = db.session.query(func.sum(MovAdquirente.valor_bruto)).filter(
            MovAdquirente.empresa_id == empresa_id,
            MovAdquirente.ativo == True  # ← MovAdquirente tem 'ativo'
        )
        
        # Aplicar filtro de data se necessário
        if inicio is not None:
            query_vendas = query_vendas.filter(MovAdquirente.data_venda >= inicio)
        if fim is not None:
            query_vendas = query_vendas.filter(MovAdquirente.data_venda <= fim)
        
        total_vendas = query_vendas.scalar()
        total_vendas = Decimal(str(total_vendas)) if total_vendas is not None else Decimal("0")
        
        # ✅ Query para RECEBIDOS (MovBanco NÃO tem coluna 'ativo' - remover filtro!)
        query_recebido = db.session.query(func.sum(MovBanco.valor)).filter(
            MovBanco.empresa_id == empresa_id,
            MovBanco.conciliado == True
            # ← REMOVIDO: MovBanco.ativo == True (não existe!)
        )
        
        # Aplicar filtro de data se necessário
        if inicio is not None:
            query_recebido = query_recebido.filter(MovBanco.data_movimento >= inicio)
        if fim is not None:
            query_recebido = query_recebido.filter(MovBanco.data_movimento <= fim)
        
        total_recebido = query_recebido.scalar()
        total_recebido = Decimal(str(total_recebido)) if total_recebido is not None else Decimal("0")
        
        diferenca = total_vendas - total_recebido
        
        # ✅ Adquirentes (com JOIN seguro)
        query_adq = db.session.query(
            Adquirente.nome,
            func.sum(MovAdquirente.valor_bruto).label('total_vendas'),
            func.sum(MovAdquirente.valor_liquido).label('total_liquido')
        ).join(
            MovAdquirente, Adquirente.id == MovAdquirente.adquirente_id
        ).filter(
            MovAdquirente.empresa_id == empresa_id,
            MovAdquirente.ativo == True  # ← MovAdquirente tem 'ativo'
        )
        
        if inicio is not None:
            query_adq = query_adq.filter(MovAdquirente.data_venda >= inicio)
        if fim is not None:
            query_adq = query_adq.filter(MovAdquirente.data_venda <= fim)
        
        adquirentes_raw = query_adq.group_by(Adquirente.nome).all()
        
        adquirentes = [{
            "nome": a.nome or "Não identificada",
            "total_vendas": str(a.total_vendas or 0),
            "total_liquido": str(a.total_liquido or 0)
        } for a in adquirentes_raw if a.nome]  # Filtra None
        
        # ✅ Bandeiras
        query_band = db.session.query(
            MovAdquirente.bandeira,
            func.count().label('quantidade'),
            func.sum(MovAdquirente.valor_bruto).label('total')
        ).filter(
            MovAdquirente.empresa_id == empresa_id,
            MovAdquirente.ativo == True  # ← MovAdquirente tem 'ativo'
        )
        
        if inicio is not None:
            query_band = query_band.filter(MovAdquirente.data_venda >= inicio)
        if fim is not None:
            query_band = query_band.filter(MovAdquirente.data_venda <= fim)
        
        bandeiras_raw = query_band.group_by(MovAdquirente.bandeira).all()
        
        bandeiras = [{
            "bandeira": b.bandeira or "Não identificada",
            "quantidade": b.quantidade or 0,
            "total": str(b.total or 0)
        } for b in bandeiras_raw if b.bandeira]  # Filtra None
        
        logger.info(f"✅ KPIs calculados: vendas={total_vendas}, recebido={total_recebido}")
        
        return {
            "periodo": {
                "inicio": inicio.strftime("%d/%m/%Y") if inicio else "todos",
                "fim": fim.strftime("%d/%m/%Y") if fim else "todos"
            },
            "total_vendas": str(total_vendas),
            "total_recebido": str(total_recebido),
            "diferenca": str(diferenca),
            "adquirentes": adquirentes,
            "bandeiras": bandeiras
        }
        
    except Exception as e:
        logger.error(f"❌ Erro fatal em calcular_kpis: {str(e)}", exc_info=True)
        raise


def tem_dados_cadastrados(empresa_id):
    """Verifica se empresa já tem dados"""
    try:
        return MovAdquirente.query.filter_by(
            empresa_id=empresa_id,
            ativo=True  # ← MovAdquirente tem 'ativo'
        ).count() > 0
    except Exception:
        return False


def calcular_resumo_rapido(empresa_id):
    """Resumo rápido para header"""
    try:
        vendas_total = db.session.query(
            func.sum(MovAdquirente.valor_bruto)
        ).filter(
            MovAdquirente.empresa_id == empresa_id,
            MovAdquirente.ativo == True  # ← MovAdquirente tem 'ativo'
        ).scalar()
        
        return {
            "vendas_total": str(Decimal(str(vendas_total)) if vendas_total is not None else 0),
            "atualizado_em": datetime.now().isoformat()
        }
    except Exception:
        return {
            "vendas_total": "0",
            "atualizado_em": datetime.now().isoformat()
        }
