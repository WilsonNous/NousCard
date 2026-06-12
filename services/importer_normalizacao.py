# services/importer_normalizacao.py
# Serviço para importar arquivos e normalizar no layout proprietário

from models import db, Normalizacao, ArquivoImportado
from datetime import datetime, date, timezone
from decimal import Decimal
import logging
import json

logger = logging.getLogger(__name__)


class ImportadorNormalizado:
    """
    Serviço centralizado para importação e normalização de dados.
    """
    
    def __init__(self, empresa_id: int, usuario_id: int):
        self.empresa_id = empresa_id
        self.usuario_id = usuario_id
        self.stats = {
            "total_registros": 0,
            "sucesso": 0,
            "falhas": 0,
            "duplicados": 0,
            "erros": []
        }
    
    def importar_arquivo(self, arquivo_id: int, registros: list, tipo_origem: str, tipo_movimento: str):
        """
        Importa registros de um arquivo e salva na tabela de normalização.
        
        Args:
            arquivo_id: ID do arquivo importado
            registros: Lista de dicionários com os dados parseados
            tipo_origem: ofx_banco, csv_adquirente, etc
            tipo_movimento: venda, recebimento, etc
        
        Returns:
            dict: Estatísticas da importação
        """
        logger.info(f"📥 Iniciando normalização: {len(registros)} registros, tipo={tipo_origem}")
        
        self.stats["total_registros"] = len(registros)
        
        for idx, reg in enumerate(registros):
            try:
                # Criar registro de normalização
                normalizacao = self._criar_normalizacao(
                    arquivo_id=arquivo_id,
                    dados=reg,
                    tipo_origem=tipo_origem,
                    tipo_movimento=tipo_movimento
                )
                
                # Validar
                valido, erro = normalizacao.validar()
                if not valido:
                    normalizacao.status = "erro"
                    normalizacao.erro_mensagem = erro
                    self.stats["falhas"] += 1
                    self.stats["erros"].append({
                        "linha": idx + 1,
                        "erro": erro,
                        "dados": reg
                    })
                    continue
                
                # Verificar duplicata
                if self._verificar_duplicata(normalizacao):
                    normalizacao.status = "cancelado"
                    normalizacao.erro_mensagem = "Registro duplicado"
                    self.stats["duplicados"] += 1
                    continue
                
                # Enriquecer dados
                normalizacao.enriquecer()
                
                # Salvar
                db.session.add(normalizacao)
                self.stats["sucesso"] += 1
                
            except Exception as e:
                logger.error(f"❌ Erro ao normalizar registro {idx}: {str(e)}", exc_info=True)
                self.stats["falhas"] += 1
                self.stats["erros"].append({
                    "linha": idx + 1,
                    "erro": str(e),
                    "dados": reg
                })
                continue
        
        db.session.commit()
        
        logger.info(
            f"✅ Normalização concluída: "
            f"{self.stats['sucesso']} sucesso, "
            f"{self.stats['falhas']} falhas, "
            f"{self.stats['duplicados']} duplicados"
        )
        
        return self.stats
    
    def _criar_normalizacao(self, arquivo_id: int, dados: dict, tipo_origem: str, tipo_movimento: str):
        """Cria objeto Normalizacao a partir dos dados parseados"""
        
        # Mapeamento inteligente de campos
        # Aceita múltiplos nomes para o mesmo campo
        
        # Data
        data_movimento = (
            dados.get("data_movimento") or 
            dados.get("data") or 
            dados.get("data_venda") or 
            dados.get("data_transacao") or 
            date.today()
        )
        
        # Valores
        valor_bruto = self._parse_decimal(dados.get("valor_bruto") or dados.get("valor") or dados.get("amount") or 0)
        valor_liquido = self._parse_decimal(
            dados.get("valor_liquido") or 
            dados.get("valor_liq") or 
            valor_bruto
        )
        valor_taxa = self._parse_decimal(dados.get("taxa") or dados.get("desconto") or dados.get("taxa_cobrada") or 0)
        
        # Adquirente
        adquirente_nome = (
            dados.get("adquirente") or 
            dados.get("nome_adquirente") or 
            dados.get("merchant") or 
            dados.get("estabelecimento")
        )
        
        # NSU/ID
        nsu = (
            dados.get("nsu") or 
            dados.get("id") or 
            dados.get("fitid") or 
            dados.get("transaction_id")
        )
        
        # Descrição
        descricao = (
            dados.get("descricao") or 
            dados.get("memo") or 
            dados.get("description") or 
            dados.get("historico") or 
            ""
        )
        
        normalizacao = Normalizacao(
            empresa_id=self.empresa_id,
            arquivo_origem_id=arquivo_id,
            tipo_origem=tipo_origem,
            tipo_movimento=tipo_movimento,
            
            # Dados da transação
            nsu=nsu[:100] if nsu else None,
            autorizacao=dados.get("autorizacao") or dados.get("authorization"),
            documento=dados.get("documento") or dados.get("document"),
            
            # Datas
            data_movimento=data_movimento if isinstance(data_movimento, date) else date.today(),
            data_venda=dados.get("data_venda"),
            data_prevista_pagamento=dados.get("data_prevista_pagamento"),
            
            # Valores
            valor_bruto=valor_bruto,
            valor_liquido=valor_liquido,
            valor_taxa=valor_taxa,
            valor_desconto=self._parse_decimal(dados.get("desconto") or 0),
            
            # Classificação
            adquirente_nome=adquirente_nome[:100] if adquirente_nome else None,
            bandeira=dados.get("bandeira") or dados.get("brand") or dados.get("card"),
            produto=dados.get("produto") or dados.get("product") or dados.get("tipo"),
            tipo_pagamento=dados.get("tipo_pagamento") or dados.get("payment_type"),
            
            # Parcelamento
            parcela=dados.get("parcela") or dados.get("parcel"),
            total_parcelas=dados.get("total_parcelas"),
            
            # Descrição
            descricao=descricao[:2000] if descricao else None,
            historico=dados.get("historico") or dados.get("history"),
            favorecido=dados.get("favorecido") or dados.get("beneficiario"),
            estabelecimento=dados.get("estabelecimento"),
            
            # Dados crus para auditoria
            dados_crus=dados,
            metadados={
                "importado_em": datetime.now(timezone.utc).isoformat(),
                "usuario_id": self.usuario_id,
                "tipo_origem": tipo_origem
            },
            
            status="importado"
        )
        
        return normalizacao
    
    def _parse_decimal(self, value):
        """Converte valor para Decimal de forma segura"""
        if value is None:
            return Decimal("0")
        if isinstance(value, Decimal):
            return value
        try:
            return Decimal(str(value))
        except:
            return Decimal("0")
    
    def _verificar_duplicata(self, normalizacao: Normalizacao) -> bool:
        """Verifica se já existe registro com mesmo NSU/data/valor"""
        if not normalizacao.nsu:
            return False
        
        duplicata = Normalizacao.query.filter_by(
            empresa_id=self.empresa_id,
            nsu=normalizacao.nsu,
            data_movimento=normalizacao.data_movimento
        ).first()
        
        return duplicata is not None
    
    def processar_para_tabelas_finais(self, normalizacoes_ids: list = None):
        """
        Processa registros normalizados e salva nas tabelas finais.
        
        Args:
            normalizacoes_ids: Lista de IDs de normalizações para processar.
                              Se None, processa todas com status='enriquecido'
        """
        query = Normalizacao.query.filter_by(
            empresa_id=self.empresa_id,
            status="enriquecido"
        )
        
        if normalizacoes_ids:
            query = query.filter(Normalizacao.id.in_(normalizacoes_ids))
        
        normalizacoes = query.all()
        
        logger.info(f"🔄 Processando {len(normalizacoes)} registros para tabelas finais")
        
        vendas = []
        recebimentos = []
        
        for norm in normalizacoes:
            try:
                if norm.tipo_movimento == "venda":
                    vendas.append(self._converter_para_mov_adquirente(norm))
                elif norm.tipo_movimento in ["recebimento", "pagamento"]:
                    recebimentos.append(self._converter_para_mov_banco(norm))
                
                # Marcar como processado
                norm.status = "processado"
                
            except Exception as e:
                logger.error(f"❌ Erro ao processar normalizacao {norm.id}: {str(e)}")
                norm.status = "erro"
                norm.erro_mensagem = str(e)
        
        # Salvar nas tabelas finais
        if vendas:
            from services.importer_db_movimento import salvar_vendas
            salvar_vendas(vendas, self.empresa_id)
        
        if recebimentos:
            from services.importer_db_movimento import salvar_recebimentos
            salvar_recebimentos(recebimentos, self.empresa_id, None)
        
        db.session.commit()
        
        logger.info(f"✅ Processamento concluído: {len(vendas)} vendas, {len(recebimentos)} recebimentos")
    
    def _converter_para_mov_adquirente(self, norm: Normalizacao) -> dict:
        """Converte Normalizacao para formato esperado por salvar_vendas"""
        return {
            "adquirente": norm.adquirente_nome,
            "nsu": norm.nsu,
            "data_venda": norm.data_venda or norm.data_movimento,
            "valor_bruto": float(norm.valor_bruto),
            "valor_liquido": float(norm.valor_liquido) if norm.valor_liquido else None,
            "desconto": float(norm.valor_taxa) if norm.valor_taxa else None,
            "bandeira": norm.bandeira,
            "produto": norm.produto,
            "tipo_pagamento": norm.tipo_pagamento or "cartao",
            "observacoes": norm.descricao,
            "empresa_id": self.empresa_id,
        }
    
    def _converter_para_mov_banco(self, norm: Normalizacao) -> dict:
        """Converte Normalizacao para formato esperado por salvar_recebimentos"""
        return {
            "data": norm.data_movimento,
            "valor": float(norm.valor_bruto),
            "descricao": norm.descricao,
            "nsu": norm.nsu,
            "tipo_pagamento": norm.tipo_pagamento,
            "categoria": norm.categoria,
            "empresa_id": self.empresa_id,
        }
