# routes/conciliacao_api.py - VERSÃO CORRIGIDA E SEGURA

from flask import Blueprint, request, jsonify, g
from utils.auth_middleware import login_required
from services.concilia import executar_conciliacao  # ✅ CORREÇÃO: importar de concilia.py
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)

# ✅ Blueprint COM prefixo definido aqui (evita confusão no __init__.py)
bp_conc = Blueprint("conciliacao_api", __name__, url_prefix="/api/v1/conciliacao")

# ============================================================
# 1️⃣ EXECUTAR CONCILIAÇÃO (CORRIGIDO)
# ============================================================
@bp_conc.route("/executar", methods=["POST"])  # ✅ POST para operação que altera dados
@login_required  # ✅ Somente usuários autenticados
def api_executar_conciliacao():
    """
    Executa conciliação automática para a empresa do usuário.
    
    ✅ Requer:
        - Usuário autenticado (@login_required)
        - Método POST
        - empresa_id vem de g.user.empresa_id (não da query string)
    
    ✅ Opcional no JSON:
        - tipo_pagamento: 'pix', 'cartao', 'boleto', ou null para todos
    """
    
    # ✅ Obter empresa_id do contexto do usuário (mais seguro que query string)
    empresa_id = g.user.empresa_id if hasattr(g, 'user') and g.user else None
    
    if not empresa_id:
        logger.warning("Tentativa de conciliação sem empresa vinculada")
        return jsonify({
            "status": "error",
            "message": "Usuário sem empresa vinculada"
        }), 400
    
    # ✅ Obter parâmetros opcionais do JSON body
    data = request.get_json(silent=True) or {}
    tipo_pagamento = data.get('tipo_pagamento')  # Filtrar por tipo de pagamento
    
    try:
        # ✅ Executar conciliação com contexto completo
        resultado = executar_conciliacao(
            empresa_id=empresa_id,
            usuario_id=g.user.id,  # ✅ Passar usuário para auditoria
            tipo_pagamento=tipo_pagamento  # ✅ Suporte a filtro por tipo
        )
        
        logger.info(f"✅ Conciliação executada: empresa={empresa_id}, usuario={g.user.id}, tipo={tipo_pagamento or 'todos'}")
        
        return jsonify({
            "status": "success",
            "message": "Conciliação executada com sucesso",
            "resultado": resultado,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }), 200
        
    except TimeoutError:
        logger.warning(f"⏱️ Timeout na conciliação: empresa={empresa_id}")
        return jsonify({
            "status": "error",
            "message": "Processamento demorou muito. Tente com menos dados ou um período menor."
        }), 408
        
    except Exception as e:
        logger.error(f"❌ Erro na conciliação: empresa={empresa_id}, erro={str(e)}", exc_info=True)
        return jsonify({
            "status": "error",
            "message": "Erro ao processar conciliação. Tente novamente."
        }), 500


# ============================================================
# 2️⃣ STATUS DA CONCILIAÇÃO (NOVO - ÚTIL PARA FRONTEND)
# ============================================================
@bp_conc.route("/status", methods=["GET"])
@login_required
def api_status_conciliacao():
    """
    Retorna status resumido da conciliação para a empresa.
    Útil para dashboard mostrar contadores sem carregar todos os detalhes.
    """
    from models import MovAdquirente, MovBanco, db
    from sqlalchemy import func, case
    
    empresa_id = g.user.empresa_id
    
    if not empresa_id:
        return jsonify({"status": "error", "message": "Empresa não encontrada"}), 400
    
    try:
        # Contar vendas por status em 1 query otimizada
        totais = db.session.query(
            func.sum(case((MovAdquirente.status_conciliacao == "conciliado", 1), else_=0)).label("conciliado"),
            func.sum(case((MovAdquirente.status_conciliacao == "parcial", 1), else_=0)).label("parcial"),
            func.sum(case((MovAdquirente.status_conciliacao == "pendente", 1), else_=0)).label("pendente")
        ).filter(
            MovAdquirente.empresa_id == empresa_id,
            MovAdquirente.ativo == True
        ).first()
        
        # Contar recebimentos não conciliados
        creditos_sem_origem = MovBanco.query.filter(
            MovBanco.empresa_id == empresa_id,
            MovBanco.conciliado == False,
            MovBanco.valor > 0
        ).count()
        
        return jsonify({
            "status": "success",
            "totais": {
                "conciliado": totais.conciliado or 0,
                "parcial": totais.parcial or 0,
                "pendente": totais.pendente or 0,
                "creditos_sem_origem": creditos_sem_origem
            },
            "timestamp": datetime.now(timezone.utc).isoformat()
        }), 200
        
    except Exception as e:
        logger.error(f"Erro ao buscar status: {str(e)}")
        return jsonify({
            "status": "error",
            "message": "Erro ao carregar status"
        }), 500


