import base64
import logging
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from flask import Blueprint, render_template, request, redirect, url_for, flash, g
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from models import db, Cliente, Orcamento, OrcamentoItem
from utils.auth_middleware import empresa_required, validar_csrf_token

logger = logging.getLogger(__name__)
orcamentos_bp = Blueprint("orcamentos", __name__)

STATUS_VALIDOS = {"RASCUNHO", "ENVIADO", "APROVADO", "RECUSADO", "CANCELADO"}
STATUS_LABELS = {
    "RASCUNHO": "Rascunho",
    "ENVIADO": "Enviado",
    "APROVADO": "Aprovado",
    "RECUSADO": "Recusado",
    "CANCELADO": "Cancelado",
}


def _dec(valor, default="0"):
    if valor is None or valor == "":
        return Decimal(default)
    try:
        texto = str(valor).strip().replace("R$", "").replace(" ", "")
        if "," in texto:
            texto = texto.replace(".", "").replace(",", ".")
        return Decimal(texto).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError):
        return Decimal(default)


def _dec_qtd(valor, default="1"):
    try:
        texto = str(valor or default).strip().replace(",", ".")
        qtd = Decimal(texto)
        if qtd <= 0:
            return Decimal(default)
        return qtd.quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError):
        return Decimal(default)


def _data(valor, default=None):
    if not valor:
        return default
    try:
        return datetime.strptime(valor, "%Y-%m-%d").date()
    except ValueError:
        return default


def _imagem_data_url(file_storage):
    if not file_storage or not file_storage.filename:
        return None
    mime = (file_storage.mimetype or "").lower()
    permitidos = {"image/jpeg", "image/png", "image/webp"}
    if mime not in permitidos:
        raise ValueError("Imagem deve ser JPG, PNG ou WEBP.")
    raw = file_storage.read()
    if len(raw) > 4 * 1024 * 1024:
        raise ValueError("Cada imagem deve ter no máximo 4 MB.")
    return f"data:{mime};base64,{base64.b64encode(raw).decode('ascii')}"


def _orcamento_tenant_or_404(orcamento_id):
    return Orcamento.query.filter_by(
        id=orcamento_id,
        empresa_id=g.user.empresa_id,
        ativo=True,
    ).first_or_404()


def _proximo_numero():
    atual = db.session.query(func.max(Orcamento.numero)).filter(
        Orcamento.empresa_id == g.user.empresa_id
    ).scalar()
    return int(atual or 0) + 1


def _clientes_ativos():
    return Cliente.query.filter_by(
        empresa_id=g.user.empresa_id, ativo=True
    ).order_by(Cliente.nome.asc()).all()


