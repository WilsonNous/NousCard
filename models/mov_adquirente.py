from .base import db
from datetime import datetime

class MovAdquirente(db.Model):
    __tablename__ = "mov_adquirente"

    id = db.Column(db.Integer, primary_key=True)
    empresa_id = db.Column(db.Integer, db.ForeignKey("empresas.id"), nullable=False)
    adquirente_id = db.Column(db.Integer, db.ForeignKey("adquirentes.id"), nullable=False)

    data_venda = db.Column(db.Date, nullable=True)
    data_prevista_pagamento = db.Column(db.Date, nullable=True)
    bandeira = db.Column(db.String(50), nullable=True)
    produto = db.Column(db.String(50), nullable=True)
    nsu = db.Column(db.String(50), nullable=True)
    autorizacao = db.Column(db.String(50), nullable=True)
    valor_bruto = db.Column(db.Numeric(12, 2), nullable=False)
    taxa_cobrada = db.Column(db.Numeric(10, 4), nullable=True)
    valor_liquido = db.Column(db.Numeric(12, 2), nullable=True)
    arquivo_origem = db.Column(db.String(255), nullable=True)

    criado_em = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<MovAdquirente id={self.id} valor={self.valor_bruto}>"
