# routes/dashboard_routes.py
# Dashboard Financeiro Inteligente - Refatorado com GROUP BY categoria
# ✅ Compatível com frontend antigo e novo

from flask import (
    Blueprint,
    jsonify,
    request,
    g,
    render_template,
    make_response,
    redirect,
    url_for,
    session,
    abort,
)

from models import (
    db,
    MovBanco,
    MovAdquirente,
    Empresa,
    ArquivoImportado,
    LogAuditoria,
)

from sqlalchemy import func
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from utils.auth_middleware import login_required, empresa_required
import logging
import time

logger = logging.getLogger(__name__)

dashboard_bp = Blueprint("dashboard", __name__)
dashboard_api_bp = Blueprint("dashboard_api", __name__)

RATE_LIMIT_WINDOW = 60
RATE_LIMIT_MAX_REQUESTS = 60
_dashboard_rate_limit_cache = {}


# ============================================================
# HELPERS
# ============================================================

def check_dashboard_rate_limit(user_id: str) -> bool:
    now = time.time()
    key = f"dashboard:{user_id}"

    _dashboard_rate_limit_cache[key] = [
        t for t in _dashboard_rate_limit_cache.get(key, [])
        if now - t < RATE_LIMIT_WINDOW
    ]

    if len(_dashboard_rate_limit_cache.get(key, [])) >= RATE_LIMIT_MAX_REQUESTS:
        return False

    _dashboard_rate_limit_cache.setdefault(key, []).append(now)
    return True


def get_periodo_datas(periodo):
    hoje = datetime.now().date()

    periodos = {
        "geral": (None, hoje),
        "todos": (None, hoje),
        "atual": (hoje.replace(day=1), hoje),
        "mes": (hoje.replace(day=1), hoje),
        "3meses": (hoje - timedelta(days=90), hoje),
        "6meses": (hoje - timedelta(days=180), hoje),
        "12meses": (hoje - timedelta(days=365), hoje),
        "ano": (hoje.replace(month=1, day=1), hoje),
    }

    if periodo == "anterior":
        if hoje.month == 1:
            return (
                hoje.replace(year=hoje.year - 1, month=12, day=1),
                hoje.replace(year=hoje.year - 1, month=12, day=31),
            )
        return (
            hoje.replace(month=hoje.month - 1, day=1),
            hoje.replace(day=1) - timedelta(days=1),
        )

    if periodo == "anoanterior":
        return (
            hoje.replace(year=hoje.year - 1, month=1, day=1),
            hoje.replace(year=hoje.year - 1, month=12, day=31),
        )

    return periodos.get(periodo, (hoje.replace(day=1), hoje))


def _to_float(valor):
    if valor is None:
        return 0.0
    try:
        return float(valor)
    except Exception:
        return 0.0


def _round(valor):
    return round(_to_float(valor), 2)


def _aplicar_periodo(query, campo_data, data_inicio, data_fim):
    if data_inicio:
        query = query.filter(
            campo_data >= data_inicio,
            campo_data <= data_fim,
        )
    return query


# ============================================================
# ROTA RAIZ
# ============================================================

@dashboard_bp.route("/")
def raiz_inteligente():
    usuario = getattr(g, "user", None)

    if usuario and getattr(usuario, "id", None):
        if getattr(usuario, "master", False):
            return redirect(url_for("master.dashboard_operacional_page"))
        return redirect(url_for("dashboard.dashboard"))

    return redirect(url_for("auth.login_page"))


# ============================================================
# ROTA HTML DO DASHBOARD
# ============================================================

