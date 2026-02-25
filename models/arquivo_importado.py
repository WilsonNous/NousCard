# models/arquivo_importado.py - VERSÃO ULTRA-MINIMALISTA (SEM CONFLITOS)
from .base import db, BaseMixin
from datetime import datetime, timezone
from decimal import Decimal

class ArquivoImportado(db.Model, BaseMixin):
    """
    Versão minimalista: apenas campos essenciais + FKs.
    Sem db.relationship para evitar qualquer conflito de back_populates.
    
    Para acessar empresa: use empresa = Empresa.query.get(arquivo.empresa_id)
    Para acessar usuário: use usuario = Usuario.query.get(arquivo.usuario_id)
    """
    __tablename__ = "arquivos_importados"

    id = db.Column(db.Integer, primary_key=True)
    # ✅ empresa_id e criado_em vêm do BaseMixin - NÃO redeclarar!
    
    # FK para usuário (apenas chave, sem relationship bidirecional)
    usuario_id = db.Column(
        db.Integer,
        db.ForeignKey("usuarios.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    
    # Metadados do arquivo
    nome_arquivo = db.Column(db.String(255), nullable=False)
    tipo = db.Column(db.String(20), nullable=False)  # "venda" ou "recebimento"
    hash_arquivo = db.Column(db.String(64), nullable=False, unique=True, index=True)
    total_registros = db.Column(db.Integer, default=0)
    total_valor = db.Column(db.Numeric(15, 2), default=Decimal("0"))
    
    # Conteúdo (pode ser JSON criptografado)
    _conteudo_json_encrypted = db.Column("conteudo_json", db.Text, nullable=True)
    
    # Status
    status_processamento = db.Column(db.String(20), default="processado", index=True)
    erro_processamento = db.Column(db.String(255), nullable=True)

    # ⚠️ SEM db.relationship() - usar queries diretas para evitar conflitos
    # Ex: Empresa.query.get(arquivo.empresa_id)

    __table_args__ = (
        db.Index('idx_arquivo_empresa_data', 'empresa_id', 'criado_em'),
        db.Index('idx_arquivo_hash', 'hash_arquivo', unique=True),
    )

    def __repr__(self):
        return f"<ArquivoImportado id={self.id} nome={self.nome_arquivo}>"
