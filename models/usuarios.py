from .base import db, TimestampMixin, SoftDeleteMixin
from datetime import datetime, timezone
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin

class Usuario(db.Model, UserMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "usuarios"

    id = db.Column(db.Integer, primary_key=True)
    empresa_id = db.Column(db.Integer, db.ForeignKey("empresas.id"), nullable=True)

    nome = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(150), nullable=False, unique=True)
    senha_hash = db.Column(db.String(255), nullable=False)

    admin = db.Column(db.Boolean, default=False)
    master = db.Column(db.Boolean, default=False)

    # Segurança
    ultimo_login = db.Column(db.DateTime(timezone=True), nullable=True)
    tentativas_login_falhas = db.Column(db.Integer, default=0)
    bloqueado_ate = db.Column(db.DateTime(timezone=True), nullable=True)
    token_recuperacao = db.Column(db.String(255), nullable=True)
    token_expiracao = db.Column(db.DateTime(timezone=True), nullable=True)

    empresa = db.relationship("Empresa", back_populates="usuarios", lazy="joined")

    __table_args__ = (
        db.Index('idx_usuario_email', 'email'),
        db.Index('idx_usuario_empresa', 'empresa_id', 'ativo'),
    )

    def set_password(self, password):
        self.senha_hash = generate_password_hash(password, method='pbkdf2:sha256')

    def check_password(self, password):
        return check_password_hash(self.senha_hash, password)

    @property
    def is_master(self):
        return bool(self.master)

    @property
    def is_admin(self):
        return bool(self.admin)

    def is_active(self):
        if not self.ativo:
            return False
        if self.bloqueado_ate and self.bloqueado_ate > datetime.now(timezone.utc):
            return False
        return True

    def __repr__(self):
        return f"<Usuario {self.email}>"
