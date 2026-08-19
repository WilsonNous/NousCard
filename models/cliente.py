from models.base import db, BaseMixin


class Cliente(db.Model, BaseMixin):
    __tablename__ = "clientes"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(180), nullable=False, index=True)
    tipo_pessoa = db.Column(db.String(2), nullable=False, default="PF")
    documento = db.Column(db.String(20), nullable=True, index=True)
    telefone = db.Column(db.String(30), nullable=True)
    email = db.Column(db.String(150), nullable=True)
    endereco = db.Column(db.String(255), nullable=True)
    cidade = db.Column(db.String(100), nullable=True)
    uf = db.Column(db.String(2), nullable=True)
    observacoes = db.Column(db.Text, nullable=True)

    empresa = db.relationship("Empresa", lazy="select")
    orcamentos = db.relationship(
        "Orcamento", back_populates="cliente", lazy="dynamic"
    )
    ordens_servico = db.relationship(
        "OrdemServico", back_populates="cliente", lazy="dynamic"
    )

    __table_args__ = (
        db.Index("idx_cliente_empresa_nome", "empresa_id", "nome"),
        db.Index("idx_cliente_empresa_documento", "empresa_id", "documento"),
    )

    def __repr__(self):
        return f"<Cliente {self.nome}>"
