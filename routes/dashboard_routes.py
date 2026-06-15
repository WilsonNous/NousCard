# routes/dashboard_routes.py
# Dashboard HTML + API de Dashboard Financeiro Inteligente

from flask import Blueprint, jsonify, request, g, render_template, make_response, redirect, url_for, session, abort
from models import db, MovBanco, MovAdquirente, Empresa, ArquivoImportado, LogAuditoria, Usuario, Normalizacao
from sqlalchemy import func, extract, and_, or_
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from utils.auth_middleware import login_required, empresa_required
import logging
import time

logger = logging.getLogger(__name__)

# ============================================================
# ✅ BLUEPRINT 1: Dashboard HTML (página visual)
# ============================================================
dashboard_bp = Blueprint("dashboard", __name__)

# ============================================================
# ✅ HELPER: Padronizar categorias para o dashboard
# ============================================================
def _padronizar_categoria(categoria: str) -> str:
    """
    Mapeia categorias variantes para as padronizadas do dashboard.
    Ex: 'transferencia_enviada_outros' → 'fornecedores_servicos'
    """
    if not categoria:
        return 'outras_despesas'
    
    categoria_lower = categoria.lower().strip()
    
    # Mapeamento direto
    mapeamento = {
        # Transporte
        'combustivel': 'transporte_combustivel',
        'posto': 'transporte_combustivel',
        'gasolina': 'transporte_combustivel',
        'uber': 'transporte_combustivel',
        '99': 'transporte_combustivel',
        'taxi': 'transporte_combustivel',
        'estacionamento': 'transporte_combustivel',
        'pedagio': 'transporte_combustivel',
        'frete': 'transporte_combustivel',
        
        # Transferências → Fornecedores
        'transferencia_enviada_outros': 'fornecedores_servicos',
        'pix_emitido': 'fornecedores_servicos',
        'pix_fornecedores': 'fornecedores_servicos',
        'boleto_pago_outros': 'fornecedores_servicos',
        
        # Energia/Telecom
        'energia': 'energia_agua_telecom',
        'agua': 'energia_agua_telecom',
        'esgoto': 'energia_agua_telecom',
        'telefone': 'energia_agua_telecom',
        'celular': 'energia_agua_telecom',
        'internet': 'energia_agua_telecom',
        'netflix': 'energia_agua_telecom',
        'claro': 'energia_agua_telecom',
        'vivo': 'energia_agua_telecom',
        
        # Impostos
        'tributos': 'impostos_tributos',
        'das': 'impostos_tributos',
        'darf': 'impostos_tributos',
        'simples': 'impostos_tributos',
        'rfb': 'impostos_tributos',
        'iptu': 'impostos_tributos',
        'iss': 'impostos_tributos',
        
        # Tarifas
        'tarifa_bancaria': 'tarifas_bancarias',
        'tarifa': 'tarifas_bancarias',
        'manutencao': 'tarifas_bancarias',
        'pacote': 'tarifas_bancarias',
        'ted': 'tarifas_bancarias',
        'doc': 'tarifas_bancarias',
        'iof': 'tarifas_bancarias',
    }
    
    return mapeamento.get(categoria_lower, categoria_lower)

# Mapeamento de categorias técnicas para nomes amigáveis
CATEGORIAS_NOME = {
    # Receitas
    'vendas_cartao': 'Vendas no Cartão',
    'vendas_mastercard': 'Vendas - Mastercard',
    'vendas_visa': 'Vendas - Visa',
    'vendas_elo': 'Vendas - Elo',
    'vendas_pix': 'Vendas via PIX',
    'vendas_boleto': 'Vendas via Boleto',
    'transferencia_recebida': 'Transferências Recebidas',
    'outras_receitas': 'Outras Receitas',
    
    # Despesas
    'fornecedores_mercadoria': 'Fornecedores - Mercadorias',
    'fornecedores_servicos': 'Fornecedores - Serviços',
    'impostos_tributos': 'Impostos e Tributos',
    'tarifas_bancarias': 'Tarifas Bancárias',
    'aluguel_condominio': 'Aluguel e Condomínio',
    'energia_agua_telecom': 'Energia, Água e Telecom',
    'marketing_publicidade': 'Marketing e Publicidade',
    'salarios_encargos': 'Salários e Encargos',
    'transporte_combustivel': 'Transporte e Combustível',
    'equipamentos_manutencao': 'Equipamentos e Manutenção',
    'seguros': 'Seguros',
    'saude_bem_estar': 'Saúde e Bem-estar',
    'viagens_hospedagem': 'Viagens e Hospedagem',
    'doacoes_patrocinios': 'Doações e Patrocínios',
    'outras_despesas': 'Outras Despesas',
}

