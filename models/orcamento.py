from decimal import Decimal
from models.base import db, BaseMixin, TimestampMixin, SoftDeleteMixin


class Orcamento(db.Model, BaseMixin):
    __tablename__ = "orcamentos"

    id = db.Column(db.Integer, primary_key=True)
    cliente_id = db.Column(
        db.Integer,
        db.ForeignKey("clientes.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    numero = db.Column(db.Integer, nullable=False)
    data_emissao = db.Column(db.Date, nullable=False)
    validade_ate = db.Column(db.Date, nullable=True)
    status = db.Column(db.String(20), nullable=False, default="RASCUNHO", index=True)

    subtotal = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    desconto = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    total = db.Column(db.Numeric(14, 2), nullable=False, default=0)

    condicoes_pagamento = db.Column(db.Text, nullable=True)
    prazo_estimado = db.Column(db.String(160), nullable=True)
    observacoes_cliente = db.Column(db.Text, nullable=True)
    observacoes_internas = db.Column(db.Text, nullable=True)

    cliente = db.relationship("Cliente", back_populates="orcamentos", lazy="joined")
    empresa = db.relationship("Empresa", lazy="select")
    itens = db.relationship(
        "OrcamentoItem",
        back_populates="orcamento",
        lazy="select",
        cascade="all, delete-orphan",
        order_by="OrcamentoItem.ordem.asc(), OrcamentoItem.id.asc()",
    )
    anexos = db.relationship(
        "OrcamentoAnexo",
        back_populates="orcamento",
        lazy="select",
        cascade="all, delete-orphan",
    )
    ordem_servico = db.relationship(
        "OrdemServico",
        back_populates="orcamento",
        uselist=False,
        lazy="select",
    )

    __table_args__ = (
        db.UniqueConstraint("empresa_id", "numero", name="uq_orcamento_empresa_numero"),
        db.Index("idx_orcamento_empresa_status", "empresa_id", "status"),
        db.Index("idx_orcamento_empresa_data", "empresa_id", "data_emissao"),
    )

    @property
    def numero_formatado(self):
        return f"{self.numero:06d}"

    @property
    def custo_estimado(self):
        total = Decimal("0")
        for item in self.itens or []:
            total += item.custo_total
        return total

    @property
    def margem_estimada(self):
        return Decimal(str(self.total or 0)) - self.custo_estimado

    @property
    def margem_percentual(self):
        total = Decimal(str(self.total or 0))
        if total <= 0:
            return Decimal("0")
        return (self.margem_estimada / total) * Decimal("100")


class OrcamentoItem(db.Model, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "orcamento_itens"

    id = db.Column(db.Integer, primary_key=True)
    orcamento_id = db.Column(
        db.Integer,
        db.ForeignKey("orcamentos.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    descricao = db.Column(db.String(220), nullable=False)
    detalhamento = db.Column(db.Text, nullable=True)
    quantidade = db.Column(db.Numeric(12, 3), nullable=False, default=1)
    valor_unitario = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    valor_total = db.Column(db.Numeric(14, 2), nullable=False, default=0)

    medidas = db.Column(db.String(255), nullable=True)
    informacoes_tecnicas = db.Column(db.Text, nullable=True)
    custo_material = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    custo_instalacao = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    outros_custos = db.Column(db.Numeric(14, 2), nullable=False, default=0)

    imagem_base64 = db.Column(db.Text, nullable=True)
    ordem = db.Column(db.Integer, nullable=False, default=0)

    orcamento = db.relationship("Orcamento", back_populates="itens")

    @property
    def custo_total(self):
        return (
            Decimal(str(self.custo_material or 0))
            + Decimal(str(self.custo_instalacao or 0))
            + Decimal(str(self.outros_custos or 0))
        )


class OrcamentoAnexo(db.Model, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "orcamento_anexos"

    id = db.Column(db.Integer, primary_key=True)
    orcamento_id = db.Column(
        db.Integer,
        db.ForeignKey("orcamentos.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    item_id = db.Column(
        db.Integer,
        db.ForeignKey("orcamento_itens.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    nome_arquivo = db.Column(db.String(255), nullable=False)
    mime_type = db.Column(db.String(100), nullable=True)
    arquivo_base64 = db.Column(db.Text, nullable=False)
    descricao = db.Column(db.String(255), nullable=True)
    visivel_cliente = db.Column(db.Boolean, nullable=False, default=False)

    orcamento = db.relationship("Orcamento", back_populates="anexos")
