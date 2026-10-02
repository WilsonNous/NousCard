from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation

from flask import Blueprint, flash, g, jsonify, redirect, render_template, request, session, url_for
from sqlalchemy import func

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

# Grupos usados pelo detalhamento sob demanda. Os grupos de despesa espelham
# o dashboard; os de receita espelham os resumos exibidos na Visão Financeira.
GRUPOS_DETALHE = {
    "alimentacao": {"nome": "Alimentação", "icone": "🍽️", "tipo": "despesa", "categorias": ["alimentacao_restaurante", "alimentacao_mercado", "supermercado"]},
    "transporte": {"nome": "Transporte", "icone": "⛽", "tipo": "despesa", "categorias": ["transporte_combustivel", "transporte_pedagio", "transporte_estacionamento"]},
    "impostos": {"nome": "Impostos e tributos", "icone": "🏛️", "tipo": "despesa", "categorias": ["impostos_federais", "impostos_municipais", "impostos_tributos", "tributos"]},
    "transferencias_enviadas": {"nome": "Transferências enviadas", "icone": "🔁", "tipo": "despesa", "categorias": ["transferencias_enviadas", "transferencia_enviada"]},
    "servicos": {"nome": "Serviços essenciais", "icone": "📡", "tipo": "despesa", "categorias": ["internet", "telefonia", "energia", "agua", "energia_agua_telecom"]},
    "financeiro": {"nome": "Financeiro", "icone": "🏦", "tipo": "despesa", "categorias": ["emprestimos", "tarifas_bancarias", "juros", "taxas"]},
    "assinaturas": {"nome": "Assinaturas", "icone": "🎬", "tipo": "despesa", "categorias": ["streaming", "assinaturas", "software"]},
    "fornecedores": {"nome": "Fornecedores e operação", "icone": "🏪", "tipo": "despesa", "categorias": ["transferencias_enviadas", "transferencia_enviada", "fornecedores_servicos", "fornecedores_mercadoria", "transporte_combustivel", "transporte_pedagio", "transporte_estacionamento", "alimentacao_restaurante", "alimentacao_mercado", "supermercado"]},
    "outras_despesas": {"nome": "Outras despesas", "icone": "📦", "tipo": "despesa", "categorias": []},
    "pix_recebido": {"nome": "PIX recebido", "icone": "⚡", "tipo": "receita", "categorias": ["receitas_pix", "pix_recebido", "vendas_pix"]},
    "transferencias_recebidas": {"nome": "Transferências recebidas", "icone": "🏦", "tipo": "receita", "categorias": ["transferencias_recebidas", "receitas_nao_classificadas", "credito_conta", "credito_em_conta", "crédito_em_conta"]},
}


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


def _periodo_datas(periodo):
    hoje = datetime.now().date()
    if periodo in {"geral", "todos"}:
        return None, hoje
    if periodo in {"atual", "mes"}:
        return hoje.replace(day=1), hoje
    if periodo == "anterior":
        fim_anterior = hoje.replace(day=1) - timedelta(days=1)
        return fim_anterior.replace(day=1), fim_anterior
    if periodo == "3meses":
        return hoje - timedelta(days=90), hoje
    if periodo == "6meses":
        return hoje - timedelta(days=180), hoje
    if periodo == "ano":
        return hoje.replace(month=1, day=1), hoje
    if periodo == "anoanterior":
        ano = hoje.year - 1
        return hoje.replace(year=ano, month=1, day=1), hoje.replace(year=ano, month=12, day=31)
    return hoje - timedelta(days=365), hoje


def _categorias_grupos_despesa_principais():
    categorias = set()
    for slug, config in GRUPOS_DETALHE.items():
        if config.get("tipo") == "despesa" and slug not in {"outras_despesas", "fornecedores"}:
            categorias.update(config["categorias"])
    return categorias


