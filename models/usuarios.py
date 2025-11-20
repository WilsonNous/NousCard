from .base import db
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

class Usuario(db.Model):
    __tablename__ = "usuarios"

    id = db.Column(db.Integer, primary_key=True)

    # Agora permite usuários sem empresa (ex.: MASTER)
    empresa_id = db.Column(db.Integer, db.ForeignKey("empresas.id"), nullable=True)

    nome = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    senha_hash = db.Column(db.String(255), nullable=False)

    # Permissões
    admin = db.Column(db.Boolean, default=False)
    master = db.Column(db.Boolean, default=False)  # 👈 NOVO

    criado_em = db.Column(db.DateTime, default=datetime.utcnow)

    # Relacionamento
    empresa = db.relationship("Empresa", backref="usuarios", lazy=True)

    # ----------------------------------------------------------------------
    # Métodos de segurança
    # ----------------------------------------------------------------------
    def set_password(self, senha):
        self.senha_hash = generate_password_hash(senha)

    def check_password(self, senha):
        return check_password_hash(self.senha_hash, senha)

    # ----------------------------------------------------------------------
    # Propriedades úteis
    # ----------------------------------------------------------------------
    @property
    def is_master(self):
        return bool(self.master)

    @property
    def is_admin(self):
        # MASTER sempre é "super admin"
        if self.master:
            return True
        return bool(self.admin)

    @property
    def has_empresa(self):
        return self.empresa_id is not None

    # ----------------------------------------------------------------------
    def __repr__(self):
        return f"<Usuario {self.email}>"
