# routes/public_leads_routes.py

from flask import Blueprint, request, jsonify, current_app
from models import db, Lead
from datetime import datetime, timezone
import logging
import re

logger = logging.getLogger(__name__)

public_leads_bp = Blueprint("public_leads", __name__, url_prefix="/api/public")


def _limpar(valor, limite=None):
    valor = (valor or "").strip()
    if limite:
        valor = valor[:limite]
    return valor


def _telefone_valido(telefone):
    digitos = re.sub(r"\D", "", telefone or "")
    return 10 <= len(digitos) <= 13


@public_leads_bp.route("/leads", methods=["POST"])
def criar_lead_publico():
    try:
        data = request.get_json(silent=True) or request.form

        nome = _limpar(data.get("nome"), 200)
        empresa = _limpar(data.get("empresa"), 200)
        telefone = _limpar(data.get("telefone"), 30)
        email = _limpar(data.get("email"), 200).lower()
        cnpj = _limpar(data.get("cnpj"), 20)
        controle_atual = _limpar(data.get("controle_atual"), 30)
        mensagem = _limpar(data.get("mensagem"), 2000)

        interesses = data.get("interesses", [])
        if isinstance(interesses, str):
            interesses = [i.strip() for i in interesses.split(",") if i.strip()]
        if not isinstance(interesses, (list, tuple)):
            interesses = []

        interesses_validos = {"clientes", "orcamentos", "os", "financeiro"}
        interesses = [i for i in interesses if i in interesses_validos]

        if not nome:
            return jsonify({"ok": False, "error": "Informe seu nome."}), 400

        if not empresa:
            return jsonify({"ok": False, "error": "Informe o nome da empresa."}), 400

        if not telefone or not _telefone_valido(telefone):
            return jsonify({"ok": False, "error": "Informe um WhatsApp válido."}), 400

        controles_validos = {"caderno", "planilha", "sistema", "misto", "outro", ""}
        if controle_atual not in controles_validos:
            controle_atual = ""

        lead = Lead(
            nome=nome,
            empresa=empresa,
            cnpj=cnpj or None,
            email=email or None,
            telefone=telefone,
            controle_atual=controle_atual or None,
            interesses=",".join(interesses) if interesses else None,
            mensagem=mensagem or None,
            status="novo",
            origem="landing_nouscard",
            ip_address=request.remote_addr,
            user_agent=(request.user_agent.string or "")[:500]
        )

        db.session.add(lead)
        db.session.commit()

        logger.info(
            "✅ Novo lead NousCard: id=%s empresa=%s telefone=%s",
            lead.id, lead.empresa, lead.telefone
        )

        numero_nous = current_app.config.get("NOUSCARD_WHATSAPP", "5548998284104")
        mensagem_whatsapp = (
            f"Olá! Acabei de demonstrar interesse no NousCard. "
            f"Meu nome é {lead.nome} e minha empresa é {lead.empresa}."
        )
        from urllib.parse import quote
        whatsapp_url = f"https://wa.me/{numero_nous}?text={quote(mensagem_whatsapp)}"

        return jsonify({
            "ok": True,
            "lead_id": lead.id,
            "message": "Recebemos seu interesse!",
            "whatsapp_url": whatsapp_url
        }), 201

    except Exception as e:
        db.session.rollback()
        logger.error("❌ Erro ao criar lead público: %s", str(e), exc_info=True)
        return jsonify({
            "ok": False,
            "error": "Não foi possível registrar seu interesse agora. Tente novamente."
        }), 500
