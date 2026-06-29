# routes/dashboard_routes.py
# Dashboard Financeiro Inteligente - Refatorado com GROUP BY categoria

from flask import Blueprint, jsonify, request, g, render_template, make_response, redirect, url_for, session, abort
from models import db, MovBanco, MovAdquirente, Empresa, ArquivoImportado, LogAuditoria
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
        t for t in _dashboard_rate_limit_cache.get(key, []) if now - t < RATE_LIMIT_WINDOW
    ]
    if len(_dashboard_rate_limit_cache.get(key, [])) >= RATE_LIMIT_MAX_REQUESTS:
        return False
    _dashboard_rate_limit_cache.setdefault(key, []).append(now)
    return True


def get_periodo_datas(periodo):
    hoje = datetime.now().date()
    periodos = {
        'geral': (None, hoje),
        'atual': (hoje.replace(day=1), hoje),
        '3meses': (hoje - timedelta(days=90), hoje),
        '6meses': (hoje - timedelta(days=180), hoje),
        '12meses': (hoje - timedelta(days=365), hoje),
        'ano': (hoje.replace(month=1, day=1), hoje),
    }
    
    if periodo == 'anterior':
        if hoje.month == 1:
            return hoje.replace(year=hoje.year-1, month=12, day=1), hoje.replace(year=hoje.year-1, month=12, day=31)
        return hoje.replace(month=hoje.month-1, day=1), hoje.replace(day=1) - timedelta(days=1)
    
    if periodo == 'anoanterior':
        return hoje.replace(year=hoje.year-1, month=1, day=1), hoje.replace(year=hoje.year-1, month=12, day=31)
    
    return periodos.get(periodo, (hoje.replace(day=1), hoje))


# ============================================================
# ROTA RAIZ
# ============================================================

@dashboard_bp.route("/")
def raiz_inteligente():
    usuario = getattr(g, 'user', None)
    if usuario and getattr(usuario, 'id', None):
        if getattr(usuario, 'master', False):
            return redirect(url_for('master.dashboard_operacional_page'))
        return redirect(url_for('dashboard.dashboard'))
    return redirect(url_for('auth.login_page'))


# ============================================================
# ROTA HTML DO DASHBOARD
# ============================================================

@dashboard_bp.route("/dashboard")
@login_required
@empresa_required
def dashboard():
    usuario = g.user
    
    if getattr(usuario, 'master', False):
        return redirect(url_for('master.dashboard_operacional_page'))
    
    empresa_id = getattr(usuario, 'empresa_id', None)
    
    if not check_dashboard_rate_limit(str(usuario.id)):
        logger.warning(f"Rate limit: usuario={usuario.id}")
    
    if not empresa_id:
        logger.error(f"❌ Usuário {usuario.id} sem empresa_id")
        return redirect(url_for('operacoes.importar_page'))
    
    try:
        empresa = Empresa.query.filter_by(id=empresa_id, ativo=True).first()
        if not empresa:
            return redirect(url_for('auth.logout'))
        empresa_nome = empresa.nome
    except Exception as e:
        logger.error(f"❌ Erro ao verificar empresa: {str(e)}")
        return redirect(url_for('auth.logout'))
    
    # Log de auditoria
    try:
        log = LogAuditoria(
            usuario_id=usuario.id, empresa_id=empresa_id,
            acao="dashboard_acesso",
            detalhes=f"User-Agent: {request.user_agent.string[:100]}",
            ip=request.remote_addr, criado_em=datetime.now(timezone.utc)
        )
        db.session.add(log)
        db.session.commit()
    except Exception:
        pass
    
    # Onboarding: redirecionar se não tiver dados
    try:
        tem_dados = (
            MovAdquirente.query.filter_by(empresa_id=empresa_id).limit(1).count() > 0 or
            MovBanco.query.filter_by(empresa_id=empresa_id).limit(1).count() > 0 or
            ArquivoImportado.query.filter_by(empresa_id=empresa_id).limit(1).count() > 0
        )
        if not tem_dados:
            return redirect(url_for('operacoes.importar_page'))
    except Exception:
        pass
    
    contexto = {
        "usuario": usuario,
        "empresa_id": empresa_id,
        "empresa_nome": empresa_nome,
        "is_admin": getattr(usuario, 'admin', False),
        "is_master": getattr(usuario, 'master', False),
        "current_year": datetime.now().year,
        "csrf_token": getattr(g, 'csrf_token', '') or session.get('csrf_token', ''),
    }
    
    try:
        html = render_template("dashboard.html", **contexto)
        response = make_response(html)
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        return response
    except Exception as e:
        logger.error(f"❌ Erro ao renderizar dashboard: {str(e)}", exc_info=True)
        abort(500)


