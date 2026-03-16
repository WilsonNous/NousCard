# utils/context_processors.py
from datetime import datetime
from flask import g

def inject_global_vars():
    """
    Injeta variáveis globais em todos os templates.
    """
    usuario = getattr(g, 'user', None)
    
    return {
        'current_year': datetime.now().year,
        'usuario': usuario,
        'is_master': usuario.master if usuario and hasattr(usuario, 'master') else False,
        'is_admin': usuario.admin if usuario and hasattr(usuario, 'admin') else False,
        'empresa_nome': usuario.empresa.nome if usuario and hasattr(usuario, 'empresa') and usuario.empresa else None,
    }
