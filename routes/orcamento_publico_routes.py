from flask import Blueprint, render_template, request, redirect, url_for, flash
from sqlalchemy.exc import SQLAlchemyError
from models import db, Orcamento, OrcamentoInteracao

orcamento_publico_bp = Blueprint("orcamento_publico", __name__)


def _orcamento_token_or_404(token):
    return Orcamento.query.filter_by(public_token=token, ativo=True).first_or_404()


def _registrar(orcamento, acao, nome=None, mensagem=None):
    evento = OrcamentoInteracao(empresa_id=orcamento.empresa_id, orcamento_id=orcamento.id, acao=acao, nome_cliente=nome, mensagem=mensagem, ip_origem=(request.headers.get("X-Forwarded-For") or request.remote_addr or "")[:64], user_agent=(request.headers.get("User-Agent") or "")[:500], ativo=True)
    db.session.add(evento)


@orcamento_publico_bp.route("/<token>", methods=["GET"])
def visualizar(token):
    o = _orcamento_token_or_404(token)
    return render_template("orcamento_publico.html", orcamento=o)


@orcamento_publico_bp.route("/<token>/responder", methods=["POST"])
def responder(token):
    o = _orcamento_token_or_404(token)
    acao=(request.form.get("acao") or "").upper(); nome=(request.form.get("nome") or "").strip() or None; mensagem=(request.form.get("mensagem") or "").strip() or None
    mapa={"APROVAR":"APROVADO", "ALTERAR":"ALTERACAO_SOLICITADA", "RECUSAR":"RECUSADO"}
    if acao not in mapa:
        flash("Resposta inválida.", "error"); return redirect(url_for("orcamento_publico.visualizar", token=token))
    o.status=mapa[acao]
    try:
        _registrar(o, acao, nome, mensagem); db.session.commit()
        return render_template("orcamento_publico_resposta.html", orcamento=o, acao=acao)
    except SQLAlchemyError:
        db.session.rollback(); flash("Não foi possível registrar sua resposta. Tente novamente.", "error"); return redirect(url_for("orcamento_publico.visualizar", token=token))
