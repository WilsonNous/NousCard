from models.base import db, BaseMixin


class OrdemServico(db.Model, BaseMixin):
    __tablename__ = "ordens_servico"

    id = db.Column(db.Integer, primary_key=True)
    orcamento_id = db.Column(
        db.Integer,
        db.ForeignKey("orcamentos.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
        index=True,
    )
    cliente_id = db.Column(
        db.Integer,
        db.ForeignKey("clientes.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    numero = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(30), nullable=False, default="AGUARDANDO_MATERIAL", index=True)
    endereco_execucao = db.Column(db.String(255), nullable=True)
    data_prevista = db.Column(db.Date, nullable=True)
    responsavel = db.Column(db.String(150), nullable=True)
    descricao_execucao = db.Column(db.Text, nullable=True)
    informacoes_tecnicas = db.Column(db.Text, nullable=True)
    observacoes = db.Column(db.Text, nullable=True)

    empresa = db.relationship("Empresa", lazy="select")
    cliente = db.relationship("Cliente", back_populates="ordens_servico", lazy="joined")
    orcamento = db.relationship("Orcamento", back_populates="ordem_servico", lazy="joined")

    __table_args__ = (
        db.UniqueConstraint("empresa_id", "numero", name="uq_os_empresa_numero"),
        db.Index("idx_os_empresa_status", "empresa_id", "status"),
    )

    @property
    def numero_formatado(self):
        return f"{self.numero:06d}"
