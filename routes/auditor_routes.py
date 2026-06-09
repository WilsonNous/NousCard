# routes/auditor_routes.py
# ✅ Blueprint para API de auditoria - integra com services/auditor.py

from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from services.auditor import (
    auditar_taxas,
    auditar_conciliacao,
    auditar_integridade,
    executar_auditoria_completa
)
import logging

logger = logging.getLogger(__name__)

# ✅ Blueprint com prefixo de API versionada
auditor_bp = Blueprint(
    "auditoria",
    __name__,
    url_prefix="/api/v1/auditoria"
)


@auditor_bp.route("/executar", methods=["POST"])
@login_required
def executar_auditoria_api():
    """
    Endpoint para executar auditoria completa.
    
    JSON Body (opcional):
    {
        "tipos": ["taxas", "conciliacao", "integridade"],  # ou null para todos
        "data_inicio": "2024-01-01",
        "data_fim": "2024-12-31",
        "adquirente_id": 123,
        "tipo_pagamento": "cartao"
    }
    """
    try:
        empresa_id = current_user.empresa_id
        data = request.get_json(silent=True) or {}
        
        # Extrair parâmetros
        tipos = data.get("tipos")  # None = todos
        data_inicio = data.get("data_inicio")
        data_fim = data.get("data_fim")
        adquirente_id = data.get("adquirente_id")
        tipo_pagamento = data.get("tipo_pagamento")
        
        # Executar auditoria
        resultado = executar_auditoria_completa(
            empresa_id=empresa_id,
            tipos=tipos,
            data_inicio=data_inicio,
            data_fim=data_fim,
            adquirente_id=adquirente_id,
            tipo_pagamento=tipo_pagamento
        )
        
        logger.info(f"Auditoria executada: empresa={empresa_id}, alertas={resultado['resumo_consolidado']['total_alertas']}")
        
        return jsonify({
            "ok": True,
            "message": "Auditoria concluída com sucesso",
            "data": resultado
        }), 200
        
    except Exception as e:
        logger.error(f"❌ Erro ao executar auditoria: {str(e)}", exc_info=True)
        return jsonify({
            "ok": False,
            "error": "Erro ao executar auditoria",
            "message": str(e) if current_user.master else "Erro interno"
        }), 500


@auditor_bp.route("/taxas", methods=["GET"])
@login_required
def auditar_taxas_api():
    """Auditoria específica de taxas"""
    try:
        empresa_id = current_user.empresa_id
        
        # Parâmetros de query string
        data_inicio = request.args.get("data_inicio")
        data_fim = request.args.get("data_fim")
        adquirente_id = request.args.get("adquirente_id", type=int)
        tipo_pagamento = request.args.get("tipo_pagamento")
        apenas_com_alertas = request.args.get("apenas_com_alertas", "true").lower() == "true"
        
        resultado = auditar_taxas(
            empresa_id=empresa_id,
            data_inicio=data_inicio,
            data_fim=data_fim,
            adquirente_id=adquirente_id,
            tipo_pagamento=tipo_pagamento,
            apenas_com_alertas=apenas_com_alertas
        )
        
        return jsonify({
            "ok": True,
            "data": resultado
        }), 200
        
    except Exception as e:
        logger.error(f"❌ Erro na auditoria de taxas: {str(e)}")
        return jsonify({
            "ok": False,
            "error": "Erro ao auditar taxas"
        }), 500


@auditor_bp.route("/conciliacao", methods=["GET"])
@login_required
def auditar_conciliacao_api():
    """Auditoria específica de conciliação"""
    try:
        empresa_id = current_user.empresa_id
        
        data_inicio = request.args.get("data_inicio")
        data_fim = request.args.get("data_fim")
        apenas_pendentes = request.args.get("apenas_pendentes", "true").lower() == "true"
        
        resultado = auditar_conciliacao(
            empresa_id=empresa_id,
            data_inicio=data_inicio,
            data_fim=data_fim,
            apenas_pendentes=apenas_pendentes
        )
        
        return jsonify({
            "ok": True,
            "data": resultado
        }), 200
        
    except Exception as e:
        logger.error(f"❌ Erro na auditoria de conciliação: {str(e)}")
        return jsonify({
            "ok": False,
            "error": "Erro ao auditar conciliação"
        }), 500


@auditor_bp.route("/integridade", methods=["GET"])
@login_required
def auditar_integridade_api():
    """Auditoria específica de integridade de dados"""
    try:
        empresa_id = current_user.empresa_id
        
        resultado = auditar_integridade(empresa_id=empresa_id)
        
        return jsonify({
            "ok": True,
            "data": resultado
        }), 200
        
    except Exception as e:
        logger.error(f"❌ Erro na auditoria de integridade: {str(e)}")
        return jsonify({
            "ok": False,
            "error": "Erro ao auditar integridade"
        }), 500


@auditor_bp.route("/status", methods=["GET"])
@login_required
def status_auditoria():
    """Endpoint leve para verificar se módulo de auditoria está disponível"""
    return jsonify({
        "ok": True,
        "status": "available",
        "tipos_suportados": ["taxas", "conciliacao", "integridade"],
        "empresa_id": current_user.empresa_id
    }), 200
