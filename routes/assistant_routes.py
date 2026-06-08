# routes/assistant_routes.py - VERSÃO APRIMORADA

from flask import Blueprint, request, jsonify, g
from utils.auth_middleware import login_required
from datetime import datetime, timezone
import logging
import re
import time

logger = logging.getLogger(__name__)

assistant_bp = Blueprint("assistant", __name__, url_prefix="/assistant")

# ============================================================
# CONFIGURAÇÕES
# ============================================================
MAX_MESSAGE_LENGTH = 1000
RATE_LIMIT_WINDOW = 60  # segundos
RATE_LIMIT_MAX_REQUESTS = 10  # por janela

# ============================================================
# RATE LIMITING SIMPLES (em memória - para produção usar Redis)
# ============================================================
_rate_limit_cache = {}

def check_rate_limit(user_id: str) -> bool:
    """Verifica se usuário excedeu limite de requisições"""
    now = time.time()
    key = f"assistant:{user_id}"
    
    # Limpar entradas antigas
    _rate_limit_cache[key] = [
        t for t in _rate_limit_cache.get(key, [])
        if now - t < RATE_LIMIT_WINDOW
    ]
    
    if len(_rate_limit_cache.get(key, [])) >= RATE_LIMIT_MAX_REQUESTS:
        return False
    
    _rate_limit_cache.setdefault(key, []).append(now)
    return True

# ============================================================
# VALIDAÇÕES
# ============================================================
def sanitize_input(text: str) -> str:
    """Sanitiza entrada do usuário"""
    if not text:
        return ""
    text = text[:MAX_MESSAGE_LENGTH]
    text = re.sub(r'<[^>]+>', '', text)  # Remove HTML tags
    text = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F]', '', text)  # Remove control chars
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
        r"__import__",
        r"exec\s*\(",
        r"eval\s*\(",
    ]
    for padrao in padroes_proibidos:
        if re.search(padrao, mensagem, re.IGNORECASE):
            logger.warning(f"🚫 Pergunta bloqueada por segurança: {mensagem[:100]}")
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
    user_key = f"user:{usuario_id}"
    
    # ✅ Rate limiting
    if not check_rate_limit(user_key):
        logger.warning(f"Rate limit excedido: usuario={usuario_id}")
        return jsonify({
            "ok": False,
            "error": "Muitas requisições. Aguarde alguns segundos antes de tentar novamente."
        }), 429
    
    # ✅ Validar Content-Type
    if not request.is_json:
        return jsonify({"ok": False, "error": "Content-Type deve ser application/json"}), 415
    
    # Parse JSON seguro
    try:
        data = request.get_json()
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
    
    # Gerar resposta PRIMEIRO (antes de logar)
    try:
        resposta = gerar_resposta_assistente(user_message, empresa_id, usuario_id)
    except Exception as e:
        logger.error(f"Erro ao gerar resposta: {str(e)}")
        return jsonify({
            "ok": False,
            "error": "Erro ao processar sua pergunta. Tente novamente."
        }), 500
    
    # ✅ Log de auditoria APÓS resposta bem-sucedida
    try:
        from models import LogAuditoria, db
        log = LogAuditoria(
            usuario_id=usuario_id,
            empresa_id=empresa_id,
            acao="assistant_pergunta",
            detalhes=f"Pergunta: {user_message[:200]} | Resposta: {resposta[:100]}",
            ip=request.remote_addr,
            criado_em=datetime.now(timezone.utc)
        )
        db.session.add(log)
        db.session.commit()
    except Exception as e:
        # Não falhar a resposta por erro de log
        logger.error(f"Erro ao logar auditoria (não crítico): {str(e)}")
        # Não faz rollback para não afetar a resposta
    
    logger.info(f"✅ Assistant: usuario={usuario_id}, empresa={empresa_id}, pergunta={user_message[:50]}")
    
    return jsonify({
        "ok": True,
        "reply": resposta,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }), 200

# ============================================================
# GERADOR DE RESPOSTA (PLACEHOLDER - INTEGRAR COM IA)
# ============================================================
def gerar_resposta_assistente(mensagem: str, empresa_id: int, usuario_id: int) -> str:
    """
    Gera resposta do assistente.
    
    ✅ TODO: Integrar com:
        - OpenAI GPT-4
        - Anthropic Claude
        - Ou regras de negócio locais para MVP
    """
    
    mensagem_lower = mensagem.lower()
    
    # ✅ Respostas contextuais baseadas em palavras-chave
    if any(p in mensagem_lower for p in ["venda", "vendas", "faturamento"]):
        return "Posso te ajudar a analisar suas vendas! 📊\n\n• Digite 'total do mês' para ver o faturamento\n• Digite 'por adquirente' para ver por maquininha\n• Digite 'por bandeira' para ver Visa/Mastercard/etc."
    
    if any(p in mensagem_lower for p in ["recebimento", "recebido", "banco", "extrato"]):
        return "Posso te ajudar com recebimentos! 🏦\n\n• Digite 'conciliar' para comparar com vendas\n• Digite 'pendentes' para ver o que falta receber\n• Digite 'por banco' para ver por instituição"
    
    if any(p in mensagem_lower for p in ["taxa", "tarifa", "custo", "desconto"]):
        return "Posso te ajudar com taxas! 💰\n\n• Digite 'total de taxas' para ver quanto pagou\n• Digite 'comparar adquirentes' para ver quem cobra menos\n• Digite 'auditoria de taxas' para verificar divergências"
    
    if any(p in mensagem_lower for p in ["concilia", "conciliação", "conciliar", "match"]):
        return "A conciliação compara suas vendas com os recebimentos! 🔗\n\n• Digite 'executar conciliação' para rodar agora\n• Digite 'ver pendentes' para ver o que não bateu\n• Digite 'detalhes' para ver linha por linha"
    
    if any(p in mensagem_lower for p in ["olá", "oi", "bom dia", "boa tarde", "hello", "hi"]):
        return "Olá! 👋 Estou aqui para te ajudar com:\n\n✅ Vendas e faturamento\n✅ Recebimentos bancários\n✅ Taxas e custos\n✅ Conciliação automática\n\nO que precisa hoje?"
    
    if any(p in mensagem_lower for p in ["ajuda", "help", "comando", "o que posso"]):
        return "Posso te ajudar com:\n\n📊 **Vendas**: totais, por adquirente, por bandeira\n🏦 **Recebimentos**: conciliação, pendentes, por banco\n💰 **Taxas**: auditoria, comparação, alertas\n🔗 **Conciliação**: executar, ver resultados, detalhar\n\nDigite sua pergunta ou um dos comandos acima! 😊"
    
    # ✅ Fallback inteligente
    return f"Entendi sua pergunta sobre '{mensagem[:50]}...'. 🤔\n\nNo momento, posso ajudar melhor com:\n• Vendas e faturamento\n• Recebimentos bancários\n• Taxas e custos\n• Conciliação\n\nTente reformular ou digite 'ajuda' para ver os comandos disponíveis! 😉"
