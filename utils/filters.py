# utils/filters.py - Filtros Jinja2 personalizados para templates

from decimal import Decimal, InvalidOperation


def currency_br(value):
    """
    Formata valor monetário para padrão brasileiro.
    
    Uso em templates Jinja2:
        {{ valor | currency_br }}
        {{ 1234.56 | currency_br }}  → "1.234,56"
    
    Args:
        value: Decimal, float, int, str ou None
        
    Returns:
        str: Valor formatado no padrão brasileiro (ex: "1.234,56")
    """
    if value is None or value == '':
        return "0,00"
    
    try:
        # Converter para Decimal para precisão monetária
        num = Decimal(str(value))
        
        # Formatar com 2 casas decimais e separadores brasileiros
        # Passo 1: formatar com separador de milhar em inglês
        formatted = f"{num:,.2f}"
        # Passo 2: trocar separadores (inglês → brasileiro)
        formatted = formatted.replace(",", "X")  # placeholder temporário
        formatted = formatted.replace(".", ",")   # decimal: ponto → vírgula
        formatted = formatted.replace("X", ".")   # milhar: X → ponto
        
        return formatted
        
    except (InvalidOperation, ValueError, TypeError) as e:
        # Fallback seguro: retorna 0,00 se não conseguir formatar
        return "0,00"


def register_filters(app):
    """
    Registra todos os filters personalizados no ambiente Jinja2 do Flask.
    
    Args:
        app: Instância Flask configurada
        
    Usage:
        from utils.filters import register_filters
        register_filters(app)  # Chamar após app = Flask(__name__)
    """
    # Registrar filter de moeda brasileira
    app.jinja_env.filters['currency_br'] = currency_br
    
    # ✅ Adicionar mais filters aqui no futuro se necessário:
    # app.jinja_env.filters['outro_filter'] = outra_funcao


def date_br(value):
    """Formata datetime para DD/MM/YYYY"""
    if not value:
        return "—"
    return value.strftime("%d/%m/%Y") if hasattr(value, 'strftime') else str(value)

def percent_br(value):
    """Formata decimal como porcentagem brasileira"""
    if value is None:
        return "0%"
    return f"{float(value)*100:.2f}%".replace(".", ",")

# No register_filters():
app.jinja_env.filters['date_br'] = date_br
app.jinja_env.filters['percent_br'] = percent_br
