from .base import db
from datetime import datetime

class MovBanco(db.Model):
    __tablename__ = "mov_banco"

    id = db.Column(db.Integer, primary_key=True)
    conta_bancaria_id = db.Column(db.Integer, db.ForeignKey("contas_bancarias.id"), nullable=False)
    empresa_id = db.Column(db.Integer, db.ForeignKey("empresas.id"), nullable=False)

    data_movimento = db.Column(db.Date, nullable=False)
    historico = db.Column(db.String(255), nullable=True)
    documento = db.Column(db.String(100), nullable=True)
    valor = db.Column(db.Numeric(12, 2), nullable=False)
    arquivo_origem = db.Column(db.String(255), nullable=True)

    criado_em = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<MovBanco id={self.id} valor={self.valor}>"
