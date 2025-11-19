from .base import db
from datetime import datetime

class ContratoTaxa(db.Model):
    __tablename__ = "contratos_taxas"

    id = db.Column(db.Integer, primary_key=True)
    empresa_id = db.Column(db.Integer, db.ForeignKey("empresas.id"), nullable=False)
    adquirente_id = db.Column(db.Integer, db.ForeignKey("adquirentes.id"), nullable=False)

    bandeira = db.Column(db.String(50), nullable=True)      # Visa, Master...
    produto = db.Column(db.String(50), nullable=True)       # Débito, Crédito, Parcelado...
    taxa_percentual = db.Column(db.Numeric(10, 4), nullable=True)
    tarifa_fixa = db.Column(db.Numeric(10, 2), nullable=True)
    aluguel_maquineta = db.Column(db.Numeric(10, 2), nullable=True)
    vigencia_inicio = db.Column(db.Date, nullable=True)
    vigencia_fim = db.Column(db.Date, nullable=True)
    ativo = db.Column(db.Boolean, default=True)

    criado_em = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<ContratoTaxa empresa={self.empresa_id} adquirente={self.adquirente_id}>"
