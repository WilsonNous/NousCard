from models.base import db, BaseMixin


class Veiculo(db.Model, BaseMixin):
    __tablename__ = "veiculos"

    id = db.Column(db.Integer, primary_key=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey("clientes.id", ondelete="CASCADE"), nullable=False, index=True)
    placa = db.Column(db.String(10), nullable=False)
    marca = db.Column(db.String(80), nullable=True)
    modelo = db.Column(db.String(100), nullable=False)
    ano = db.Column(db.String(10), nullable=True)
    cor = db.Column(db.String(50), nullable=True)
    quilometragem = db.Column(db.Integer, nullable=True)
    chassi = db.Column(db.String(30), nullable=True)
    seguradora = db.Column(db.String(120), nullable=True)
    observacoes = db.Column(db.Text, nullable=True)

    empresa = db.relationship("Empresa", lazy="select")
    cliente = db.relationship("Cliente", back_populates="veiculos", lazy="joined")
    orcamentos = db.relationship("Orcamento", back_populates="veiculo", lazy="dynamic")

    __table_args__ = (
        db.UniqueConstraint("empresa_id", "placa", name="uq_veiculo_empresa_placa"),
        db.Index("idx_veiculo_empresa_cliente", "empresa_id", "cliente_id"),
    )

    @property
    def descricao(self):
        partes = [self.placa, self.marca, self.modelo, self.ano]
        return " • ".join(str(x) for x in partes if x)
