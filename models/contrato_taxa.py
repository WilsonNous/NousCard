# models/contrato_taxa.py
from models.base import db, BaseMixin
from datetime import datetime, timezone
from decimal import Decimal

class ContratoTaxa(db.Model, BaseMixin):
    __tablename__ = "contratos_taxas"

    id = db.Column(db.Integer, primary_key=True)
    # empresa_id vem do BaseMixin (MultiTenantMixin)
    
    adquirente_id = db.Column(
        db.Integer,
        db.ForeignKey("adquirentes.id"),
        nullable=False
    )
    
    bandeira = db.Column(db.String(50), nullable=True)  # Visa, Mastercard, etc.
    produto = db.Column(db.String(50), nullable=True)   # Débito, Crédito, PIX
    taxa_percentual = db.Column(db.Numeric(5, 2), nullable=True)  # Ex: 2.50 = 2.5%
    tarifa_fixa = db.Column(db.Numeric(10, 2), default=Decimal("0"))  # Ex: 0.10 = R$ 0,10
    
    vigencia_inicio = db.Column(db.Date, nullable=True)
    vigencia_fim = db.Column(db.Date, nullable=True)
    
    observacoes = db.Column(db.Text, nullable=True)

    # ============================================================
    # RELACIONAMENTOS
    # ============================================================
    
    # Back-populate para Empresa (DEVE bater com Empresa.contratos)
    empresa = db.relationship(
        "Empresa",
        back_populates="contratos",  # ✅ Este nome deve existir em Empresa
        lazy=True
    )
    
    # Back-populate para Adquirente
    adquirente = db.relationship(
        "Adquirente",
        back_populates="contratos",  # ✅ Deve bater com Adquirente.contratos
        lazy=True
    )

    # ============================================================
    # REPRESENTAÇÃO
    # ============================================================
    
    def __repr__(self):
        return f"<ContratoTaxa {self.bandeira}/{self.produto} - {self.taxa_percentual}%>"
