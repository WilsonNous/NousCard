# models/lead.py
# Lead comercial capturado pela landing do NousCard

from .base import db, TimestampMixin, SoftDeleteMixin


class Lead(db.Model, TimestampMixin, SoftDeleteMixin):
    """
    Lead comercial da Nous Tecnologia.

    Importante:
    - NÃO é um Cliente de uma empresa usuária do NousCard.
    - Pode posteriormente ser convertido em Empresa.
    """
    __tablename__ = "leads"

    id = db.Column(db.Integer, primary_key=True)

    # Dados principais
    nome = db.Column(db.String(200), nullable=False)
    empresa = db.Column(db.String(200), nullable=False)
    cnpj = db.Column(db.String(20), nullable=True)
    email = db.Column(db.String(200), nullable=True, index=True)
    telefone = db.Column(db.String(30), nullable=False, index=True)

    # Descoberta comercial
    controle_atual = db.Column(
        db.String(30),
        nullable=True,
        index=True,
        comment="caderno, planilha, sistema, misto, outro"
    )
    interesses = db.Column(
        db.String(255),
        nullable=True,
        comment="Lista CSV: clientes,orcamentos,os,financeiro"
    )
    mensagem = db.Column(db.Text, nullable=True)

    # Funil comercial
    status = db.Column(db.String(50), default='novo', nullable=False, index=True)
    origem = db.Column(db.String(100), default='landing_nouscard', nullable=False)

    # Metadados
    ip_address = db.Column(db.String(50), nullable=True)
    user_agent = db.Column(db.String(500), nullable=True)

    # Empresa criada após conversão
    empresa_id = db.Column(
        db.Integer,
        db.ForeignKey('empresas.id', ondelete='SET NULL'),
        nullable=True,
        index=True
    )

    contacted_at = db.Column(db.DateTime(timezone=True), nullable=True)
    converted_at = db.Column(db.DateTime(timezone=True), nullable=True)

    empresa_convertida = db.relationship(
        "Empresa",
        foreign_keys=[empresa_id],
        lazy="select"
    )

    __table_args__ = (
        db.Index("idx_lead_status_data", "status", "criado_em"),
        db.Index("idx_lead_origem_data", "origem", "criado_em"),
    )

    STATUS_VALIDOS = ("novo", "contato", "qualificado", "cliente", "perdido")

    @property
    def interesses_lista(self):
        if not self.interesses:
            return []
        return [item.strip() for item in self.interesses.split(",") if item.strip()]

    @property
    def whatsapp_url(self):
        numero = "".join(ch for ch in (self.telefone or "") if ch.isdigit())
        if not numero:
            return None
        if len(numero) in (10, 11):
            numero = "55" + numero
        return f"https://wa.me/{numero}"

    def __repr__(self):
        return f"<Lead {self.id} {self.empresa} - {self.status}>"

    def to_dict(self):
        return {
            "id": self.id,
            "nome": self.nome,
            "empresa": self.empresa,
            "cnpj": self.cnpj,
            "email": self.email,
            "telefone": self.telefone,
            "controle_atual": self.controle_atual,
            "interesses": self.interesses_lista,
            "mensagem": self.mensagem,
            "status": self.status,
            "origem": self.origem,
            "empresa_id": self.empresa_id,
            "created_at": self.criado_em.isoformat() if self.criado_em else None,
            "updated_at": self.atualizado_em.isoformat() if self.atualizado_em else None,
            "contacted_at": self.contacted_at.isoformat() if self.contacted_at else None,
            "converted_at": self.converted_at.isoformat() if self.converted_at else None
        }
