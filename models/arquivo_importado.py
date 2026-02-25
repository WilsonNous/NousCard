# models/arquivo_importado.py - VERSÃO MINIMALISTA FUNCIONAL
from .base import db, BaseMixin
from datetime import datetime, timezone
from decimal import Decimal

class ArquivoImportado(db.Model, BaseMixin):
    """Versão simplificada sem conflitos de relacionamento"""
    __tablename__ = "arquivos_importados"

    id = db.Column(db.Integer, primary_key=True)
    # empresa_id vem do BaseMixin
    
    # FK para usuário (sem relationship bidirecional para evitar conflito)
    usuario_id = db.Column(
        db.Integer,
        db.ForeignKey("usuarios.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    
    nome_arquivo = db.Column(db.String(255), nullable=False)
    tipo = db.Column(db.String(20), nullable=False)  # "venda" ou "recebimento"
    hash_arquivo = db.Column(db.String(64), nullable=False, unique=True, index=True)
    total_registros = db.Column(db.Integer, default=0)
    total_valor = db.Column(db.Numeric(15, 2), default=Decimal("0"))
    
    # Conteúdo (pode ser criptografado depois)
    _conteudo_json_encrypted = db.Column("conteudo_json", db.Text, nullable=True)
    
    status_processamento = db.Column(db.String(20), default="processado", index=True)
    erro_processamento = db.Column(db.String(255), nullable=True)

    # ✅ APENAS relacionamento com Empresa (sem back_populates conflitante)
    # Removemos usuario relationship para evitar conflito com Usuario.arquivos_importados
    # Se precisar acessar usuário, use query direta: Usuario.query.get(arquivo.usuario_id)

    __table_args__ = (
        db.Index('idx_arquivo_empresa_data', 'empresa_id', 'criado_em'),
        db.Index('idx_arquivo_hash', 'hash_arquivo', unique=True),
    )

    def __repr__(self):
        return f"<ArquivoImportado {self.nome_arquivo}>"