# ============================================================
# ✅ ROTA DRE (COMPATIBILIDADE COM base.html)
# ============================================================

@dashboard_bp.route("/dre")
@login_required
@empresa_required
def dre_resumo():
    """
    DRE - Demonstrativo de Resultado do Exercício.
    Redireciona para o dashboard principal.
    Implementação completa do DRE será feita futuramente.
    """
    return redirect(url_for('dashboard.dashboard'))


# ============================================================
# API: KPIs DO DASHBOARD (REFATORADO COM GROUP BY)
# ============================================================

@dashboard_api_bp.route('/kpis', methods=['GET'])
@login_required
@empresa_required
def get_dashboard_kpis():
    """
    API principal do dashboard.
    ✅ USA GROUP BY categoria em vez de dezenas de LIKEs.
    """
    try:
        periodo = request.args.get('periodo', '12meses')
        empresa_id = g.user.empresa_id
        
        if not empresa_id:
            return jsonify({'ok': False, 'error': 'Usuário sem empresa vinculada'}), 403
        
        data_inicio, data_fim = get_periodo_datas(periodo)
        
        # ============================================================
        # RECEITAS: GROUP BY categoria (entradas)
        # ============================================================
        receitas_por_categoria = _agrupar_por_categoria(
            empresa_id, data_inicio, data_fim, tipo='receita'
        )
        
        # ============================================================
        # DESPESAS: GROUP BY categoria (saídas)
        # ============================================================
        despesas_por_categoria = _agrupar_por_categoria(
            empresa_id, data_inicio, data_fim, tipo='despesa'
        )
        
        # ============================================================
        # TOTAIS
        # ============================================================
        total_entradas = sum(item['total'] for item in receitas_por_categoria)
        total_saidas = sum(item['total'] for item in despesas_por_categoria)
        saldo = total_entradas - total_saidas
        
        # ============================================================
        # VENDAS POR BANDEIRA (MovAdquirente)
        # ============================================================
        vendas_por_bandeira = _agrupar_por_bandeira(empresa_id, data_inicio, data_fim)
        vendas_cartao_total = sum(vendas_por_bandeira.values())
        
        # ============================================================
        # BREAKDOWN PARA O FRONTEND
        # ============================================================
        receitas_breakdown = _formatar_breakdown(receitas_por_categoria, total_entradas)
        despesas_breakdown = _formatar_breakdown(despesas_por_categoria, total_saidas)
        
        # ============================================================
        # INSIGHT INTELIGENTE
        # ============================================================
        insight = _gerar_insight(total_entradas, total_saidas, saldo, vendas_cartao_total)
        
        response = {
            'ok': True,
            'periodo': {
                'inicio': data_inicio.isoformat() if data_inicio else None,
                'fim': data_fim.isoformat(),
                'tipo': periodo
            },
            'saldo': round(saldo, 2),
            'entradas': round(total_entradas, 2),
            'saidas': round(total_saidas, 2),
            'vendas_cartao': round(vendas_cartao_total, 2),
            'vendas_por_bandeira': vendas_por_bandeira,
            'receitas_breakdown': receitas_breakdown,
            'despesas_breakdown': despesas_breakdown,
            'insight': insight,
            'total_registros': len(receitas_por_categoria) + len(despesas_por_categoria)
        }
        
        return jsonify(response), 200
        
    except Exception as e:
        logger.error(f"❌ Erro ao calcular KPIs: {str(e)}", exc_info=True)
        return jsonify({'ok': False, 'error': 'Erro ao processar dados do dashboard'}), 500