def _salvar_itens(orcamento):
    descricoes = request.form.getlist("item_descricao[]")
    detalhes = request.form.getlist("item_detalhamento[]")
    quantidades = request.form.getlist("item_quantidade[]")
    valores = request.form.getlist("item_valor_unitario[]")
    medidas = request.form.getlist("item_medidas[]")
    tecnicas = request.form.getlist("item_informacoes_tecnicas[]")
    custos_material = request.form.getlist("item_custo_material[]")
    custos_instalacao = request.form.getlist("item_custo_instalacao[]")
    outros_custos = request.form.getlist("item_outros_custos[]")
    ids = request.form.getlist("item_id[]")
    imagens = request.files.getlist("item_imagem[]")

    # Preserva a imagem dos itens já existentes sem reenviar base64 no formulário.
    imagens_existentes = {str(item.id): item.imagem_base64 for item in list(orcamento.itens) if item.id}

    # Substituição integral mantém o formulário simples e previsível no MVP.
    for item in list(orcamento.itens):
        db.session.delete(item)
    db.session.flush()

    subtotal = Decimal("0")
    ordem = 0
    for idx, descricao in enumerate(descricoes):
        descricao = (descricao or "").strip()
        if not descricao:
            continue
        qtd = _dec_qtd(quantidades[idx] if idx < len(quantidades) else "1")
        unit = _dec(valores[idx] if idx < len(valores) else "0")
        total_item = (qtd * unit).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        subtotal += total_item

        item_id_antigo = ids[idx] if idx < len(ids) else ""
        imagem = imagens_existentes.get(str(item_id_antigo))
        if idx < len(imagens) and imagens[idx] and imagens[idx].filename:
            imagem = _imagem_data_url(imagens[idx])

        item = OrcamentoItem(
            orcamento=orcamento,
            descricao=descricao,
            detalhamento=(detalhes[idx] if idx < len(detalhes) else "").strip() or None,
            quantidade=qtd,
            valor_unitario=unit,
            valor_total=total_item,
            medidas=(medidas[idx] if idx < len(medidas) else "").strip() or None,
            informacoes_tecnicas=(tecnicas[idx] if idx < len(tecnicas) else "").strip() or None,
            custo_material=_dec(custos_material[idx] if idx < len(custos_material) else "0"),
            custo_instalacao=_dec(custos_instalacao[idx] if idx < len(custos_instalacao) else "0"),
            outros_custos=_dec(outros_custos[idx] if idx < len(outros_custos) else "0"),
            imagem_base64=imagem or None,
            ordem=ordem,
            ativo=True,
        )
        db.session.add(item)
        ordem += 1

    if ordem == 0:
        raise ValueError("Adicione pelo menos um item ao orçamento.")

    desconto = _dec(request.form.get("desconto"))
    if desconto < 0:
        desconto = Decimal("0")
    if desconto > subtotal:
        desconto = subtotal
    orcamento.subtotal = subtotal
    orcamento.desconto = desconto
    orcamento.total = subtotal - desconto


@orcamentos_bp.route("/")
@empresa_required
def listar():
    status = (request.args.get("status") or "").upper()
    query = Orcamento.query.filter_by(empresa_id=g.user.empresa_id, ativo=True)
    if status in STATUS_VALIDOS:
        query = query.filter_by(status=status)
    orcamentos = query.order_by(Orcamento.numero.desc()).all()
    return render_template(
        "orcamentos_listar.html",
        orcamentos=orcamentos,
        status_filtro=status,
        status_labels=STATUS_LABELS,
    )


@orcamentos_bp.route("/novo", methods=["GET", "POST"])
@empresa_required
def novo():
    clientes = _clientes_ativos()
    if request.method == "GET":
        cliente_pre = request.args.get("cliente_id", type=int)
        return render_template(
            "orcamento_form.html",
            orcamento=None,
            clientes=clientes,
            cliente_pre=cliente_pre,
            hoje=date.today(),
            validade_padrao=date.today() + timedelta(days=7),
        )

    if not validar_csrf_token(request.form.get("csrf_token")):
        flash("Erro de segurança. Recarregue a página e tente novamente.", "error")
        return redirect(url_for("orcamentos.novo"))

    cliente_id = request.form.get("cliente_id", type=int)
    cliente = Cliente.query.filter_by(
        id=cliente_id, empresa_id=g.user.empresa_id, ativo=True
    ).first()
    if not cliente:
        flash("Selecione um cliente válido.", "error")
        return render_template("orcamento_form.html", orcamento=None, clientes=clientes)

    orcamento = Orcamento(
        empresa_id=g.user.empresa_id,
        cliente_id=cliente.id,
        numero=_proximo_numero(),
        data_emissao=_data(request.form.get("data_emissao"), date.today()),
        validade_ate=_data(request.form.get("validade_ate")),
        status="RASCUNHO",
        condicoes_pagamento=(request.form.get("condicoes_pagamento") or "").strip() or None,
        prazo_estimado=(request.form.get("prazo_estimado") or "").strip() or None,
        observacoes_cliente=(request.form.get("observacoes_cliente") or "").strip() or None,
        observacoes_internas=(request.form.get("observacoes_internas") or "").strip() or None,
        ativo=True,
    )
    try:
        db.session.add(orcamento)
        db.session.flush()
        _salvar_itens(orcamento)
        db.session.commit()
        flash(f"Orçamento {orcamento.numero_formatado} criado com sucesso.", "success")
        return redirect(url_for("orcamentos.visualizar", orcamento_id=orcamento.id))
    except ValueError as e:
        db.session.rollback()
        flash(str(e), "error")
    except IntegrityError:
        db.session.rollback()
        logger.exception("Conflito de numeração ao criar orçamento")
        flash("Houve um conflito na numeração. Tente salvar novamente.", "error")
    except SQLAlchemyError:
        db.session.rollback()
        logger.exception("Erro ao criar orçamento")
        flash("Não foi possível salvar o orçamento.", "error")

    return render_template("orcamento_form.html", orcamento=None, clientes=clientes)


