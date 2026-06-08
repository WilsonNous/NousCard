# services/concilia_detalhe.py (ou em dashboard_service.py)

from models import MovAdquirente, MovBanco, Conciliacao, Adquirente, db
from sqlalchemy.orm import joinedload, lazyload
from datetime import datetime
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)


def gerar_detalhamento(
    empresa_id,
    data_inicio=None,
    data_fim=None,
    adquirente_id=None,
    status=None,
    tipo_pagamento=None,
    page=1,
    per_page=50,
    incluir_recebimentos=True
):
    """
    Gera detalhamento linha por linha para conciliação.
    
    ✅ Features:
        - Paginação para performance
        - Filtros por data, adquirente, status, tipo_pagamento
        - Eager loading para evitar N+1 queries
        - Dados de recebimento conciliado (opcional)
        - Valores como Decimal/string para precisão monetária
    
    Returns:
        dict: {
            "total": int,
            "page": int,
            "per_page": int,
            "pages": int,
            "linhas": [ {...}, ... ]
        }
    """
    
    try:
        # ✅ Query base com eager loading para evitar N+1
        query = db.session.query(MovAdquirente).options(
            joinedload(MovAdquirente.adquirente),  # Carrega adquirente em 1 query
            lazyload('*')  # Não carrega outros relacionamentos desnecessários
        ).filter(
            MovAdquirente.empresa_id == empresa_id,
            MovAdquirente.ativo == True
        )
        
        # ✅ Aplicar filtros
        if data_inicio:
            query = query.filter(MovAdquirente.data_venda >= data_inicio)
        if data_fim:
            query = query.filter(MovAdquirente.data_venda <= data_fim)
        if adquirente_id:
            query = query.filter(MovAdquirente.adquirente_id == adquirente_id)
        if status and status != 'todos':
            query = query.filter(MovAdquirente.status_conciliacao == status)
        if tipo_pagamento and tipo_pagamento != 'todos':
            query = query.filter(MovAdquirente.tipo_pagamento == tipo_pagamento)
        
        # ✅ Contar total para paginação
        total = query.count()
        
        # ✅ Aplicar ordenação e paginação
        query = query.order_by(
            MovAdquirente.data_venda.desc(),
            MovAdquirente.nsu.desc()
        ).offset((page - 1) * per_page).limit(per_page)
        
        vendas = query.all()
        
        # ✅ Para cada venda, buscar dados de recebimento conciliado
        linhas = []
        for v in vendas:
            # Dados básicos da venda
            linha = {
                "id": v.id,
                "data_venda": v.data_venda.strftime("%d/%m/%Y") if v.data_venda else "-",
                "nsu": v.nsu or "-",
                "autorizacao": v.autorizacao or "-",
                "adquirente": v.adquirente.nome if v.adquirente else "-",
                "bandeira": v.bandeira or "-",
                "produto": v.produto or "-",
                "parcela": f"{v.parcela or 1}/{v.total_parcelas or 1}",
                "tipo_pagamento": v.tipo_pagamento or "cartao",
                # ✅ Valores como string para precisão monetária
                "valor_bruto": str(v.valor_bruto or 0),
                "valor_liquido": str(v.valor_liquido or 0),
                "valor_conciliado": str(v.valor_conciliado or 0),
                "valor_pendente": str(max(Decimal("0"), (v.valor_liquido or 0) - (v.valor_conciliado or 0))),
                "data_prevista": v.data_prevista_pagamento.strftime("%d/%m/%Y") if v.data_prevista_pagamento else "-",
                "status_conciliacao": v.status_conciliacao or "pendente",
                "criado_em": v.criado_em.strftime("%d/%m/%Y %H:%M") if v.criado_em else "-",
            }
            
            # ✅ Incluir dados de recebimento conciliado (se solicitado)
            if incluir_recebimentos:
                # Tentar encontrar via tabela Conciliacao
                conc = Conciliacao.query.filter_by(
                    mov_adquirente_id=v.id,
                    ativo=True
                ).first()
                
                if conc and conc.mov_banco_id:
                    mov_banco = MovBanco.query.get(conc.mov_banco_id)
                    if mov_banco:
                        linha.update({
                            "recebimento_id": mov_banco.id,
                            "data_recebimento": mov_banco.data_movimento.strftime("%d/%m/%Y") if mov_banco.data_movimento else "-",
                            "banco": mov_banco.banco or "-",
                            "documento": mov_banco.documento or "-",
                            "valor_recebido": str(mov_banco.valor or 0),
                            "diferenca": str((v.valor_liquido or 0) - (mov_banco.valor or 0)),
                        })
                    else:
                        linha.update({
                            "recebimento_id": None,
                            "data_recebimento": "-",
                            "banco": "-",
                            "documento": "-",
                            "valor_recebido": "0",
                            "diferenca": str(v.valor_liquido or 0),
                        })
                else:
                    # Sem conciliação registrada
                    linha.update({
                        "recebimento_id": None,
                        "data_recebimento": "-",
                        "banco": "-",
                        "documento": "-",
                        "valor_recebido": "0",
                        "diferenca": str(v.valor_liquido or 0),
                    })
            
            linhas.append(linha)
        
        logger.info(f"✅ Detalhamento gerado: {len(linhas)} itens, página {page}/{(total + per_page - 1) // per_page}")
        
        return {
            "total": total,
            "page": page,
            "per_page": per_page,
            "pages": (total + per_page - 1) // per_page,
            "linhas": linhas
        }
        
    except Exception as e:
        logger.error(f"❌ Erro ao gerar detalhamento: {str(e)}", exc_info=True)
        raise
