from .base import db
from datetime import datetime

class Adquirente(db.Model):
    __tablename__ = "adquirentes"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    codigo = db.Column(db.String(30), nullable=True)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)

    contratos = db.relationship("ContratoTaxa", backref="adquirente", lazy=True)
    movimentos = db.relationship("MovAdquirente", backref="adquirente", lazy=True)

    def __repr__(self):
        return f"<Adquirente {self.nome}>"