# ============================================================
# FUNÇÕES DE AGRUPAMENTO (SUBSTITUEM OS LIKEs)
# ============================================================

def _agrupar_por_categoria(empresa_id, data_inicio, data_fim, tipo='receita'):
    """
    Agrupa movimentos por categoria.
    ✅ Usa GROUP BY categoria - sem LIKEs espalhados.
    
    Args:
        tipo: 'receita' (valores > 0) ou 'despesa' (valores < 0)
    """
    resultados = []
    
    # 1. MovBanco
    query_banco = db.session.query(
        MovBanco.categoria,
        func.sum(func.abs(MovBanco.valor)).label('total'),
        func.count().label('quantidade')
    ).filter(
        MovBanco.empresa_id == empresa_id,
        MovBanco.categoria.isnot(None),
        MovBanco.categoria != '',
        MovBanco.categoria != 'outros'
    )
    
    if tipo == 'receita':
        query_banco = query_banco.filter(MovBanco.valor > 0)
    else:
        query_banco = query_banco.filter(MovBanco.valor < 0)
    
    if data_inicio:
        query_banco = query_banco.filter(
            MovBanco.data_movimento >= data_inicio,
            MovBanco.data_movimento <= data_fim
        )
    
    query_banco = query_banco.group_by(MovBanco.categoria).all()
    
    for cat, total, qtd in query_banco:
        if total and total > 0:
            resultados.append({
                'categoria': cat,
                'total': float(total),
                'quantidade': qtd
            })
    
    # 2. MovAdquirente (apenas receitas)
    if tipo == 'receita':
        query_adq = db.session.query(
            MovAdquirente.tipo_pagamento,
            func.sum(MovAdquirente.valor_bruto).label('total'),
            func.count().label('quantidade')
        ).filter(
            MovAdquirente.empresa_id == empresa_id,
            MovAdquirente.ativo == True,
            MovAdquirente.valor_bruto > 0
        )
        
        if data_inicio:
            query_adq = query_adq.filter(
                MovAdquirente.data_venda >= data_inicio,
                MovAdquirente.data_venda <= data_fim
            )
        
        query_adq = query_adq.group_by(MovAdquirente.tipo_pagamento).all()
        
        for tipo_pag, total, qtd in query_adq:
            if total and total > 0:
                cat = f'vendas_{tipo_pag or "cartao"}'
                existente = next((r for r in resultados if r['categoria'] == cat), None)
                if existente:
                    existente['total'] += float(total)
                    existente['quantidade'] += qtd
                else:
                    resultados.append({
                        'categoria': cat,
                        'total': float(total),
                        'quantidade': qtd
                    })
    
    return sorted(resultados, key=lambda x: x['total'], reverse=True)


def _agrupar_por_bandeira(empresa_id, data_inicio, data_fim):
    """Agrupa vendas por bandeira de cartão."""
    query = db.session.query(
        MovAdquirente.bandeira,
        func.sum(MovAdquirente.valor_bruto).label('total')
    ).filter(
        MovAdquirente.empresa_id == empresa_id,
        MovAdquirente.ativo == True,
        MovAdquirente.valor_bruto > 0,
        MovAdquirente.bandeira.isnot(None),
        MovAdquirente.bandeira != ''
    )
    
    if data_inicio:
        query = query.filter(
            MovAdquirente.data_venda >= data_inicio,
            MovAdquirente.data_venda <= data_fim
        )
    
    resultados = query.group_by(MovAdquirente.bandeira).all()
    
    bandeiras = {}
    for bandeira, total in resultados:
        nome = bandeira.strip().title()
        bandeiras[nome] = float(total or 0)
    
    return bandeiras


