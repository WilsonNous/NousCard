from datetime import datetime
from decimal import Decimal, InvalidOperation

from flask import Blueprint, flash, g, redirect, render_template, request, session, url_for

from models import ContaBancaria, MovBanco, db
from utils.auth_middleware import empresa_required, login_required, validar_csrf_token


lancamentos_bp = Blueprint("lancamentos", __name__, url_prefix="/financeiro/lancamentos")

CATEGORIAS_RECEITA = [
    ("pix_recebido", "PIX recebido"),
    ("transferencias_recebidas", "Transferência recebida"),
    ("vendas", "Venda / serviço"),
    ("outras_receitas", "Outra receita"),
]

CATEGORIAS_DESPESA = [
    ("fornecedores_servicos", "Fornecedor / serviço"),
    ("fornecedores_mercadoria", "Material / mercadoria"),
    ("transporte_combustivel", "Transporte / combustível"),
    ("alimentacao_restaurante", "Alimentação"),
    ("impostos_tributos", "Impostos / tributos"),
    ("internet", "Internet"),
    ("telefonia", "Telefonia"),
    ("tarifas_bancarias", "Tarifas bancárias"),
    ("outras_despesas", "Outra despesa"),
]


def _parse_valor_br(valor_texto):
    texto = (valor_texto or "").strip().replace("R$", "").replace(" ", "")
    if not texto:
        raise InvalidOperation
    if "," in texto:
        texto = texto.replace(".", "").replace(",", ".")
    valor = Decimal(texto).quantize(Decimal("0.01"))
    if valor <= 0:
        raise InvalidOperation
    return valor


@lancamentos_bp.route("/novo", methods=["GET", "POST"])
@login_required
@empresa_required
def novo():
    usuario = g.user
    empresa_id = usuario.empresa_id
    contas = ContaBancaria.query.filter_by(empresa_id=empresa_id, ativo=True).order_by(ContaBancaria.nome).all()

    if request.method == "POST":
        if not validar_csrf_token(request.form.get("csrf_token")):
            flash("Sua sessão expirou. Recarregue a página e tente novamente.", "error")
            return redirect(url_for("lancamentos.novo"))

        tipo = (request.form.get("tipo") or "").strip().lower()
        descricao = (request.form.get("descricao") or "").strip()
        categoria = (request.form.get("categoria") or "").strip()
        conta_id = request.form.get("conta_bancaria_id", type=int)

        if tipo not in {"receita", "despesa"}:
            flash("Escolha se o lançamento é uma receita ou despesa.", "error")
            return redirect(url_for("lancamentos.novo"))

        if not descricao:
            flash("Informe uma descrição simples para o lançamento.", "error")
            return redirect(url_for("lancamentos.novo"))

        try:
            valor = _parse_valor_br(request.form.get("valor"))
            data_movimento = datetime.strptime(request.form.get("data_movimento") or "", "%Y-%m-%d").date()
        except (InvalidOperation, ValueError):
            flash("Confira o valor e a data informados.", "error")
            return redirect(url_for("lancamentos.novo"))

        categorias_validas = dict(CATEGORIAS_RECEITA if tipo == "receita" else CATEGORIAS_DESPESA)
        if categoria not in categorias_validas:
            categoria = "outras_receitas" if tipo == "receita" else "outras_despesas"

        conta = None
        if conta_id:
            conta = ContaBancaria.query.filter_by(id=conta_id, empresa_id=empresa_id, ativo=True).first()
            if not conta:
                flash("A conta selecionada não pertence à empresa atual.", "error")
                return redirect(url_for("lancamentos.novo"))

        movimento = MovBanco(
            empresa_id=empresa_id,
            conta_bancaria_id=conta.id if conta else None,
            data_movimento=data_movimento,
            banco=conta.banco if conta else None,
            historico=descricao[:255],
            origem="manual",
            valor=valor if tipo == "receita" else -valor,
            valor_conciliado=Decimal("0"),
            conciliado=False,
            tipo_pagamento="manual",
            categoria=categoria,
            categoria_principal="Receitas" if tipo == "receita" else "Despesas",
            subcategoria=categorias_validas.get(categoria),
            score_classificacao=100,
            classificacao_automatica=False,
            classificacao_manual=True,
            origem_classificacao="manual",
            regra_utilizada="lancamento_manual",
            observacoes="Lançamento digitado manualmente no NousCard.",
        )

        try:
            db.session.add(movimento)
            db.session.commit()
        except Exception:
            db.session.rollback()
            flash("Não foi possível salvar o lançamento. Tente novamente.", "error")
            return redirect(url_for("lancamentos.novo"))

        flash(f"{'Receita' if tipo == 'receita' else 'Despesa'} registrada com sucesso.", "success")
        return redirect(url_for("lancamentos.novo"))

    return render_template(
        "lancamento_form.html",
        usuario=usuario,
        empresa_nome=getattr(getattr(usuario, "empresa", None), "nome", ""),
        contas=contas,
        categorias_receita=CATEGORIAS_RECEITA,
        categorias_despesa=CATEGORIAS_DESPESA,
        hoje=datetime.now().date().isoformat(),
        csrf_token=session.get("csrf_token", ""),
    )