@dashboard_bp.route("/dashboard")
@login_required
@empresa_required
def dashboard():
    usuario = g.user

    if getattr(usuario, "master", False):
        return redirect(url_for("master.dashboard_operacional_page"))

    empresa_id = getattr(usuario, "empresa_id", None)

    if not check_dashboard_rate_limit(str(usuario.id)):
        logger.warning(f"Rate limit dashboard: usuario={usuario.id}")

    if not empresa_id:
        logger.error(f"❌ Usuário {usuario.id} sem empresa_id")
        return redirect(url_for("operacoes.importar_page"))

    try:
        empresa = Empresa.query.filter_by(id=empresa_id, ativo=True).first()
        if not empresa:
            return redirect(url_for("auth.logout"))
        empresa_nome = empresa.nome
    except Exception as e:
        logger.error(f"❌ Erro ao verificar empresa: {str(e)}", exc_info=True)
        return redirect(url_for("auth.logout"))

    try:
        log = LogAuditoria(
            usuario_id=usuario.id,
            empresa_id=empresa_id,
            acao="dashboard_acesso",
            detalhes=f"User-Agent: {request.user_agent.string[:100]}",
            ip=request.remote_addr,
            criado_em=datetime.now(timezone.utc),
        )
        db.session.add(log)
        db.session.commit()
    except Exception:
        db.session.rollback()

    try:
        tem_dados = (
            MovAdquirente.query.filter_by(empresa_id=empresa_id).limit(1).count() > 0
            or MovBanco.query.filter_by(empresa_id=empresa_id).limit(1).count() > 0
            or ArquivoImportado.query.filter_by(empresa_id=empresa_id).limit(1).count() > 0
        )

        if not tem_dados:
            return redirect(url_for("operacoes.importar_page"))

    except Exception:
        pass

    contexto = {
        "usuario": usuario,
        "empresa_id": empresa_id,
        "empresa_nome": empresa_nome,
        "is_admin": getattr(usuario, "admin", False),
        "is_master": getattr(usuario, "master", False),
        "current_year": datetime.now().year,
        "csrf_token": getattr(g, "csrf_token", "") or session.get("csrf_token", ""),
    }

    try:
        html = render_template("dashboard.html", **contexto)
        response = make_response(html)
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response

    except Exception as e:
        logger.error(f"❌ Erro ao renderizar dashboard: {str(e)}", exc_info=True)
        abort(500)


# ============================================================
# ROTA DRE
# ============================================================

@dashboard_bp.route("/dre")
@login_required
@empresa_required
def dre_resumo():
    return redirect(url_for("dashboard.dashboard"))


# ============================================================
# API: KPIs DO DASHBOARD
# ============================================================

@dashboard_api_bp.route("/kpis", methods=["GET"])
@dashboard_api_bp.route("/api/v1/dashboard/kpis", methods=["GET"])
@login_required
@empresa_required
def get_dashboard_kpis():
    try:
        periodo = request.args.get("periodo", "12meses")
        empresa_id = g.user.empresa_id

        if not empresa_id:
            return jsonify({"ok": False, "error": "Usuário sem empresa vinculada"}), 403

        data_inicio, data_fim = get_periodo_datas(periodo)

        receitas_por_categoria = _agrupar_por_categoria(
            empresa_id,
            data_inicio,
            data_fim,
            tipo="receita",
        )

        despesas_por_categoria = _agrupar_por_categoria(
            empresa_id,
            data_inicio,
            data_fim,
            tipo="despesa",
        )

        total_entradas = sum(item["total"] for item in receitas_por_categoria)
        total_saidas = sum(item["total"] for item in despesas_por_categoria)
        saldo = total_entradas - total_saidas

        vendas_por_bandeira = _agrupar_por_bandeira(
            empresa_id,
            data_inicio,
            data_fim,
        )

        vendas_cartao_total = sum(vendas_por_bandeira.values())

        receitas_breakdown = _formatar_breakdown(
            receitas_por_categoria,
            total_entradas,
        )

        despesas_breakdown = _formatar_breakdown(
            despesas_por_categoria,
            total_saidas,
        )

        receitas_resumo = _montar_resumo_receitas(
            receitas_por_categoria,
            vendas_cartao_total,
        )

        despesas_resumo = _montar_resumo_despesas(
            despesas_por_categoria,
        )

        insight = _gerar_insight(
            total_entradas,
            total_saidas,
            saldo,
            vendas_cartao_total,
        )

        total_registros = _total_registros_dashboard(empresa_id)

        response = {
            "ok": True,
            "periodo": {
                "inicio": data_inicio.isoformat() if data_inicio else None,
                "fim": data_fim.isoformat() if data_fim else None,
                "tipo": periodo,
            },

            # Contrato novo
            "saldo": _round(saldo),
            "entradas": _round(total_entradas),
            "saidas": _round(total_saidas),
            "vendas_cartao": _round(vendas_cartao_total),
            "vendas_por_bandeira": vendas_por_bandeira,
            "receitas": receitas_resumo,
            "despesas": despesas_resumo,
            "receitas_breakdown": receitas_breakdown,
            "despesas_breakdown": despesas_breakdown,
            "insight": insight,
            "total_registros": total_registros,
        }

        # ========================================================
        # Compatibilidade com JS antigo
        # ========================================================

        response["kpis"] = {
            "total_vendas": _round(vendas_cartao_total),
            "total_recebido": _round(total_entradas),
            "diferenca": _round(saldo),
            "total_vendas_pix": _round(receitas_resumo.get("pix", 0)),
            "alertas": 0,
            "adquirentes": [],
            "bandeiras": vendas_por_bandeira,
            "receitas": receitas_resumo,
            "despesas": despesas_resumo,
            "receitas_breakdown": receitas_breakdown,
            "despesas_breakdown": despesas_breakdown,
            "detalhamento": {
                "vendas": [],
                "recebidos": [],
                "pendentes": [],
            },
        }

        logger.info(
            f"📊 Dashboard KPIs empresa={empresa_id}: "
            f"entradas={total_entradas}, saidas={total_saidas}, saldo={saldo}"
        )

        return jsonify(response), 200

    except Exception as e:
        logger.error(f"❌ Erro ao calcular KPIs: {str(e)}", exc_info=True)
        return jsonify({
            "ok": False,
            "error": "Erro ao processar dados do dashboard",
        }), 500


