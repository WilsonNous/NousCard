# models/lead.py
# Modelo para captura de leads e futuros clientes

from .base import db, BaseMixin
from datetime import datetime, timezone


class Lead(db.Model, BaseMixin):
    """Lead capturado pela landing page ou cadastrado manualmente"""
    __tablename__ = "leads"
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Dados do lead
    nome = db.Column(db.String(200), nullable=False)
    empresa = db.Column(db.String(200), nullable=False)
    cnpj = db.Column(db.String(20), nullable=False)
    email = db.Column(db.String(200), nullable=False, index=True)
    telefone = db.Column(db.String(20), nullable=False)
    mensagem = db.Column(db.Text, nullable=True)
    
    # Status do lead
    status = db.Column(db.String(50), default='novo', index=True)
    # Possíveis valores: novo, contato, qualificado, cliente, perdido
    
    # Metadados
    origem = db.Column(db.String(100), default='landing_nouscard')
    ip_address = db.Column(db.String(50), nullable=True)
    user_agent = db.Column(db.String(500), nullable=True)
    
    # Relacionamento com empresa (quando convertido em cliente)
    empresa_id = db.Column(db.Integer, db.ForeignKey('empresas.id'), nullable=True)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), 
                          onupdate=lambda: datetime.now(timezone.utc))
    contacted_at = db.Column(db.DateTime, nullable=True)
    converted_at = db.Column(db.DateTime, nullable=True)
    
    def __repr__(self):
        return f"<Lead {self.email} - {self.empresa}>"
    
    def to_dict(self):
        return {
            "id": self.id,
            "nome": self.nome,
            "empresa": self.empresa,
            "cnpj": self.cnpj,
            "email": self.email,
            "telefone": self.telefone,
            "mensagem": self.mensagem,
            "status": self.status,
            "origem": self.origem,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "contacted_at": self.contacted_at.isoformat() if self.contacted_at else None,
            "converted_at": self.converted_at.isoformat() if self.converted_at else None
        }
