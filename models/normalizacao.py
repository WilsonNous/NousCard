# models/normalizacao.py
# Layout proprietário NousCard para normalização de dados importados

from .base import db, BaseMixin
from datetime import datetime, timezone, date
from decimal import Decimal
from sqlalchemy import JSON


class Normalizacao(db.Model, BaseMixin):
    """
    Tabela intermediária para normalização de dados importados.
    Funciona como camada de abstração entre arquivos de entrada e tabelas finais.
    """
    __tablename__ = "tous_normalizacao"
    
    id = db.Column(db.Integer, primary_key=True)
    
    # ============================================================
    # IDENTIFICAÇÃO
    # ============================================================
    empresa_id = db.Column(db.Integer, db.ForeignKey("empresas.id"), nullable=False, index=True)
    arquivo_origem_id = db.Column(db.Integer, db.ForeignKey("arquivos_importados.id"), nullable=True, index=True)
    
    # Tipo e origem
    tipo_origem = db.Column(db.String(50), nullable=False, index=True)
    tipo_movimento = db.Column(db.String(50), nullable=False, index=True)
    
    # ============================================================
    # DADOS DA TRANSAÇÃO
    # ============================================================
    
    nsu = db.Column(db.String(100), nullable=True, index=True)
    autorizacao = db.Column(db.String(50), nullable=True)
    documento = db.Column(db.String(100), nullable=True)
    
    data_movimento = db.Column(db.Date, nullable=False, index=True)
    data_venda = db.Column(db.Date, nullable=True, index=True)
    data_prevista_pagamento = db.Column(db.Date, nullable=True)
    
    valor_bruto = db.Column(db.Numeric(12, 2), nullable=False, default=Decimal("0"))
    valor_liquido = db.Column(db.Numeric(12, 2), nullable=True)
    valor_taxa = db.Column(db.Numeric(10, 4), nullable=True, default=Decimal("0"))
    valor_desconto = db.Column(db.Numeric(10, 2), nullable=True, default=Decimal("0"))
    valor_acrescimo = db.Column(db.Numeric(10, 2), nullable=True, default=Decimal("0"))
    
    # ============================================================
    # CLASSIFICAÇÃO
    # ============================================================
    
    adquirente_nome = db.Column(db.String(100), nullable=True, index=True)
    adquirente_id = db.Column(db.Integer, db.ForeignKey("adquirentes.id"), nullable=True)
    bandeira = db.Column(db.String(50), nullable=True, index=True)
    produto = db.Column(db.String(50), nullable=True)
    tipo_pagamento = db.Column(db.String(50), nullable=True, index=True)
    
    parcela = db.Column(db.Integer, nullable=True)
    total_parcelas = db.Column(db.Integer, nullable=True)
    
    conta_bancaria_id = db.Column(db.Integer, db.ForeignKey("contas_bancarias.id"), nullable=True)
    banco_codigo = db.Column(db.String(10), nullable=True)
    agencia = db.Column(db.String(20), nullable=True)
    conta = db.Column(db.String(30), nullable=True)
    
    # ============================================================
    # DESCRIÇÃO E DETALHES
    # ============================================================
    descricao = db.Column(db.Text, nullable=True)
    historico = db.Column(db.Text, nullable=True)
    favorecido = db.Column(db.String(200), nullable=True)
    estabelecimento = db.Column(db.String(200), nullable=True)
    quantidade = db.Column(db.Integer, nullable=True)
    
    # ============================================================
    # CATEGORIZAÇÃO
    # ============================================================
    categoria = db.Column(db.String(100), nullable=True, index=True)
    subcategoria = db.Column(db.String(100), nullable=True)
    tags = db.Column(db.String(500), nullable=True)
    
    # ============================================================
    # ✅ NOVOS CAMPOS: INTELIGÊNCIA FINANCEIRA
    # ============================================================
    score_classificacao = db.Column(db.Integer, default=0)
    origem_classificacao = db.Column(db.String(100), default='')
    regra_utilizada = db.Column(db.String(100), default='')
    grupo = db.Column(db.String(100), default='')
    natureza = db.Column(db.String(20), default='')
    centro_custo = db.Column(db.String(100), default='')
    
    # ============================================================
    # CONTROLE E STATUS
    # ============================================================
    status = db.Column(db.String(30), nullable=False, default="importado", index=True)
    erro_mensagem = db.Column(db.Text, nullable=True)
    
    dados_crus = db.Column(JSON, nullable=True)
    metadados = db.Column(JSON, nullable=True)
    
    # ============================================================
    # RELACIONAMENTOS
    # ============================================================
    empresa = db.relationship("Empresa", backref=db.backref("normalizacoes", lazy="dynamic"))
    arquivo_origem = db.relationship("ArquivoImportado", backref=db.backref("normalizacoes", lazy="dynamic"))
    adquirente = db.relationship("Adquirente", backref=db.backref("normalizacoes", lazy="dynamic"))
    conta_bancaria = db.relationship("ContaBancaria", backref=db.backref("normalizacoes", lazy="dynamic"))
    
    # ============================================================
    # MÉTODOS AUXILIARES
    # ============================================================
    def __repr__(self):
        return f"<Normalizacao {self.id} - {self.tipo_movimento} - {self.data_movimento}>"
    
    def to_dict(self):
        """Converte para dicionário"""
        return {
            "id": self.id,
            "empresa_id": self.empresa_id,
            "tipo_origem": self.tipo_origem,
            "tipo_movimento": self.tipo_movimento,
            "nsu": self.nsu,
            "data_movimento": self.data_movimento.isoformat() if self.data_movimento else None,
            "data_venda": self.data_venda.isoformat() if self.data_venda else None,
            "valor_bruto": float(self.valor_bruto) if self.valor_bruto else 0,
            "valor_liquido": float(self.valor_liquido) if self.valor_liquido else None,
            "valor_taxa": float(self.valor_taxa) if self.valor_taxa else None,
            "adquirente_nome": self.adquirente_nome,
            "bandeira": self.bandeira,
            "produto": self.produto,
            "tipo_pagamento": self.tipo_pagamento,
            "status": self.status,
            "categoria": self.categoria,
            "descricao": self.descricao,
            "score_classificacao": self.score_classificacao,
            "grupo": self.grupo,
            "natureza": self.natureza,
            "centro_custo": self.centro_custo,
            "criado_em": self.criado_em.isoformat() if self.criado_em else None
        }
    
    def validar(self):
        """Valida os dados antes do processamento"""
        erros = []
        
        if not self.empresa_id:
            erros.append("empresa_id é obrigatório")
        
        if not self.data_movimento:
            erros.append("data_movimento é obrigatório")
        
        if not self.valor_bruto or self.valor_bruto <= 0:
            erros.append("valor_bruto deve ser maior que zero")
        
        if not self.tipo_movimento:
            erros.append("tipo_movimento é obrigatório")
        
        if self.tipo_movimento == "venda":
            if not self.adquirente_nome and not self.adquirente_id:
                self.adquirente_nome = "Flow"
        
        if erros:
            return False, "; ".join(erros)
        
        return True, None
    
    def enriquecer(self):
        """Enriquece os dados com informações adicionais"""
        from models import Adquirente
        
        if self.adquirente_nome and not self.adquirente_id:
            adquirente = Adquirente.query.filter(
                db.func.lower(Adquirente.nome) == self.adquirente_nome.lower()
            ).first()
            
            if adquirente:
                self.adquirente_id = adquirente.id
            else:
                nova_adquirente = Adquirente(
                    nome=self.adquirente_nome[:100],
                    codigo=self.adquirente_nome[:20].upper().replace(" ", "_"),
                    ativo=True
                )
                db.session.add(nova_adquirente)
                db.session.flush()
                self.adquirente_id = nova_adquirente.id
        
        if not self.categoria and self.descricao:
            self.categoria = self._categorizar_automatico()
        
        return True
    
    def _categorizar_automatico(self):
        """Categorização automática baseada em palavras-chave"""
        texto = f"{self.descricao or ''} {self.historico or ''}".upper()
        
        if any(kw in texto for kw in ["VENDA", "SIPAG", "CR COMPRAS", "CRED.COMPRAS"]):
            if "MASTERCARD" in texto:
                return "vendas_mastercard"
            elif "VISA" in texto:
                return "vendas_visa"
            elif "ELO" in texto:
                return "vendas_elo"
        
        if "PIX" in texto:
            if "RECEBIDO" in texto or "CREDITADO" in texto:
                return "pix_recebido"
            else:
                return "pix_emitido"
        
        if any(kw in texto for kw in ["TARIFA", "MANUTENÇÃO", "PACOTE SERVIÇOS"]):
            return "tarifa_bancaria"
        
        if any(kw in texto for kw in ["DAS", "IMPOSTO", "TRIBUTOS", "RFB"]):
            return "tributos"
        
        if any(kw in texto for kw in ["TED", "DOC", "TRANSFERÊNCIA", "TRANSF"]):
            if "RECEBIDA" in texto or "CRÉDITO" in texto:
                return "transferencia_recebida"
            else:
                return "transferencia_enviada"
        
        return "outros"