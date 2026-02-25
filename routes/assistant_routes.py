from flask import Blueprint, request, jsonify, g
from utils.auth_middleware import login_required
from datetime import datetime, timezone
import logging
import re

logger = logging.getLogger(__name__)

assistant_bp = Blueprint("assistant", __name__, url_prefix="/assistant")

# ============================================================
# CONFIGURAÇÕES
# ============================================================
MAX_MESSAGE_LENGTH = 1000

# ============================================================
# VALIDAÇÕES
# ============================================================
def sanitize_input(text: str) -> str:
    """Sanitiza entrada do usuário"""
    if not text:
        return ""
    text = text[:MAX_MESSAGE_LENGTH]
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F]', '', text)
    return text.strip()

def validar_pergunta_segura(mensagem: str) -> bool:
    """Bloqueia tentativas de injection ou acesso indevido"""
    padroes_proibidos = [
        r"ignore\s+previous",
        r"bypass",
        r"admin\s+access",
        r"empresa\s+\d+",
        r"outro\s+cliente",
        r"system\s+prompt",
        r"desenvolvedor",
    ]
    for padrao in padroes_proibidos:
        if re.search(padrao, mensagem, re.IGNORECASE):
            logger.warning(f"Pergunta bloqueada: {mensagem[:100]}")
            return False
    return True

# ============================================================
# ENDPOINT PRINCIPAL
# ============================================================
@assistant_bp.route("/", methods=["POST"])
@login_required
def assistant_chat():
    """Endpoint de chat com assistente IA"""
    
    usuario_id = g.user.id
    empresa_id = g.user.empresa_id
    
    # Parse JSON seguro
    try:
        data = request.get_json(force=True)
        if not isinstance(data, dict):
            return jsonify({"ok": False, "error": "Formato inválido"}), 400
    except Exception as e:
        logger.error(f"Erro ao parsear JSON: {str(e)}")
        return jsonify({"ok": False, "error": "JSON inválido"}), 400
    
    # Sanitizar entrada
    user_message = sanitize_input(data.get("message", ""))
    if not user_message:
        return jsonify({"ok": False, "error": "Mensagem vazia"}), 400
    
    # Validar segurança
    if not validar_pergunta_segura(user_message):
        return jsonify({
            "ok": False,
            "error": "Não posso responder essa pergunta por segurança."
        }), 403
    
    # Log de auditoria
    try:
        from models import LogAuditoria, db
        log = LogAuditoria(
            usuario_id=usuario_id,
            empresa_id=empresa_id,
            acao="assistant_pergunta",
            detalhes=f"Pergunta: {user_message[:200]}",
            ip=request.remote_addr,
            criado_em=datetime.now(timezone.utc)
        )
        db.session.add(log)
        db.session.commit()
    except Exception as e:
        logger.error(f"Erro ao logar auditoria: {str(e)}")
    
    # Gerar resposta
    try:
        resposta = gerar_resposta_assistente(user_message, empresa_id, usuario_id)
        
        logger.info(f"Assistant: usuario={usuario_id}, empresa={empresa_id}, pergunta={user_message[:50]}")
        
        return jsonify({
            "ok": True,
            "reply": resposta,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }), 200
        
    except Exception as e:
        logger.error(f"Erro ao gerar resposta: {str(e)}")
        return jsonify({
            "ok": False,
            "error": "Erro ao processar sua pergunta. Tente novamente."
        }), 500

# ============================================================
# GERADOR DE RESPOSTA (PLACEHOLDER)
# ============================================================
def gerar_resposta_assistente(mensagem: str, empresa_id: int, usuario_id: int) -> str:
    """
    Gera resposta do assistente.
    TODO: Integrar com IA (OpenAI, Anthropic, etc.)
    """
    
    mensagem_lower = mensagem.lower()
    
    if any(p in mensagem_lower for p in ["venda", "vendas"]):
        return "Posso te ajudar a analisar suas vendas! Você quer ver o total do mês, por adquirente ou por bandeira? 📊"
    
    if any(p in mensagem_lower for p in ["recebimento", "recebido", "banco"]):
        return "Posso te ajudar com recebimentos! Quer conciliar com as vendas ou ver o que está pendente? 🏦"
    
    if any(p in mensagem_lower for p in ["taxa", "tarifa", "custo"]):
        return "Posso te ajudar com taxas! Quer ver quanto pagou de taxas no mês ou comparar adquirentes? 💰"
    
    if any(p in mensagem_lower for p in ["concilia", "conciliação", "conciliar"]):
        return "A conciliação compara suas vendas com os recebimentos. Quer executar uma nova conciliação? 🔗"
    
    if any(p in mensagem_lower for p in ["olá", "oi", "bom dia", "boa tarde"]):
        return "Olá! Estou aqui para te ajudar com suas vendas, recebimentos e taxas. O que precisa? 😊"
    
    return "Estou aqui pra te ajudar a entender suas vendas, recebimentos e taxas. Em breve vou te mostrar alertas e explicações personalizadas 😉"
