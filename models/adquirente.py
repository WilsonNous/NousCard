# ============================================================
#  MODELS • Adquirente
#  Compatível com SQLAlchemy 1.4.x + Flask-SQLAlchemy 3.0.x
# ============================================================

from .base import db, BaseMixin
from datetime import datetime, timezone

class Adquirente(db.Model, BaseMixin):
    """
    Representa uma adquirente de pagamentos (Cielo, Rede, Getnet, etc.).
    
    Pode ser:
    - Global: disponível para todas as empresas (empresa_id = None)
    - Específica: vinculada a uma empresa (empresa_id = X)
    """
    __tablename__ = "adquirentes"

    id = db.Column(db.Integer, primary_key=True)
    # empresa_id vem do BaseMixin (MultiTenantMixin) - nullable para adquirentes globais
    
    nome = db.Column(db.String(100), nullable=False)
    codigo = db.Column(db.String(30), nullable=True)  # Código interno/API

    # ============================================================
    # CONFIGURAÇÕES DE CONCILIAÇÃO
    # ============================================================
    
    # Prazo de liquidação padrão (D+0, D+1, D+2, etc.)
    prazo_dias = db.Column(db.Integer, default=2)
    
    # Se a adquirente consolida vendas por dia (útil para matching)
    consolida_por_dia = db.Column(db.Boolean, default=False)
    
    # Palavras-chave para identificar esta adquirente em extratos bancários
    # Ex: "CIELO, CIE, VENDAS CIELO" → usado no parser de OFX/CSV
    palavras_chave_extrato = db.Column(db.String(255), nullable=True)
    
    # Banco preferencial para recebimentos desta adquirente
    banco_preferencial = db.Column(db.String(50), nullable=True)

    # ============================================================
    # RELACIONAMENTOS (com back_populates CONSISTENTE)
    # ============================================================
    
    # Contratos de taxas desta adquirente
    # ✅ back_populates="adquirente" deve bater com ContratoTaxa.adquirente
    contratos = db.relationship(
        "ContratoTaxa",
        back_populates="adquirente",  # ✅ Nome deve existir em ContratoTaxa
        lazy=True,
        cascade="all, delete-orphan"
    )
    
    # Movimentos de vendas desta adquirente
    # ✅ back_populates="adquirente" deve bater com MovAdquirente.adquirente
    movimentos = db.relationship(
        "MovAdquirente",
        back_populates="adquirente",  # ✅ Nome deve existir em MovAdquirente
        lazy=True,
        cascade="all, delete-orphan"
    )
    
    # Se Adquirente for vinculado a Empresa (opcional)
    # empresa = db.relationship(
    #     "Empresa",
    #     back_populates="adquirentes",  # Se Empresa tiver esta lista
    #     lazy=True
    # )

    # ============================================================
    # ÍNDICES PARA PERFORMANCE
    # ============================================================
    
    __table_args__ = (
        db.Index('idx_adquirente_nome', 'nome'),
        db.Index('idx_adquirente_codigo', 'codigo'),
        db.Index('idx_adquirente_empresa', 'empresa_id', 'ativo'),
    )

    # ============================================================
    # MÉTODOS ÚTEIS
    # ============================================================
    
    def matches_extrato(self, descricao: str) -> bool:
        """
        Verifica se uma descrição de extrato corresponde a esta adquirente.
        Útil para parsing automático de OFX/CSV.
        
        Args:
            descricao: Texto da descrição do extrato
            
        Returns:
            bool: True se houver match com palavras_chave_extrato
        """
        if not self.palavras_chave_extrato or not descricao:
            return False
        
        palavras = [p.strip().upper() for p in self.palavras_chave_extrato.split(',') if p.strip()]
        descricao_upper = descricao.upper()
        
        return any(palavra in descricao_upper for palavra in palavras)
    
    def get_prazo_liquidação(self) -> int:
        """Retorna o prazo de liquidação em dias (D+X)"""
        return self.prazo_dias or 2

    # ============================================================
    # REPRESENTAÇÃO
    # ============================================================
    
    def __repr__(self):
        return f"<Adquirente {self.nome} (id={self.id})>"
    
    def to_dict(self):
        """Serializa para dict (útil para APIs)"""
        return {
            "id": self.id,
            "nome": self.nome,
            "codigo": self.codigo,
            "prazo_dias": self.prazo_dias,
            "consolida_por_dia": self.consolida_por_dia,
            "palavras_chave_extrato": self.palavras_chave_extrato,
            "banco_preferencial": self.banco_preferencial,
            "ativo": self.ativo,
            "criado_em": self.criado_em.isoformat() if self.criado_em else None
        }
