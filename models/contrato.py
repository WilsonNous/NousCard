# models/contrato.py - Contrato COMERCIAL do NousCard (diferente de ContratoTaxa)

from .base import db, BaseMixin
from datetime import datetime, timezone, date
from decimal import Decimal


class Contrato(db.Model, BaseMixin):
    """
    Contrato COMERCIAL de prestação de serviço NousCard.
    Diferente de ContratoTaxa (que é contrato de taxas da maquininha).
    """
    __tablename__ = "contratos_comerciais"  # ✅ Nome diferente da tabela
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Relacionamento com empresa
    empresa_id = db.Column(db.Integer, db.ForeignKey('empresas.id'), nullable=False, index=True)
    
    # Dados do contrato
    numero = db.Column(db.String(20), unique=True, nullable=False, index=True)
    data_emissao = db.Column(db.Date, default=lambda: date.today())
    data_inicio_vigencia = db.Column(db.Date, nullable=False)
    data_fim_vigencia = db.Column(db.Date, nullable=True)
    
    # Valores
    valor_setup = db.Column(db.Numeric(10, 2), default=Decimal('297.00'))
    valor_mensal = db.Column(db.Numeric(10, 2), default=Decimal('97.00'))
    plano = db.Column(db.String(50), default='inicial')
    
    # Status
    status = db.Column(db.String(30), default='gerado', index=True)
    
    # Pagamento setup
    setup_pago = db.Column(db.Boolean, default=False)
    data_pagamento_setup = db.Column(db.DateTime, nullable=True)
    
    # Assinatura
    assinado_digitalmente = db.Column(db.Boolean, default=False)
    data_assinatura = db.Column(db.DateTime, nullable=True)
    ip_assinatura = db.Column(db.String(50), nullable=True)
    
    # PDF do contrato
    pdf_base64 = db.Column(db.Text, nullable=True)
    pdf_url = db.Column(db.String(500), nullable=True)
    
    # Observações
    observacoes = db.Column(db.Text, nullable=True)
    
    # ✅ Relacionamento com Empresa (usa contratos_comerciais)
    empresa = db.relationship('Empresa', back_populates='contratos_comerciais')
    
    def __repr__(self):
        return f"<ContratoComercial {self.numero} - Empresa {self.empresa_id}>"
    
    def to_dict(self):
        return {
            "id": self.id,
            "numero": self.numero,
            "empresa_id": self.empresa_id,
            "empresa_nome": self.empresa.nome if self.empresa else None,
            "data_emissao": self.data_emissao.isoformat() if self.data_emissao else None,
            "data_inicio_vigencia": self.data_inicio_vigencia.isoformat() if self.data_inicio_vigencia else None,
            "valor_setup": float(self.valor_setup or 0),
            "valor_mensal": float(self.valor_mensal or 0),
            "plano": self.plano,
            "status": self.status,
            "setup_pago": self.setup_pago,
            "assinado_digitalmente": self.assinado_digitalmente,
            "criado_em": self.criado_em.isoformat() if self.criado_em else None
        }
    
    @staticmethod
    def gerar_numero_contrato():
        """Gera número sequencial: NC-2026-001, NC-2026-002, etc."""
        ano_atual = date.today().year
        ultimo = Contrato.query.filter(
            Contrato.numero.like(f'NC-{ano_atual}-%')
        ).order_by(Contrato.numero.desc()).first()
        
        if ultimo:
            seq = int(ultimo.numero.split('-')[-1]) + 1
        else:
            seq = 1
        
        return f"NC-{ano_atual}-{seq:03d}"