CATEGORIAS_DESC = {
    'vendas_cartao': 'Recebimentos via maquininha de cartão',
    'vendas_pix': 'Recebimentos via PIX de clientes',
    'fornecedores_mercadoria': 'Compra de produtos para revenda ou estoque',
    'fornecedores_servicos': 'Serviços terceirizados e manutenção',
    'impostos_tributos': 'DAS, INSS, IR, taxas governamentais',
    'tarifas_bancarias': 'Tarifas de conta, TED, manutenção bancária',
    'outras_despesas': 'Transações não classificadas automaticamente',
}

PERIODOS_LABEL = {
    'mes': 'Este Mês',
    'trimestre': 'Último Trimestre',
    'ano': 'Este Ano',
    '12meses': 'Últimos 12 Meses',
}

# ============================================================
# ✅ ROTA RAIZ INTELIGENTE
# ============================================================
@dashboard_bp.route("/")
def raiz_inteligente():
    """Rota raiz inteligente do NousCard"""
    usuario = getattr(g, 'user', None)
    
    if usuario and getattr(usuario, 'id', None):
        if getattr(usuario, 'master', False):
            return redirect(url_for('master.dashboard_operacional_page'))
        else:
            return redirect(url_for('dashboard.dashboard'))
    else:
        return redirect(url_for('auth.login_page'))


# ============================================================
# CONFIGURAÇÕES DE SEGURANÇA
# ============================================================
RATE_LIMIT_WINDOW = 60
RATE_LIMIT_MAX_REQUESTS = 60
_dashboard_rate_limit_cache = {}

def check_dashboard_rate_limit(user_id: str) -> bool:
    """Verifica rate limiting para acesso ao dashboard"""
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


# ============================================================
# ROTA HTML DO DASHBOARD
# ============================================================
@dashboard_bp.route("/dashboard")
@login_required
@empresa_required
def dashboard():
    """Página principal do dashboard (HTML)"""
    
    usuario = g.user
    
    if getattr(usuario, 'master', False):
        return redirect(url_for('master.dashboard_operacional_page'))
        
    empresa_id = getattr(usuario, 'empresa_id', None)
    
    if not check_dashboard_rate_limit(str(usuario.id)):
        logger.warning(f"Rate limit aproximado: usuario={usuario.id}")
    
    if not empresa_id:
        logger.error(f"❌ Usuário {usuario.id} não tem empresa_id vinculado")
        return redirect(url_for('operacoes.importar_page'))
    
    try:
        empresa = Empresa.query.filter_by(id=empresa_id, ativo=True).first()
        if not empresa:
            logger.warning(f"⚠️ Empresa {empresa_id} não encontrada ou inativa")
            return redirect(url_for('auth.logout'))
        empresa_nome = empresa.nome
    except Exception as e:
        logger.error(f"❌ Erro ao verificar empresa: {str(e)}")
        return redirect(url_for('auth.logout'))
    
    try:
        log = LogAuditoria(
            usuario_id=usuario.id,
            empresa_id=empresa_id,
            acao="dashboard_acesso",
            detalhes=f"User-Agent: {request.user_agent.string[:100]}",
            ip=request.remote_addr,
            criado_em=datetime.now(timezone.utc)
        )
        db.session.add(log)
        db.session.commit()
    except Exception as e:
        logger.debug(f"⚠️ Erro ao logar acesso ao dashboard (não crítico): {str(e)}")
    
    try:
        tem_vendas = MovAdquirente.query.filter_by(empresa_id=empresa_id).limit(1).count() > 0
        tem_arquivos = ArquivoImportado.query.filter_by(empresa_id=empresa_id).limit(1).count() > 0
        
        if not tem_vendas and not tem_arquivos:
            logger.info(f"🔄 Onboarding: empresa {empresa_id} sem dados, redirecionando para importar")
            return redirect(url_for('operacoes.importar_page'))
    except Exception as e:
        logger.debug(f"⚠️ Não foi possível verificar dados para onboarding: {str(e)}")
    
    contexto = {
        "usuario": usuario,
        "empresa_id": empresa_id,
        "empresa_nome": empresa_nome,
        "is_admin": getattr(usuario, 'admin', False),
        "is_master": getattr(usuario, 'master', False),
        "current_year": datetime.now().year,
        "current_month": datetime.now().month,
        "page_title": "Dashboard - NousCard",
        "csrf_token": getattr(g, 'csrf_token', '') or session.get('csrf_token', ''),
        "tipos_pagamento_disponiveis": ["todos", "cartao", "pix", "boleto", "outros"],
    }
    
    try:
        html = render_template("dashboard.html", **contexto)
        response = make_response(html)
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        return response
    except Exception as e:
        logger.error(f"❌ Erro ao renderizar dashboard: {str(e)}", exc_info=True)
        abort(500)


