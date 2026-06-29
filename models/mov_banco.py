# ============================================================
#  MODELS • MovBanco (Recebimentos Bancários)
#  Compatível com SQLAlchemy 1.4.x + Flask-SQLAlchemy 3.0.x
#  ✅ Atualizado com campos de inteligência financeira
# ============================================================

from .base import db, BaseMixin
from datetime import datetime, timezone
from decimal import Decimal

class MovBanco(db.Model, BaseMixin):
    """
    Representa um recebimento/lançamento bancário (extrato).
    
    Fluxo típico:
    1. Importado de CSV/OFX do banco
    2. Categorizado automaticamente (Classificador Financeiro)
    3. Conciliado com MovAdquirente (vendas)
    """
    __tablename__ = "mov_banco"

    id = db.Column(db.Integer, primary_key=True)
    
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
    
    # ============================================================
    # ✅ INTELIGÊNCIA FINANCEIRA (CLASSIFICAÇÃO AUTOMÁTICA)
    # ============================================================
    
    # Tipo de pagamento (pix, debito, credito, boleto, ted, etc.)
    tipo_pagamento = db.Column(db.String(50), nullable=True, default='outros', index=True)
    
    # Categoria principal (transporte_combustivel, alimentacao_restaurante, etc.)
    categoria = db.Column(db.String(100), nullable=True, default='outros', index=True)
    
    # Categoria principal (grupo macro: Transporte, Alimentação, Tributos, etc.)
    categoria_principal = db.Column(db.String(100), nullable=True, index=True,
        comment="Grupo macro da classificação: Transporte, Alimentação, Tributos, etc.")
    
    # Subcategoria (detalhamento: Combustível, Restaurante, Federais, etc.)
    subcategoria = db.Column(db.String(100), nullable=True,
        comment="Subcategoria detalhada: Combustível, Restaurante, Federais, etc.")
    
    # Score de confiança da classificação automática (0-100)
    score_classificacao = db.Column(db.Integer, default=0,
        comment="Score de confiança da classificação automática (0-100)")
    
    # Flag: classificação foi automática?
    classificacao_automatica = db.Column(db.Boolean, default=True,
        comment="True se a classificação foi feita automaticamente")
    
    # Flag: classificação foi revisada manualmente?
    classificacao_manual = db.Column(db.Boolean, default=False,
        comment="True se um usuário revisou/alterou a classificação")
    
    # Palavra-chave que acionou a classificação
    palavra_chave = db.Column(db.String(100), nullable=True,
        comment="Palavra-chave que acionou a classificação (ex: POSTO, NETFLIX)")
    
    # Origem da classificação (classificador_financeiro_v2, manual, etc.)
    origem_classificacao = db.Column(db.String(100), nullable=True,
        comment="Origem da classificação: classificador_financeiro_v2, manual, etc.")
    
    # Regra utilizada na classificação
    regra_utilizada = db.Column(db.String(100), nullable=True,
        comment="Nome da regra que classificou esta transação")
    
    # ============================================================
    # METADADOS
    # ============================================================
    
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
        db.Index('idx_mov_banco_tipo', 'tipo_pagamento'),
        db.Index('idx_mov_banco_categoria', 'categoria'),
        db.Index('idx_mov_banco_categoria_principal', 'categoria_principal'),  # ✅ Novo
        db.Index('idx_mov_banco_score', 'score_classificacao'),                # ✅ Novo
        db.Index('idx_mov_banco_auto', 'classificacao_automatica'),            # ✅ Novo
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
    
    @property
    def classificacao_confiavel(self) -> bool:
        """Verifica se a classificação tem score alto"""
        return self.score_classificacao >= 70
    
    @property
    def precisa_revisao(self) -> bool:
        """Verifica se a classificação precisa de revisão manual"""
        return self.classificacao_automatica and self.score_classificacao < 50
    
    def atualizar_status_conciliacao(self):
        """Atualiza flag conciliado baseado em valor_conciliado"""
        self.conciliado = abs(self.valor_conciliado) >= abs(self.valor)
    
    def aplicar_classificacao(self, resultado: dict):
        """
        Aplica resultado do Classificador Financeiro ao registro.
        
        Args:
            resultado: dict com categoria, tipo_pagamento, score, etc.
        """
        self.categoria = resultado.get("categoria", "outros")
        self.tipo_pagamento = resultado.get("tipo_pagamento", "outros")
        self.categoria_principal = resultado.get("grupo", "Outros")
        self.subcategoria = resultado.get("subgrupo", "Não Classificado")
        self.score_classificacao = resultado.get("score", 0)
        self.classificacao_automatica = True
        self.palavra_chave = resultado.get("regra_utilizada", "")
        self.origem_classificacao = resultado.get("origem_classificacao", "classificador_financeiro_v2")
        self.regra_utilizada = resultado.get("categoria", "")
    
    def marcar_revisao_manual(self, nova_categoria: str = None):
        """
        Marca que a classificação foi revisada manualmente.
        """
        self.classificacao_manual = True
        self.classificacao_automatica = False
        if nova_categoria:
            self.categoria = nova_categoria
            self.origem_classificacao = "manual"
    
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
        return (
            f"<MovBanco id={self.id} "
            f"Valor={self.valor} "
            f"Categoria={self.categoria} "
            f"Score={self.score_classificacao}>"
        )
    
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
            
            # ✅ Campos de inteligência financeira
            "tipo_pagamento": self.tipo_pagamento,
            "categoria": self.categoria,
            "categoria_principal": self.categoria_principal,
            "subcategoria": self.subcategoria,
            "score_classificacao": self.score_classificacao,
            "classificacao_automatica": self.classificacao_automatica,
            "classificacao_manual": self.classificacao_manual,
            "palavra_chave": self.palavra_chave,
            "origem_classificacao": self.origem_classificacao,
            "regra_utilizada": self.regra_utilizada,
            "classificacao_confiavel": self.classificacao_confiavel,
            "precisa_revisao": self.precisa_revisao,
            
            # Metadados
            "arquivo_origem": self.arquivo_origem,
            "criado_em": self.criado_em.isoformat() if self.criado_em else None
        }