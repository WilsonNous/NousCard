# routes/dashboard_routes.py
from flask import Blueprint, render_template, g, request, make_response, redirect, url_for, current_app
from utils.auth_middleware import login_required, empresa_required
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)

dashboard_bp = Blueprint("dashboard", __name__)

@dashboard_bp.route("/")
@dashboard_bp.route("/dashboard")  # ← Suporta ambas as rotas
@login_required
@empresa_required
def dashboard():
    """
    Página principal do dashboard.
    Requer usuário logado e vinculado a uma empresa.
    """
    
    usuario = g.user
    empresa_id = getattr(usuario, 'empresa_id', None)
    
    # Debug log crítico
    logger.info(f"🔍 DEBUG Dashboard: usuario_id={getattr(usuario, 'id', None)}, empresa_id={empresa_id}")
    
    if not empresa_id:
        logger.error(f"❌ Usuário {getattr(usuario, 'id', None)} não tem empresa_id vinculado")
        return redirect(url_for('operacoes.importar_page'))
    
    # ✅ Garantir que empresa_nome esteja disponível
    empresa_nome = getattr(getattr(usuario, 'empresa', None), 'nome', None)
    
    # Log de acesso (auditoria) - não crítico, não bloqueia o dashboard
    try:
        from models import LogAuditoria, db
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
        logger.warning(f"⚠️ Erro ao logar acesso ao dashboard (não crítico): {str(e)}")
        # Não faz rollback aqui para não afetar o dashboard
    
    # ✅ Onboarding Inteligente: Verificar se empresa tem DADOS OU ARQUIVOS
    try:
        from models import MovAdquirente, ArquivoImportado
        
        # Conta vendas conciliadas
        tem_vendas = MovAdquirente.query.filter_by(empresa_id=empresa_id).count() > 0
        
        # Conta arquivos importados (mesmo que não tenham gerado movimentos ainda)
        tem_arquivos = ArquivoImportado.query.filter_by(
            empresa_id=empresa_id, 
            ativo=True
        ).count() > 0
        
        logger.info(f"🔍 DEBUG Onboarding: tem_vendas={tem_vendas}, tem_arquivos={tem_arquivos}")
        
        # Só redireciona se NÃO tiver NENHUM dos dois
        if not tem_vendas and not tem_arquivos:
            logger.info(f"🔄 Onboarding: empresa {empresa_id} sem dados, redirecionando para importar")
            return redirect(url_for('operacoes.importar_page'))
            
    except Exception as e:
        logger.warning(f"⚠️ Não foi possível verificar dados para onboarding: {str(e)}")
        # Em caso de erro, NÃO redireciona - deixa o usuário ver o dashboard
    
    # ✅ Preparar contexto para o template (COM todas as variáveis que base.html espera)
    contexto = {
        "usuario": usuario,
        "empresa_id": empresa_id,
        "empresa_nome": empresa_nome,
        "is_admin": getattr(usuario, 'admin', False),
        "is_master": getattr(usuario, 'master', False),
        "current_year": datetime.now().year,
        "current_month": datetime.now().month,
        "page_title": "Dashboard - NousCard",
    }
    
    # Renderizar com cache control
    try:
        html = render_template("dashboard.html", **contexto)
        response = make_response(html)
        
        # Prevenir cache de página sensível
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        
        return response
        
    except Exception as e:
        logger.error(f"❌ Erro ao renderizar dashboard: {str(e)}", exc_info=True)
        from flask import abort
        abort(500)
