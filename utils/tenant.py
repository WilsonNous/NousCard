# utils/tenant.py
# ============================================================
# HELPERS MULTI-TENANT - ISOLAMENTO POR EMPRESA
# ============================================================

from flask import g, request, flash, redirect, url_for
from functools import wraps
import logging

logger = logging.getLogger(__name__)


def get_empresa_id() -> int:
    """
    Retorna o empresa_id do usuário logado.
    
    ✅ USE SEMPRE este helper em queries para garantir isolamento.
    ✅ Masters podem ver qualquer empresa (via query param).
    
    Returns:
        int: ID da empresa do usuário
        
    Raises:
        ValueError: Se usuário não tem empresa vinculada
    """
    if not hasattr(g, 'user') or not g.user:
        raise ValueError("Usuário não autenticado")
    
    # Master pode escolher empresa (via query param)
    if getattr(g.user, 'master', False):
        empresa_override = request.args.get('empresa_id', type=int)
        if empresa_override:
            from models import Empresa
            if Empresa.query.get(empresa_override):
                return empresa_override
    
    # Usuário normal: sempre sua própria empresa
    empresa_id = getattr(g.user, 'empresa_id', None)
    if not empresa_id:
        raise ValueError("Usuário sem empresa vinculada")
    
    return empresa_id


def query_empresa(model_class, empresa_id: int = None):
    """
    Retorna query já filtrada pela empresa do usuário.
    
    Usage:
        # ❌ ERRADO (vaza dados):
        vendas = MovAdquirente.query.all()
        
        # ✅ CORRETO (isolado):
        vendas = query_empresa(MovAdquirente).all()
        
        # ✅ COM FILTRO ADICIONAL:
        vendas = query_empresa(MovAdquirente).filter_by(adquirente='Cielo').all()
    
    Args:
        model_class: Classe do modelo (ex: MovAdquirente)
        empresa_id: Opcional (usa get_empresa_id() se None)
    
    Returns:
        Query: Query já filtrada por empresa_id
    """
    if empresa_id is None:
        empresa_id = get_empresa_id()
    return model_class.query.filter_by(empresa_id=empresa_id)


def salvar_com_empresa(objeto, empresa_id: int = None):
    """
    Garante que o objeto tem empresa_id antes de salvar.
    
    Usage:
        venda = MovAdquirente(valor=100, adquirente='Cielo')
        salvar_com_empresa(venda)  # ← Atribui empresa_id automaticamente
        db.session.add(venda)
        db.session.commit()
    
    Args:
        objeto: Instância do modelo SQLAlchemy
        empresa_id: Opcional (usa get_empresa_id() se None)
    """
    if not hasattr(objeto, 'empresa_id'):
        raise ValueError(f"Objeto {type(objeto).__name__} não tem campo empresa_id")
    
    if empresa_id is None:
        empresa_id = get_empresa_id()
    
    # Se já tem empresa_id, validar que é a mesma
    if objeto.empresa_id and objeto.empresa_id != empresa_id:
        raise ValueError(f"Tentativa de salvar em outra empresa: objeto={objeto.empresa_id}, usuário={empresa_id}")
    
    # Atribuir empresa_id do usuário
    objeto.empresa_id = empresa_id


def validar_acesso_empresa(empresa_id: int) -> bool:
    """
    Valida se o usuário atual tem acesso à empresa especificada.
    
    ✅ Masters têm acesso a todas.
    ✅ Usuários normais só têm acesso à sua própria empresa.
    
    Args:
        empresa_id: ID da empresa a validar
    
    Returns:
        bool: True se tem acesso, False caso contrário
    """
    if not hasattr(g, 'user') or not g.user:
        return False
    
    # Master tem acesso a todas
    if getattr(g.user, 'master', False):
        return True
    
    # Usuário normal: só sua própria empresa
    return getattr(g.user, 'empresa_id', None) == empresa_id


# ============================================================
# DECORADORES
# ============================================================

def tenant_context(f):
    """
    Decorador que injeta g.empresa_id automaticamente.
    
    Usage:
        @operacoes_bp.route("/upload")
        @tenant_context
        def upload():
            # g.empresa_id já está disponível
            arquivos = query_empresa(ArquivoImportado).all()
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            g.empresa_id = get_empresa_id()
        except ValueError as e:
            logger.warning(f"Tenant context falhou: {str(e)}")
            flash(str(e), "error")
            return redirect(url_for('dashboard.dashboard'))
        
        return f(*args, **kwargs)
    return decorated_function
