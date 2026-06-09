# utils/filters.py - Filtros Jinja2 personalizados

from decimal import Decimal, InvalidOperation

def currency_br(value):
    """
    Formata valor monetário para padrão brasileiro.
    Uso em templates: {{ valor | currency_br }}
    
    Args:
        value: Decimal, float, int ou string numérica
        
    Returns:
        str: Valor formatado (ex: "1.234,56")
    """
    if value is None:
        return "0,00"
    
    try:
        # Converter para Decimal para precisão
        num = Decimal(str(value))
        # Formatar para padrão brasileiro
        return f"{num:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except (InvalidOperation, ValueError, TypeError):
        return "0,00"


def register_filters(app):
    """
    Registra todos os filters personalizados no app Flask.
    Chamar em app.py após criar o app.
    """
    app.jinja_env.filters['currency_br'] = currency_br
    # Adicionar mais filters aqui no futuro se necessário