# ============================================================
# ✅ BLUEPRINT 2: Dashboard API (JSON)
# ============================================================
dashboard_api_bp = Blueprint("dashboard_api", __name__)


def get_periodo_datas(periodo):
    """Retorna data_inicio e data_fim baseado no período selecionado"""
    hoje = datetime.now().date()
    
    if periodo == 'geral':
        return None, hoje
    elif periodo == 'atual':
        data_inicio = hoje.replace(day=1)
        data_fim = hoje
    elif periodo == 'anterior':
        if hoje.month == 1:
            data_inicio = hoje.replace(year=hoje.year-1, month=12, day=1)
            data_fim = hoje.replace(year=hoje.year-1, month=12, day=31)
        else:
            data_inicio = hoje.replace(month=hoje.month-1, day=1)
            data_fim = hoje.replace(day=1) - timedelta(days=1)
    elif periodo == '3meses':
        data_fim = hoje
        data_inicio = hoje - timedelta(days=90)
    elif periodo == '6meses':
        data_fim = hoje
        data_inicio = hoje - timedelta(days=180)
    elif periodo == '12meses':
        data_fim = hoje
        data_inicio = hoje - timedelta(days=365)
    elif periodo == 'ano':
        data_inicio = hoje.replace(month=1, day=1)
        data_fim = hoje
    elif periodo == 'anoanterior':
        data_inicio = hoje.replace(year=hoje.year-1, month=1, day=1)
        data_fim = hoje.replace(year=hoje.year-1, month=12, day=31)
    else:
        data_inicio = hoje.replace(day=1)
        data_fim = hoje
    
    return data_inicio, data_fim


