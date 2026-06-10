# utils/tenant.py
# ============================================================
# HELPERS MULTI-TENANT - ISOLAMENTO POR EMPRESA
# ============================================================

from flask import g, request
from functools import wraps
import logging

logger = logging.getLogger(__name__)


def get_empresa_id() -> int:
    """
    Retorna o empresa_id do usuário logado.
    
    ✅ SEMPRE usar este helper em queries para garantir isolamento.
    ✅ Masters podem ver qualquer empresa (passando empresa_id como parâmetro).
    
    Returns:
        int: ID da empresa do usuário
        
    Raises:
        ValueError: Se usuário não tem empresa vinculada
    """
    if not hasattr(g, 'user') or not g.user:
        raise ValueError("Usuário não autenticado")
    
    # Master pode escolher empresa (via query param ou sessão)
    if g.user.master:
        # Se master especificou empresa na URL, usar essa
        empresa_override = request.args.get('empresa_id', type=int)
        if empresa_override:
            # Validar que empresa existe
            from models import Empresa
            if Empresa.query.get(empresa_override):
                return empresa_override
    
    # Usuário normal: sempre sua própria empresa
    if not g.user.empresa_id:
        raise ValueError("Usuário sem empresa vinculada")
    
    return g.user.empresa_id


def query_empresa(model_class):
    """
    Retorna uma query já filtrada pela empresa do usuário logado.
    
    Usage:
        # ❌ ERRADO (vaza dados entre empresas):
        vendas = MovAdquirente.query.filter_by(adquirente='Cielo').all()
        
        # ✅ CORRETO (isolado por empresa):
        vendas = query_empresa(MovAdquirente).filter_by(adquirente='Cielo').all()
    
    Args:
        model_class: Classe do modelo SQLAlchemy (ex: MovAdquirente)
    
    Returns:
        Query: Query já filtrada por empresa_id
    """
    empresa_id = get_empresa_id()
    return model_class.query.filter_by(empresa_id=empresa_id)


def salvar_com_empresa(objeto):
    """
    Garante que o objeto tem empresa_id antes de salvar.
    
    Usage:
        venda = MovAdquirente(valor=100, adquirente='Cielo')
        salvar_com_empresa(venda)  # ← Atribui empresa_id automaticamente
        db.session.add(venda)
        db.session.commit()
    
    Args:
        objeto: Instância do modelo SQLAlchemy
    """
    if not hasattr(objeto, 'empresa_id'):
        raise ValueError(f"Objeto {type(objeto).__name__} não tem campo empresa_id")
    
    # Se já tem empresa_id, validar que é a mesma do usuário
    if objeto.empresa_id:
        if objeto.empresa_id != get_empresa_id():
            raise ValueError("Tentativa de salvar em outra empresa")
    else:
        # Atribuir empresa_id do usuário
        objeto.empresa_id = get_empresa_id()


def decorator_empresa_required(f):
    """
    Decorador que garante que a rota tem empresa_id disponível.
    Já existe no auth_middleware.py, mas vamos reforçar o uso.
    """
    from functools import wraps
    
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            empresa_id = get_empresa_id()
            g.empresa_id = empresa_id  # Disponibiliza para a rota
        except ValueError as e:
            from flask import flash, redirect, url_for
            flash(str(e), "error")
            return redirect(url_for('dashboard.dashboard'))
        
        return f(*args, **kwargs)
    return decorated_function
