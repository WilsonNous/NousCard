from .base import db, TimestampMixin
from datetime import datetime, timezone
from decimal import Decimal
import os
from cryptography.fernet import Fernet

class ArquivoImportado(db.Model, TimestampMixin):
    __tablename__ = "arquivos_importados"

    id = db.Column(db.Integer, primary_key=True)
    empresa_id = db.Column(db.Integer, db.ForeignKey("empresas.id"), nullable=False)
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=False)
    nome_arquivo = db.Column(db.String(255), nullable=False)
    tipo = db.Column(db.String(20), nullable=False)  # "venda" ou "recebimento"
    hash_arquivo = db.Column(db.String(64), unique=True, nullable=False, index=True)
    total_registros = db.Column(db.Integer, default=0)
    total_valor = db.Column(db.Numeric(15, 2), default=0)
    _conteudo_json_encrypted = db.Column("conteudo_json", db.Text, nullable=True)

    empresa = db.relationship("Empresa", back_populates="arquivos_importados")
    usuario = db.relationship("Usuario", backref="arquivos_importados")

    __table_args__ = (
        db.Index('idx_arquivo_empresa', 'empresa_id', 'criado_em'),
        db.Index('idx_arquivo_hash', 'hash_arquivo'),
    )

    # Criptografia de conteúdo
    @property
    def conteudo_json(self):
        if self._conteudo_json_encrypted and os.getenv("ENCRYPTION_KEY"):
            try:
                f = Fernet(os.getenv("ENCRYPTION_KEY"))
                return f.decrypt(self._conteudo_json_encrypted.encode()).decode()
            except:
                return self._conteudo_json_encrypted
        return self._conteudo_json_encrypted

    @conteudo_json.setter
    def conteudo_json(self, value):
        if value and os.getenv("ENCRYPTION_KEY"):
            try:
                f = Fernet(os.getenv("ENCRYPTION_KEY"))
                self._conteudo_json_encrypted = f.encrypt(value.encode()).decode()
            except:
                self._conteudo_json_encrypted = value
        else:
            self._conteudo_json_encrypted = value

    def __repr__(self):
        return f"<ArquivoImportado {self.nome_arquivo}>"
