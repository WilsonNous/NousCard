# models/normalizacao.py
# Layout proprietário NousCard para normalização de dados importados

from .base import db, BaseMixin
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum as PythonEnum


class TipoOrigemEnum(PythonEnum):
    """Tipos de origem dos dados"""
    OFX_BANCO = "ofx_banco"
    CSV_BANCO = "csv_banco"
    CSV_ADQUIRENTE = "csv_adquirente"
    EXCEL_ADQUIRENTE = "excel_adquirente"
    API = "api"


class TipoMovimentoEnum(PythonEnum):
    """Tipos de movimento"""
    VENDA = "venda"
    RECEBIMENTO = "recebimento"
    PAGAMENTO = "pagamento"
    TRANSFERENCIA = "transferencia"
    TARIFA = "tarifa"
    OUTRO = "outro"


class StatusNormalizacaoEnum(PythonEnum):
    """Status do processo de normalização"""
    IMPORTADO = "importado"  # Dados brutos importados
    VALIDADO = "validado"    # Validação passou
    ENRIQUECIDO = "enriquecido"  # Dados enriquecidos (adquirente, categoria, etc)
    PROCESSADO = "processado"  # Gravado nas tabelas finais
    ERRO = "erro"  # Erro na validação/processamento
    CANCELADO = "cancelado"  # Cancelado pelo usuário


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
    arquivo_origem_id = db.Column(db.Integer, db.ForeignKey("arquivos_importados.id"), nullable=True)
    
    # Tipo e origem
    tipo_origem = db.Column(db.String(50), nullable=False)  # ofx_banco, csv_adquirente, etc
    tipo_movimento = db.Column(db.String(50), nullable=False)  # venda, recebimento, etc
    
    # ============================================================
    # DADOS DA TRANSAÇÃO (CAMPOS PADRONIZADOS)
    # ============================================================
    
    # Identificadores únicos
    nsu = db.Column(db.String(100), nullable=True, index=True)  # NSU, ID da transação
    autorizacao = db.Column(db.String(50), nullable=True)  # Código de autorização
    documento = db.Column(db.String(100), nullable=True)  # Documento fiscal, boleto, etc
    
    # Datas
    data_movimento = db.Column(db.Date, nullable=False, index=True)  # Data do movimento
    data_venda = db.Column(db.Date, nullable=True)  # Data da venda (pode ser diferente)
    data_prevista_pagamento = db.Column(db.Date, nullable=True)  # Previsão de recebimento
    
    # Valores monetários
    valor_bruto = db.Column(db.Numeric(12, 2), nullable=False)  # Valor bruto
    valor_liquido = db.Column(db.Numeric(12, 2), nullable=True)  # Valor líquido (após taxas)
    valor_taxa = db.Column(db.Numeric(10, 4), nullable=True)  # Valor da taxa cobrada
    valor_desconto = db.Column(db.Numeric(10, 2), nullable=True)  # Descontos
    valor_acrescimo = db.Column(db.Numeric(10, 2), nullable=True)  # Acréscimos
    
    # ============================================================
    # CLASSIFICAÇÃO
    # ============================================================
    
    # Adquirente/Meio de pagamento
    adquirente_nome = db.Column(db.String(100), nullable=True)  # Nome da adquirente (Flow, Cielo, etc)
    adquirente_id = db.Column(db.Integer, db.ForeignKey("adquirentes.id"), nullable=True)
    bandeira = db.Column(db.String(50), nullable=True)  # Visa, Mastercard, Elo, etc
    produto = db.Column(db.String(50), nullable=True)  # Crédito, Débito, PIX, etc
    tipo_pagamento = db.Column(db.String(50), nullable=True)  # cartao, pix, boleto
    
    # Parcelamento
    parcela = db.Column(db.Integer, nullable=True)  # Número da parcela
    total_parcelas = db.Column(db.Integer, nullable=True)  # Total de parcelas
    
    # Conta bancária (para recebimentos/pagamentos)
    conta_bancaria_id = db.Column(db.Integer, db.ForeignKey("contas_bancarias.id"), nullable=True)
    banco_codigo = db.Column(db.String(10), nullable=True)  # Código do banco
    agencia = db.Column(db.String(20), nullable=True)
    conta = db.Column(db.String(30), nullable=True)
    
    # ============================================================
    # DESCRIÇÃO E DETALHES
    # ============================================================
    descricao = db.Column(db.Text, nullable=True)  # Descrição completa
    historico = db.Column(db.Text, nullable=True)  # Histórico complementar
    favorecido = db.Column(db.String(200), nullable=True)  # Nome do favorecido/pagador
    estabelecimento = db.Column(db.String(200), nullable=True)  # Estabelecimento comercial
    
    # ============================================================
    # CATEGORIZAÇÃO
    # ============================================================
    categoria = db.Column(db.String(100), nullable=True)  # Categoria automática
    subcategoria = db.Column(db.String(100), nullable=True)  # Subcategoria
    tags = db.Column(db.String(500), nullable=True)  # Tags separadas por vírgula
    
    # ============================================================
    # CONTROLE E STATUS
    # ============================================================
    status = db.Column(db.String(30), nullable=False, default="importado", index=True)
    erro_mensagem = db.Column(db.Text, nullable=True)  # Mensagem de erro se houver
    
    # Dados crus (JSON) para auditoria e reprocessamento
    dados_crus = db.Column(db.JSON, nullable=True)
    metadados = db.Column(db.JSON, nullable=True)  # Metadados da importação
    
    # ============================================================
    # RELACIONAMENTOS
    # ============================================================
    empresa = db.relationship("Empresa", backref="normalizacoes")
    arquivo_origem = db.relationship("ArquivoImportado", backref="normalizacoes")
    adquirente = db.relationship("Adquirente", backref="normalizacoes")
    conta_bancaria = db.relationship("ContaBancaria", backref="normalizacoes")
    
    # ============================================================
    # MÉTODOS AUXILIARES
    # ============================================================
    def __repr__(self):
        return f"<Normalizacao {self.id} - {self.tipo_movimento} - {self.data_movimento}>"
    
    def to_dict(self):
        """Converte para dicionário (útil para APIs e debug)"""
        return {
            "id": self.id,
            "empresa_id": self.empresa_id,
            "tipo_origem": self.tipo_origem,
            "tipo_movimento": self.tipo_movimento,
            "nsu": self.nsu,
            "data_movimento": self.data_movimento.isoformat() if self.data_movimento else None,
            "data_venda": self.data_venda.isoformat() if self.data_venda else None,
            "valor_bruto": float(self.valor_bruto) if self.valor_bruto else None,
            "valor_liquido": float(self.valor_liquido) if self.valor_liquido else None,
            "adquirente_nome": self.adquirente_nome,
            "bandeira": self.bandeira,
            "produto": self.produto,
            "status": self.status,
            "categoria": self.categoria,
            "descricao": self.descricao,
        }
    
    def validar(self):
        """
        Valida os dados antes do processamento.
        Retorna tuple (bool, str): (valido, mensagem_erro)
        """
        erros = []
        
        # Validações obrigatórias
        if not self.empresa_id:
            erros.append("empresa_id é obrigatório")
        
        if not self.data_movimento:
            erros.append("data_movimento é obrigatório")
        
        if not self.valor_bruto or self.valor_bruto <= 0:
            erros.append("valor_bruto deve ser maior que zero")
        
        if not self.tipo_movimento:
            erros.append("tipo_movimento é obrigatório")
        
        # Validações específicas por tipo
        if self.tipo_movimento == "venda":
            if not self.adquirente_nome and not self.adquirente_id:
                erros.append("venda requer adquirente")
        
        if erros:
            return False, "; ".join(erros)
        
        return True, None
    
    def enriquecer(self):
        """
        Enriquece os dados com informações adicionais.
        Ex: Resolver adquirente por nome, categorizar automaticamente, etc.
        """
        from models import Adquirente
        
        # Resolver adquirente por nome se tiver
        if self.adquirente_nome and not self.adquirente_id:
            adquirente = Adquirente.query.filter(
                db.func.lower(Adquirente.nome) == self.adquirente_nome.lower()
            ).first()
            
            if adquirente:
                self.adquirente_id = adquirente.id
            else:
                # Criar adquirente se não existir
                nova_adquirente = Adquirente(
                    nome=self.adquirente_nome[:100],
                    codigo=self.adquirente_nome[:20].upper().replace(" ", "_"),
                    ativo=True
                )
                db.session.add(nova_adquirente)
                db.session.flush()
                self.adquirente_id = nova_adquirente.id
        
        # Categorização automática baseada em descrição/histórico
        if not self.categoria and self.descricao:
            self.categoria = self._categorizar_automatico()
        
        return True
    
    def _categorizar_automatico(self):
        """Categorização automática baseada em palavras-chave"""
        texto = f"{self.descricao or ''} {self.historico or ''}".upper()
        
        # Vendas
        if any(kw in texto for kw in ["VENDA", "SIPAG", "CR COMPRAS", "CRED.COMPRAS"]):
            if "MASTERCARD" in texto:
                return "vendas_mastercard"
            elif "VISA" in texto:
                return "vendas_visa"
            elif "ELO" in texto:
                return "vendas_elo"
        
        # PIX
        if "PIX" in texto:
            if "RECEBIDO" in texto or "CREDITADO" in texto:
                return "pix_recebido"
            else:
                return "pix_emitido"
        
        # Tarifas
        if any(kw in texto for kw in ["TARIFA", "MANUTENÇÃO", "PACOTE SERVIÇOS"]):
            return "tarifa_bancaria"
        
        # Tributos
        if any(kw in texto for kw in ["DAS", "IMPOSTO", "TRIBUTOS", "RFB"]):
            return "tributos"
        
        # Transferências
        if any(kw in texto for kw in ["TED", "DOC", "TRANSFERÊNCIA", "TRANSF"]):
            if "RECEBIDA" in texto or "CRÉDITO" in texto:
                return "transferencia_recebida"
            else:
                return "transferencia_enviada"
        
        return "outros"
