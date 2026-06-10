# models/empresa.py - VERSÃO LIMPA (SEM CRIPTOGRAFIA)

from models.base import db, TimestampMixin, SoftDeleteMixin
from datetime import datetime, timezone

class Empresa(db.Model, TimestampMixin, SoftDeleteMixin):
    """
    Modelo de Empresa (tenant principal).
    NÃO usa MultiTenantMixin porque é a tabela raiz.
    """
    __tablename__ = "empresas"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(150), nullable=False)
    documento = db.Column(db.String(20), nullable=True)      # CNPJ (dado público)
    email = db.Column(db.String(120), nullable=True)          # Email (dado público)
    telefone = db.Column(db.String(30), nullable=True)        # Telefone
    logo_url = db.Column(db.String(500), nullable=True)       # Logo da empresa
    
    # Soft-delete estendido
    excluido_em = db.Column(db.DateTime, nullable=True)
    excluido_por = db.Column(db.Integer, nullable=True)

    # ============================================================
    # RELACIONAMENTOS
    # ============================================================
    usuarios = db.relationship(
        "Usuario", back_populates="empresa", lazy=True,
        cascade="all, delete-orphan"
    )
    contas_bancarias = db.relationship(
        "ContaBancaria", back_populates="empresa", lazy=True,
        cascade="all, delete-orphan"
    )
    contratos = db.relationship(
        "ContratoTaxa", back_populates="empresa", lazy=True,
        cascade="all, delete-orphan"
    )
    movimentos_adquirente = db.relationship(
        "MovAdquirente", back_populates="empresa", lazy=True,
        cascade="all, delete-orphan"
    )
    movimentos_banco = db.relationship(
        "MovBanco", back_populates="empresa", lazy=True,
        cascade="all, delete-orphan"
    )
    conciliacoes = db.relationship(
        "Conciliacao", back_populates="empresa", lazy=True,
        cascade="all, delete-orphan"
    )
    logs_auditoria = db.relationship(
        "LogAuditoria", back_populates="empresa", lazy=True,
        cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Empresa {self.nome}>"
