# routes/public_leads_routes.py
# Captação pública de interessados no NousCard

from flask import Blueprint, request, jsonify
from models import db, Lead
from urllib.parse import quote
import logging
import os
import re
import time


logger = logging.getLogger(__name__)

# O prefixo /api/public é definido em routes/__init__.py
public_leads_bp = Blueprint("public_leads", __name__)


# ============================================================
# RATE LIMIT SIMPLES PARA O MVP
# ============================================================
RATE_LIMIT_WINDOW = 60 * 10  # 10 minutos
RATE_LIMIT_MAX_REQUESTS = 5
_rate_limit_cache = {}


def _check_rate_limit(ip_address: str) -> bool:
    """
    Rate limit leve em memória para reduzir abuso básico.

    Observação:
    em múltiplas instâncias/containers, o ideal futuro é Redis.
    """
    now = time.time()
    key = ip_address or "unknown"

    recentes = [
        timestamp
        for timestamp in _rate_limit_cache.get(key, [])
        if now - timestamp < RATE_LIMIT_WINDOW
    ]

    if len(recentes) >= RATE_LIMIT_MAX_REQUESTS:
        _rate_limit_cache[key] = recentes
        return False

    recentes.append(now)
    _rate_limit_cache[key] = recentes
    return True


def _limpar(valor, limite=None):
    valor = (valor or "").strip()

    if limite:
        valor = valor[:limite]

    return valor


def _telefone_valido(telefone):
    digitos = re.sub(r"\D", "", telefone or "")
    return 10 <= len(digitos) <= 13


def _email_valido(email):
    if not email:
        return True

    return re.match(
        r"^[^@\s]+@[^@\s]+\.[^@\s]+$",
        email
    ) is not None


@public_leads_bp.route("/leads", methods=["POST"])
def criar_lead_publico():
    """
    Cria um lead comercial a partir da landing pública.

    Endpoint final:
        POST /api/public/leads
    """
    ip_address = request.headers.get(
        "X-Forwarded-For",
        request.remote_addr or ""
    ).split(",")[0].strip()

    if not _check_rate_limit(ip_address):
        return jsonify({
            "ok": False,
            "error": (
                "Recebemos várias solicitações deste acesso. "
                "Aguarde alguns minutos e tente novamente."
            ),
        }), 429

    try:
        data = request.get_json(silent=True) or request.form

        # Honeypot: campo invisível para humanos.
        # Se preenchido, devolvemos sucesso sem gravar.
        website = _limpar(data.get("website"), 255)
        if website:
            return jsonify({
                "ok": True,
                "message": "Recebemos seu interesse!",
            }), 201

        nome = _limpar(data.get("nome"), 200)
        empresa = _limpar(data.get("empresa"), 200)
        telefone = _limpar(data.get("telefone"), 30)
        email = _limpar(data.get("email"), 200).lower()
        cnpj = _limpar(data.get("cnpj"), 20)
        controle_atual = _limpar(
            data.get("controle_atual"),
            30
        ).lower()
        mensagem = _limpar(data.get("mensagem"), 2000)

        interesses = data.get("interesses", [])

        if isinstance(interesses, str):
            interesses = [
                item.strip()
                for item in interesses.split(",")
                if item.strip()
            ]

        if not isinstance(interesses, (list, tuple)):
            interesses = []

        interesses = [
            str(item).strip().lower()
            for item in interesses
            if str(item).strip().lower()
            in Lead.INTERESSES_VALIDOS
        ]

        # ========================================================
        # VALIDAÇÕES
        # ========================================================
        if not nome:
            return jsonify({
                "ok": False,
                "error": "Informe seu nome.",
            }), 400

        if not empresa:
            return jsonify({
                "ok": False,
                "error": "Informe o nome da empresa.",
            }), 400

        if not telefone or not _telefone_valido(telefone):
            return jsonify({
                "ok": False,
                "error": "Informe um WhatsApp válido.",
            }), 400

        if email and not _email_valido(email):
            return jsonify({
                "ok": False,
                "error": "Informe um e-mail válido.",
            }), 400

        if (
            controle_atual
            and controle_atual not in Lead.CONTROLES_VALIDOS
        ):
            controle_atual = None

        # ========================================================
        # EVITAR DUPLICAÇÃO ACIDENTAL IMEDIATA
        # ========================================================
        digitos_telefone = re.sub(r"\D", "", telefone)

        lead_existente = Lead.query.filter(
            Lead.ativo.is_(True),
            Lead.telefone.isnot(None),
        ).order_by(
            Lead.criado_em.desc()
        ).first()

        # Não fazemos bloqueio rígido por telefone neste MVP,
        # pois a mesma empresa pode voltar depois para novo contato.
        # O dado acima fica apenas preparado para evolução futura.
        _ = lead_existente, digitos_telefone

        # ========================================================
        # GRAVAR
        # ========================================================
        lead = Lead(
            nome=nome,
            empresa=empresa,
            cnpj=cnpj or None,
            email=email or None,
            telefone=telefone,
            controle_atual=controle_atual or None,
            interesses=(
                ",".join(dict.fromkeys(interesses))
                if interesses else None
            ),
            mensagem=mensagem or None,
            status="novo",
            origem="landing_nouscard",
            ip_address=ip_address[:50] if ip_address else None,
            user_agent=(request.user_agent.string or "")[:500],
        )

        db.session.add(lead)
        db.session.commit()

        logger.info(
            "✅ Novo lead NousCard: id=%s empresa=%s",
            lead.id,
            lead.empresa,
        )

        # WhatsApp comercial da Nous Tecnologia.
        # Pode ser sobrescrito no Render:
        # NOUSCARD_WHATSAPP=5548998284104
        numero_nous = re.sub(
            r"\D",
            "",
            os.getenv(
                "NOUSCARD_WHATSAPP",
                "5548998284104"
            )
        )

        mensagem_whatsapp = (
            "Olá! Acabei de demonstrar interesse no NousCard. "
            f"Meu nome é {lead.nome} e minha empresa é "
            f"{lead.empresa}. Gostaria de conhecer melhor a solução."
        )

        whatsapp_url = (
            f"https://wa.me/{numero_nous}"
            f"?text={quote(mensagem_whatsapp)}"
        )

        return jsonify({
            "ok": True,
            "lead_id": lead.id,
            "message": "Recebemos seu interesse!",
            "whatsapp_url": whatsapp_url,
        }), 201

    except Exception as exc:
        db.session.rollback()

        logger.error(
            "❌ Erro ao criar lead público: %s",
            str(exc),
            exc_info=True,
        )

        return jsonify({
            "ok": False,
            "error": (
                "Não foi possível registrar seu interesse agora. "
                "Tente novamente em alguns instantes."
            ),
        }), 500
