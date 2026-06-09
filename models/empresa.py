# models/empresa.py - VERSÃO CORRIGIDA
from models.base import db, TimestampMixin, SoftDeleteMixin
from datetime import datetime, timezone
import os
from cryptography.fernet import Fernet

class Empresa(db.Model, TimestampMixin, SoftDeleteMixin):
    """
    Modelo de Empresa (tenant principal).
    NÃO usa MultiTenantMixin porque é a tabela raiz.
    """
    __tablename__ = "empresas"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(150), nullable=False)
    _documento_encrypted = db.Column("documento", db.String(255), nullable=True)
    _email_encrypted = db.Column("email", db.String(255), nullable=True)
    telefone = db.Column(db.String(30), nullable=True)
    logo_url = db.Column(db.String(500), nullable=True)  # ✅ Explícito aqui
    
    # Campos de soft-delete estendido
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

    # ============================================================
    # CRIPTOGRAFIA
    # ============================================================
    @property
    def documento(self):
        if self._documento_encrypted and os.getenv("ENCRYPTION_KEY"):
            try:
                f = Fernet(os.getenv("ENCRYPTION_KEY"))
                return f.decrypt(self._documento_encrypted.encode()).decode()
            except:
                return self._documento_encrypted
        return self._documento_encrypted

    @documento.setter
    def documento(self, value):
        if value and os.getenv("ENCRYPTION_KEY"):
            try:
                f = Fernet(os.getenv("ENCRYPTION_KEY"))
                self._documento_encrypted = f.encrypt(value.encode()).decode()
            except:
                self._documento_encrypted = value
        else:
            self._documento_encrypted = value

    @property
    def email(self):
        if self._email_encrypted and os.getenv("ENCRYPTION_KEY"):
            try:
                f = Fernet(os.getenv("ENCRYPTION_KEY"))
                return f.decrypt(self._email_encrypted.encode()).decode()
            except:
                return self._email_encrypted
        return self._email_encrypted

    @email.setter
    def email(self, value):
        if value and os.getenv("ENCRYPTION_KEY"):
            try:
                f = Fernet(os.getenv("ENCRYPTION_KEY"))
                self._email_encrypted = f.encrypt(value.encode()).decode()
            except:
                self._email_encrypted = value
        else:
            self._email_encrypted = value

    def __repr__(self):
        return f"<Empresa {self.nome}>"
