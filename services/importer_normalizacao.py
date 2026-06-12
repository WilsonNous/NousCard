# services/importer_normalizacao.py
# Serviço para importar arquivos e normalizar no layout proprietário

from models import db, Normalizacao
from datetime import datetime, date, timezone
from decimal import Decimal
import logging
import json

logger = logging.getLogger(__name__)


# ============================================================
# ✅ FUNÇÃO AUXILIAR: Converter tipos não-serializáveis para JSON
# ============================================================
def _preparar_para_json(obj):
    """
    Converte recursivamente objetos não-serializáveis (date, datetime, Decimal)
    para tipos compatíveis com JSON.
    """
    if obj is None:
        return None
    
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    
    if isinstance(obj, Decimal):
        return float(obj)
    
    if isinstance(obj, dict):
        return {k: _preparar_para_json(v) for k, v in obj.items()}
    
    if isinstance(obj, (list, tuple)):
        return [_preparar_para_json(item) for item in obj]
    
    # Se já é tipo primitivo (str, int, float, bool), retorna como está
    return obj


class ImportadorNormalizado:
    """Serviço centralizado para importação e normalização de dados"""
    
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
        """
        logger.info(f"📥 Iniciando normalização: {len(registros)} registros, tipo={tipo_origem}")
        
        self.stats["total_registros"] = len(registros)
        
        # Processar em batches para evitar timeout
        BATCH_SIZE = 50
        total_batches = (len(registros) + BATCH_SIZE - 1) // BATCH_SIZE
        
        for batch_num in range(total_batches):
            inicio_idx = batch_num * BATCH_SIZE
            fim_idx = min((batch_num + 1) * BATCH_SIZE, len(registros))
            batch = registros[inicio_idx:fim_idx]
            
            logger.info(f"📦 Batch {batch_num + 1}/{total_batches}: registros {inicio_idx + 1}-{fim_idx}")
            
            batch_sucesso = 0
            batch_falhas = 0
            batch_duplicados = 0
            
            for idx, reg in enumerate(batch):
                try:
                    # ✅ Garantir rollback se sessão estiver em estado inválido
                    try:
                        db.session.execute(db.text("SELECT 1"))
                    except Exception:
                        db.session.rollback()
                        logger.warning(f"🔄 Rollback executado antes do registro {inicio_idx + idx + 1}")
                    
                    # Criar registro de normalização
                    normalizacao = self._criar_normalizacao(
                        arquivo_id=arquivo_id,
                        dados=reg,
                        tipo_origem=tipo_origem,
                        tipo_movimento=tipo_movimento
                    )
                    
                    # ✅ CORREÇÃO: Auto-preencher adquirente para vendas
                    if normalizacao.tipo_movimento == "venda" and not normalizacao.adquirente_nome:
                        normalizacao.adquirente_nome = "Flow"
                    
                    # Validar
                    valido, erro = normalizacao.validar()
                    if not valido:
                        normalizacao.status = "erro"
                        normalizacao.erro_mensagem = erro
                        self.stats["falhas"] += 1
                        batch_falhas += 1
                        self.stats["erros"].append({
                            "linha": inicio_idx + idx + 1,
                            "erro": erro
                        })
                        db.session.add(normalizacao)
                        continue
                    
                    # Verificar duplicata
                    if self._verificar_duplicata(normalizacao):
                        normalizacao.status = "duplicado"
                        normalizacao.erro_mensagem = "Registro duplicado"
                        self.stats["duplicados"] += 1
                        batch_duplicados += 1
                        db.session.add(normalizacao)
                        continue
                    
                    # Enriquecer dados (resolver adquirente, categorizar)
                    try:
                        normalizacao.enriquecer()
                        normalizacao.status = "validado"
                    except Exception as e:
                        logger.warning(f"⚠️ Erro ao enriquecer registro {inicio_idx + idx + 1}: {str(e)}")
                        normalizacao.status = "validado"  # Continua mesmo sem enriquecimento completo
                    
                    # Salvar
                    db.session.add(normalizacao)
                    self.stats["sucesso"] += 1
                    batch_sucesso += 1
                    
                except Exception as e:
                    logger.error(f"❌ Erro ao normalizar registro {inicio_idx + idx + 1}: {str(e)}", exc_info=True)
                    self.stats["falhas"] += 1
                    batch_falhas += 1
                    self.stats["erros"].append({
                        "linha": inicio_idx + idx + 1,
                        "erro": str(e)
                    })
                    # ✅ Rollback para não contaminar próximos registros
                    try:
                        db.session.rollback()
                    except:
                        pass
                    continue
            
            # Commit do batch
            try:
                db.session.commit()
                logger.info(f"✅ Batch {batch_num + 1}/{total_batches} salvo: {batch_sucesso} sucesso, {batch_falhas} falhas, {batch_duplicados} duplicados")
            except Exception as e:
                logger.error(f"❌ Erro no commit do batch {batch_num + 1}: {str(e)}", exc_info=True)
                db.session.rollback()
                continue
        
        # ✅ Converter set em list para serialização JSON
        if isinstance(self.stats.get("erros"), list):
            pass  # já é lista
        
        logger.info(
            f"✅ Normalização concluída: "
            f"{self.stats['sucesso']} sucesso, "
            f"{self.stats['falhas']} falhas, "
            f"{self.stats['duplicados']} duplicados"
        )
        
        return self.stats
    
    def _criar_normalizacao(self, arquivo_id: int, dados: dict, tipo_origem: str, tipo_movimento: str):
        """Cria objeto Normalizacao a partir dos dados parseados"""
        
        # Data
        data_movimento = (
            dados.get("data_movimento") or 
            dados.get("data") or 
            dados.get("data_venda") or 
            dados.get("data_transacao") or 
            date.today()
        )
        
        if isinstance(data_movimento, str):
            for fmt in ['%Y-%m-%d', '%d/%m/%Y', '%Y/%m/%d']:
                try:
                    data_movimento = datetime.strptime(data_movimento, fmt).date()
                    break
                except:
                    continue
            else:
                data_movimento = date.today()
        
        # Data venda (pode ser diferente da data movimento)
        data_venda_raw = dados.get("data_venda")
        data_venda = None
        if data_venda_raw:
            if isinstance(data_venda_raw, str):
                for fmt in ['%Y-%m-%d', '%d/%m/%Y', '%Y/%m/%d']:
                    try:
                        data_venda = datetime.strptime(data_venda_raw, fmt).date()
                        break
                    except:
                        continue
        
        # Valores
        valor_bruto = self._parse_decimal(dados.get("valor_bruto") or dados.get("valor") or 0)
        valor_liquido = self._parse_decimal(dados.get("valor_liquido") or valor_bruto)
        valor_taxa = self._parse_decimal(dados.get("taxa") or dados.get("desconto") or 0)
        
        # Adquirente - ✅ CORREÇÃO: Sempre definir um nome para vendas
        adquirente_nome = (
            dados.get("adquirente") or 
            dados.get("nome_adquirente") or 
            dados.get("estabelecimento")
        )
        
        # Se for venda e não tem adquirente, usar "Flow"
        if tipo_movimento == "venda" and not adquirente_nome:
            adquirente_nome = "Flow"
        
        # NSU
        nsu = (
            dados.get("nsu") or 
            dados.get("id") or 
            dados.get("fitid")
        )
        
        # Descrição
        descricao = (
            dados.get("descricao") or 
            dados.get("memo") or 
            dados.get("observacoes") or 
            ""
        )
        
        # ✅ CORREÇÃO CRÍTICA: Preparar dados crus para JSON
        dados_crus_preparados = _preparar_para_json(dados)
        
        # Metadados
        metadados = {
            "importado_em": datetime.now(timezone.utc).isoformat(),
            "usuario_id": self.usuario_id,
            "tipo_origem": tipo_origem,
            "nome_arquivo": dados.get("nome_arquivo", "")
        }
        
        normalizacao = Normalizacao(
            empresa_id=self.empresa_id,
            arquivo_origem_id=arquivo_id,
            tipo_origem=tipo_origem,
            tipo_movimento=tipo_movimento,
            
            # Identificadores
            nsu=nsu[:100] if nsu else None,
            autorizacao=dados.get("autorizacao"),
            documento=dados.get("documento"),
            
            # Datas
            data_movimento=data_movimento if isinstance(data_movimento, date) else date.today(),
            data_venda=data_venda,
            
            # Valores
            valor_bruto=valor_bruto,
            valor_liquido=valor_liquido,
            valor_taxa=valor_taxa,
            
            # Classificação
            adquirente_nome=adquirente_nome[:100] if adquirente_nome else None,
            bandeira=dados.get("bandeira"),
            produto=dados.get("produto"),
            tipo_pagamento=dados.get("tipo_pagamento") or "cartao",
            quantidade=dados.get("quantidade"),
            
            # Descrição
            descricao=descricao[:2000] if descricao else None,
            estabelecimento=dados.get("estabelecimento"),
            
            # ✅ CORREÇÃO: Dados crus preparados para JSON
            dados_crus=dados_crus_preparados,
            metadados=metadados,
            
            status="importado"
        )
        
        return normalizacao
    
    def _parse_decimal(self, value):
        """Converte valor para Decimal"""
        if value is None:
            return Decimal("0")
        if isinstance(value, Decimal):
            return value
        try:
            return Decimal(str(value))
        except:
            return Decimal("0")
    
    def _verificar_duplicata(self, normalizacao: Normalizacao) -> bool:
        """Verifica se já existe registro com mesmo NSU/data"""
        if not normalizacao.nsu:
            return False
        
        try:
            duplicata = Normalizacao.query.filter_by(
                empresa_id=self.empresa_id,
                nsu=normalizacao.nsu,
                data_movimento=normalizacao.data_movimento
            ).first()
            
            return duplicata is not None
        except Exception as e:
            logger.warning(f"⚠️ Erro ao verificar duplicata: {str(e)}")
            return False
