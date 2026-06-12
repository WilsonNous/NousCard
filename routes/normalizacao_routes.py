# routes/normalizacao_routes.py
# Rotas para gerenciar dados normalizados

from flask import Blueprint, render_template, request, jsonify, g
from models import Normalizacao
from utils.auth_middleware import login_required, empresa_required
from sqlalchemy import func

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


@normalizacao_bp.route("/api/reprocessar", methods=["POST"])
@login_required
@empresa_required
def reprocessar_normalizacoes():
    """Reprocessa normalizações com erro ou pendentes"""
    data = request.get_json()
    ids = data.get("ids", [])
    
    from services.importer_normalizacao import ImportadorNormalizado
    
    importador = ImportadorNormalizado(g.user.empresa_id, g.user.id)
    importador.processar_para_tabelas_finais(ids)
    
    return jsonify({"ok": True, "message": "Reprocessamento iniciado"})
