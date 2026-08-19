# models/lead.py
# Modelo comercial de leads do NousCard / Nous Tecnologia

from .base import db, TimestampMixin, SoftDeleteMixin


class Lead(db.Model, TimestampMixin, SoftDeleteMixin):
    """
    Lead comercial capturado pela landing pública do NousCard.

    IMPORTANTE:
    - Lead NÃO é o mesmo que Cliente.
    - Cliente pertence a uma empresa usuária do NousCard.
    - Lead representa uma oportunidade comercial da Nous Tecnologia.
    - empresa_id só é preenchido quando houver vínculo com uma Empresa criada.
    """
    __tablename__ = "leads"

    id = db.Column(db.Integer, primary_key=True)

    # ============================================================
    # DADOS PRINCIPAIS
    # ============================================================
    nome = db.Column(db.String(200), nullable=False)
    empresa = db.Column(db.String(200), nullable=False)
    cnpj = db.Column(db.String(20), nullable=True)
    email = db.Column(db.String(200), nullable=True, index=True)
    telefone = db.Column(db.String(30), nullable=False, index=True)

    # ============================================================
    # DESCOBERTA COMERCIAL
    # ============================================================
    controle_atual = db.Column(
        db.String(30),
        nullable=True,
        index=True,
        comment="caderno, planilha, sistema, misto, outro",
    )

    # Armazenado como CSV simples para manter o MVP leve:
    # clientes,orcamentos,os,financeiro
    interesses = db.Column(db.String(255), nullable=True)

    mensagem = db.Column(db.Text, nullable=True)

    # ============================================================
    # FUNIL COMERCIAL
    # ============================================================
    status = db.Column(
        db.String(50),
        nullable=False,
        default="novo",
        index=True,
    )

    origem = db.Column(
        db.String(100),
        nullable=False,
        default="landing_nouscard",
        index=True,
    )

    # ============================================================
    # METADADOS / AUDITORIA
    # ============================================================
    ip_address = db.Column(db.String(50), nullable=True)
    user_agent = db.Column(db.String(500), nullable=True)

    # Quando o lead virar empresa dentro do NousCard, pode ser vinculado aqui.
    empresa_id = db.Column(
        db.Integer,
        db.ForeignKey("empresas.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    contacted_at = db.Column(db.DateTime(timezone=True), nullable=True)
    converted_at = db.Column(db.DateTime(timezone=True), nullable=True)

    empresa_convertida = db.relationship(
        "Empresa",
        foreign_keys=[empresa_id],
        lazy="select",
    )

    STATUS_VALIDOS = (
        "novo",
        "contato",
        "qualificado",
        "cliente",
        "perdido",
    )

    CONTROLES_VALIDOS = (
        "caderno",
        "planilha",
        "sistema",
        "misto",
        "outro",
    )

    INTERESSES_VALIDOS = (
        "clientes",
        "orcamentos",
        "os",
        "financeiro",
    )

    __table_args__ = (
        db.Index("idx_lead_status_data", "status", "criado_em"),
        db.Index("idx_lead_origem_data", "origem", "criado_em"),
    )

    @property
    def interesses_lista(self):
        if not self.interesses:
            return []

        return [
            item.strip()
            for item in self.interesses.split(",")
            if item.strip()
        ]

    @property
    def interesses_labels(self):
        labels = {
            "clientes": "Clientes",
            "orcamentos": "Orçamentos",
            "os": "Ordens de Serviço",
            "financeiro": "Financeiro",
        }
        return [labels.get(item, item) for item in self.interesses_lista]

    @property
    def controle_atual_label(self):
        labels = {
            "caderno": "Caderno / papel",
            "planilha": "Planilhas",
            "sistema": "Outro sistema",
            "misto": "Um pouco de cada",
            "outro": "Outro",
        }
        return labels.get(self.controle_atual, "Não informado")

    @property
    def whatsapp_url(self):
        numero = "".join(
            ch for ch in (self.telefone or "")
            if ch.isdigit()
        )

        if not numero:
            return None

        # Telefone brasileiro sem DDI
        if len(numero) in (10, 11):
            numero = "55" + numero

        return f"https://wa.me/{numero}"

    def __repr__(self):
        return (
            f"<Lead id={self.id} empresa={self.empresa!r} "
            f"status={self.status!r}>"
        )

    def to_dict(self):
        return {
            "id": self.id,
            "nome": self.nome,
            "empresa": self.empresa,
            "cnpj": self.cnpj,
            "email": self.email,
            "telefone": self.telefone,
            "controle_atual": self.controle_atual,
            "controle_atual_label": self.controle_atual_label,
            "interesses": self.interesses_lista,
            "interesses_labels": self.interesses_labels,
            "mensagem": self.mensagem,
            "status": self.status,
            "origem": self.origem,
            "empresa_id": self.empresa_id,
            "created_at": (
                self.criado_em.isoformat()
                if self.criado_em else None
            ),
            "updated_at": (
                self.atualizado_em.isoformat()
                if self.atualizado_em else None
            ),
            "contacted_at": (
                self.contacted_at.isoformat()
                if self.contacted_at else None
            ),
            "converted_at": (
                self.converted_at.isoformat()
                if self.converted_at else None
            ),
        }
