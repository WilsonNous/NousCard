from flask import Blueprint, render_template, g, request, make_response, redirect, url_for
from utils.auth_middleware import login_required, empresa_required
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)

dashboard_bp = Blueprint("dashboard", __name__)

@dashboard_bp.route("/")
@login_required
@empresa_required
def dashboard():
    """
    Página principal do dashboard.
    Requer usuário logado e vinculado a uma empresa.
    """
    
    usuario = g.user
    empresa_id = usuario.empresa_id
    
    # Garantir que empresa_nome esteja disponível
    empresa_nome = usuario.empresa.nome if usuario.empresa else None
    
    # Log de acesso (auditoria)
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
        logger.error(f"Erro ao logar acesso ao dashboard: {str(e)}")
    
    # Verificar se empresa tem dados cadastrados (onboarding)
    try:
        from models import MovAdquirente
        tem_dados = MovAdquirente.query.filter_by(empresa_id=empresa_id).count() > 0
        if not tem_dados:
            return redirect(url_for('operacoes.importar_page'))
    except Exception as e:
        logger.warning(f"Não foi possível verificar dados: {str(e)}")
    
    # Preparar contexto para o template
    contexto = {
        "usuario": usuario,
        "empresa_id": empresa_id,
        "is_admin": usuario.admin,
        "is_master": usuario.master,
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
        logger.error(f"Erro ao renderizar dashboard: {str(e)}")
        from flask import abort
        abort(500)
