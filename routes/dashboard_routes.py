# routes/dashboard_routes.py
# Dashboard Financeiro Inteligente
# ✅ Corrigido: entradas/saídas por sinal + categoria inteligente
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


def _categoria_eh_receita(categoria):
    cat = str(categoria or "").lower()

    return (
        cat.startswith("receita")
        or cat.startswith("receitas")
        or cat.startswith("venda")
        or cat.startswith("vendas")
        or cat in {
            "pix_recebido",
            "transferencias_recebidas",
            "transferencia_recebida",
            "credito_conta",
            "credito_em_conta",
            "crédito_em_conta",
        }
    )


def _categoria_eh_despesa(categoria):
    cat = str(categoria or "").lower()

    return (
        cat.startswith("despesa")
        or cat.startswith("despesas")
        or cat in {
            "transferencias_enviadas",
            "transferencia_enviada",
            "impostos_federais",
            "impostos_municipais",
            "impostos_tributos",
            "tributos",
            "internet",
            "telefonia",
            "streaming",
            "transporte_combustivel",
            "transporte_pedagio",
            "transporte_estacionamento",
            "alimentacao_restaurante",
            "alimentacao_mercado",
            "supermercado",
            "emprestimos",
            "outras_despesas",
            "tarifas_bancarias",
            "fornecedores_servicos",
            "fornecedores_mercadoria",
        }
    )


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
            empresa_id, data_inicio, data_fim, tipo="receita"
        )

        despesas_por_categoria = _agrupar_por_categoria(
            empresa_id, data_inicio, data_fim, tipo="despesa"
        )

        total_entradas = sum(item["total"] for item in receitas_por_categoria)
        total_saidas = sum(item["total"] for item in despesas_por_categoria)
        saldo = total_entradas - total_saidas
        margem_caixa = (saldo / total_entradas * 100) if total_entradas > 0 else 0
        indice_despesa = (total_saidas / total_entradas * 100) if total_entradas > 0 else 0

        vendas_por_bandeira = _agrupar_por_bandeira(
            empresa_id, data_inicio, data_fim
        )

        vendas_cartao_total = sum(vendas_por_bandeira.values())

        receitas_breakdown = _formatar_breakdown(
            receitas_por_categoria, total_entradas
        )

        despesas_breakdown = _formatar_breakdown(
            despesas_por_categoria, total_saidas
        )

        receitas_resumo = _montar_resumo_receitas(
            receitas_por_categoria, vendas_cartao_total
        )

        despesas_resumo = _montar_resumo_despesas(
            despesas_por_categoria
        )

        despesas_por_grupo = _montar_despesas_por_grupo(
            despesas_por_categoria,
            total_saidas
        )

        top_receitas = _top_categorias(
            receitas_por_categoria,
            total_entradas,
            limite=5
        )

        top_despesas = _top_categorias(
            despesas_por_categoria,
            total_saidas,
            limite=5
        )

        diagnostico = _gerar_diagnostico_dashboard(
            entradas=total_entradas,
            saidas=total_saidas,
            saldo=saldo,
            margem_caixa=margem_caixa,
            indice_despesa=indice_despesa,
            top_receitas=top_receitas,
            top_despesas=top_despesas,
            vendas_cartao=vendas_cartao_total,
        )

        insight = diagnostico.get("mensagem_principal") or _gerar_insight(
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

            # KPIs principais
            "saldo": _round(saldo),
            "entradas": _round(total_entradas),
            "saidas": _round(total_saidas),
            "margem_caixa": _round(margem_caixa),
            "indice_despesa": _round(indice_despesa),

            # Cartões/adquirentes
            "vendas_cartao": _round(vendas_cartao_total),
            "vendas_por_bandeira": vendas_por_bandeira,

            # Resumos atuais
            "receitas": receitas_resumo,
            "despesas": despesas_resumo,
            "receitas_breakdown": receitas_breakdown,
            "despesas_breakdown": despesas_breakdown,

            # Nova camada gerencial
            "top_receitas": top_receitas,
            "top_despesas": top_despesas,
            "despesas_por_grupo": despesas_por_grupo,
            "diagnostico": diagnostico,

            # Compatibilidade
            "insight": insight,
            "total_registros": total_registros,
        }

        response["kpis"] = {
            "total_vendas": _round(vendas_cartao_total),
            "total_recebido": _round(total_entradas),
            "diferenca": _round(saldo),
            "total_vendas_pix": _round(receitas_resumo.get("pix", 0)),
            "alertas": len(diagnostico.get("alertas", [])),
            "adquirentes": [],
            "bandeiras": vendas_por_bandeira,
            "receitas": receitas_resumo,
            "despesas": despesas_resumo,
            "receitas_breakdown": receitas_breakdown,
            "despesas_breakdown": despesas_breakdown,
            "margem_caixa": _round(margem_caixa),
            "indice_despesa": _round(indice_despesa),
            "top_receitas": top_receitas,
            "top_despesas": top_despesas,
            "despesas_por_grupo": despesas_por_grupo,
            "diagnostico": diagnostico,
            "detalhamento": {
                "vendas": [],
                "recebidos": [],
                "pendentes": [],
            },
        }

        logger.info(
            f"📊 Dashboard KPIs empresa={empresa_id}: "
            f"entradas={total_entradas}, saidas={total_saidas}, "
            f"saldo={saldo}, margem={margem_caixa:.2f}%"
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
    resultados_map = {}

    query_banco = MovBanco.query.filter(
        MovBanco.empresa_id == empresa_id,
    )

    if hasattr(MovBanco, "ativo"):
        query_banco = query_banco.filter(MovBanco.ativo == True)

    query_banco = _aplicar_periodo(
        query_banco,
        MovBanco.data_movimento,
        data_inicio,
        data_fim,
    )

    movimentos = query_banco.all()

    for mov in movimentos:
        categoria = mov.categoria or "outros"
        valor = _to_float(mov.valor)

        if valor == 0:
            continue

        eh_receita = _categoria_eh_receita(categoria)
        eh_despesa = _categoria_eh_despesa(categoria)

        incluir = False
        total = 0.0

        if tipo == "receita":
            if eh_receita:
                incluir = True
                total = abs(valor)
            elif valor > 0 and not eh_despesa:
                incluir = True
                total = valor

        else:
            if eh_receita:
                incluir = False
            elif valor < 0:
                incluir = True
                total = abs(valor)

        if not incluir:
            continue

        if categoria not in resultados_map:
            resultados_map[categoria] = {
                "categoria": categoria,
                "total": 0.0,
                "quantidade": 0,
                "origem": "banco",
            }

        resultados_map[categoria]["total"] += total
        resultados_map[categoria]["quantidade"] += 1

    resultados = list(resultados_map.values())

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
        "credito_em_conta",
        "crédito_em_conta",
    ])

    outras_receitas = sum(
        item["total"]
        for item in categorias
        if item["categoria"] not in {
            "receitas_pix",
            "pix_recebido",
            "vendas_pix",
            "transferencias_recebidas",
            "receitas_nao_classificadas",
            "credito_conta",
            "credito_em_conta",
            "crédito_em_conta",
        }
        and item["categoria"].startswith(("receita", "receitas"))
    )

    return {
        "cartao": _round(vendas_cartao_total),
        "pix": _round(pix),
        "transferencias": _round(transferencias + outras_receitas),
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

def _montar_despesas_por_grupo(categorias, total_saidas):
    grupos_definicao = {
        "transferencias": {
            "nome": "Transferências Enviadas",
            "icone": "🔁",
            "categorias": {
                "transferencias_enviadas",
                "transferencia_enviada",
            },
        },
        "alimentacao": {
            "nome": "Alimentação",
            "icone": "🍽️",
            "categorias": {
                "alimentacao_restaurante",
                "alimentacao_mercado",
                "supermercado",
            },
        },
        "transporte": {
            "nome": "Transporte",
            "icone": "⛽",
            "categorias": {
                "transporte_combustivel",
                "transporte_pedagio",
                "transporte_estacionamento",
            },
        },
        "impostos": {
            "nome": "Impostos e Tributos",
            "icone": "🏛️",
            "categorias": {
                "impostos_federais",
                "impostos_municipais",
                "impostos_tributos",
                "tributos",
            },
        },
        "servicos": {
            "nome": "Serviços Essenciais",
            "icone": "📡",
            "categorias": {
                "internet",
                "telefonia",
                "energia",
                "agua",
                "energia_agua_telecom",
            },
        },
        "financeiro": {
            "nome": "Financeiro",
            "icone": "🏦",
            "categorias": {
                "emprestimos",
                "tarifas_bancarias",
                "juros",
                "taxas",
            },
        },
        "assinaturas": {
            "nome": "Assinaturas",
            "icone": "🎬",
            "categorias": {
                "streaming",
                "assinaturas",
                "software",
            },
        },
    }

    grupos = {}

    for chave, config in grupos_definicao.items():
        grupos[chave] = {
            "chave": chave,
            "nome": config["nome"],
            "icone": config["icone"],
            "valor": 0.0,
            "percentual": 0.0,
            "quantidade": 0,
            "categorias": [],
        }

    outros = {
        "chave": "outros",
        "nome": "Outras Despesas",
        "icone": "📦",
        "valor": 0.0,
        "percentual": 0.0,
        "quantidade": 0,
        "categorias": [],
    }

    for item in categorias:
        categoria = item.get("categoria")
        valor = _to_float(item.get("total"))
        quantidade = item.get("quantidade", 0)

        grupo_encontrado = None

        for chave, config in grupos_definicao.items():
            if categoria in config["categorias"]:
                grupo_encontrado = chave
                break

        destino = grupos.get(grupo_encontrado) if grupo_encontrado else outros

        destino["valor"] += valor
        destino["quantidade"] += quantidade
        destino["categorias"].append({
            "categoria": categoria,
            "nome": _nome_amigavel(categoria),
            "valor": _round(valor),
            "quantidade": quantidade,
            "percentual": round((valor / total_saidas * 100), 1) if total_saidas > 0 else 0,
        })

    resultado = []

    for grupo in list(grupos.values()) + [outros]:
        if grupo["valor"] <= 0:
            continue

        grupo["valor"] = _round(grupo["valor"])
        grupo["percentual"] = round((grupo["valor"] / total_saidas * 100), 1) if total_saidas > 0 else 0
        grupo["categorias"] = sorted(
            grupo["categorias"],
            key=lambda x: x["valor"],
            reverse=True
        )

        resultado.append(grupo)

    return sorted(resultado, key=lambda x: x["valor"], reverse=True)


def _top_categorias(categorias, total_geral, limite=5):
    resultado = []

    for item in categorias[:limite]:
        valor = _to_float(item.get("total"))
        categoria = item.get("categoria")

        resultado.append({
            "categoria": categoria,
            "nome": _nome_amigavel(categoria),
            "valor": _round(valor),
            "percentual": round((valor / total_geral * 100), 1) if total_geral > 0 else 0,
            "quantidade": item.get("quantidade", 0),
            "origem": item.get("origem", "banco"),
        })

    return resultado

def _gerar_diagnostico_dashboard(
    entradas,
    saidas,
    saldo,
    margem_caixa,
    indice_despesa,
    top_receitas,
    top_despesas,
    vendas_cartao,
):
    alertas = []
    oportunidades = []
    pontos_positivos = []

    maior_receita = top_receitas[0] if top_receitas else None
    maior_despesa = top_despesas[0] if top_despesas else None

    if entradas <= 0 and saidas <= 0:
        return {
            "nivel": "sem_dados",
            "titulo": "Sem dados suficientes",
            "mensagem_principal": "Importe seu extrato bancário para visualizar seus KPIs financeiros.",
            "alertas": [],
            "oportunidades": ["Importar OFX ou CSV bancário para iniciar a análise."],
            "pontos_positivos": [],
            "resumo": {
                "margem_caixa": 0,
                "indice_despesa": 0,
                "maior_receita": None,
                "maior_despesa": None,
            },
        }

    if saldo > 0:
        pontos_positivos.append(f"Fluxo positivo no período: R$ {_round(saldo):,.2f}.")
    else:
        alertas.append(f"Fluxo negativo no período: R$ {_round(abs(saldo)):,.2f}.")

    if margem_caixa < 0:
        alertas.append("A operação consumiu mais caixa do que gerou no período.")
    elif margem_caixa < 10:
        alertas.append(f"Margem de caixa apertada: {margem_caixa:.1f}%.")
    elif margem_caixa < 20:
        oportunidades.append(f"Margem de caixa positiva, mas ainda moderada: {margem_caixa:.1f}%.")
    else:
        pontos_positivos.append(f"Boa margem de caixa: {margem_caixa:.1f}%.")

    if indice_despesa > 90:
        alertas.append(f"Despesas consumiram {indice_despesa:.1f}% das entradas.")
    elif indice_despesa > 70:
        oportunidades.append(f"Despesas acima de 70% das entradas: {indice_despesa:.1f}%.")
    else:
        pontos_positivos.append(f"Despesas controladas: {indice_despesa:.1f}% das entradas.")

    if maior_despesa:
        oportunidades.append(
            f"Maior grupo de saída: {maior_despesa['nome']} "
            f"com R$ {maior_despesa['valor']:,.2f} "
            f"({maior_despesa['percentual']}%)."
        )

    if maior_receita:
        pontos_positivos.append(
            f"Principal fonte de entrada: {maior_receita['nome']} "
            f"com R$ {maior_receita['valor']:,.2f}."
        )

    if vendas_cartao <= 0:
        oportunidades.append("Nenhuma venda de cartão/adquirente identificada no período.")
    elif entradas > 0:
        percentual_cartao = (vendas_cartao / entradas) * 100
        if percentual_cartao > 30:
            oportunidades.append(
                f"{percentual_cartao:.1f}% das entradas vêm de cartão. Vale revisar taxas da adquirente."
            )

    if saldo < 0:
        nivel = "critico"
        titulo = "Fluxo negativo"
        mensagem = "⚠️ O caixa fechou negativo. Revise despesas e acelere recebimentos."
    elif margem_caixa < 10:
        nivel = "atencao"
        titulo = "Fluxo positivo, mas apertado"
        mensagem = f"✅ O caixa fechou positivo, porém com margem de apenas {margem_caixa:.1f}%."
    elif indice_despesa > 70:
        nivel = "atencao"
        titulo = "Despesas elevadas"
        mensagem = f"📉 As despesas consumiram {indice_despesa:.1f}% das entradas."
    else:
        nivel = "saudavel"
        titulo = "Fluxo saudável"
        mensagem = f"✅ O período teve saldo positivo e margem de caixa de {margem_caixa:.1f}%."

    return {
        "nivel": nivel,
        "titulo": titulo,
        "mensagem_principal": mensagem,
        "alertas": alertas,
        "oportunidades": oportunidades,
        "pontos_positivos": pontos_positivos,
        "resumo": {
            "margem_caixa": _round(margem_caixa),
            "indice_despesa": _round(indice_despesa),
            "maior_receita": maior_receita,
            "maior_despesa": maior_despesa,
        },
    }
    

def _total_registros_dashboard(empresa_id):
    total = 0

    try:
        query = MovBanco.query.filter_by(empresa_id=empresa_id)
        if hasattr(MovBanco, "ativo"):
            query = query.filter(MovBanco.ativo == True)
        total += query.count()
    except Exception:
        pass

    try:
        query = MovAdquirente.query.filter_by(empresa_id=empresa_id)
        if hasattr(MovAdquirente, "ativo"):
            query = query.filter(MovAdquirente.ativo == True)
        total += query.count()
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
        "credito_conta": "Crédito em Conta",
        "credito_em_conta": "Crédito em Conta",
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

            entradas_categorias = _agrupar_por_categoria(
                empresa_id,
                data_inicio,
                data_fim,
                tipo="receita",
            )

            saidas_categorias = _agrupar_por_categoria(
                empresa_id,
                data_inicio,
                data_fim,
                tipo="despesa",
            )

            entradas = sum(item["total"] for item in entradas_categorias)
            saidas = sum(item["total"] for item in saidas_categorias)

            meses.append({
                "mes": f"{mes_atual:02d}/{ano_atual}",
                "entradas": _round(entradas),
                "saidas": _round(saidas),
                "saldo": _round(entradas - saidas),
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
