# ============================================================
#  MODELS BASE • NousCard
#  Compatível com SQLAlchemy 1.4.x + Flask-SQLAlchemy 3.0.x
# ============================================================

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.ext.declarative import declared_attr  # ✅ IMPORTANTE para ForeignKeys em mixins
from datetime import datetime, timezone
from flask import g

# Inicializar SQLAlchemy
db = SQLAlchemy()

# ============================================================
# MIXINS PARA PADRÕES TRANSVERSAIS
# ============================================================

class TimestampMixin:
    """
    Adiciona campos de timestamp com timezone.
    Compatível com SQLAlchemy 1.4 e 2.0.
    """
    @declared_attr
    def criado_em(cls):
        return db.Column(
            db.DateTime(timezone=True),
            default=lambda: datetime.now(timezone.utc),
            nullable=False,
            index=True
        )
    
    @declared_attr
    def atualizado_em(cls):
        return db.Column(
            db.DateTime(timezone=True),
            onupdate=lambda: datetime.now(timezone.utc),
            nullable=True,
            index=True
        )


class SoftDeleteMixin:
    """
    Adiciona soft delete (flag ativo/inativo).
    Nunca exclui dados permanentemente, apenas marca como inativo.
    """
    @declared_attr
    def ativo(cls):
        return db.Column(
            db.Boolean,
            default=True,
            nullable=False,
            index=True
        )


class MultiTenantMixin:
    """
    Garante isolamento de dados por empresa (multi-tenant).
    Todas as queries devem filtrar por empresa_id.
    
    Nota: ForeignKey em mixins DEVE usar @declared_attr no SQLAlchemy 1.4+
    """
    @declared_attr
    def empresa_id(cls):
        return db.Column(
            db.Integer,
            db.ForeignKey("empresas.id", ondelete="CASCADE"),
            nullable=False,
            index=True
        )

    @classmethod
    def query_tenant(cls, empresa_id=None):
        """
        Retorna query já filtrada por empresa_id.
        
        Args:
            empresa_id: ID da empresa (opcional, usa g.user se None)
        
        Returns:
            Query filtrada por empresa_id
        
        Raises:
            ValueError: Se empresa_id não estiver disponível no contexto
        """
        if empresa_id is None:
            user = getattr(g, "user", None)
            if user and hasattr(user, "empresa_id"):
                empresa_id = user.empresa_id
            else:
                raise ValueError("empresa_id não disponível no contexto")
        
        return cls.query.filter_by(empresa_id=empresa_id)


class BaseMixin(TimestampMixin, SoftDeleteMixin, MultiTenantMixin):
    """
    Combina todos os mixins padrão.
    Use este mixin em todos os modelos que precisam de:
    - Timestamps (criado_em, atualizado_em)
    - Soft delete (ativo)
    - Multi-tenant (empresa_id)
    """
    pass


# ============================================================
# HELPER: INICIALIZAÇÃO DO BANCO
# ============================================================

def init_db(app):
    """
    Inicializa o banco de dados com o app Flask.
    
    Args:
        app: Aplicação Flask
    
    Usage:
        from models.base import db, init_db
        db.init_app(app)
        init_db(app)
    """
    db.init_app(app)
    
    with app.app_context():
        # Criar tabelas se não existirem (apenas para desenvolvimento)
        # Em produção, use: flask db upgrade
        if app.config.get('FLASK_ENV') == 'development':
            db.create_all()


# ============================================================
# HELPER: LIMPEZA DE SESSÃO
# ============================================================

def cleanup_session(exception=None):
    """
    Remove a sessão do banco após cada request.
    Previne vazamento de conexões e memória.
    
    Usage:
        app.teardown_appcontext(cleanup_session)
    """
    db.session.remove()
