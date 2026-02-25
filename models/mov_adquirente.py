# ============================================================
#  MODELS • MovAdquirente (Vendas de Maquininha)
#  Compatível com SQLAlchemy 1.4.x + Flask-SQLAlchemy 3.0.x
# ============================================================

from .base import db, BaseMixin
from datetime import datetime, timezone
from decimal import Decimal

class MovAdquirente(db.Model, BaseMixin):
    """
    Representa uma venda/transação de adquirente (Cielo, Rede, Getnet, etc.).
    
    Fluxo típico:
    1. Importado de CSV/OFX da adquirente
    2. Conciliado com MovBanco (recebimento bancário)
    3. Status: pendente → parcial → conciliado
    """
    __tablename__ = "mov_adquirente"

    id = db.Column(db.Integer, primary_key=True)
    # empresa_id vem do BaseMixin (MultiTenantMixin) ✅
    
    # ============================================================
    # CHAVES ESTRANGEIRAS
    # ============================================================
    
    adquirente_id = db.Column(
        db.Integer,
        db.ForeignKey("adquirentes.id", ondelete="SET NULL"),
        nullable=True,  # Pode ser null se adquirente for deletada
        index=True
    )
    
    # ============================================================
    # DADOS DA VENDA
    # ============================================================
    
    # Datas
    data_venda = db.Column(db.Date, nullable=False, index=True)
    data_prevista_pagamento = db.Column(db.Date, nullable=True, index=True)
    data_primeiro_recebimento = db.Column(db.Date, nullable=True)
    data_ultimo_recebimento = db.Column(db.Date, nullable=True)
    
    # Identificadores
    nsu = db.Column(db.String(50), nullable=True, index=True)  # Número Sequencial Único
    autorizacao = db.Column(db.String(50), nullable=True)
    
    # Produto/Bandeira
    bandeira = db.Column(db.String(50), nullable=True)  # Visa, Mastercard, etc.
    produto = db.Column(db.String(50), nullable=True)   # Débito, Crédito, PIX
    parcela = db.Column(db.Integer, nullable=True)      # 1, 2, 3...
    total_parcelas = db.Column(db.Integer, nullable=True)  # Total de parcelas da venda
    
    # Valores (usar Numeric para precisão monetária)
    valor_bruto = db.Column(db.Numeric(15, 2), nullable=False)
    taxa_cobrada = db.Column(db.Numeric(10, 2), default=Decimal("0"))
    valor_liquido = db.Column(db.Numeric(15, 2), nullable=False)
    
    # Conciliação
    valor_conciliado = db.Column(db.Numeric(15, 2), default=Decimal("0"))
    status_conciliacao = db.Column(
        db.String(20),
        default="pendente",  # pendente, parcial, conciliado, nao_recebido
        index=True
    )
    
    # Metadados
    arquivo_origem = db.Column(db.String(255), nullable=True)  # Hash/nome do arquivo importado
    observacoes = db.Column(db.Text, nullable=True)

    # ============================================================
    # RELACIONAMENTOS (com back_populates CONSISTENTE)
    # ============================================================
    
    # ✅ Empresa: back_populates deve bater com Empresa.movimentos_adquirente
    empresa = db.relationship(
        "Empresa",
        back_populates="movimentos_adquirente",  # ✅ Este nome deve existir em Empresa
        lazy=True
    )
    
    # ✅ Adquirente: back_populates deve bater com Adquirente.movimentos
    adquirente = db.relationship(
        "Adquirente",
        back_populates="movimentos",  # ✅ Este nome deve existir em Adquirente
        lazy=True
    )
    
    # ✅ Conciliações: uma venda pode ter múltiplos recebimentos conciliados
    conciliacoes = db.relationship(
        "Conciliacao",
        back_populates="mov_adquirente",  # ✅ Deve bater com Conciliacao.mov_adquirente
        lazy=True,
        cascade="all, delete-orphan"
    )

    # ============================================================
    # ÍNDICES PARA PERFORMANCE
    # ============================================================
    
    __table_args__ = (
        db.Index('idx_mov_adq_empresa_data', 'empresa_id', 'data_venda'),
        db.Index('idx_mov_adq_nsu', 'nsu'),
        db.Index('idx_mov_adq_status', 'status_conciliacao'),
        db.Index('idx_mov_adq_adquirente', 'adquirente_id'),
    )

    # ============================================================
    # MÉTODOS ÚTEIS
    # ============================================================
    
    @property
    def valor_pendente(self) -> Decimal:
        """Calcula valor ainda não conciliado"""
        return max(Decimal("0"), self.valor_liquido - self.valor_conciliado)
    
    @property
    def esta_conciliado(self) -> bool:
        """Verifica se venda está 100% conciliada"""
        return self.status_conciliacao == "conciliado"
    
    @property
    def esta_parcial(self) -> bool:
        """Verifica se venda está parcialmente conciliada"""
        return self.status_conciliacao == "parcial"
    
    def atualizar_status_conciliacao(self):
        """Atualiza status_conciliacao baseado em valor_conciliado"""
        if self.valor_conciliado >= self.valor_liquido:
            self.status_conciliacao = "conciliado"
        elif self.valor_conciliado > 0:
            self.status_conciliacao = "parcial"
        else:
            self.status_conciliacao = "pendente"

    # ============================================================
    # REPRESENTAÇÃO
    # ============================================================
    
    def __repr__(self):
        return f"<MovAdquirente NSU={self.nsu} Valor={self.valor_liquido} Status={self.status_conciliacao}>"
    
    def to_dict(self):
        """Serializa para dict (útil para APIs)"""
        return {
            "id": self.id,
            "empresa_id": self.empresa_id,
            "adquirente_id": self.adquirente_id,
            "adquirente_nome": self.adquirente.nome if self.adquirente else None,
            "data_venda": self.data_venda.isoformat() if self.data_venda else None,
            "data_prevista": self.data_prevista_pagamento.isoformat() if self.data_prevista_pagamento else None,
            "nsu": self.nsu,
            "bandeira": self.bandeira,
            "produto": self.produto,
            "parcela": self.parcela,
            "total_parcelas": self.total_parcelas,
            "valor_bruto": str(self.valor_bruto),
            "valor_liquido": str(self.valor_liquido),
            "valor_conciliado": str(self.valor_conciliado),
            "valor_pendente": str(self.valor_pendente),
            "status_conciliacao": self.status_conciliacao,
            "criado_em": self.criado_em.isoformat() if self.criado_em else None
        }
