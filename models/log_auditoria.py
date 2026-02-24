from .base import db
from datetime import datetime, timezone

class LogAuditoria(db.Model):
    __tablename__ = "log_auditoria"

    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=True)
    empresa_id = db.Column(db.Integer, db.ForeignKey("empresas.id"), nullable=True)
    acao = db.Column(db.String(50), nullable=False)
    detalhes = db.Column(db.Text, nullable=True)
    ip = db.Column(db.String(45), nullable=True)
    criado_em = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    usuario = db.relationship("Usuario", backref="logs_auditoria")
    empresa = db.relationship("Empresa", backref="logs_auditoria")

    __table_args__ = (
        db.Index('idx_log_empresa', 'empresa_id', 'criado_em'),
        db.Index('idx_log_usuario', 'usuario_id', 'criado_em'),
        db.Index('idx_log_acao', 'acao'),
    )

    def __repr__(self):
        return f"<LogAuditoria {self.acao} - {self.criado_em}>"
