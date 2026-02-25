# models/conta_bancaria.py
from models.base import db, BaseMixin
from datetime import datetime, timezone

class ContaBancaria(db.Model, BaseMixin):
    __tablename__ = "contas_bancarias"

    id = db.Column(db.Integer, primary_key=True)
    # empresa_id vem do BaseMixin (MultiTenantMixin)
    
    nome = db.Column(db.String(100), nullable=False)
    banco = db.Column(db.String(100), nullable=True)
    agencia = db.Column(db.String(20), nullable=True)
    conta = db.Column(db.String(30), nullable=True)
    tipo = db.Column(db.String(20), nullable=True)  # "corrente", "poupança", etc.
    
    # ============================================================
    # RELACIONAMENTOS
    # ============================================================
    
    # Back-populate para Empresa
    empresa = db.relationship(
        "Empresa",
        back_populates="contas_bancarias",
        lazy=True
    )
    
    # Movimentos bancários
    movimentos = db.relationship(
        "MovBanco",
        back_populates="conta_bancaria",
        lazy=True,
        cascade="all, delete-orphan"
    )

    # ============================================================
    # REPRESENTAÇÃO
    # ============================================================
    
    def __repr__(self):
        return f"<ContaBancaria {self.nome} - {self.banco}>"
