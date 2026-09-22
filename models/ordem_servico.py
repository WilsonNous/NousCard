from decimal import Decimal
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
    valor_recebido = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    taxa_pagamento = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    forma_pagamento = db.Column(db.String(30), nullable=True)

    empresa = db.relationship("Empresa", lazy="select")
    cliente = db.relationship("Cliente", back_populates="ordens_servico", lazy="joined")
    orcamento = db.relationship("Orcamento", back_populates="ordem_servico", lazy="joined")
    custos = db.relationship("OrdemServicoCusto", back_populates="ordem_servico", lazy="select", cascade="all, delete-orphan", order_by="OrdemServicoCusto.id.desc()")

    __table_args__ = (
        db.UniqueConstraint("empresa_id", "numero", name="uq_os_empresa_numero"),
        db.Index("idx_os_empresa_status", "empresa_id", "status"),
    )


    @property
    def custo_real(self):
        return sum((Decimal(str(c.valor or 0)) for c in (self.custos or [])), Decimal("0"))

    @property
    def receita_bruta(self):
        return Decimal(str(self.orcamento.total or 0)) if self.orcamento else Decimal("0")

    @property
    def resultado_real(self):
        recebido = Decimal(str(self.valor_recebido or 0)) or self.receita_bruta
        return recebido - self.custo_real - Decimal(str(self.taxa_pagamento or 0))

    @property
    def margem_real_percentual(self):
        base = Decimal(str(self.valor_recebido or 0)) or self.receita_bruta
        return (self.resultado_real / base * Decimal("100")) if base > 0 else Decimal("0")

    @property
    def numero_formatado(self):
        return f"{self.numero:06d}"