@orcamentos_bp.route("/<int:orcamento_id>/editar", methods=["GET", "POST"])
@empresa_required
def editar(orcamento_id):
    orcamento = _orcamento_tenant_or_404(orcamento_id)
    clientes = _clientes_ativos()
    if request.method == "GET":
        return render_template("orcamento_form.html", orcamento=orcamento, clientes=clientes)

    if not validar_csrf_token(request.form.get("csrf_token")):
        flash("Erro de segurança. Recarregue a página e tente novamente.", "error")
        return redirect(url_for("orcamentos.editar", orcamento_id=orcamento_id))

    cliente_id = request.form.get("cliente_id", type=int)
    cliente = Cliente.query.filter_by(
        id=cliente_id, empresa_id=g.user.empresa_id, ativo=True
    ).first()
    if not cliente:
        flash("Selecione um cliente válido.", "error")
        return render_template("orcamento_form.html", orcamento=orcamento, clientes=clientes)

    orcamento.cliente_id = cliente.id
    orcamento.data_emissao = _data(request.form.get("data_emissao"), orcamento.data_emissao)
    orcamento.validade_ate = _data(request.form.get("validade_ate"))
    orcamento.condicoes_pagamento = (request.form.get("condicoes_pagamento") or "").strip() or None
    orcamento.prazo_estimado = (request.form.get("prazo_estimado") or "").strip() or None
    orcamento.observacoes_cliente = (request.form.get("observacoes_cliente") or "").strip() or None
    orcamento.observacoes_internas = (request.form.get("observacoes_internas") or "").strip() or None

    try:
        _salvar_itens(orcamento)
        db.session.commit()
        flash("Orçamento atualizado com sucesso.", "success")
        return redirect(url_for("orcamentos.visualizar", orcamento_id=orcamento.id))
    except ValueError as e:
        db.session.rollback()
        flash(str(e), "error")
    except SQLAlchemyError:
        db.session.rollback()
        logger.exception("Erro ao atualizar orçamento")
        flash("Não foi possível atualizar o orçamento.", "error")
    return render_template("orcamento_form.html", orcamento=orcamento, clientes=clientes)


@orcamentos_bp.route("/<int:orcamento_id>")
@empresa_required
def visualizar(orcamento_id):
    orcamento = _orcamento_tenant_or_404(orcamento_id)
    return render_template(
        "orcamento_visualizar.html",
        orcamento=orcamento,
        status_labels=STATUS_LABELS,
        modo_impressao=False,
    )


@orcamentos_bp.route("/<int:orcamento_id>/imprimir")
@empresa_required
def imprimir(orcamento_id):
    orcamento = _orcamento_tenant_or_404(orcamento_id)
    return render_template(
        "orcamento_impressao.html",
        orcamento=orcamento,
        empresa=g.user.empresa,
    )


@orcamentos_bp.route("/<int:orcamento_id>/status", methods=["POST"])
@empresa_required
def alterar_status(orcamento_id):
    orcamento = _orcamento_tenant_or_404(orcamento_id)
    if not validar_csrf_token(request.form.get("csrf_token")):
        flash("Erro de segurança.", "error")
        return redirect(url_for("orcamentos.visualizar", orcamento_id=orcamento_id))

    novo = (request.form.get("status") or "").upper()
    if novo not in STATUS_VALIDOS:
        flash("Status inválido.", "error")
        return redirect(url_for("orcamentos.visualizar", orcamento_id=orcamento_id))
    orcamento.status = novo
    db.session.commit()
    flash(f"Orçamento marcado como {STATUS_LABELS[novo]}.", "success")
    return redirect(url_for("orcamentos.visualizar", orcamento_id=orcamento_id))