# ============================================================
# AGRUPAMENTOS
# ============================================================

def _agrupar_por_categoria(empresa_id, data_inicio, data_fim, tipo="receita"):
    resultados = []

    query_banco = db.session.query(
        MovBanco.categoria,
        func.sum(func.abs(MovBanco.valor)).label("total"),
        func.count().label("quantidade"),
    ).filter(
        MovBanco.empresa_id == empresa_id,
        MovBanco.categoria.isnot(None),
        MovBanco.categoria != "",
    )

    if hasattr(MovBanco, "ativo"):
        query_banco = query_banco.filter(MovBanco.ativo == True)

    if tipo == "receita":
        query_banco = query_banco.filter(MovBanco.valor > 0)
    else:
        query_banco = query_banco.filter(MovBanco.valor < 0)

    query_banco = _aplicar_periodo(
        query_banco,
        MovBanco.data_movimento,
        data_inicio,
        data_fim,
    )

    for categoria, total, quantidade in query_banco.group_by(MovBanco.categoria).all():
        total_float = _to_float(total)

        if total_float > 0:
            resultados.append({
                "categoria": categoria or "outros",
                "total": total_float,
                "quantidade": quantidade or 0,
                "origem": "banco",
            })

    if tipo == "receita":
        query_adq = db.session.query(
            MovAdquirente.tipo_pagamento,
            func.sum(MovAdquirente.valor_bruto).label("total"),
            func.count().label("quantidade"),
        ).filter(
            MovAdquirente.empresa_id == empresa_id,
            MovAdquirente.ativo == True,
            MovAdquirente.valor_bruto > 0,
        )

        query_adq = _aplicar_periodo(
            query_adq,
            MovAdquirente.data_venda,
            data_inicio,
            data_fim,
        )

        for tipo_pagamento, total, quantidade in query_adq.group_by(MovAdquirente.tipo_pagamento).all():
            total_float = _to_float(total)

            if total_float > 0:
                categoria = f"vendas_{tipo_pagamento or 'cartao'}"

                existente = next(
                    (item for item in resultados if item["categoria"] == categoria),
                    None,
                )

                if existente:
                    existente["total"] += total_float
                    existente["quantidade"] += quantidade or 0
                else:
                    resultados.append({
                        "categoria": categoria,
                        "total": total_float,
                        "quantidade": quantidade or 0,
                        "origem": "adquirente",
                    })

    return sorted(resultados, key=lambda x: x["total"], reverse=True)


