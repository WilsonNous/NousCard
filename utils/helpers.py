def format_currency_br(value: float) -> str:
    try:
        value = float(value)
        return f"R$ {value:,.2f}".replace(",", "v").replace(".", ",").replace("v", ".")
    except (TypeError, ValueError):
        return "R$ 0,00"
