# routes/empresas_routes.py
from flask import Blueprint, render_template, request, redirect, url_for, flash
from models import db, Empresa
from utils.auth_middleware import master_required

empresas_bp = Blueprint("empresas", __name__, url_prefix="/empresas")

@empresas_bp.route("/")
@master_required
def listar_empresas():
    empresas = Empresa.query.order_by(Empresa.criado_em.desc()).all()
    return render_template("empresas_listar.html", empresas=empresas)


@empresas_bp.route("/nova", methods=["GET", "POST"])
@master_required
def nova_empresa():
    if request.method == "POST":
        nome = request.form.get("nome")
        documento = request.form.get("documento")

        if not nome:
            flash("Nome da empresa é obrigatório.", "erro")
            return redirect(url_for("empresas.nova_empresa"))

        empresa = Empresa(nome=nome, documento=documento, ativa=True)
        db.session.add(empresa)
        db.session.commit()

        flash("Empresa criada com sucesso.", "sucesso")
        return redirect(url_for("empresas.listar_empresas"))

    return render_template("empresas_form.html", empresa=None)


@empresas_bp.route("/<int:empresa_id>/editar", methods=["GET", "POST"])
@master_required
def editar_empresa(empresa_id):
    empresa = Empresa.query.get_or_404(empresa_id)

    if request.method == "POST":
        empresa.nome = request.form.get("nome")
        empresa.documento = request.form.get("documento")
        empresa.ativa = bool(request.form.get("ativa"))

        db.session.commit()
        flash("Empresa atualizada com sucesso.", "sucesso")
        return redirect(url_for("empresas.listar_empresas"))

    return render_template("empresas_form.html", empresa=empresa)
