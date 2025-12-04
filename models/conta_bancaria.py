from .base import db
from datetime import datetime

class ContaBancaria(db.Model):
    __tablename__ = "contas_bancarias"

    id = db.Column(db.Integer, primary_key=True)
    empresa_id = db.Column(db.Integer, db.ForeignKey("empresas.id"), nullable=False)

    banco = db.Column(db.String(100), nullable=False)
    agencia = db.Column(db.String(20), nullable=True)
    conta = db.Column(db.String(20), nullable=True)
    apelido = db.Column(db.String(50), nullable=True)

    criado_em = db.Column(db.DateTime, default=datetime.utcnow)

    mov_banco = db.relationship("MovBanco", backref="conta_bancaria", lazy=True)

    def __repr__(self):
        return f"<Conta {self.banco} - {self.agencia}/{self.conta}>"