def _formatar_breakdown(categorias, total_geral):
    """Formata categorias para exibição no frontend."""
    breakdown = []
    for item in categorias[:6]:  # Top 6
        percentual = (item['total'] / total_geral * 100) if total_geral > 0 else 0
        breakdown.append({
            'nome': _nome_amigavel(item['categoria']),
            'categoria': item['categoria'],
            'valor': round(item['total'], 2),
            'percentual': round(percentual, 1),
            'quantidade': item['quantidade']
        })
    return breakdown


def _nome_amigavel(categoria):
    """Converte categoria técnica para nome amigável."""
    nomes = {
        'transporte_combustivel': 'Transporte e Combustível',
        'alimentacao_restaurante': 'Alimentação',
        'alimentacao_mercado': 'Mercado',
        'streaming': 'Streaming',
        'telefonia': 'Telefonia',
        'internet': 'Internet',
        'impostos_federais': 'Impostos Federais',
        'impostos_municipais': 'Impostos Municipais',
        'tarifas_bancarias': 'Tarifas Bancárias',
        'salarios': 'Salários',
        'beneficios': 'Benefícios',
        'emprestimos': 'Empréstimos',
        'investimentos': 'Investimentos',
        'transferencias_enviadas': 'Transferências Enviadas',
        'transferencias_recebidas': 'Transferências Recebidas',
        'receitas_pix': 'PIX Recebido',
        'receitas_nao_classificadas': 'Outras Receitas',
        'vendas_cartao': 'Vendas no Cartão',
        'vendas_pix': 'Vendas via PIX',
        'vendas_elo': 'Vendas Elo',
        'fornecedores_servicos': 'Fornecedores',
        'fornecedores_mercadoria': 'Fornecedores',
        'outras_despesas': 'Outras Despesas',
    }
    return nomes.get(categoria, categoria.replace('_', ' ').title())


def _gerar_insight(entradas, saidas, saldo, vendas_cartao):
    """Gera insight inteligente baseado nos dados."""
    if entradas == 0 and saidas == 0:
        return "Importe seu extrato bancário (OFX ou CSV) para visualizar seus KPIs financeiros!"
    
    insights = []
    
    if vendas_cartao > 0:
        perc = (vendas_cartao / entradas * 100) if entradas > 0 else 0
        if perc > 30:
            insights.append(f"💳 {perc:.0f}% das receitas vêm de maquininha. Verifique as taxas da adquirente!")
    
    if saldo < 0:
        insights.append("⚠️ Fluxo de caixa negativo. Revise despesas ou acelere recebimentos.")
    elif entradas > 0 and saldo > entradas * 0.2:
        insights.append(f"✅ Excelente! Margem positiva de {((saldo/entradas)*100):.0f}%.")
    
    if saidas > entradas * 0.7:
        insights.append("📉 Suas despesas estão acima de 70% da receita. Hora de revisar gastos!")
    
    return insights[0] if insights else "Continue acompanhando seu fluxo de caixa regularmente."


# ============================================================
# ROTA DE RESUMO MENSAL (GRÁFICO)
# ============================================================

@dashboard_api_bp.route('/resumo-mensal', methods=['GET'])
@login_required
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
            
            entradas = db.session.query(func.sum(MovBanco.valor)).filter(
                MovBanco.empresa_id == empresa_id,
                MovBanco.valor > 0,
                MovBanco.data_movimento >= data_inicio,
                MovBanco.data_movimento <= data_fim
            ).scalar() or Decimal('0')
            
            saidas = db.session.query(func.sum(func.abs(MovBanco.valor))).filter(
                MovBanco.empresa_id == empresa_id,
                MovBanco.valor < 0,
                MovBanco.data_movimento >= data_inicio,
                MovBanco.data_movimento <= data_fim
            ).scalar() or Decimal('0')
            
            meses.append({
                'mes': f'{mes_atual:02d}/{ano_atual}',
                'entradas': float(entradas),
                'saidas': float(saidas),
                'saldo': float(entradas - saidas)
            })
        
        return jsonify({'ok': True, 'meses': meses}), 200
        
    except Exception as e:
        logger.error(f"Erro ao calcular resumo mensal: {str(e)}")
        return jsonify({'ok': False, 'error': str(e)}), 500