def calcular_kpis_financeiros(empresa_id, data_inicio, data_fim):
    """
    Calcula todos os KPIs financeiros baseados em MovBanco E MovAdquirente.
    ✅ CORREÇÃO: Busca saídas por CATEGORIA, não por valor negativo
    """
    from models import MovAdquirente, MovBanco, Normalizacao
    from sqlalchemy import or_, and_
    
    logger.info(f"🔍 KPIs: empresa_id={empresa_id}, data_inicio={data_inicio}, data_fim={data_fim}")
    
    # ============================================================
    # RECEITAS: Somar de todas as fontes
    # ============================================================
    
    # 1. Receitas de MovBanco
    query_banco_entradas = MovBanco.query.filter(
        MovBanco.empresa_id == empresa_id,
        MovBanco.ativo == True,
        or_(
            MovBanco.valor > 0,
            MovBanco.categoria.in_(['pix_recebido', 'transferencia_recebida', 'vendas_cartao', 'vendas_pix'])
        )
    )
    if data_inicio is not None:
        query_banco_entradas = query_banco_entradas.filter(
            MovBanco.data_movimento >= data_inicio,
            MovBanco.data_movimento <= data_fim
        )
    total_entradas_banco = query_banco_entradas.with_entities(
        func.sum(MovBanco.valor)
    ).scalar() or Decimal('0')
    
    # 2. Receitas de MovAdquirente
    query_adq_entradas = MovAdquirente.query.filter(
        MovAdquirente.empresa_id == empresa_id,
        MovAdquirente.ativo == True,
        MovAdquirente.valor_bruto > 0
    )
    if data_inicio is not None:
        query_adq_entradas = query_adq_entradas.filter(
            MovAdquirente.data_venda >= data_inicio,
            MovAdquirente.data_venda <= data_fim
        )
    total_entradas_adquirente = query_adq_entradas.with_entities(
        func.sum(MovAdquirente.valor_bruto)
    ).scalar() or Decimal('0')
    
    # 3. Fallback: tous_normalizacao para receitas
    total_entradas_norm = Decimal('0')
    if total_entradas_banco == 0 and total_entradas_adquirente == 0:
        query_norm_entradas = Normalizacao.query.filter(
            Normalizacao.empresa_id == empresa_id,
            Normalizacao.status == 'processado',
            Normalizacao.valor_bruto > 0
        )
        if data_inicio is not None:
            query_norm_entradas = query_norm_entradas.filter(
                Normalizacao.data_movimento >= data_inicio,
                Normalizacao.data_movimento <= data_fim
            )
        total_entradas_norm = query_norm_entradas.with_entities(
            func.sum(Normalizacao.valor_bruto)
        ).scalar() or Decimal('0')
        if total_entradas_norm > 0:
            logger.info(f"🔄 Fallback receitas: {total_entradas_norm} em tous_normalizacao")
    
    total_entradas = total_entradas_banco + total_entradas_adquirente + total_entradas_norm
    
    # ============================================================
    # SAÍDAS: Buscar por CATEGORIA + fallback em tous_normalizacao
    # ============================================================
    
    CATEGORIAS_SAIDA = [
        'pix_emitido', 'pix_fornecedores', 'boleto', 'fornecedores_mercadoria',
        'fornecedores_servicos', 'tarifa_bancaria', 'emprestimo',
        'impostos_tributos', 'outras_despesas', 'transporte_combustivel',
        'energia_agua_telecom', 'transferencia_enviada_outros', 'aluguel_condominio',
        'marketing_publicidade', 'salarios_encargos', 'equipamentos_manutencao',
        'seguros', 'saude_bem_estar', 'viagens_hospedagem', 'doacoes_patrocinios'
    ]
    
    # 1. Saídas de MovBanco
    query_banco_saidas = MovBanco.query.filter(
        MovBanco.empresa_id == empresa_id,
        MovBanco.ativo == True,
        or_(
            MovBanco.valor < 0,
            and_(MovBanco.valor > 0, MovBanco.categoria.in_(CATEGORIAS_SAIDA))
        )
    )
    if data_inicio is not None:
        query_banco_saidas = query_banco_saidas.filter(
            MovBanco.data_movimento >= data_inicio,
            MovBanco.data_movimento <= data_fim
        )
    total_saidas_banco = query_banco_saidas.with_entities(
        func.sum(func.abs(MovBanco.valor))
    ).scalar() or Decimal('0')
    
    # 2. Fallback: tous_normalizacao para saídas
    total_saidas_norm = Decimal('0')
    if total_saidas_banco == 0:
        query_norm_saidas = Normalizacao.query.filter(
            Normalizacao.empresa_id == empresa_id,
            Normalizacao.status == 'processado',
            or_(
                Normalizacao.valor_bruto < 0,
                and_(Normalizacao.valor_bruto > 0, Normalizacao.categoria.in_(CATEGORIAS_SAIDA))
            )
        )
        if data_inicio is not None:
            query_norm_saidas = query_norm_saidas.filter(
                Normalizacao.data_movimento >= data_inicio,
                Normalizacao.data_movimento <= data_fim
            )
        total_saidas_norm = query_norm_saidas.with_entities(
            func.sum(func.abs(Normalizacao.valor_bruto))
        ).scalar() or Decimal('0')
        if total_saidas_norm > 0:
            logger.info(f"🔄 Fallback saídas: {total_saidas_norm} em tous_normalizacao")
    
    total_saidas = total_saidas_banco + total_saidas_norm
    
    # Saldo
    saldo = total_entradas - total_saidas
    
    # ============================================================
    # DETALHAMENTO POR CATEGORIA (com fallback e padronização)
    # ============================================================
    
    def _somar_por_categoria(tabela, campo_valor, campo_data, categorias, data_inicio, data_fim):
        """Helper para somar valores por lista de categorias"""
        query = tabela.query.filter(
            tabela.empresa_id == empresa_id,
            tabela.ativo == True if hasattr(tabela, 'ativo') else True,
            getattr(tabela, 'categoria').in_(categorias)
        )
        if data_inicio is not None:
            query = query.filter(
                getattr(tabela, campo_data) >= data_inicio,
                getattr(tabela, campo_data) <= data_fim
            )
        return query.with_entities(func.sum(func.abs(getattr(tabela, campo_valor)))).scalar() or Decimal('0')
    
    # Fornecedores
    cats_fornecedores = ['pix_emitido', 'pix_fornecedores', 'boleto', 'fornecedores_mercadoria', 'fornecedores_servicos', 'transporte_combustivel']
    fornecedores_banco = _somar_por_categoria(MovBanco, 'valor', 'data_movimento', cats_fornecedores, data_inicio, data_fim)
    fornecedores_norm = Decimal('0') if fornecedores_banco > 0 else _somar_por_categoria(Normalizacao, 'valor_bruto', 'data_movimento', cats_fornecedores, data_inicio, data_fim)
    fornecedores_total = fornecedores_banco + fornecedores_norm
    
    # Impostos
    cats_impostos = ['tributos', 'impostos_tributos']
    impostos_banco = _somar_por_categoria(MovBanco, 'valor', 'data_movimento', cats_impostos, data_inicio, data_fim)
    impostos_norm = Decimal('0') if impostos_banco > 0 else _somar_por_categoria(Normalizacao, 'valor_bruto', 'data_movimento', cats_impostos, data_inicio, data_fim)
    impostos_total = impostos_banco + impostos_norm
    
    # Outras despesas
    cats_outras = ['tarifa_bancaria', 'emprestimo', 'aplicacao_investimento', 'seguro', 'outras_despesas', 'energia_agua_telecom', 'transferencia_enviada_outros']
    outras_banco = _somar_por_categoria(MovBanco, 'valor', 'data_movimento', cats_outras, data_inicio, data_fim)
    outras_norm = Decimal('0') if outras_banco > 0 else _somar_por_categoria(Normalizacao, 'valor_bruto', 'data_movimento', cats_outras, data_inicio, data_fim)
    outras_total = outras_banco + outras_norm
    
    # Vendas no cartão (só MovAdquirente)
    vendas_cartao = MovAdquirente.query.filter(
        MovAdquirente.empresa_id == empresa_id,
        MovAdquirente.ativo == True,
        MovAdquirente.valor_bruto > 0
    )
    if data_inicio is not None:
        vendas_cartao = vendas_cartao.filter(
            MovAdquirente.data_venda >= data_inicio,
            MovAdquirente.data_venda <= data_fim
        )
    vendas_cartao_total = vendas_cartao.with_entities(func.sum(MovAdquirente.valor_bruto)).scalar() or Decimal('0')
    
    # PIX Recebido
    pix_banco = MovBanco.query.filter(
        MovBanco.empresa_id == empresa_id,
        MovBanco.categoria == 'pix_recebido',
        MovBanco.ativo == True
    )
    if data_inicio is not None:
        pix_banco = pix_banco.filter(
            MovBanco.data_movimento >= data_inicio,
            MovBanco.data_movimento <= data_fim
        )
    pix_recebido_banco = pix_banco.with_entities(func.sum(MovBanco.valor)).scalar() or Decimal('0')
    
    pix_adq = MovAdquirente.query.filter(
        MovAdquirente.empresa_id == empresa_id,
        MovAdquirente.ativo == True,
        MovAdquirente.valor_bruto > 0,
        or_(
            MovAdquirente.tipo_pagamento == 'pix',
            MovAdquirente.produto.ilike('%pix%'),
            MovAdquirente.bandeira.ilike('%pix%')
        )
    )
    if data_inicio is not None:
        pix_adq = pix_adq.filter(
            MovAdquirente.data_venda >= data_inicio,
            MovAdquirente.data_venda <= data_fim
        )
    pix_recebido_adq = pix_adq.with_entities(func.sum(MovAdquirente.valor_bruto)).scalar() or Decimal('0')
    
    pix_recebido = pix_recebido_banco + pix_recebido_adq
    
    # Transferências Recebidas
    transferencias = MovBanco.query.filter(
        MovBanco.empresa_id == empresa_id,
        MovBanco.categoria == 'transferencia_recebida',
        MovBanco.ativo == True
    )
    if data_inicio is not None:
        transferencias = transferencias.filter(
            MovBanco.data_movimento >= data_inicio,
            MovBanco.data_movimento <= data_fim
        )
    transferencias_recebidas = transferencias.with_entities(func.sum(MovBanco.valor)).scalar() or Decimal('0')
    
    # Total de registros
    total_registros = (
        MovBanco.query.filter_by(empresa_id=empresa_id, ativo=True).count() +
        MovAdquirente.query.filter_by(empresa_id=empresa_id, ativo=True).count() +
        Normalizacao.query.filter_by(empresa_id=empresa_id, status='processado').count()
    )
    
    logger.info(f"📊 KPIs: entradas={total_entradas}, saidas={total_saidas}, saldo={saldo}")
    
    return {
        'saldo': float(saldo),
        'entradas': float(total_entradas),
        'saidas': float(total_saidas),
        'vendas_cartao': float(vendas_cartao_total),
        'receitas': {
            'cartao': float(vendas_cartao_total),
            'pix': float(pix_recebido),
            'transferencias': float(transferencias_recebidas)
        },
        'despesas': {
            'fornecedores': float(fornecedores_total),
            'impostos': float(impostos_total),
            'outras': float(outras_total)
        },
        'total_registros': total_registros
    }


