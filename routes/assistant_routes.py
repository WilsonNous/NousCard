from flask import Blueprint, request, jsonify
from utils.auth_middleware import login_required

assistant_bp = Blueprint("assistant", __name__)

@assistant_bp.route("/", methods=["POST"])
@login_required
def assistant_chat():
    data = request.get_json() or {}
    user_message = data.get("message", "")

    # Versão bem simples por enquanto
    resposta = "Estou aqui pra te ajudar a entender suas vendas, recebimentos e taxas. Em breve vou te mostrar alertas e explicações personalizadas 😉"

    return jsonify({"ok": True, "reply": resposta})
