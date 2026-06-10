# utils/timezone_helpers.py
# Helpers para conversão de timezone (UTC → Horário de Brasília)

from datetime import datetime, timezone
from zoneinfo import ZoneInfo  # Python 3.9+ (nativo, não precisa instalar nada)

# Timezone do Brasil (São Paulo considera horário de verão automaticamente)
BRASIL_TZ = ZoneInfo("America/Sao_Paulo")
UTC_TZ = timezone.utc


def to_brazilia(dt: datetime) -> datetime:
    """
    Converte datetime para horário de Brasília.
    
    Aceita:
    - datetime em UTC (converte para Brasília)
    - datetime naive (assume UTC e converte)
    - datetime já em outro timezone (converte para Brasília)
    
    Returns:
        datetime com timezone America/Sao_Paulo
    """
    if dt is None:
        return None
    
    # Se é naive (sem timezone), assume UTC
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC_TZ)
    
    # Converte para horário de Brasília
    return dt.astimezone(BRASIL_TZ)


def format_brazilia(dt: datetime, fmt: str = "%d/%m/%Y %H:%M") -> str:
    """
    Formata datetime diretamente para string no horário de Brasília.
    
    Args:
        dt: datetime a formatar
        fmt: formato (padrão: '31/12/2024 23:59')
    
    Returns:
        String formatada no horário de Brasília
    """
    if dt is None:
        return "—"
    
    dt_br = to_brazilia(dt)
    return dt_br.strftime(fmt)


def format_brazilia_full(dt: datetime) -> str:
    """Formato completo com dia da semana."""
    if dt is None:
        return "—"
    
    dt_br = to_brazilia(dt)
    # Ex: "Segunda, 09/06/2026 às 19:30"
    dias_semana = [
        "Domingo", "Segunda", "Terça", "Quarta", 
        "Quinta", "Sexta", "Sábado"
    ]
    dia = dias_semana[dt_br.weekday()]
    return f"{dia}, {dt_br.strftime('%d/%m/%Y às %H:%M')}"


def agora_brasil() -> datetime:
    """Retorna o horário atual no fuso de Brasília."""
    return datetime.now(BRASIL_TZ)
