from decimal import Decimal
from models.base import db, BaseMixin


class OrdemServicoCusto(db.Model, BaseMixin):
    __tablename__ = "ordem_servico_custos"

    id = db.Column(db.Integer, primary_key=True)
    ordem_servico_id = db.Column(db.Integer, db.ForeignKey("ordens_servico.id", ondelete="CASCADE"), nullable=False, index=True)
    tipo = db.Column(db.String(30), nullable=False, default="OUTRO")
    descricao = db.Column(db.String(220), nullable=False)
    fornecedor = db.Column(db.String(160), nullable=True)
    valor = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    data_custo = db.Column(db.Date, nullable=True)
    observacoes = db.Column(db.Text, nullable=True)

    empresa = db.relationship("Empresa", lazy="select")
    ordem_servico = db.relationship("OrdemServico", back_populates="custos")

    @property
    def valor_decimal(self):
        return Decimal(str(self.valor or 0))
