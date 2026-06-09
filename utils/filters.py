# utils/filters.py - Filtros Jinja2 personalizados para templates
# ✅ Todos os filters usados nos templates devem estar aqui

from decimal import Decimal, InvalidOperation
from datetime import datetime


def currency_br(value):
    """
    Formata valor monetário para padrão brasileiro.
    
    Uso em templates: {{ valor | currency_br }}
    Exemplo: {{ 1234.56 | currency_br }} → "1.234,56"
    
    Args:
        value: Decimal, float, int, str ou None
        
    Returns:
        str: Valor formatado (ex: "1.234,56")
    """
    if value is None or value == '':
        return "0,00"
    
    try:
        num = Decimal(str(value))
        formatted = f"{num:,.2f}"
        formatted = formatted.replace(",", "X")
        formatted = formatted.replace(".", ",")
        formatted = formatted.replace("X", ".")
        return formatted
    except (InvalidOperation, ValueError, TypeError):
        return "0,00"


def date_br(value, format="%d/%m/%Y %H:%M"):
    """
    Formata datetime para padrão brasileiro.
    
    Uso em templates: {{ data | date_br }}
    Exemplo: {{ datetime(2024, 6, 9, 14, 30) | date_br }} → "09/06/2024 14:30"
    
    Args:
        value: datetime, date, str ou None
        format: Formato de saída (default: "%d/%m/%Y %H:%M")
        
    Returns:
        str: Data formatada ou "—" se valor inválido
    """
    if value is None:
        return "—"
    
    try:
        # Se for string, tentar converter para datetime
        if isinstance(value, str):
            # Tentar formatos comuns
            for fmt in ["%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"]:
                try:
                    value = datetime.strptime(value.split('+')[0].split('Z')[0], fmt)
                    break
                except ValueError:
                    continue
            else:
                return value  # Retorna a string original se não conseguir converter
        
        # Se for datetime/date, formatar
        if hasattr(value, 'strftime'):
            return value.strftime(format)
        
        return str(value)
        
    except (ValueError, TypeError, AttributeError) as e:
        return "—"


def date_br_short(value):
    """
    Formata data apenas como DD/MM/YYYY (sem hora).
    
    Uso em templates: {{ data | date_br_short }}
    Exemplo: {{ datetime(2024, 6, 9) | date_br_short }} → "09/06/2024"
    """
    return date_br(value, format="%d/%m/%Y")


def register_filters(app):
    """
    Registra todos os filters personalizados no ambiente Jinja2 do Flask.
    
    Args:
        app: Instância Flask configurada (passada como parâmetro)
        
    Usage:
        from utils.filters import register_filters
        register_filters(app)  # Chamar DENTRO de create_app()
    """
    # ✅ Registrar todos os filters
    app.jinja_env.filters['currency_br'] = currency_br
    app.jinja_env.filters['date_br'] = date_br
    app.jinja_env.filters['date_br_short'] = date_br_short
    
    # ✅ Adicionar mais filters aqui no futuro se necessário
