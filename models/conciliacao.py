# ============================================================
#  MODELS • Conciliacao (Matching Venda × Recebimento)
#  Compatível com SQLAlchemy 1.4.x + Flask-SQLAlchemy 3.0.x
# ============================================================

from .base import db, BaseMixin
from datetime import datetime, timezone
from decimal import Decimal

class Conciliacao(db.Model, BaseMixin):
    """
    Representa o matching entre uma venda (MovAdquirente) e um recebimento (MovBanco).
    
    Tipos de conciliação:
    - automatico: Match feito pelo algoritmo (data + valor)
    - manual: Match feito pelo usuário
    - parcial: Múltiplas vendas × um recebimento (ou vice-versa)
    
    Nota: empresa_id vem do BaseMixin (MultiTenantMixin).
    """
    __tablename__ = "conciliacoes"

    id = db.Column(db.Integer, primary_key=True)
    # ✅ empresa_id vem do BaseMixin - NÃO redeclarar!
    
    # ============================================================
    # CHAVES ESTRANGEIRAS
    # ============================================================
    
    mov_adquirente_id = db.Column(
        db.Integer,
        db.ForeignKey("mov_adquirente.id", ondelete="CASCADE"),
        nullable=True,  # Pode ser null em conciliações manuais
        index=True
    )
    
    mov_banco_id = db.Column(
        db.Integer,
        db.ForeignKey("mov_banco.id", ondelete="CASCADE"),
        nullable=True,  # Pode ser null em conciliações manuais
        index=True
    )
    
    # ============================================================
    # DADOS DA CONCILIAÇÃO
    # ============================================================
    
    # Valores (Numeric para precisão monetária)
    valor_previsto = db.Column(db.Numeric(15, 2), nullable=True)
    valor_conciliado = db.Column(db.Numeric(15, 2), nullable=True)
    
    # Tipo de matching
    tipo = db.Column(
        db.String(20),
        default="automatico",  # automatico, manual, parcial
        index=True
    )
    
    # Status da conciliação
    status = db.Column(
        db.String(30),
        default="conciliado",  # conciliado, pendente, divergente
        index=True
    )
    
    # Motivo/observação (ex: "Match por NSU", "Match por data+valor")
    motivo = db.Column(db.String(255), nullable=True)
    
    # Usuário que realizou (se manual)
    usuario_id = db.Column(
        db.Integer,
        db.ForeignKey("usuarios.id", ondelete="SET NULL"),
        nullable=True
    )
    
    # Metadados
    observacoes = db.Column(db.Text, nullable=True)

    # ============================================================
    # RELACIONAMENTOS (com back_populates CONSISTENTE)
    # ============================================================
    
    # ✅ Empresa: back_populates deve bater com Empresa.conciliacoes
    empresa = db.relationship(
        "Empresa",
        back_populates="conciliacoes",  # ✅ Deve existir em Empresa
        lazy=True
    )
    
    # ✅ MovAdquirente: back_populates deve bater com MovAdquirente.conciliacoes
    mov_adquirente = db.relationship(
        "MovAdquirente",
        back_populates="conciliacoes",  # ✅ Deve existir em MovAdquirente
        lazy=True
    )
    
    # ✅ MovBanco: back_populates deve bater com MovBanco.conciliacoes
    mov_banco = db.relationship(
        "MovBanco",
        back_populates="conciliacoes",  # ✅ Deve existir em MovBanco
        lazy=True
    )
    
    # ✅ Usuário (quem realizou a conciliação manual)
    usuario = db.relationship(
        "Usuario",
        back_populates="conciliacoes",  # ✅ Deve existir em Usuario (se existir)
        lazy=True
    )

    # ============================================================
    # ÍNDICES PARA PERFORMANCE
    # ============================================================
    
    __table_args__ = (
        db.Index('idx_conciliacao_empresa', 'empresa_id', 'criado_em'),
        db.Index('idx_conciliacao_mov_adq', 'mov_adquirente_id'),
        db.Index('idx_conciliacao_mov_banco', 'mov_banco_id'),
        db.Index('idx_conciliacao_status', 'status'),
        db.Index('idx_conciliacao_tipo', 'tipo'),
    )

    # ============================================================
    # MÉTODOS ÚTEIS
    # ============================================================
    
    @property
    def diferenca(self) -> Decimal:
        """Calcula diferença entre previsto e conciliado"""
        if self.valor_previsto is None or self.valor_conciliado is None:
            return Decimal("0")
        return self.valor_previsto - self.valor_conciliado
    
    @property
    def esta_conciliado(self) -> bool:
        """Verifica se conciliação está completa"""
        return self.status == "conciliado"
    
    @property
    def esta_divergente(self) -> bool:
        """Verifica se há divergência de valores"""
        return self.status == "divergente" or abs(self.diferenca) > Decimal("0.02")
    
    def validar_match(self) -> bool:
        """
        Valida se os dados da conciliação são consistentes.
        
        Returns:
            bool: True se conciliação é válida
        """
        # Precisa ter pelo menos um lado do match
        if not self.mov_adquirente_id and not self.mov_banco_id:
            return False
        
        # Valores devem ser positivos
        if self.valor_previsto and self.valor_previsto < 0:
            return False
        if self.valor_conciliado and self.valor_conciliado < 0:
            return False
        
        return True
    
    def atualizar_status(self):
        """Atualiza status baseado na diferença de valores"""
        diff = abs(self.diferenca)
        
        if diff <= Decimal("0.02"):  # Tolerância de 2 centavos
            self.status = "conciliado"
        elif diff > Decimal("0.02"):
            self.status = "divergente"
            self.motivo = f"Diferença de R$ {diff:.2f}"
        else:
            self.status = "pendente"

    # ============================================================
    # REPRESENTAÇÃO
    # ============================================================
    
    def __repr__(self):
        return f"<Conciliacao id={self.id} mov_adq={self.mov_adquirente_id} mov_banco={self.mov_banco_id} status={self.status}>"
    
    def to_dict(self) -> dict:
        """Serializa para dict (útil para APIs)"""
        return {
            "id": self.id,
            "empresa_id": self.empresa_id,
            "mov_adquirente_id": self.mov_adquirente_id,
            "mov_banco_id": self.mov_banco_id,
            "valor_previsto": str(self.valor_previsto) if self.valor_previsto else None,
            "valor_conciliado": str(self.valor_conciliado) if self.valor_conciliado else None,
            "diferenca": str(self.diferenca),
            "tipo": self.tipo,
            "status": self.status,
            "motivo": self.motivo,
            "usuario_id": self.usuario_id,
            "criado_em": self.criado_em.isoformat() if self.criado_em else None,
            "mov_adquirente": self.mov_adquirente.to_dict() if self.mov_adquirente else None,
            "mov_banco": self.mov_banco.to_dict() if self.mov_banco else None,
        }
