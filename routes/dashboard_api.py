from flask import Blueprint, jsonify, g, request
from utils.auth_middleware import login_required, empresa_required
from services.dashboard_service import calcular_kpis
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)

dashboard_api = Blueprint("dashboard_api", __name__, url_prefix="/api/v1/dashboard")

@dashboard_api.route("/kpis", methods=["GET"])
@login_required
@empresa_required
def api_kpis():
    """
    Retorna KPIs do dashboard para a empresa do usuário.
    
    Query params:
        - periodo: 'semana', 'mes', 'ano', 'personalizado'
        - data_inicio: YYYY-MM-DD (se periodo=personalizado)
        - data_fim: YYYY-MM-DD (se periodo=personalizado)
    """
    
    usuario_id = g.user.id
    empresa_id = g.user.empresa_id
    
    # Parâmetros de período
    periodo = request.args.get('periodo', 'mes')
    data_inicio = request.args.get('data_inicio')
    data_fim = request.args.get('data_fim')
    
    try:
        data = calcular_kpis(
            empresa_id=empresa_id,
            periodo=periodo,
            data_inicio=data_inicio,
            data_fim=data_fim
        )
        
        # Log de auditoria
        try:
            from models import LogAuditoria, db
            log = LogAuditoria(
                usuario_id=usuario_id,
                empresa_id=empresa_id,
                acao="dashboard_kpis_acesso",
                detalhes=f"Período: {periodo}",
                ip=request.remote_addr,
                criado_em=datetime.now(timezone.utc)
            )
            db.session.add(log)
            db.session.commit()
        except Exception as e:
            logger.error(f"Erro ao logar auditoria: {str(e)}")
        
        logger.info(f"Dashboard KPIs: usuario={usuario_id}, empresa={empresa_id}, periodo={periodo}")
        
        return jsonify({
            "ok": True,
            "kpis": data,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "cached": False
        }), 200
        
    except ValueError as e:
        logger.warning(f"Erro de validação KPIs: {str(e)}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 400
        
    except Exception as e:
        logger.error(f"Erro ao calcular KPIs: usuario={usuario_id}, erro={str(e)}")
        return jsonify({
            "ok": False,
            "error": "Erro interno ao carregar dashboard"
        }), 500

@dashboard_api.route("/health", methods=["GET"])
def api_health():
    """Health check para monitoramento"""
    return jsonify({
        "status": "ok",
        "service": "dashboard_api",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }), 200