# ============================================================
# 3️⃣ DETALHES DA CONCILIAÇÃO (NOVO - COM PAGINAÇÃO)
# ============================================================
@bp_conc.route("/detalhes", methods=["GET"])
@login_required
def api_detalhes_conciliacao():
    """
    Retorna detalhes das vendas para conciliação com paginação.
    
    ✅ Query params suportados:
        - page: número da página (default: 1)
        - per_page: itens por página (default: 50, max: 100)
        - status: filtrar por 'pendente', 'parcial', 'conciliado'
        - tipo_pagamento: filtrar por 'pix', 'cartao', 'boleto'
    """
    from models import MovAdquirente, db
    from sqlalchemy.orm import joinedload
    
    empresa_id = g.user.empresa_id
    
    if not empresa_id:
        return jsonify({"status": "error", "message": "Empresa não encontrada"}), 400
    
    # Parâmetros de paginação e filtro
    page = max(1, request.args.get('page', 1, type=int))
    per_page = min(request.args.get('per_page', 50, type=int), 100)  # Limitar a 100
    status = request.args.get('status')
    tipo_pagamento = request.args.get('tipo_pagamento')
    
    try:
        # Query base com eager loading para evitar N+1
        query = MovAdquirente.query.options(
            joinedload(MovAdquirente.adquirente)
        ).filter(
            MovAdquirente.empresa_id == empresa_id,
            MovAdquirente.ativo == True
        )
        
        # Aplicar filtros
        if status and status != 'todos':
            query = query.filter(MovAdquirente.status_conciliacao == status)
        if tipo_pagamento and tipo_pagamento != 'todos':
            query = query.filter(MovAdquirente.tipo_pagamento == tipo_pagamento)
        
        # Ordenar e paginar
        query = query.order_by(MovAdquirente.data_venda.desc())
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        
        # Serializar resultados
        def venda_to_dict(v):
            return {
                "id": v.id,
                "data_venda": v.data_venda.strftime("%d/%m/%Y") if v.data_venda else None,
                "nsu": v.nsu,
                "adquirente": v.adquirente.nome if v.adquirente else None,
                "bandeira": v.bandeira,
                "produto": v.produto,
                "parcela": f"{v.parcela or 1}/{v.total_parcelas or 1}",
                "tipo_pagamento": v.tipo_pagamento or "cartao",
                "valor_bruto": str(v.valor_bruto or 0),
                "valor_liquido": str(v.valor_liquido or 0),
                "valor_conciliado": str(v.valor_conciliado or 0),
                "status": v.status_conciliacao
            }
        
        return jsonify({
            "status": "success",
            "page": page,
            "per_page": per_page,
            "total": pagination.total,
            "pages": pagination.pages,
            "dados": [venda_to_dict(v) for v in pagination.items],
            "timestamp": datetime.now(timezone.utc).isoformat()
        }), 200
        
    except Exception as e:
        logger.error(f"Erro ao buscar detalhes: {str(e)}")
        return jsonify({
            "status": "error",
            "message": "Erro ao carregar detalhes"
        }), 500