def _agrupar_por_bandeira(empresa_id, data_inicio, data_fim):
    query = db.session.query(
        MovAdquirente.bandeira,
        func.sum(MovAdquirente.valor_bruto).label("total"),
    ).filter(
        MovAdquirente.empresa_id == empresa_id,
        MovAdquirente.ativo == True,
        MovAdquirente.valor_bruto > 0,
        MovAdquirente.bandeira.isnot(None),
        MovAdquirente.bandeira != "",
    )

    query = _aplicar_periodo(
        query,
        MovAdquirente.data_venda,
        data_inicio,
        data_fim,
    )

    bandeiras = {}

    for bandeira, total in query.group_by(MovAdquirente.bandeira).all():
        nome = (bandeira or "Outras").strip().title()
        bandeiras[nome] = _round(total)

    return bandeiras


def _formatar_breakdown(categorias, total_geral):
    breakdown = []

    for item in categorias[:8]:
        percentual = (item["total"] / total_geral * 100) if total_geral > 0 else 0

        breakdown.append({
            "nome": _nome_amigavel(item["categoria"]),
            "categoria": item["categoria"],
            "valor": _round(item["total"]),
            "percentual": round(percentual, 1),
            "quantidade": item["quantidade"],
            "origem": item.get("origem", "banco"),
        })

    return breakdown


# ============================================================
# RESUMOS PARA FRONTEND
# ============================================================

def _montar_resumo_receitas(categorias, vendas_cartao_total):
    def soma(lista):
        return sum(
            item["total"]
            for item in categorias
            if item["categoria"] in lista
        )

    pix = soma([
        "receitas_pix",
        "pix_recebido",
        "vendas_pix",
    ])

    transferencias = soma([
        "transferencias_recebidas",
        "receitas_nao_classificadas",
        "credito_conta",
    ])

    return {
        "cartao": _round(vendas_cartao_total),
        "pix": _round(pix),
        "transferencias": _round(transferencias),
    }


def _montar_resumo_despesas(categorias):
    fornecedores_cats = {
        "transferencias_enviadas",
        "fornecedores_servicos",
        "fornecedores_mercadoria",
        "transporte_combustivel",
        "transporte_pedagio",
        "transporte_estacionamento",
        "alimentacao_restaurante",
        "alimentacao_mercado",
        "supermercado",
    }

    impostos_cats = {
        "impostos_federais",
        "impostos_municipais",
        "impostos_tributos",
        "tributos",
    }

    fornecedores = 0
    impostos = 0
    outras = 0

    for item in categorias:
        cat = item["categoria"]
        total = item["total"]

        if cat in fornecedores_cats:
            fornecedores += total
        elif cat in impostos_cats:
            impostos += total
        else:
            outras += total

    return {
        "fornecedores": _round(fornecedores),
        "impostos": _round(impostos),
        "outras": _round(outras),
    }


def _total_registros_dashboard(empresa_id):
    total = 0

    try:
        total += MovBanco.query.filter_by(empresa_id=empresa_id).count()
    except Exception:
        pass

    try:
        total += MovAdquirente.query.filter_by(empresa_id=empresa_id).count()
    except Exception:
        pass

    return total


# ============================================================
# NOMES AMIGÁVEIS
# ============================================================

