# services/dashboard_service.py - Função gerar_detalhamento CORRIGIDA

from models import db, MovAdquirente, MovBanco, Adquirente
from sqlalchemy import func
from datetime import datetime
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)

def gerar_detalhamento(empresa_id, data_inicio=None, data_fim=None, adquirente_id=None, status=None, tipo_pagamento=None, page=1, per_page=50):
    """
    Gera detalhamento linha por linha das vendas.
    
    ✅ Suporta:
        - Filtros por data, adquirente, status_conciliacao, tipo_pagamento
        - Paginação para performance
        - JOIN correto para receber relacionados (via conciliação ou NSU)
    
    Returns:
        dict: {
            "total": int,
            "page": int,
            "per_page": int,
            "itens": [ {...}, ... ]
        }
    """
    
    try:
        # ✅ Query base para VENDAS (MovAdquirente)
        query_vendas = db.session.query(
            MovAdquirente.id.label('venda_id'),
            MovAdquirente.data_venda,
            MovAdquirente.nsu,
            MovAdquirente.autorizacao,
            Adquirente.nome.label('adquirente'),
            MovAdquirente.bandeira,
            MovAdquirente.produto,
            MovAdquirente.parcela,
            MovAdquirente.total_parcelas,
            MovAdquirente.valor_bruto,
            MovAdquirente.valor_liquido,
            MovAdquirente.valor_conciliado,
            MovAdquirente.status_conciliacao,
            MovAdquirente.tipo_pagamento,  # ✅ NOVO: incluir no select
            MovAdquirente.criado_em
        ).join(
            Adquirente, MovAdquirente.adquirente_id == Adquirente.id, isouter=True
        ).filter(
            MovAdquirente.empresa_id == empresa_id,
            MovAdquirente.ativo == True
        )
        
        # ✅ Aplicar filtros
        if data_inicio:
            query_vendas = query_vendas.filter(MovAdquirente.data_venda >= data_inicio)
        if data_fim:
            query_vendas = query_vendas.filter(MovAdquirente.data_venda <= data_fim)
        if adquirente_id:
            query_vendas = query_vendas.filter(MovAdquirente.adquirente_id == adquirente_id)
        if status:
            query_vendas = query_vendas.filter(MovAdquirente.status_conciliacao == status)
        if tipo_pagamento and tipo_pagamento != 'todos':  # ✅ NOVO: filtro por tipo de pagamento
            query_vendas = query_vendas.filter(MovAdquirente.tipo_pagamento == tipo_pagamento)
        
        # ✅ Contar total para paginação
        total = query_vendas.count()
        
        # ✅ Aplicar paginação
        query_vendas = query_vendas.order_by(
            MovAdquirente.data_venda.desc(),
            MovAdquirente.nsu.desc()
        ).offset((page - 1) * per_page).limit(per_page)
        
        vendas = query_vendas.all()
        
        # ✅ Para cada venda, buscar recebimentos relacionados (via conciliação ou NSU)
        itens = []
        for v in vendas:
            # Tentar encontrar recebimento conciliado (via tabela Conciliacao se existir)
            recebido = Decimal("0")
            data_recebimento = None
            banco_nome = None
            
            try:
                # Opção A: Via tabela Conciliacao (se existir no seu schema)
                from models import Conciliacao
                conc = Conciliacao.query.filter_by(
                    mov_adquirente_id=v.venda_id,
                    ativo=True
                ).first()
                if conc and conc.mov_banco_id:
                    from models import MovBanco
                    mov_banco = MovBanco.query.get(conc.mov_banco_id)
                    if mov_banco:
                        recebido = mov_banco.valor or Decimal("0")
                        data_recebimento = mov_banco.data_movimento
                        banco_nome = mov_banco.banco
            except:
                pass  # Se não houver tabela Conciliacao, tenta opção B
            
            # Opção B: Match por NSU/documento (fallback)
            if recebido == 0 and v.nsu:
                try:
                    from models import MovBanco
                    mov_banco = MovBanco.query.filter(
                        MovBanco.empresa_id == empresa_id,
                        MovBanco.documento == v.nsu,
                        MovBanco.conciliado == True
                    ).first()
                    if mov_banco:
                        recebido = mov_banco.valor or Decimal("0")
                        data_recebimento = mov_banco.data_movimento
                        banco_nome = mov_banco.banco
                except:
                    pass
            
            # Calcular diferença
            diferenca = (v.valor_bruto or Decimal("0")) - recebido
            
            itens.append({
                "id": v.venda_id,
                "data_venda": v.data_venda.strftime("%d/%m/%Y") if v.data_venda else "",
                "nsu": v.nsu or "",
                "autorizacao": v.autorizacao or "",
                "adquirente": v.adquirente or "Não identificada",
                "bandeira": v.bandeira or "",
                "produto": v.produto or "",
                "parcela": f"{v.parcela or 1}/{v.total_parcelas or 1}",
                "valor_bruto": str(v.valor_bruto or 0),
                "valor_liquido": str(v.valor_liquido or 0),
                "valor_recebido": str(recebido),
                "diferenca": str(diferenca),
                "status_conciliacao": v.status_conciliacao or "pendente",
                "tipo_pagamento": v.tipo_pagamento or "cartao",  # ✅ NOVO: incluir no output
                "data_recebimento": data_recebimento.strftime("%d/%m/%Y") if data_recebimento else "",
                "banco": banco_nome or "",
                "criado_em": v.criado_em.strftime("%d/%m/%Y %H:%M") if v.criado_em else ""
            })
        
        logger.info(f"✅ Detalhamento gerado: {len(itens)} itens, página {page}/{(total + per_page - 1) // per_page}")
        
        return {
            "total": total,
            "page": page,
            "per_page": per_page,
            "pages": (total + per_page - 1) // per_page,
            "itens": itens
        }
        
    except Exception as e:
        logger.error(f"❌ Erro ao gerar detalhamento: {str(e)}", exc_info=True)
        raise
