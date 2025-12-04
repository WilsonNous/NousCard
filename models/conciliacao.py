from .base import db
from datetime import datetime

class Conciliacao(db.Model):
    __tablename__ = "conciliacoes"

    id = db.Column(db.Integer, primary_key=True)

    # Empresa dona do registro
    empresa_id = db.Column(db.Integer, db.ForeignKey("empresas.id"), nullable=False)

    # Ligações
    mov_adquirente_id = db.Column(db.Integer, db.ForeignKey("mov_adquirente.id"), nullable=True)
    mov_banco_id = db.Column(db.Integer, db.ForeignKey("mov_banco.id"), nullable=True)

    # Valores
    valor_previsto = db.Column(db.Numeric(12, 2), nullable=True)
    valor_conciliado = db.Column(db.Numeric(12, 2), nullable=True)

    # Metadados
    tipo = db.Column(db.String(20), default="automatico")  # automatico / manual
    status = db.Column(db.String(30), default="pendente")  # pendente / conciliado / parcial / divergente
    motivo = db.Column(db.String(255), nullable=True)

    criado_em = db.Column(db.DateTime, default=datetime.utcnow)

    # -----------------------------------------------------------
    # RELACIONAMENTOS AUTOMÁTICOS (ajuda nas consultas)
    # -----------------------------------------------------------
    mov_adquirente = db.relationship("MovAdquirente", backref="historico_conciliacao", lazy=True)
    mov_banco = db.relationship("MovBanco", backref="historico_conciliacao", lazy=True)

    def __repr__(self):
        return (
            f"<Conciliacao "
            f"id={self.id} "
            f"empresa={self.empresa_id} "
            f"status={self.status} "
            f"valor={self.valor_conciliado}>"
        )
