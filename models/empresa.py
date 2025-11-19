from .base import db
from datetime import datetime

class Empresa(db.Model):
    __tablename__ = "empresas"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(150), nullable=False)
    documento = db.Column(db.String(20), nullable=True)  # CNPJ/CPF
    email = db.Column(db.String(120), nullable=True)
    telefone = db.Column(db.String(30), nullable=True)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)

    contas_bancarias = db.relationship("ContaBancaria", backref="empresa", lazy=True)
    contratos = db.relationship("ContratoTaxa", backref="empresa", lazy=True)

    def __repr__(self):
        return f"<Empresa {self.nome}>"
