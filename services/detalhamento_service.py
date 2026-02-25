from models import db, MovAdquirente, MovBanco, Adquirente
from sqlalchemy import func
from datetime import datetime
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)

def gerar_detalhamento(empresa_id, data_inicio=None, data_fim=None, adquirente_id=None, status=None):
    """Gera detalhamento linha por linha"""
    
    # Query base
    query = db.session.query(
        MovAdquirente.data_venda,
        Adquirente.nome.label('adquirente'),
        func.sum(MovAdquirente.valor_bruto).label('vendas'),
        func.sum(MovBanco.valor).label('recebido'),
        func.sum(MovAdquirente.valor_bruto - MovBanco.valor).label('diferenca'),
        MovAdquirente.status_conciliacao.label('status')
    ).join(
        Adquirente, MovAdquirente.adquirente_id == Adquirente.id
    ).outerjoin(
        MovBanco, MovAdquirente.id == MovBanco.id
    ).filter(
        MovAdquirente.empresa_id == empresa_id
    )
    
    # Filtros
    if data_inicio:
        query = query.filter(MovAdquirente.data_venda >= data_inicio)
    if data_fim:
        query = query.filter(MovAdquirente.data_venda <= data_fim)
    if adquirente_id:
        query = query.filter(MovAdquirente.adquirente_id == adquirente_id)
    if status:
        query = query.filter(MovAdquirente.status_conciliacao == status)
    
    # Agrupar por data e adquirente
    query = query.group_by(
        MovAdquirente.data_venda,
        Adquirente.nome,
        MovAdquirente.status_conciliacao
    ).order_by(
        MovAdquirente.data_venda.desc()
    )
    
    resultados = query.all()
    
    return [{
        "data": r.data_venda.strftime("%d/%m/%Y") if r.data_venda else "",
        "adquirente": r.adquirente,
        "vendas": str(r.vendas or 0),
        "recebido": str(r.recebido or 0),
        "diferenca": str(r.diferenca or 0),
        "status": r.status
    } for r in resultados]
