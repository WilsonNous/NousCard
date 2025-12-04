# models/mov_adquirente.py
from .base import db
from datetime import datetime

class MovAdquirente(db.Model):
    __tablename__ = "mov_adquirente"

    id = db.Column(db.Integer, primary_key=True)

    empresa_id = db.Column(db.Integer, db.ForeignKey("empresas.id"), nullable=False)
    adquirente_id = db.Column(db.Integer, db.ForeignKey("adquirentes.id"), nullable=False)

    # Datas
    data_venda = db.Column(db.Date, nullable=True)
    data_prevista_pagamento = db.Column(db.Date, nullable=True)

    # Identificação
    bandeira = db.Column(db.String(50), nullable=True)
    produto = db.Column(db.String(50), nullable=True)

    parcela = db.Column(db.Integer, nullable=True)
    total_parcelas = db.Column(db.Integer, nullable=True)

    nsu = db.Column(db.String(50), nullable=True)
    autorizacao = db.Column(db.String(50), nullable=True)

    # Valores
    valor_bruto = db.Column(db.Numeric(12, 2), nullable=False)
    taxa_cobrada = db.Column(db.Numeric(10, 4), nullable=True)
    valor_liquido = db.Column(db.Numeric(12, 2), nullable=True)

    # Conciliação
    valor_conciliado = db.Column(db.Numeric(12, 2), default=0)
    status_conciliacao = db.Column(db.String(30), default="pendente")  
    # pendente | conciliado | parcial | nao_recebido | divergente

    data_primeiro_recebimento = db.Column(db.Date, nullable=True)
    data_ultimo_recebimento = db.Column(db.Date, nullable=True)

    arquivo_origem = db.Column(db.String(255), nullable=True)

    criado_em = db.Column(db.DateTime, default=datetime.utcnow)

    # Relacionamento com histórico (opcional)
    conciliacoes = db.relationship("Conciliacao", backref="mov_adquirente", lazy=True)

    def __repr__(self):
        return f"<MovAdquirente {self.id} R${self.valor_bruto}>"
