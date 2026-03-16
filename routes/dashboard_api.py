# routes/dashboard_api.py - VERSÃO CORRIGIDA

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
    
    ✅ COMPORTAMENTO PADRÃO: Mostra TODOS os dados (sem filtro de data)
    
    Query params (opcionais):
        - periodo: 'semana', 'mes', 'ano', 'todos' (padrão: 'todos')
        - data_inicio: YYYY-MM-DD (apenas se periodo='personalizado')
        - data_fim: YYYY-MM-DD (apenas se periodo='personalizado')
    """
    
    usuario_id = g.user.id
    empresa_id = g.user.empresa_id
    
    # ✅ CORREÇÃO: Padrão 'todos' para mostrar todos os dados
    periodo = request.args.get('periodo', 'todos')  # ← Mudado de 'mes' para 'todos'
    data_inicio = request.args.get('data_inicio')
    data_fim = request.args.get('data_fim')
    
    # ✅ Validação: Se periodo='personalizado', exigir datas
    if periodo == 'personalizado':
        if not data_inicio or not data_fim:
            return jsonify({
                "ok": False,
                "error": "Para período personalizado, informe data_inicio e data_fim no formato YYYY-MM-DD"
            }), 400
    
    try:
        # ✅ Passar parâmetros para o serviço (que deve tratar 'todos' como sem filtro)
        data = calcular_kpis(
            empresa_id=empresa_id,
            periodo=periodo,
            data_inicio=data_inicio,
            data_fim=data_fim
        )
        
        # Log de auditoria (não crítico)
        try:
            from models import LogAuditoria, db
            log = LogAuditoria(
                usuario_id=usuario_id,
                empresa_id=empresa_id,
                acao="dashboard_kpis_acesso",
                detalhes=f"Período: {periodo}, inicio: {data_inicio}, fim: {data_fim}",
                ip=request.remote_addr,
                criado_em=datetime.now(timezone.utc)
            )
            db.session.add(log)
            db.session.commit()
        except Exception as e:
            logger.warning(f"⚠️ Erro ao logar auditoria (não crítico): {str(e)}")
            # Não faz rollback para não afetar a resposta da API
        
        logger.info(f"✅ Dashboard KPIs: usuario={usuario_id}, empresa={empresa_id}, periodo={periodo}")
        
        return jsonify({
            "ok": True,
            "kpis": data,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "cached": False,
            "periodo_aplicado": periodo  # ← Útil para debug no frontend
        }), 200
        
    except ValueError as e:
        logger.warning(f"⚠️ Erro de validação KPIs: {str(e)}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 400
        
    except Exception as e:
        logger.error(f"❌ Erro ao calcular KPIs: usuario={usuario_id}, erro={str(e)}", exc_info=True)
        return jsonify({
            "ok": False,
            "error": "Erro interno ao carregar dashboard. Tente novamente."
        }), 500

@dashboard_api.route("/health", methods=["GET"])
def api_health():
    """Health check para monitoramento"""
    return jsonify({
        "status": "ok",
        "service": "dashboard_api",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }), 200
