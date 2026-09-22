import logging
from flask import Blueprint, render_template, request, redirect, url_for, flash, g
from sqlalchemy.exc import SQLAlchemyError
from models import db, Cliente, Veiculo
from utils.auth_middleware import empresa_required, validar_csrf_token

logger = logging.getLogger(__name__)
veiculos_bp = Blueprint("veiculos", __name__)


def _veiculo_tenant_or_404(veiculo_id):
    return Veiculo.query.filter_by(id=veiculo_id, empresa_id=g.user.empresa_id, ativo=True).first_or_404()


@veiculos_bp.route("/")
@empresa_required
def listar():
    veiculos = Veiculo.query.filter_by(empresa_id=g.user.empresa_id, ativo=True).order_by(Veiculo.placa.asc()).all()
    return render_template("veiculos_listar.html", veiculos=veiculos)


@veiculos_bp.route("/novo", methods=["GET", "POST"])
@empresa_required
def novo():
    clientes = Cliente.query.filter_by(empresa_id=g.user.empresa_id, ativo=True).order_by(Cliente.nome.asc()).all()
    if request.method == "GET":
        return render_template("veiculo_form.html", veiculo=None, clientes=clientes, cliente_pre=request.args.get("cliente_id", type=int))
    if not validar_csrf_token(request.form.get("csrf_token")):
        flash("Erro de segurança.", "error"); return redirect(url_for("veiculos.novo"))
    cliente = Cliente.query.filter_by(id=request.form.get("cliente_id", type=int), empresa_id=g.user.empresa_id, ativo=True).first()
    if not cliente:
        flash("Cliente inválido.", "error"); return render_template("veiculo_form.html", veiculo=None, clientes=clientes)
    v = Veiculo(empresa_id=g.user.empresa_id, cliente_id=cliente.id, placa=(request.form.get("placa") or "").upper().replace("-", "").strip(), modelo=(request.form.get("modelo") or "").strip(), marca=(request.form.get("marca") or "").strip() or None, ano=(request.form.get("ano") or "").strip() or None, cor=(request.form.get("cor") or "").strip() or None, chassi=(request.form.get("chassi") or "").strip() or None, seguradora=(request.form.get("seguradora") or "").strip() or None, observacoes=(request.form.get("observacoes") or "").strip() or None, ativo=True)
    km = request.form.get("quilometragem", type=int); v.quilometragem = km
    if not v.placa or not v.modelo:
        flash("Informe placa e modelo.", "error"); return render_template("veiculo_form.html", veiculo=v, clientes=clientes)
    try:
        db.session.add(v); db.session.commit(); flash("Veículo cadastrado.", "success"); return redirect(url_for("veiculos.listar"))
    except SQLAlchemyError:
        db.session.rollback(); logger.exception("Erro ao cadastrar veículo"); flash("Não foi possível cadastrar o veículo. Verifique se a placa já existe.", "error")
        return render_template("veiculo_form.html", veiculo=v, clientes=clientes)


@veiculos_bp.route("/<int:veiculo_id>/editar", methods=["GET", "POST"])
@empresa_required
def editar(veiculo_id):
    v = _veiculo_tenant_or_404(veiculo_id)
    clientes = Cliente.query.filter_by(empresa_id=g.user.empresa_id, ativo=True).order_by(Cliente.nome.asc()).all()
    if request.method == "GET": return render_template("veiculo_form.html", veiculo=v, clientes=clientes)
    if not validar_csrf_token(request.form.get("csrf_token")):
        flash("Erro de segurança.", "error"); return redirect(url_for("veiculos.editar", veiculo_id=v.id))
    v.placa=(request.form.get("placa") or "").upper().replace("-", "").strip(); v.modelo=(request.form.get("modelo") or "").strip(); v.marca=(request.form.get("marca") or "").strip() or None; v.ano=(request.form.get("ano") or "").strip() or None; v.cor=(request.form.get("cor") or "").strip() or None; v.quilometragem=request.form.get("quilometragem", type=int); v.chassi=(request.form.get("chassi") or "").strip() or None; v.seguradora=(request.form.get("seguradora") or "").strip() or None; v.observacoes=(request.form.get("observacoes") or "").strip() or None
    try: db.session.commit(); flash("Veículo atualizado.", "success")
    except SQLAlchemyError: db.session.rollback(); logger.exception("Erro ao atualizar veículo"); flash("Não foi possível atualizar.", "error")
    return redirect(url_for("veiculos.listar"))
