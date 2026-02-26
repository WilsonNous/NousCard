# models/arquivo_importado.py
from models.base import db, BaseMixin
from decimal import Decimal

class ArquivoImportado(db.Model, BaseMixin):
    """
    Representa um arquivo importado pelo usuário.
    
    Nota: Não usa db.relationship() para evitar circular imports.
    Para acessar usuario/empresa, use query direta:
    - Usuario.query.get(arquivo.usuario_id)
    - Empresa.query.get(arquivo.empresa_id)
    """
    __tablename__ = "arquivos_importados"

    id = db.Column(db.Integer, primary_key=True)
    
    # ============================================================
    # FOREIGN KEYS (apenas referência, sem relationships)
    # ============================================================
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=False, index=True)
    empresa_id = db.Column(db.Integer, db.ForeignKey("empresas.id"), nullable=False, index=True)
    
    # ============================================================
    # DADOS DO ARQUIVO
    # ============================================================
    nome_arquivo = db.Column(db.String(255), nullable=False)
    caminho_arquivo = db.Column(db.String(500), nullable=True)  # ← Pode ser NULL se não salvar local
    tipo_arquivo = db.Column(db.String(50), nullable=False)  # ← 'venda', 'recebimento', 'desconhecido'
    
    # ============================================================
    # IDENTIFICAÇÃO ÚNICA (para deduplicação)
    # ============================================================
    hash_arquivo = db.Column(db.String(64), nullable=False, index=True)  # ← SHA-256, CRÍTICO!
    
    # ============================================================
    # STATUS E PROCESSAMENTO
    # ============================================================
    status = db.Column(db.String(30), default="pendente", index=True)  # ← pendente, processado, erro
    mensagem_erro = db.Column(db.Text, nullable=True)  # ← Detalhe do erro se status='erro'
    
    # ============================================================
    # MÉTRICAS E TOTAIS
    # ============================================================
    total_registros = db.Column(db.Integer, default=0)  # ← Quantidade de linhas processadas
    total_valor = db.Column(db.Numeric(15, 2), default=0)  # ← Soma dos valores (Decimal)
    
    # ============================================================
    # CONTEÚDO CRIPTOGRAFADO
    # ============================================================
    conteudo_json = db.Column(db.Text, nullable=True)  # ← Dados JSON criptografados
    
    # ============================================================
    # ÍNDICES PARA PERFORMANCE
    # ============================================================
    __table_args__ = (
        db.Index('idx_arquivo_hash_empresa', 'hash_arquivo', 'empresa_id', unique=True),
        db.Index('idx_arquivo_empresa_status', 'empresa_id', 'status', 'criado_em'),
        db.Index('idx_arquivo_usuario', 'usuario_id', 'criado_em'),
    )
    
    # ============================================================
    # REPRESENTAÇÃO
    # ============================================================
    def __repr__(self):
        return f"<ArquivoImportado id={self.id} nome={self.nome_arquivo} tipo={self.tipo_arquivo} status={self.status}>"
    
    # ============================================================
    # MÉTODOS UTILITÁRIOS
    # ============================================================
    @property
    def is_processado(self):
        """Verifica se o arquivo foi processado com sucesso"""
        return self.status == "processado"
    
    @property
    def has_error(self):
        """Verifica se houve erro no processamento"""
        return self.status == "erro" and bool(self.mensagem_erro)
    
    def to_dict(self):
        """Serializa para dict (útil para APIs)"""
        return {
            "id": self.id,
            "nome_arquivo": self.nome_arquivo,
            "tipo_arquivo": self.tipo_arquivo,
            "status": self.status,
            "total_registros": self.total_registros,
            "total_valor": str(self.total_valor) if self.total_valor else "0",
            "hash_arquivo": self.hash_arquivo[:16] + "..." if self.hash_arquivo else None,  # Truncar para segurança
            "created_at": self.criado_em.isoformat() if hasattr(self, 'criado_em') and self.criado_em else None,
        }
