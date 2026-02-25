from flask import Blueprint, request, jsonify, g
from utils.auth_middleware import login_required
from services.conciliacao import executar_conciliacao
from models import db, MovAdquirente, MovBanco, LogAuditoria
from sqlalchemy.orm import joinedload
from sqlalchemy import func, case
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)

bp_conc = Blueprint("conciliacao_api", __name__, url_prefix="/api/v1/conciliacao")

# ============================================================
# 1️⃣ PROCESSAR CONCILIAÇÃO
# ============================================================
@bp_conc.route("/processar", methods=["POST"])
@login_required
def api_processar_conciliacao():
    empresa_id = g.user.empresa_id
    
    if not empresa_id:
        return jsonify({"status": "error", "message": "Usuário sem empresa vinculada"}), 400
    
    try:
        resultado = executar_conciliacao(empresa_id, usuario_id=g.user.id)
        
        # Log de auditoria
        log = LogAuditoria(
            usuario_id=g.user.id,
            empresa_id=empresa_id,
            acao="conciliacao_executada",
            detalhes=f"Conciliados: {resultado.get('conciliados', 0)}",
            ip=request.remote_addr,
            criado_em=datetime.now(timezone.utc)
        )
        db.session.add(log)
        db.session.commit()
        
        logger.info(f"Conciliação: empresa={empresa_id}, usuario={g.user.id}")
        
        return jsonify({
            "status": "success",
            "message": "Conciliação executada com sucesso",
            "resultado": resultado
        }), 200
        
    except TimeoutError:
        logger.warning(f"Timeout na conciliação: empresa={empresa_id}")
        return jsonify({
            "status": "error",
            "message": "Processamento demorou muito. Tente com menos dados."
        }), 408
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Erro na conciliação: empresa={empresa_id}, erro={str(e)}")
        return jsonify({
            "status": "error",
            "message": "Erro ao processar conciliação."
        }), 500

# ============================================================
# 2️⃣ STATUS GERAL (OTIMIZADO)
# ============================================================
@bp_conc.route("/status", methods=["GET"])
@login_required
def api_status_conciliacao():
    empresa_id = g.user.empresa_id
    
    # 1 query em vez de 5
    totais_query = db.session.query(
        func.sum(case((MovAdquirente.status_conciliacao == "conciliado", 1), else_=0)).label("conciliado"),
        func.sum(case((MovAdquirente.status_conciliacao == "parcial", 1), else_=0)).label("parcial"),
        func.sum(case((MovAdquirente.status_conciliacao == "pendente", 1), else_=0)).label("pendente"),
        func.sum(case((MovAdquirente.status_conciliacao == "nao_recebido", 1), else_=0)).label("nao_recebido")
    ).filter(MovAdquirente.empresa_id == empresa_id).first()
    
    creditos_sem_origem = MovBanco.query.filter(
        MovBanco.empresa_id == empresa_id,
        MovBanco.conciliado == False,
        MovBanco.valor > 0
    ).count()
    
    return jsonify({
        "status": "success",
        "totais": {
            "conciliado": totais_query.conciliado or 0,
            "parcial": totais_query.parcial or 0,
            "pendente": totais_query.pendente or 0,
            "nao_recebido": totais_query.nao_recebido or 0,
            "creditos_sem_origem": creditos_sem_origem
        }
    }), 200

# ============================================================
# 3️⃣ DETALHES (COM PAGINAÇÃO)
# ============================================================
@bp_conc.route("/detalhes", methods=["GET"])
@login_required
def api_detalhes_conciliacao():
    empresa_id = g.user.empresa_id
    
    # Paginação
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    status = request.args.get('status', None)
    
    # Limitar per_page máximo
    per_page = min(per_page, 100)
    
    # Query base com joinedload
    query = MovAdquirente.query.options(
        joinedload(MovAdquirente.adquirente)
    ).filter(MovAdquirente.empresa_id == empresa_id)
    
    if status:
        query = query.filter(MovAdquirente.status_conciliacao == status)
    
    # Ordenar por data (mais recente primeiro)
    query = query.order_by(MovAdquirente.data_venda.desc())
    
    # Paginar
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    
    def venda_json(v):
        return {
            "id": v.id,
            "data_venda": str(v.data_venda) if v.data_venda else None,
            "data_prevista": str(v.data_prevista_pagamento) if v.data_prevista_pagamento else None,
            "valor_bruto": str(v.valor_bruto),
            "valor_liquido": str(v.valor_liquido) if v.valor_liquido else "0",
            "status": v.status_conciliacao,
            "bandeira": v.bandeira,
            "adquirente": v.adquirente.nome if v.adquirente else None
        }
    
    return jsonify({
        "status": "success",
        "page": page,
        "per_page": per_page,
        "total": pagination.total,
        "pages": pagination.pages,
        "dados": [venda_json(v) for v in pagination.items]
    }), 200
