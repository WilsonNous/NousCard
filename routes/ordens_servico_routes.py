import logging
from datetime import date
from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError
from flask import Blueprint, render_template, request, redirect, url_for, flash, g

from models import db, Orcamento, OrdemServico
from utils.auth_middleware import empresa_required, validar_csrf_token

logger = logging.getLogger(__name__)
ordens_servico_bp = Blueprint("ordens_servico", __name__)

STATUS_LABELS = {
    "AGUARDANDO_MATERIAL": "Aguardando material",
    "MATERIAL_RECEBIDO": "Material recebido",
    "AGENDADO": "Agendado",
    "EM_EXECUCAO": "Em execução",
    "CONCLUIDO": "Concluído",
    "CANCELADO": "Cancelado",
}


def _os_tenant_or_404(os_id):
    return OrdemServico.query.filter_by(
        id=os_id, empresa_id=g.user.empresa_id, ativo=True
    ).first_or_404()


def _proximo_numero():
    atual = db.session.query(func.max(OrdemServico.numero)).filter(
        OrdemServico.empresa_id == g.user.empresa_id
    ).scalar()
    return int(atual or 0) + 1


@ordens_servico_bp.route("/")
@empresa_required
def listar():
    ordens = OrdemServico.query.filter_by(
        empresa_id=g.user.empresa_id, ativo=True
    ).order_by(OrdemServico.numero.desc()).all()
    return render_template("ordens_servico_listar.html", ordens=ordens, status_labels=STATUS_LABELS)


@ordens_servico_bp.route("/gerar/<int:orcamento_id>", methods=["POST"])
@empresa_required
def gerar_de_orcamento(orcamento_id):
    if not validar_csrf_token(request.form.get("csrf_token")):
        flash("Erro de segurança.", "error")
        return redirect(url_for("orcamentos.visualizar", orcamento_id=orcamento_id))

    orcamento = Orcamento.query.filter_by(
        id=orcamento_id, empresa_id=g.user.empresa_id, ativo=True
    ).first_or_404()

    if orcamento.status != "APROVADO":
        flash("A Ordem de Serviço só pode ser gerada de um orçamento aprovado.", "warning")
        return redirect(url_for("orcamentos.visualizar", orcamento_id=orcamento_id))

    if orcamento.ordem_servico:
        flash("Este orçamento já possui uma Ordem de Serviço.", "info")
        return redirect(url_for("ordens_servico.visualizar", os_id=orcamento.ordem_servico.id))

    tecnicas = []
    descricoes = []
    for item in orcamento.itens:
        descricoes.append(item.descricao)
        bloco = f"{item.descricao}"
        if item.medidas:
            bloco += f" | Medidas: {item.medidas}"
        if item.informacoes_tecnicas:
            bloco += f"\n{item.informacoes_tecnicas}"
        tecnicas.append(bloco)

    ordem = OrdemServico(
        empresa_id=g.user.empresa_id,
        orcamento_id=orcamento.id,
        cliente_id=orcamento.cliente_id,
        numero=_proximo_numero(),
        status="AGUARDANDO_MATERIAL",
        endereco_execucao=orcamento.cliente.endereco,
        descricao_execucao="\n".join(descricoes),
        informacoes_tecnicas="\n\n".join(tecnicas),
        observacoes=orcamento.observacoes_internas,
        ativo=True,
    )
    try:
        db.session.add(ordem)
        db.session.commit()
        flash(f"Ordem de Serviço OS-{ordem.numero_formatado} criada com sucesso.", "success")
        return redirect(url_for("ordens_servico.visualizar", os_id=ordem.id))
    except SQLAlchemyError:
        db.session.rollback()
        logger.exception("Erro ao gerar OS")
        flash("Não foi possível gerar a Ordem de Serviço.", "error")
        return redirect(url_for("orcamentos.visualizar", orcamento_id=orcamento_id))


@ordens_servico_bp.route("/<int:os_id>", methods=["GET", "POST"])
@empresa_required
def visualizar(os_id):
    ordem = _os_tenant_or_404(os_id)
    if request.method == "POST":
        if not validar_csrf_token(request.form.get("csrf_token")):
            flash("Erro de segurança.", "error")
            return redirect(url_for("ordens_servico.visualizar", os_id=os_id))
        novo_status = (request.form.get("status") or "").upper()
        if novo_status in STATUS_LABELS:
            ordem.status = novo_status
        ordem.endereco_execucao = (request.form.get("endereco_execucao") or "").strip() or None
        ordem.responsavel = (request.form.get("responsavel") or "").strip() or None
        ordem.descricao_execucao = (request.form.get("descricao_execucao") or "").strip() or None
        ordem.informacoes_tecnicas = (request.form.get("informacoes_tecnicas") or "").strip() or None
        ordem.observacoes = (request.form.get("observacoes") or "").strip() or None
        data_prevista = request.form.get("data_prevista")
        if data_prevista:
            try:
                ordem.data_prevista = date.fromisoformat(data_prevista)
            except ValueError:
                pass
        else:
            ordem.data_prevista = None
        try:
            db.session.commit()
            flash("Ordem de Serviço atualizada.", "success")
        except SQLAlchemyError:
            db.session.rollback()
            logger.exception("Erro ao atualizar OS")
            flash("Não foi possível atualizar a Ordem de Serviço.", "error")
        return redirect(url_for("ordens_servico.visualizar", os_id=os_id))

    return render_template("ordem_servico_visualizar.html", ordem=ordem, status_labels=STATUS_LABELS)