def gerar_insight_inteligente(kpis, periodo):
    """Gera insights automáticos baseados nos dados financeiros"""
    insights = []
    
    if kpis['vendas_cartao'] > 0:
        percentual_cartao = (kpis['vendas_cartao'] / kpis['entradas'] * 100) if kpis['entradas'] > 0 else 0
        if percentual_cartao > 30:
            insights.append(f"Você recebeu R$ {kpis['vendas_cartao']:,.2f} via maquininha este período ({percentual_cartao:.1f}% das receitas). Verifique se as taxas da adquirente estão competitivas!")
    
    if kpis['receitas']['pix'] > 0:
        percentual_pix = (kpis['receitas']['pix'] / kpis['entradas'] * 100) if kpis['entradas'] > 0 else 0
        insights.append(f"PIX representa {percentual_pix:.1f}% das suas receitas - ótima alternativa às taxas de cartão!")
    
    if kpis['despesas']['fornecedores'] > kpis['entradas'] * 0.5:
        percentual_forn = (kpis['despesas']['fornecedores'] / kpis['entradas'] * 100) if kpis['entradas'] > 0 else 0
        insights.append(f"Atenção: {percentual_forn:.1f}% da receita vai para fornecedores. Revise contratos!")
    
    if kpis['saldo'] < 0:
        insights.append("⚠️ Fluxo de caixa negativo neste período. Considere revisar despesas ou acelerar recebimentos.")
    elif kpis['entradas'] > 0 and kpis['saldo'] > kpis['entradas'] * 0.2:
        percentual_margem = (kpis['saldo'] / kpis['entradas'] * 100) if kpis['entradas'] > 0 else 0
        insights.append(f"✅ Excelente gestão! Você manteve {percentual_margem:.1f}% de margem positiva.")
    
    if kpis['despesas']['impostos'] > 0:
        insights.append(f"Você pagou R$ {kpis['despesas']['impostos']:,.2f} em impostos. Mantenha a regularidade fiscal!")
    
    return insights[0] if insights else "Continue acompanhando seu fluxo de caixa regularmente para tomar melhores decisões financeiras."


