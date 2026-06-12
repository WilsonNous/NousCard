# routes/normalizacao_routes.py
# Rotas para gerenciar e reprocessar normalizações

from flask import Blueprint, jsonify, g, request, render_template
from models import db, Normalizacao  # ✅ Adicionado 'db' que faltava
from flask import abort  # ✅ Adicionado 'abort' que faltava
from utils.auth_middleware import login_required, empresa_required
from sqlalchemy import func
import logging

logger = logging.getLogger(__name__)

normalizacao_bp = Blueprint("normalizacao", __name__, url_prefix="/normalizacao")


@normalizacao_bp.route("/")
@login_required
@empresa_required
def listar_normalizacoes():
    """Lista todas as normalizações da empresa"""
    empresa_id = g.user.empresa_id
    
    # Filtros
    status = request.args.get("status")
    tipo_origem = request.args.get("tipo_origem")
    data_inicio = request.args.get("data_inicio")
    data_fim = request.args.get("data_fim")
    
    query = Normalizacao.query.filter_by(empresa_id=empresa_id)
    
    if status:
        query = query.filter_by(status=status)
    if tipo_origem:
        query = query.filter_by(tipo_origem=tipo_origem)
    if data_inicio:
        query = query.filter(Normalizacao.data_movimento >= data_inicio)
    if data_fim:
        query = query.filter(Normalizacao.data_movimento <= data_fim)
    
    normalizacoes = query.order_by(Normalizacao.data_movimento.desc()).paginate(
        page=request.args.get("page", 1, type=int),
        per_page=request.args.get("per_page", 50, type=int)
    )
    
    return render_template(
        "normalizacao/listar.html",
        normalizacoes=normalizacoes,
        status_filter=status,
        tipo_origem_filter=tipo_origem
    )


@normalizacao_bp.route("/<int:id>")
@login_required
@empresa_required
def detalhe_normalizacao(id):
    """Detalhes de uma normalização específica"""
    normalizacao = Normalizacao.query.get_or_404(id)
    
    if normalizacao.empresa_id != g.user.empresa_id:
        abort(403)
    
    return render_template("normalizacao/detalhe.html", normalizacao=normalizacao)


@normalizacao_bp.route("/api/estatisticas")
@login_required
@empresa_required
def estatisticas_normalizacao():
    """Retorna estatísticas das normalizações"""
    empresa_id = g.user.empresa_id
    
    stats = db.session.query(
        Normalizacao.status,
        Normalizacao.tipo_origem,
        func.count(Normalizacao.id).label("total"),
        func.sum(Normalizacao.valor_bruto).label("valor_total")
    ).filter_by(
        empresa_id=empresa_id
    ).group_by(
        Normalizacao.status,
        Normalizacao.tipo_origem
    ).all()
    
    return jsonify({
        "ok": True,
        "stats": [
            {
                "status": s.status,
                "tipo_origem": s.tipo_origem,
                "total": s.total,
                "valor_total": float(s.valor_total) if s.valor_total else 0
            }
            for s in stats
        ]
    })


# ============================================================
# 🔄 ROTAS DE REPROCESSAMENTO (ATUALIZADAS)
# ============================================================

@normalizacao_bp.route("/reprocessar", methods=["GET", "POST"])
@login_required
@empresa_required
def reprocessar():
    """
    Reprocessa todas as normalizações pendentes ou com erro.
    Aceita GET (para testar no navegador) ou POST (para APIs).
    """
    empresa_id = g.user.empresa_id
    
    logger.info(f"🔄 Rota /normalizacao/reprocessar chamada pelo usuário {g.user.id}")
    
    try:
        # ✅ Importa e chama a função correta que criamos no service
        from services.processador_normalizacao import processar_normalizacoes
        
        # Processa tudo que não está com status 'processado'
        stats = processar_normalizacoes(empresa_id, arquivo_id=None)
        
        # Resposta para API (POST)
        if request.method == "POST":
            return jsonify({
                "ok": True,
                "message": "Reprocessamento concluído com sucesso",
                "stats": stats
            })
        
        # Resposta Visual para Navegador (GET) - Útil para debug rápido
        return f"""
        <html>
        <head>
            <title>Reprocessamento Concluído</title>
            <style>
                body {{ font-family: sans-serif; padding: 2rem; background: #f4f6f9; }}
                .container {{ background: white; padding: 2rem; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); max-width: 600px; margin: 0 auto; }}
                h2 {{ color: #28a745; margin-top: 0; }}
                pre {{ background: #f8f9fa; padding: 1rem; border-radius: 4px; overflow-x: auto; }}
                .btn {{ display: inline-block; padding: 10px 20px; background: #007bff; color: white; text-decoration: none; border-radius: 4px; margin-top: 1rem; }}
                .btn:hover {{ background: #0056b3; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h2>✅ Reprocessamento Concluído!</h2>
                <p>O sistema tentou processar os registros parados na tabela <strong>tous_normalizacao</strong>.</p>
                
                <h3>📊 Resultados:</h3>
                <pre>{stats}</pre>
                
                <h3>🔍 Próximos Passos:</h3>
                <ul>
                    <li>Verifique se os dados aparecem no <strong>Dashboard</strong>.</li>
                    <li>Confira a tabela <strong>mov_adquirente</strong> no banco.</li>
                </ul>

                <a href="/operacoes/importar" class="btn">← Voltar para Operações</a>
            </div>
        </body>
        </html>
        """
        
    except Exception as e:
        logger.error(f"❌ Erro no reprocessamento: {str(e)}", exc_info=True)
        return jsonify({
            "ok": False,
            "message": f"Erro ao reprocessar: {str(e)}"
        }), 500


@normalizacao_bp.route("/limpar", methods=["POST"])
@login_required
@empresa_required
def limpar_normalizacoes():
    """Limpa todas as normalizações da empresa (CUIDADO: deleta dados)"""
    empresa_id = g.user.empresa_id
    
    total = Normalizacao.query.filter_by(empresa_id=empresa_id).delete()
    db.session.commit()
    
    logger.info(f"🗑️ {total} normalizações removidas da empresa {empresa_id}")
    
    return jsonify({
        "ok": True,
        "message": f"{total} registros removidos com sucesso"
    })
