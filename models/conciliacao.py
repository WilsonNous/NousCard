from .base import db
from datetime import datetime

class Conciliacao(db.Model):
    __tablename__ = "conciliacoes"

    id = db.Column(db.Integer, primary_key=True)
    empresa_id = db.Column(db.Integer, db.ForeignKey("empresas.id"), nullable=False)

    mov_adquirente_id = db.Column(db.Integer, db.ForeignKey("mov_adquirente.id"), nullable=True)
    mov_banco_id = db.Column(db.Integer, db.ForeignKey("mov_banco.id"), nullable=True)

    valor_previsto = db.Column(db.Numeric(12, 2), nullable=True)
    valor_conciliado = db.Column(db.Numeric(12, 2), nullable=True)

    tipo = db.Column(db.String(20), default="automatico") # automatico / manual
    status = db.Column(db.String(30), default="pendente")
    motivo = db.Column(db.String(255), nullable=True)

    criado_em = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Conciliacao id={self.id} status={self.status} valor={self.valor_conciliado}>"