@dashboard_api_bp.route('/api/v1/dashboard/kpis', methods=['GET'])
@login_required
def get_dashboard_kpis():
    """API principal do dashboard com KPIs de vendas por bandeira"""
    try:
        periodo = request.args.get('periodo', 'atual')
        
        if not hasattr(g, 'user') or not g.user:
            return jsonify({'error': 'Usuário não autenticado'}), 401
        
        empresa_id = g.user.empresa_id
        
        if not empresa_id:
            return jsonify({'error': 'Usuário sem empresa vinculada'}), 403
        
        data_inicio, data_fim = get_periodo_datas(periodo)
        kpis = calcular_kpis_financeiros(empresa_id, data_inicio, data_fim)
        insight = gerar_insight_inteligente(kpis, periodo)
        
        # Calcular vendas por bandeira
        vendas_por_bandeira = calcular_vendas_por_bandeira(empresa_id, data_inicio, data_fim)
        
        response = {
            'ok': True,
            'periodo': {
                'inicio': data_inicio.isoformat() if data_inicio else None,
                'fim': data_fim.isoformat(),
                'tipo': periodo
            },
            'saldo': round(kpis['saldo'], 2),
            'entradas': round(kpis['entradas'], 2),
            'saidas': round(kpis['saidas'], 2),
            'vendas_cartao': round(kpis['vendas_cartao'], 2),
            'receitas': {
                'cartao': round(kpis['receitas']['cartao'], 2),
                'pix': round(kpis['receitas']['pix'], 2),
                'transferencias': round(kpis['receitas']['transferencias'], 2)
            },
            'despesas': {
                'fornecedores': round(kpis['despesas']['fornecedores'], 2),
                'impostos': round(kpis['despesas']['impostos'], 2),
                'outras': round(kpis['despesas']['outras'], 2)
            },
            'vendas_por_bandeira': vendas_por_bandeira,
            'insight': insight,
            'total_registros': kpis['total_registros']
        }
        
        return jsonify(response), 200
        
    except Exception as e:
        logger.error(f"Erro ao calcular KPIs: {str(e)}", exc_info=True)
        return jsonify({
            'ok': False,
            'error': 'Erro ao processar dados do dashboard',
            'details': str(e) if app.debug else None
        }), 500


