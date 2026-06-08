# services/dashboard_service.py
# ✅ VERSÃO FINAL: Suporte completo a tipo_pagamento (cartao/pix/boleto/outros)

from models import db, MovAdquirente, MovBanco, Adquirente
from sqlalchemy import func, and_
from datetime import datetime, timedelta
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)

def calcular_kpis(empresa_id, periodo='todos', data_inicio=None, data_fim=None, tipo_pagamento=None):
    """
    Calcula KPIs do dashboard com suporte a múltiplos tipos de pagamento.
    
    ✅ Suporta:
        - periodo: 'todos', 'semana', 'mes', 'ano', 'personalizado'
        - tipo_pagamento: None (todos), 'cartao', 'pix', 'boleto', 'outros'
    
    ✅ IMPORTANTE: 
        - MovBanco NÃO tem coluna 'ativo' → não filtramos por ela
        - MovAdquirente TEM coluna 'ativo' → filtramos sempre
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
        else:  # mes (padrão)
            inicio = hoje.replace(day=1)
            fim = hoje
        
        logger.info(f"🔍 Calcular KPIs: empresa={empresa_id}, periodo={periodo}, tipo_pagamento={tipo_pagamento}, inicio={inicio}, fim={fim}")
        
        # ✅ Query base para VENDAS (sempre filtra por empresa_id e ativo)
        query_vendas_base = db.session.query(func.sum(MovAdquirente.valor_bruto)).filter(
            MovAdquirente.empresa_id == empresa_id,
            MovAdquirente.ativo == True
        )
        
        # Aplicar filtro de data se necessário
        if inicio is not None:
            query_vendas_base = query_vendas_base.filter(MovAdquirente.data_venda >= inicio)
        if fim is not None:
            query_vendas_base = query_vendas_base.filter(MovAdquirente.data_venda <= fim)
        
        # Aplicar filtro de tipo_pagamento se especificado
        if tipo_pagamento and tipo_pagamento != 'todos':
            query_vendas_base = query_vendas_base.filter(MovAdquirente.tipo_pagamento == tipo_pagamento)
        
        # ✅ Total geral de vendas
        total_vendas = query_vendas_base.scalar()
        total_vendas = Decimal(str(total_vendas)) if total_vendas is not None else Decimal("0")
        
        # ✅ Totais por tipo de pagamento (sempre calcula, mesmo com filtro aplicado)
        query_tipos = db.session.query(
            MovAdquirente.tipo_pagamento,
            func.count().label('quantidade'),
            func.sum(MovAdquirente.valor_bruto).label('total')
        ).filter(
            MovAdquirente.empresa_id == empresa_id,
            MovAdquirente.ativo == True
        )
        if inicio is not None:
            query_tipos = query_tipos.filter(MovAdquirente.data_venda >= inicio)
        if fim is not None:
            query_tipos = query_tipos.filter(MovAdquirente.data_venda <= fim)
        
        tipos_raw = query_tipos.group_by(MovAdquirente.tipo_pagamento).all()
        tipos_pagamento = [{
            "tipo": t.tipo_pagamento or "outros",
            "quantidade": t.quantidade or 0,
            "total": str(t.total or 0)
        } for t in tipos_raw if t.tipo_pagamento]
        
        # ✅ Totais individuais por tipo (para acesso rápido no frontend)
        total_vendas_cartao = Decimal("0")
        total_vendas_pix = Decimal("0")
        total_vendas_boleto = Decimal("0")
        total_vendas_outros = Decimal("0")
        
        for t in tipos_pagamento:
            if t['tipo'] == 'cartao':
                total_vendas_cartao = Decimal(t['total'])
            elif t['tipo'] == 'pix':
                total_vendas_pix = Decimal(t['total'])
            elif t['tipo'] == 'boleto':
                total_vendas_boleto = Decimal(t['total'])
            else:
                total_vendas_outros = Decimal(t['total'])
        
        # ✅ RECEBIDOS: MovBanco (NÃO tem tipo_pagamento, NÃO tem coluna 'ativo')
        query_recebido = db.session.query(func.sum(MovBanco.valor)).filter(
            MovBanco.empresa_id == empresa_id,
            MovBanco.conciliado == True
        )
        if inicio is not None:
            query_recebido = query_recebido.filter(MovBanco.data_movimento >= inicio)
        if fim is not None:
            query_recebido = query_recebido.filter(MovBanco.data_movimento <= fim)
        
        total_recebido = query_recebido.scalar()
        total_recebido = Decimal(str(total_recebido)) if total_recebido is not None else Decimal("0")
        
        diferenca = total_vendas - total_recebido
        
        # ✅ Adquirentes (apenas para cartão, pois PIX/boleto não têm adquirente tradicional)
        # Se filtro de tipo_pagamento for aplicado e não for 'cartao', retorna lista vazia
        adquirentes = []
        if not tipo_pagamento or tipo_pagamento == 'todos' or tipo_pagamento == 'cartao':
            query_adq = db.session.query(
                Adquirente.nome,
                func.sum(MovAdquirente.valor_bruto).label('total_vendas'),
                func.sum(MovAdquirente.valor_liquido).label('total_liquido')
            ).join(
                MovAdquirente, Adquirente.id == MovAdquirente.adquirente_id
            ).filter(
                MovAdquirente.empresa_id == empresa_id,
                MovAdquirente.ativo == True,
                MovAdquirente.tipo_pagamento == 'cartao'  # ← Apenas cartão tem adquirente
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
            } for a in adquirentes_raw if a.nome]
        
        # ✅ Bandeiras (apenas para cartão)
        bandeiras = []
        if not tipo_pagamento or tipo_pagamento == 'todos' or tipo_pagamento == 'cartao':
            query_band = db.session.query(
                MovAdquirente.bandeira,
                func.count().label('quantidade'),
                func.sum(MovAdquirente.valor_bruto).label('total')
            ).filter(
                MovAdquirente.empresa_id == empresa_id,
                MovAdquirente.ativo == True,
                MovAdquirente.tipo_pagamento == 'cartao'  # ← Apenas cartão tem bandeira
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
            } for b in bandeiras_raw if b.bandeira]
        
        logger.info(f"✅ KPIs calculados: vendas={total_vendas}, pix={total_vendas_pix}, recebido={total_recebido}")
        
        return {
            "periodo": {
                "inicio": inicio.strftime("%d/%m/%Y") if inicio else "todos",
                "fim": fim.strftime("%d/%m/%Y") if fim else "todos"
            },
            # Filtro aplicado
            "tipo_pagamento_filtro": tipo_pagamento or "todos",
            # Totais gerais
            "total_vendas": str(total_vendas),
            "total_recebido": str(total_recebido),
            "diferenca": str(diferenca),
            # ✅ NOVOS: Detalhamento por tipo de pagamento
            "total_vendas_cartao": str(total_vendas_cartao),
            "total_vendas_pix": str(total_vendas_pix),
            "total_vendas_boleto": str(total_vendas_boleto),
            "total_vendas_outros": str(total_vendas_outros),
            "tipos_pagamento": tipos_pagamento,
            # Dados existentes (apenas para cartão)
            "adquirentes": adquirentes,
            "bandeiras": bandeiras
        }
        
    except Exception as e:
        logger.error(f"❌ Erro fatal em calcular_kpis: {str(e)}", exc_info=True)
        raise


def tem_dados_cadastrados(empresa_id):
    """Verifica se empresa já tem dados (ignora filtro de data)"""
    try:
        return MovAdquirente.query.filter_by(
            empresa_id=empresa_id,
            ativo=True
        ).count() > 0
    except Exception:
        return False


def calcular_resumo_rapido(empresa_id):
    """Resumo rápido para header (sem filtro de data, todos os tipos de pagamento)"""
    try:
        vendas_total = db.session.query(
            func.sum(MovAdquirente.valor_bruto)
        ).filter(
            MovAdquirente.empresa_id == empresa_id,
            MovAdquirente.ativo == True
        ).scalar()
        
        return {
            "vendas_total": str(Decimal(str(vendas_total)) if vendas_total is not None else 0),
            "atualizado_em": datetime.now().isoformat()
        }
    except Exception:
        return {"vendas_total": "0", "atualizado_em": datetime.now().isoformat()}
