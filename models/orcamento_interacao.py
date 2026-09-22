from models.base import db, BaseMixin


class OrcamentoInteracao(db.Model, BaseMixin):
    __tablename__ = "orcamento_interacoes"

    id = db.Column(db.Integer, primary_key=True)
    orcamento_id = db.Column(db.Integer, db.ForeignKey("orcamentos.id", ondelete="CASCADE"), nullable=False, index=True)
    acao = db.Column(db.String(30), nullable=False)
    nome_cliente = db.Column(db.String(150), nullable=True)
    mensagem = db.Column(db.Text, nullable=True)
    ip_origem = db.Column(db.String(64), nullable=True)
    user_agent = db.Column(db.String(500), nullable=True)

    empresa = db.relationship("Empresa", lazy="select")
    orcamento = db.relationship("Orcamento", back_populates="interacoes")