def calcular_vendas_por_bandeira(empresa_id, data_inicio, data_fim):
    """Calcula vendas por bandeira (Mastercard, Visa, Elo, etc.)"""
    from models import MovAdquirente
    
    query = db.session.query(
        MovAdquirente.bandeira,
        func.sum(MovAdquirente.valor_bruto).label('total')
    ).filter(
        MovAdquirente.empresa_id == empresa_id,
        MovAdquirente.ativo == True,
        MovAdquirente.valor_bruto > 0,
        MovAdquirente.bandeira != None,
        MovAdquirente.bandeira != ''
    )
    
    if data_inicio is not None:
        query = query.filter(
            MovAdquirente.data_venda >= data_inicio,
            MovAdquirente.data_venda <= data_fim
        )
    
    resultados = query.group_by(MovAdquirente.bandeira).all()
    
    vendas_por_bandeira = {}
    for bandeira, total in resultados:
        if bandeira:
            nome = bandeira.strip().title()
            vendas_por_bandeira[nome] = float(total or 0)
    
    return vendas_por_bandeira


@dashboard_api_bp.route('/api/v1/dashboard/resumo-mensal', methods=['GET'])
@login_required
def get_resumo_mensal():
    """API para gráfico de evolução mensal"""
    try:
        if not hasattr(g, 'user') or not g.user:
            return jsonify({'error': 'Usuário não autenticado'}), 401
        
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
            
            saldo_banco = MovBanco.query.filter(
                MovBanco.empresa_id == empresa_id,
                MovBanco.data_movimento >= data_inicio,
                MovBanco.data_movimento <= data_fim
            ).with_entities(func.sum(MovBanco.valor)).scalar() or Decimal('0')
            
            saldo_adq = MovAdquirente.query.filter(
                MovAdquirente.empresa_id == empresa_id,
                MovAdquirente.data_venda >= data_inicio,
                MovAdquirente.data_venda <= data_fim
            ).with_entities(func.sum(MovAdquirente.valor_bruto)).scalar() or Decimal('0')
            
            saldo_total = saldo_banco + saldo_adq
            
            meses.append({
                'mes': f'{mes_atual:02d}/{ano_atual}',
                'saldo': float(saldo_total),
                'label': f'{mes_atual:02d}/{str(ano_atual)[-2:]}'
            })
        
        return jsonify({'ok': True, 'meses': meses}), 200
        
    except Exception as e:
        logger.error(f"Erro ao calcular resumo mensal: {str(e)}", exc_info=True)
        return jsonify({'ok': False, 'error': str(e)}), 500

