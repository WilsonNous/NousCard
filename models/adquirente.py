from .base import db
from datetime import datetime

class Adquirente(db.Model):
    __tablename__ = "adquirentes"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    codigo = db.Column(db.String(30), nullable=True)

    # NOVOS CAMPOS
    prazo_dias = db.Column(db.Integer, default=2)  # D+2, D+1, etc.
    consolida_por_dia = db.Column(db.Boolean, default=False)
    palavras_chave_extrato = db.Column(db.String(255))  # p/ identificar no histórico do banco
    banco_preferencial = db.Column(db.String(50))        # Itaú, Bradesco, etc.

    criado_em = db.Column(db.DateTime, default=datetime.utcnow)

    contratos = db.relationship("ContratoTaxa", backref="adquirente", lazy=True)
    movimentos = db.relationship("MovAdquirente", backref="adquirente", lazy=True)

    def __repr__(self):
        return f"<Adquirente {self.nome}>"