def _nome_amigavel(categoria):
    nomes = {
        "transporte_combustivel": "Transporte e Combustível",
        "transporte_pedagio": "Pedágio",
        "transporte_estacionamento": "Estacionamento",
        "alimentacao_restaurante": "Alimentação",
        "alimentacao_mercado": "Mercado",
        "supermercado": "Supermercado",
        "streaming": "Streaming",
        "telefonia": "Telefonia",
        "internet": "Internet",
        "impostos_federais": "Impostos Federais",
        "impostos_municipais": "Impostos Municipais",
        "impostos_tributos": "Impostos e Tributos",
        "tarifas_bancarias": "Tarifas Bancárias",
        "salarios": "Salários",
        "beneficios": "Benefícios",
        "emprestimos": "Empréstimos",
        "investimentos": "Investimentos",
        "transferencias_enviadas": "Transferências Enviadas",
        "transferencias_recebidas": "Transferências Recebidas",
        "receitas_pix": "PIX Recebido",
        "receitas_nao_classificadas": "Outras Receitas",
        "vendas_cartao": "Vendas no Cartão",
        "vendas_pix": "Vendas via PIX",
        "vendas_boleto": "Vendas via Boleto",
        "vendas_elo": "Vendas Elo",
        "fornecedores_servicos": "Fornecedores",
        "fornecedores_mercadoria": "Fornecedores",
        "outras_despesas": "Outras Despesas",
        "outros": "Outros",
    }

    return nomes.get(categoria, str(categoria or "outros").replace("_", " ").title())


def _gerar_insight(entradas, saidas, saldo, vendas_cartao):
    if entradas == 0 and saidas == 0:
        return "Importe seu extrato bancário para visualizar seus KPIs financeiros."

    if vendas_cartao > 0 and entradas > 0:
        percentual = (vendas_cartao / entradas) * 100
        if percentual > 30:
            return f"💳 {percentual:.0f}% das receitas vêm de maquininha. Revise as taxas da adquirente."

    if saldo < 0:
        return "⚠️ Fluxo de caixa negativo. Revise despesas ou acelere recebimentos."

    if entradas > 0 and saldo > entradas * 0.2:
        return f"✅ Excelente! Margem positiva de {(saldo / entradas) * 100:.0f}%."

    if entradas > 0 and saidas > entradas * 0.7:
        return "📉 Suas despesas estão acima de 70% da receita. Revise gastos."

    return "Continue acompanhando seu fluxo de caixa regularmente."


# ============================================================
# API: RESUMO MENSAL
# ============================================================

@dashboard_api_bp.route("/resumo-mensal", methods=["GET"])
@dashboard_api_bp.route("/api/v1/dashboard/resumo-mensal", methods=["GET"])
@login_required
@empresa_required
def get_resumo_mensal():
    try:
        empresa_id = g.user.empresa_id
        hoje = datetime.now().date()
        num_meses = 12

        meses = []

        for i in range(num_meses - 1, -1, -1):
            mes_atual = hoje.month - i
            ano_atual = hoje.year

            while mes_atual <= 0:
                mes_atual += 12
                ano_atual -= 1

            data_inicio = datetime(ano_atual, mes_atual, 1).date()

            if mes_atual == 12:
                data_fim = datetime(ano_atual, 12, 31).date()
            else:
                data_fim = datetime(ano_atual, mes_atual + 1, 1).date() - timedelta(days=1)

            entradas = db.session.query(
                func.sum(MovBanco.valor)
            ).filter(
                MovBanco.empresa_id == empresa_id,
                MovBanco.valor > 0,
                MovBanco.data_movimento >= data_inicio,
                MovBanco.data_movimento <= data_fim,
            ).scalar() or Decimal("0")

            saidas = db.session.query(
                func.sum(func.abs(MovBanco.valor))
            ).filter(
                MovBanco.empresa_id == empresa_id,
                MovBanco.valor < 0,
                MovBanco.data_movimento >= data_inicio,
                MovBanco.data_movimento <= data_fim,
            ).scalar() or Decimal("0")

            meses.append({
                "mes": f"{mes_atual:02d}/{ano_atual}",
                "entradas": _round(entradas),
                "saidas": _round(saidas),
                "saldo": _round(_to_float(entradas) - _to_float(saidas)),
            })

        return jsonify({
            "ok": True,
            "meses": meses,
        }), 200

    except Exception as e:
        logger.error(f"❌ Erro ao calcular resumo mensal: {str(e)}", exc_info=True)
        return jsonify({
            "ok": False,
            "error": str(e),
        }), 500