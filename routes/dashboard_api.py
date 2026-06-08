# routes/dashboard_api.py - VERSÃO APRIMORADA COM SEGURANÇA REFORÇADA

from flask import Blueprint, jsonify, g, request
from utils.auth_middleware import login_required, empresa_required
from services.dashboard_service import calcular_kpis
from datetime import datetime, timezone
import logging
import re
import time

logger = logging.getLogger(__name__)

dashboard_api = Blueprint("dashboard_api", __name__, url_prefix="/api/v1/dashboard")

# ============================================================
# CONFIGURAÇÕES DE SEGURANÇA
# ============================================================
RATE_LIMIT_WINDOW = 60  # segundos
RATE_LIMIT_MAX_REQUESTS = 30  # por janela para endpoints de dashboard
_rate_limit_cache = {}

def check_rate_limit(user_id: str, endpoint: str) -> bool:
    """Verifica rate limiting por usuário e endpoint"""
    now = time.time()
    key = f"dashboard:{user_id}:{endpoint}"
    
    # Limpar entradas antigas
    _rate_limit_cache[key] = [
        t for t in _rate_limit_cache.get(key, [])
        if now - t < RATE_LIMIT_WINDOW
    ]
    
    if len(_rate_limit_cache.get(key, [])) >= RATE_LIMIT_MAX_REQUESTS:
        return False
    
    _rate_limit_cache.setdefault(key, []).append(now)
    return True

def validar_data_iso(valor: str) -> bool:
    """Valida formato de data ISO: YYYY-MM-DD"""
    if not valor:
        return True  # None é válido (sem filtro)
    return bool(re.match(r'^\d{4}-\d{2}-\d{2}$', valor))

# ============================================================
# ENDPOINT PRINCIPAL: KPIs
# ============================================================
@dashboard_api.route("/kpis", methods=["GET"])
@login_required
@empresa_required
def api_kpis():
    """
    Retorna KPIs do dashboard para a empresa do usuário.
    
    ✅ COMPORTAMENTO PADRÃO: Mostra TODOS os dados (sem filtro de data)
    
    Query params (opcionais):
        - periodo: 'semana', 'mes', 'ano', 'todos', 'personalizado' (padrão: 'todos')
        - data_inicio: YYYY-MM-DD (obrigatório se periodo='personalizado')
        - data_fim: YYYY-MM-DD (obrigatório se periodo='personalizado')
        - tipo_pagamento: 'cartao', 'pix', 'boleto', ou null para todos
    """
    
    usuario_id = g.user.id
    empresa_id = g.user.empresa_id
    
    # ✅ Rate limiting por usuário
    if not check_rate_limit(str(usuario_id), "kpis"):
        logger.warning(f"Rate limit excedido: usuario={usuario_id}, endpoint=kpis")
        return jsonify({
            "ok": False,
            "error": "Muitas requisições. Aguarde alguns segundos antes de tentar novamente."
        }), 429
    
    # Coletar e validar parâmetros
    periodo = request.args.get('periodo', 'todos')
    data_inicio = request.args.get('data_inicio')
    data_fim = request.args.get('data_fim')
    tipo_pagamento = request.args.get('tipo_pagamento')  # ✅ NOVO: suporte a filtro por tipo
    
    # ✅ Validar formato de datas
    if not validar_data_iso(data_inicio) or not validar_data_iso(data_fim):
        return jsonify({
            "ok": False,
            "error": "Formato de data inválido. Use YYYY-MM-DD."
        }), 400
    
    # ✅ Validação: Se periodo='personalizado', exigir datas válidas
    if periodo == 'personalizado':
        if not data_inicio or not data_fim:
            return jsonify({
                "ok": False,
                "error": "Para período personalizado, informe data_inicio e data_fim no formato YYYY-MM-DD"
            }), 400
    
    # ✅ Validar tipo_pagamento se fornecido
    if tipo_pagamento and tipo_pagamento not in ('cartao', 'pix', 'boleto', 'outros'):
        return jsonify({
            "ok": False,
            "error": "tipo_pagamento deve ser: cartao, pix, boleto ou outros"
        }), 400
    
    try:
        # ✅ Passar parâmetros para o serviço
        data = calcular_kpis(
            empresa_id=empresa_id,
            periodo=periodo,
            data_inicio=data_inicio,
            data_fim=data_fim,
            tipo_pagamento=tipo_pagamento  # ✅ Passar filtro de tipo de pagamento
        )
        
        # Log de auditoria (não crítico - se falhar, não afeta resposta)
        try:
            from models import LogAuditoria, db
            log = LogAuditoria(
                usuario_id=usuario_id,
                empresa_id=empresa_id,
                acao="dashboard_kpis_acesso",
                detalhes=f"Período: {periodo}, tipo_pagamento: {tipo_pagamento or 'todos'}, inicio: {data_inicio}, fim: {data_fim}",
                ip=request.remote_addr,
                criado_em=datetime.now(timezone.utc)
            )
            db.session.add(log)
            db.session.commit()
        except Exception as log_err:
            # Não fazer rollback para não afetar a resposta principal
            logger.warning(f"⚠️ Erro ao logar auditoria (não crítico): {str(log_err)}")
        
        logger.info(f"✅ Dashboard KPIs: usuario={usuario_id}, empresa={empresa_id}, periodo={periodo}, tipo={tipo_pagamento or 'todos'}")
        
        return jsonify({
            "ok": True,
            "kpis": data,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            # Removido "cached": False para não enganar frontend
            "periodo_aplicado": periodo,
            "tipo_pagamento_aplicado": tipo_pagamento or "todos"  # ✅ Útil para debug
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

# ============================================================
# HEALTH CHECK (SEM AUTH PARA MONITORAMENTO EXTERNO)
# ============================================================
@dashboard_api.route("/health", methods=["GET"])
def api_health():
    """
    Health check para monitoramento.
    ✅ Sem autenticação para permitir checks externos (UptimeRobot, etc.)
    """
    return jsonify({
        "status": "ok",
        "service": "dashboard_api",
        "version": "1.0.0",  # ✅ Útil para deploy tracking
        "timestamp": datetime.now(timezone.utc).isoformat()
    }), 200

# ============================================================
# NOVO: ENDPOINT PARA METADADOS DO DASHBOARD
# ============================================================
@dashboard_api.route("/metadata", methods=["GET"])
@login_required
@empresa_required
def api_metadata():
    """
    Retorna metadados úteis para o frontend do dashboard.
    Ex: períodos disponíveis, tipos de pagamento, adquirentes da empresa.
    """
    from models import Adquirente
    
    empresa_id = g.user.empresa_id
    
    try:
        # Buscar adquirentes ativas da empresa (para filtros)
        adquirentes = Adquirente.query.filter_by(
            empresa_id=empresa_id,
            ativo=True
        ).order_by(Adquirente.nome).all()
        
        return jsonify({
            "ok": True,
            "metadata": {
                "periodos_disponiveis": ["todos", "semana", "mes", "ano", "personalizado"],
                "tipos_pagamento": ["todos", "cartao", "pix", "boleto", "outros"],
                "adquirentes": [{
                    "id": a.id,
                    "nome": a.nome,
                    "codigo": a.codigo
                } for a in adquirentes],
                "data_atual": datetime.now(timezone.utc).strftime("%Y-%m-%d")
            },
            "timestamp": datetime.now(timezone.utc).isoformat()
        }), 200
        
    except Exception as e:
        logger.error(f"Erro ao buscar metadados: {str(e)}")
        return jsonify({
            "ok": False,
            "error": "Erro ao carregar metadados"
        }), 500
