from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timezone
from flask import g

db = SQLAlchemy()

# ============================================================
# MIXINS PARA PADRÕES TRANSVERSAIS
# ============================================================

class TimestampMixin:
    """Adiciona timestamps com timezone"""
    criado_em = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )
    atualizado_em = db.Column(
        db.DateTime(timezone=True),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=True
    )

class SoftDeleteMixin:
    """Adiciona soft delete"""
    ativo = db.Column(db.Boolean, default=True, nullable=False)

class MultiTenantMixin:
    """Garante isolamento por empresa"""
    empresa_id = db.Column(db.Integer, db.ForeignKey("empresas.id"), nullable=False)

    @classmethod
    def query_tenant(cls, empresa_id=None):
        if empresa_id is None:
            user = getattr(g, "user", None)
            if user and hasattr(user, "empresa_id"):
                empresa_id = user.empresa_id
            else:
                raise ValueError("empresa_id não disponível no contexto")
        return cls.query.filter_by(empresa_id=empresa_id)

class BaseMixin(TimestampMixin, SoftDeleteMixin, MultiTenantMixin):
    """Combina todos os mixins padrão"""
    pass
