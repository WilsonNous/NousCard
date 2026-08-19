import logging
from flask import Blueprint, render_template, request, redirect, url_for, flash, g
from sqlalchemy import or_
from sqlalchemy.exc import SQLAlchemyError

from models import db, Cliente
from utils.auth_middleware import empresa_required, validar_csrf_token

logger = logging.getLogger(__name__)
clientes_bp = Blueprint("clientes", __name__)


def _cliente_tenant_or_404(cliente_id):
    return Cliente.query.filter_by(
        id=cliente_id,
        empresa_id=g.user.empresa_id,
        ativo=True,
    ).first_or_404()


@clientes_bp.route("/")
@empresa_required
def listar():
    termo = (request.args.get("q") or "").strip()
    query = Cliente.query.filter_by(empresa_id=g.user.empresa_id, ativo=True)
    if termo:
        like = f"%{termo}%"
        query = query.filter(
            or_(
                Cliente.nome.ilike(like),
                Cliente.documento.ilike(like),
                Cliente.telefone.ilike(like),
            )
        )
    clientes = query.order_by(Cliente.nome.asc()).all()
    return render_template("clientes_listar.html", clientes=clientes, termo=termo)


@clientes_bp.route("/novo", methods=["GET", "POST"])
@empresa_required
def novo():
    if request.method == "GET":
        return render_template("cliente_form.html", cliente=None)

    if not validar_csrf_token(request.form.get("csrf_token")):
        flash("Erro de segurança. Recarregue a página e tente novamente.", "error")
        return redirect(url_for("clientes.novo"))

    nome = (request.form.get("nome") or "").strip()
    if not nome:
        flash("Informe o nome do cliente.", "error")
        return render_template("cliente_form.html", cliente=None)

    cliente = Cliente(
        empresa_id=g.user.empresa_id,
        nome=nome,
        tipo_pessoa=(request.form.get("tipo_pessoa") or "PF")[:2],
        documento=(request.form.get("documento") or "").strip() or None,
        telefone=(request.form.get("telefone") or "").strip() or None,
        email=(request.form.get("email") or "").strip() or None,
        endereco=(request.form.get("endereco") or "").strip() or None,
        cidade=(request.form.get("cidade") or "").strip() or None,
        uf=(request.form.get("uf") or "").strip().upper()[:2] or None,
        observacoes=(request.form.get("observacoes") or "").strip() or None,
        ativo=True,
    )
    try:
        db.session.add(cliente)
        db.session.commit()
        flash("Cliente cadastrado com sucesso.", "success")
        proximo = request.args.get("next")
        if proximo == "orcamento":
            return redirect(url_for("orcamentos.novo", cliente_id=cliente.id))
        return redirect(url_for("clientes.listar"))
    except SQLAlchemyError:
        db.session.rollback()
        logger.exception("Erro ao cadastrar cliente")
        flash("Não foi possível cadastrar o cliente.", "error")
        return render_template("cliente_form.html", cliente=None)


@clientes_bp.route("/<int:cliente_id>/editar", methods=["GET", "POST"])
@empresa_required
def editar(cliente_id):
    cliente = _cliente_tenant_or_404(cliente_id)
    if request.method == "GET":
        return render_template("cliente_form.html", cliente=cliente)

    if not validar_csrf_token(request.form.get("csrf_token")):
        flash("Erro de segurança. Recarregue a página e tente novamente.", "error")
        return redirect(url_for("clientes.editar", cliente_id=cliente_id))

    nome = (request.form.get("nome") or "").strip()
    if not nome:
        flash("Informe o nome do cliente.", "error")
        return render_template("cliente_form.html", cliente=cliente)

    cliente.nome = nome
    cliente.tipo_pessoa = (request.form.get("tipo_pessoa") or "PF")[:2]
    cliente.documento = (request.form.get("documento") or "").strip() or None
    cliente.telefone = (request.form.get("telefone") or "").strip() or None
    cliente.email = (request.form.get("email") or "").strip() or None
    cliente.endereco = (request.form.get("endereco") or "").strip() or None
    cliente.cidade = (request.form.get("cidade") or "").strip() or None
    cliente.uf = (request.form.get("uf") or "").strip().upper()[:2] or None
    cliente.observacoes = (request.form.get("observacoes") or "").strip() or None

    try:
        db.session.commit()
        flash("Cliente atualizado com sucesso.", "success")
        return redirect(url_for("clientes.listar"))
    except SQLAlchemyError:
        db.session.rollback()
        logger.exception("Erro ao atualizar cliente")
        flash("Não foi possível atualizar o cliente.", "error")
        return render_template("cliente_form.html", cliente=cliente)
