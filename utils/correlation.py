import uuid
from datetime import datetime


def gerar_correlation_id(prefixo="PROC"):
    return (
        f"{prefixo}_"
        f"{datetime.utcnow():%Y%m%d%H%M%S}_"
        f"{uuid.uuid4().hex[:8]}"
    )