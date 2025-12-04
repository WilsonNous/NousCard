from .base import db
from datetime import datetime

class MovBanco(db.Model):
    __tablename__ = "mov_banco"

    id = db.Column(db.Integer, primary_key=True)
    empresa_id = db.Column(db.Integer, db.ForeignKey("empresas.id"), nullable=False)

    # Relacionamento com contas bancárias
    conta_bancaria_id = db.Column(
        db.Integer,
        db.ForeignKey("contas_bancarias.id"),
        nullable=True
    )

    data_movimento = db.Column(db.Date, nullable=False)

    banco = db.Column(db.String(50), nullable=True)
    historico = db.Column(db.String(255), nullable=True)

    # 🔹 CAMPO EXISTENTE NO BANCO, FALTAVA NO MODELO
    documento = db.Column(db.String(100), nullable=True)

    origem = db.Column(db.String(50), nullable=True)

    valor = db.Column(db.Numeric(12, 2), nullable=False)

    valor_conciliado = db.Column(db.Numeric(12, 2), default=0)
    conciliado = db.Column(db.Boolean, default=False)

    # 🔹 TAMBÉM EXISTE NO BANCO E É USADO PELO IMPORTADOR
    arquivo_origem = db.Column(db.String(255), nullable=True)

    criado_em = db.Column(db.DateTime, default=datetime.utcnow)

    # Relacionamento com conciliações
    conciliacoes = db.relationship(
        "Conciliacao",
        back_populates="mov_banco",
        lazy=True
    )

    def __repr__(self):
        return f"<MovBanco {self.id} R${self.valor}>"