@lancamentos_bp.route("/detalhes", methods=["GET"])
@login_required
@empresa_required
def detalhes_grupo():
    """Drill-down sob demanda por grupo ou categoria da Visão Financeira."""
    grupo_slug = (request.args.get("grupo") or "").strip().lower()
    categoria = (request.args.get("categoria") or "").strip()
    natureza = (request.args.get("natureza") or "").strip().lower()
    periodo = (request.args.get("periodo") or "12meses").strip().lower()
    limite = min(max(request.args.get("limite", 100, type=int), 1), 200)
    grupo = GRUPOS_DETALHE.get(grupo_slug) if grupo_slug else None

    if not grupo and not categoria:
        return jsonify({"ok": False, "error": "Informe um grupo ou categoria financeira válida."}), 400
    if categoria and natureza not in {"receita", "despesa"}:
        return jsonify({"ok": False, "error": "Natureza financeira inválida."}), 400

    tipo = grupo.get("tipo") if grupo else natureza
    data_inicio, data_fim = _periodo_datas(periodo)
    query = MovBanco.query.filter(MovBanco.empresa_id == g.user.empresa_id)
    if hasattr(MovBanco, "ativo"):
        query = query.filter(MovBanco.ativo == True)

    # Mantém a mesma semântica do dashboard: despesas são movimentos negativos;
    # receitas bancárias são positivas ou categorias explicitamente de receita.
    if tipo == "despesa":
        query = query.filter(MovBanco.valor < 0)
    else:
        query = query.filter(MovBanco.valor > 0)

    if categoria:
        query = query.filter(MovBanco.categoria == categoria)
        nome = categoria.replace("_", " ").strip().title()
        icone = "📈" if tipo == "receita" else "📉"
    else:
        nome = grupo["nome"]
        icone = grupo["icone"]
        if grupo_slug == "outras_despesas":
            query = query.filter(~MovBanco.categoria.in_(_categorias_grupos_despesa_principais()))
        else:
            query = query.filter(MovBanco.categoria.in_(grupo["categorias"]))

    if data_inicio:
        query = query.filter(MovBanco.data_movimento >= data_inicio)
    query = query.filter(MovBanco.data_movimento <= data_fim)

    quantidade, total = query.with_entities(
        func.count(MovBanco.id),
        func.coalesce(func.sum(func.abs(MovBanco.valor)), 0),
    ).one()
    quantidade = int(quantidade or 0)
    total = Decimal(str(total or 0))
    media = (total / quantidade) if quantidade else Decimal("0")

    movimentos = query.order_by(MovBanco.data_movimento.desc(), MovBanco.id.desc()).limit(limite).all()
    itens = [{
        "id": mov.id,
        "data": mov.data_movimento.isoformat() if mov.data_movimento else None,
        "descricao": mov.historico or "Movimento sem descrição",
        "categoria": mov.categoria,
        "subcategoria": mov.subcategoria,
        "origem": mov.origem,
        "banco": mov.banco,
        "valor": float(abs(Decimal(str(mov.valor or 0)))),
        "conciliado": bool(mov.conciliado),
    } for mov in movimentos]

    return jsonify({
        "ok": True,
        "grupo": grupo_slug or None,
        "categoria": categoria or None,
        "natureza": tipo,
        "nome": nome,
        "icone": icone,
        "periodo": periodo,
        "total": float(total),
        "quantidade": quantidade,
        "media": float(media),
        "limitado": quantidade > limite,
        "itens": itens,
    })


@lancamentos_bp.after_app_request
def carregar_drilldown_financeiro(response):
    """Carrega o JS apenas na Visão Financeira; as demais telas não pagam esse custo."""
    if request.endpoint != "dashboard.financeiro" or not response.content_type.startswith("text/html"):
        return response

    html = response.get_data(as_text=True)
    if "</body>" in html and "financeiro-drilldown.js" not in html:
        script = '<script src="/static/js/financeiro-drilldown.js?v=2" defer></script>'
        response.set_data(html.replace("</body>", f"{script}\n</body>", 1))
        response.headers["Content-Length"] = len(response.get_data())
    return response


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