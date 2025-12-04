# models/mov_banco.py
from .base import db
from datetime import datetime

class MovBanco(db.Model):
    __tablename__ = "mov_banco"

    id = db.Column(db.Integer, primary_key=True)
    empresa_id = db.Column(db.Integer, db.ForeignKey("empresas.id"), nullable=False)

    data_movimento = db.Column(db.Date, nullable=False)

    banco = db.Column(db.String(50), nullable=True)
    historico = db.Column(db.String(255), nullable=True)

    origem = db.Column(db.String(50), nullable=True)   # ex: cielo, rede, stone...

    valor = db.Column(db.Numeric(12, 2), nullable=False)

    # ===================================================================
    # Novos campos necessários para conciliação avançada
    # ===================================================================
    valor_conciliado = db.Column(db.Numeric(12, 2), default=0)
    conciliado = db.Column(db.Boolean, default=False)

    criado_em = db.Column(db.DateTime, default=datetime.utcnow)

    conciliacoes = db.relationship("Conciliacao", backref="mov_banco", lazy=True)

    def __repr__(self):
        return (
            f"<MovBanco id={self.id} "
            f"data={self.data_movimento} "
            f"valor={float(self.valor) if self.valor is not None else 0} "
            f"conciliado={self.conciliado}>"
        )