@dashboard_bp.route("/dre")
@login_required
@empresa_required
def dre_resumo():
    """Exibe o DRE - Demonstrativo de Resultado"""
    empresa_id = g.user.empresa_id
    periodo = request.args.get('periodo', '12meses')
    
    data_inicio, data_fim = get_periodo_datas(periodo)
    
    # Buscar receitas
    receitas_query = db.session.query(
        Normalizacao.categoria,
        func.sum(Normalizacao.valor_bruto).label('total')
    ).filter(
        Normalizacao.empresa_id == empresa_id,
        Normalizacao.status == 'processado',
        Normalizacao.valor_bruto > 0
    )
    
    if data_inicio is not None:
        receitas_query = receitas_query.filter(
            Normalizacao.data_movimento.between(data_inicio, data_fim)
        )
    
    receitas_query = receitas_query.group_by(Normalizacao.categoria)
    receitas_result = receitas_query.all()
    
    receitas = []
    total_receitas = Decimal('0')
    
    for cat, total in receitas_result:
        receitas.append({
            'nome': CATEGORIAS_NOME.get(cat, cat),
            'descricao': CATEGORIAS_DESC.get(cat, ''),
            'valor': float(total),
            'categoria': cat
        })
        total_receitas += total
    
    # Buscar despesas
    despesas_query = db.session.query(
        Normalizacao.categoria,
        func.sum(Normalizacao.valor_bruto).label('total')
    ).filter(
        Normalizacao.empresa_id == empresa_id,
        Normalizacao.status == 'processado',
        Normalizacao.valor_bruto < 0
    )
    
    if data_inicio is not None:
        despesas_query = despesas_query.filter(
            Normalizacao.data_movimento.between(data_inicio, data_fim)
        )
    
    despesas_query = despesas_query.group_by(Normalizacao.categoria)
    despesas_result = despesas_query.all()
    
    despesas = []
    total_despesas = Decimal('0')
    
    for cat, total in despesas_result:
        # ✅ Padronizar categoria antes de agregar
        cat_padronizada = _padronizar_categoria(cat)
        percentual = (abs(total) / total_receitas * 100) if total_receitas > 0 else 0
        despesas.append({
            'nome': CATEGORIAS_NOME.get(cat_padronizada, cat_padronizada),
            'descricao': CATEGORIAS_DESC.get(cat_padronizada, ''),
            'valor': float(abs(total)),
            'percentual': round(percentual, 1),
            'categoria': cat_padronizada
        })
        total_despesas += abs(total)
    
    # Calcular resultado
    saldo = total_receitas - total_despesas
    margem = (saldo / total_receitas * 100) if total_receitas > 0 else 0
    
    # Buscar sugestões de refinamento
    from services.categorizacao_service import sugerir_categorias
    sugestoes = sugerir_categorias(empresa_id, limite=10)
    
    return render_template(
        'dashboard/dre_resumo.html',
        empresa=g.user.empresa,
        periodo=periodo,
        periodo_label=PERIODOS_LABEL.get(periodo, 'Período'),
        receitas=receitas,
        despesas=despesas,
        total_receitas=float(total_receitas),
        total_despesas=float(total_despesas),
        saldo=float(saldo),
        margem=margem,
        sugestoes_refinamento=sugestoes
    )
