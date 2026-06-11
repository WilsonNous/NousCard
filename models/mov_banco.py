# ============================================================
#  MODELS • MovBanco (Recebimentos Bancários)
#  Compatível com SQLAlchemy 1.4.x + Flask-SQLAlchemy 3.0.x
# ============================================================

from .base import db, BaseMixin
from datetime import datetime, timezone
from decimal import Decimal

class MovBanco(db.Model, BaseMixin):
    """
    Representa um recebimento/lançamento bancário (extrato).
    
    Fluxo típico:
    1. Importado de CSV/OFX do banco
    2. Categorizado automaticamente (tipo_pagamento, categoria)
    3. Conciliado com MovAdquirente (vendas)
    """
    __tablename__ = "mov_banco"

    id = db.Column(db.Integer, primary_key=True)
    # ✅ empresa_id vem do BaseMixin (MultiTenantMixin) - NÃO redeclarar!
    
    # ============================================================
    # CHAVES ESTRANGEIRAS
    # ============================================================
    
    conta_bancaria_id = db.Column(
        db.Integer,
        db.ForeignKey("contas_bancarias.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    
    # ============================================================
    # DADOS DO MOVIMENTO BANCÁRIO
    # ============================================================
    
    data_movimento = db.Column(db.Date, nullable=False, index=True)
    banco = db.Column(db.String(50), nullable=True)
    historico = db.Column(db.String(255), nullable=True, index=True)
    documento = db.Column(db.String(100), nullable=True)
    origem = db.Column(db.String(50), nullable=True, index=True)
    
    # Valores (Numeric para precisão monetária)
    valor = db.Column(db.Numeric(15, 2), nullable=False)
    
    # Conciliação
    valor_conciliado = db.Column(db.Numeric(15, 2), default=Decimal("0"))
    conciliado = db.Column(db.Boolean, default=False, index=True)
    
    # ✅ NOVOS CAMPOS: Inteligência Financeira Automática
    tipo_pagamento = db.Column(db.String(50), nullable=True, default='outros', index=True)
    categoria = db.Column(db.String(100), nullable=True, default='outros', index=True)
    
    # Metadados
    arquivo_origem = db.Column(db.String(255), nullable=True)
    observacoes = db.Column(db.Text, nullable=True)

    # ============================================================
    # RELACIONAMENTOS
    # ============================================================
    
    empresa = db.relationship(
        "Empresa",
        back_populates="movimentos_banco",
        lazy=True
    )
    
    conta_bancaria = db.relationship(
        "ContaBancaria",
        back_populates="movimentos",
        lazy=True
    )
    
    conciliacoes = db.relationship(
        "Conciliacao",
        back_populates="mov_banco",
        lazy=True,
        cascade="all, delete-orphan"
    )

    # ============================================================
    # ÍNDICES PARA PERFORMANCE
    # ============================================================
    
    __table_args__ = (
        db.Index('idx_mov_banco_empresa_data', 'empresa_id', 'data_movimento'),
        db.Index('idx_mov_banco_conciliado', 'conciliado'),
        db.Index('idx_mov_banco_conta', 'conta_bancaria_id'),
        db.Index('idx_mov_banco_origem', 'origem'),
        db.Index('idx_mov_banco_tipo', 'tipo_pagamento'),       # ✅ Novo índice
        db.Index('idx_mov_banco_categoria', 'categoria'),       # ✅ Novo índice
    )

    # ============================================================
    # MÉTODOS ÚTEIS
    # ============================================================
    
    @property
    def valor_pendente(self) -> Decimal:
        """Calcula valor ainda não conciliado"""
        return max(Decimal("0"), abs(self.valor) - abs(self.valor_conciliado))
    
    @property
    def esta_conciliado(self) -> bool:
        """Verifica se recebimento está 100% conciliado"""
        return self.conciliado
    
    def atualizar_status_conciliacao(self):
        """Atualiza flag conciliado baseado em valor_conciliado"""
        self.conciliado = abs(self.valor_conciliado) >= abs(self.valor)
    
    def matches_adquirente(self, nome_adquirente: str) -> bool:
        """Verifica se este movimento pode ser de uma adquirente específica."""
        if not nome_adquirente or not self.historico:
            return False
        
        texto = f"{self.historico or ''} {self.origem or ''}".upper()
        return nome_adquirente.upper() in texto

    # ============================================================
    # REPRESENTAÇÃO
    # ============================================================
    
    def __repr__(self):
        return f"<MovBanco id={self.id} Valor={self.valor} Categoria={self.categoria}>"
    
    def to_dict(self):
        """Serializa para dict (útil para APIs e Dashboards)"""
        return {
            "id": self.id,
            "empresa_id": self.empresa_id,
            "conta_bancaria_id": self.conta_bancaria_id,
            "conta_nome": self.conta_bancaria.nome if self.conta_bancaria else None,
            "data_movimento": self.data_movimento.isoformat() if self.data_movimento else None,
            "banco": self.banco,
            "historico": self.historico,
            "documento": self.documento,
            "origem": self.origem,
            "valor": str(self.valor),
            "valor_conciliado": str(self.valor_conciliado),
            "valor_pendente": str(self.valor_pendente),
            "conciliado": self.conciliado,
            "tipo_pagamento": self.tipo_pagamento,      # ✅ Novo
            "categoria": self.categoria,                # ✅ Novo
            "arquivo_origem": self.arquivo_origem,
            "criado_em": self.criado_em.isoformat() if self.criado_em else None
        }
