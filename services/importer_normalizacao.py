# services/importer_normalizacao.py
# ✅ INTEGRADO COM CLASSIFICADOR FINANCEIRO
# ✅ CORRIGIDO: não envia campos inexistentes para a model Normalizacao

from models import db, Normalizacao
from datetime import datetime, date, timezone
from decimal import Decimal
import logging

from services.classificador_financeiro import classificador

logger = logging.getLogger(__name__)


def _preparar_para_json(obj):
    """Converte recursivamente objetos não serializáveis para JSON."""
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

    return obj


class ImportadorNormalizado:
    """Serviço centralizado para importação e normalização de dados."""

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
        """Importa registros e salva na tabela de normalização."""
        logger.info(
            f"📥 Iniciando normalização: {len(registros)} registros, "
            f"tipo_origem={tipo_origem}, tipo_movimento={tipo_movimento}"
        )

        self.stats["total_registros"] = len(registros)

        BATCH_SIZE = 50
        total_batches = (len(registros) + BATCH_SIZE - 1) // BATCH_SIZE

        for batch_num in range(total_batches):
            inicio_idx = batch_num * BATCH_SIZE
            fim_idx = min((batch_num + 1) * BATCH_SIZE, len(registros))
            batch = registros[inicio_idx:fim_idx]

            batch_sucesso = 0
            batch_falhas = 0
            batch_duplicados = 0

            for idx, reg in enumerate(batch):
                numero_registro = inicio_idx + idx + 1

                try:
                    try:
                        db.session.execute(db.text("SELECT 1"))
                    except Exception:
                        db.session.rollback()

                    normalizacao = self._criar_normalizacao(
                        arquivo_id=arquivo_id,
                        dados=reg,
                        tipo_origem=tipo_origem,
                        tipo_movimento=tipo_movimento
                    )

                    if normalizacao.tipo_movimento == "venda" and not normalizacao.adquirente_nome:
                        normalizacao.adquirente_nome = "Flow"

                    valido, erro = normalizacao.validar()

                    if not valido:
                        normalizacao.status = "erro"
                        normalizacao.erro_mensagem = erro

                        self.stats["falhas"] += 1
                        batch_falhas += 1

                        db.session.add(normalizacao)
                        continue

                    if self._verificar_duplicata(normalizacao):
                        normalizacao.status = "duplicado"
                        normalizacao.erro_mensagem = "Registro duplicado"

                        self.stats["duplicados"] += 1
                        batch_duplicados += 1

                        db.session.add(normalizacao)
                        continue

                    try:
                        normalizacao.enriquecer()
                        normalizacao.status = "validado"
                    except Exception as e:
                        logger.debug(
                            f"⚠️ Falha ao enriquecer normalização {numero_registro}: {str(e)}"
                        )
                        normalizacao.status = "validado"

                    db.session.add(normalizacao)

                    self.stats["sucesso"] += 1
                    batch_sucesso += 1

                except Exception as e:
                    logger.error(
                        f"❌ Erro ao normalizar registro {numero_registro}: {str(e)}",
                        exc_info=True
                    )

                    self.stats["falhas"] += 1
                    batch_falhas += 1

                    try:
                        db.session.rollback()
                    except Exception:
                        pass

                    continue

            try:
                db.session.commit()
                logger.info(
                    f"✅ Batch {batch_num + 1}/{total_batches}: "
                    f"{batch_sucesso} OK, {batch_falhas} falhas, {batch_duplicados} duplicados"
                )

            except Exception as e:
                logger.error(
                    f"❌ Erro no commit do batch {batch_num + 1}: {str(e)}",
                    exc_info=True
                )
                db.session.rollback()
                continue

        logger.info(
            f"✅ Normalização concluída: "
            f"{self.stats['sucesso']} sucesso, "
            f"{self.stats['falhas']} falhas, "
            f"{self.stats['duplicados']} duplicados"
        )

        return self.stats

    def _criar_normalizacao(self, arquivo_id: int, dados: dict, tipo_origem: str, tipo_movimento: str):
        """Cria objeto Normalizacao a partir dos dados parseados."""

        data_movimento = (
            dados.get("data_movimento")
            or dados.get("data")
            or dados.get("data_venda")
            or dados.get("data_transacao")
            or date.today()
        )

        data_movimento = self._parse_date(data_movimento) or date.today()

        data_venda_raw = dados.get("data_venda")
        data_venda = self._parse_date(data_venda_raw) if data_venda_raw else None

        valor_bruto = self._parse_decimal(
            dados.get("valor_bruto")
            if dados.get("valor_bruto") is not None
            else dados.get("valor", 0)
        )

        valor_liquido = self._parse_decimal(
            dados.get("valor_liquido")
            if dados.get("valor_liquido") is not None
            else valor_bruto
        )

        valor_taxa = self._parse_decimal(
            dados.get("valor_taxa")
            if dados.get("valor_taxa") is not None
            else dados.get("taxa")
            if dados.get("taxa") is not None
            else dados.get("desconto", 0)
        )

        adquirente_nome = (
            dados.get("adquirente")
            or dados.get("nome_adquirente")
            or dados.get("estabelecimento")
        )

        if tipo_movimento == "venda" and not adquirente_nome:
            adquirente_nome = "Flow"

        nsu = dados.get("nsu") or dados.get("id") or dados.get("fitid")

        descricao = (
            dados.get("descricao")
            or dados.get("memo")
            or dados.get("historico")
            or dados.get("observacoes")
            or ""
        )

        categoria = dados.get("categoria")
        tipo_pagamento = dados.get("tipo_pagamento") or "outros"

        score = dados.get("score_classificacao", 0)
        origem = dados.get("origem_classificacao", "")
        regra = dados.get("regra_utilizada", "")
        grupo = dados.get("grupo", "")
        subgrupo = dados.get("subgrupo", "")
        natureza = dados.get("natureza", "")
        centro_custo = dados.get("centro_custo", "")
        palavra_chave = dados.get("palavra_chave", "")
        icone = dados.get("icone", "")
        cor = dados.get("cor", "")

        if not categoria or categoria in ["outros", "outras_despesas"]:
            resultado = classificador.classificar(
                descricao=descricao or "",
                valor=float(valor_bruto),
                trntype="DEBIT" if valor_bruto < 0 else "CREDIT"
            )

            categoria = resultado.get("categoria") or categoria or "outros"
            tipo_pagamento = resultado.get("tipo_pagamento") or tipo_pagamento or "outros"
            score = resultado.get("score", 0)
            origem = "classificador_financeiro_v2"
            regra = resultado.get("regra") or resultado.get("categoria") or categoria
            grupo = resultado.get("grupo", "")
            subgrupo = resultado.get("subgrupo", "")
            natureza = resultado.get("natureza", "")
            centro_custo = resultado.get("centro_custo", "")
            palavra_chave = resultado.get("palavra_chave", "")
            icone = resultado.get("icone", "")
            cor = resultado.get("cor", "")

        dados_crus_preparados = _preparar_para_json(dados)

        metadados = {
            "importado_em": datetime.now(timezone.utc).isoformat(),
            "usuario_id": self.usuario_id,
            "tipo_origem": tipo_origem,
            "nome_arquivo": dados.get("nome_arquivo", ""),
            "classificacao": {
                "score_classificacao": score,
                "origem_classificacao": origem,
                "regra_utilizada": regra,
                "grupo": grupo,
                "subgrupo": subgrupo,
                "natureza": natureza,
                "centro_custo": centro_custo,
                "palavra_chave": palavra_chave,
                "icone": icone,
                "cor": cor,
            }
        }

        # IMPORTANTE:
        # Não passar grupo/subgrupo/score/origem/regra/natureza/centro_custo
        # diretamente para Normalizacao, pois esses campos não existem na model atual.
        # Eles ficam seguros dentro de metadados["classificacao"].

        normalizacao = Normalizacao(
            empresa_id=self.empresa_id,
            arquivo_origem_id=arquivo_id,
            tipo_origem=tipo_origem,
            tipo_movimento=tipo_movimento,
            nsu=nsu[:100] if nsu else None,
            autorizacao=dados.get("autorizacao"),
            documento=dados.get("documento"),
            data_movimento=data_movimento,
            data_venda=data_venda,
            valor_bruto=valor_bruto,
            valor_liquido=valor_liquido,
            valor_taxa=valor_taxa,
            adquirente_nome=adquirente_nome[:100] if adquirente_nome else None,
            bandeira=dados.get("bandeira"),
            produto=dados.get("produto"),
            tipo_pagamento=tipo_pagamento,
            quantidade=dados.get("quantidade"),
            descricao=descricao[:2000] if descricao else None,
            estabelecimento=dados.get("estabelecimento"),
            categoria=categoria,
            dados_crus=dados_crus_preparados,
            metadados=metadados,
            status="importado"
        )

        return normalizacao

    def _parse_decimal(self, value):
        if value is None:
            return Decimal("0")

        if isinstance(value, Decimal):
            return value

        try:
            return Decimal(str(value))
        except Exception:
            return Decimal("0")

    def _parse_date(self, value):
        if not value:
            return None

        if isinstance(value, date) and not isinstance(value, datetime):
            return value

        if isinstance(value, datetime):
            return value.date()

        if isinstance(value, str):
            value = value.strip()

            formatos = [
                "%Y-%m-%d",
                "%d/%m/%Y",
                "%Y/%m/%d",
                "%Y%m%d",
                "%Y-%m-%d %H:%M:%S",
                "%d/%m/%Y %H:%M:%S",
            ]

            for fmt in formatos:
                try:
                    return datetime.strptime(value, fmt).date()
                except Exception:
                    continue

        return None

    def _verificar_duplicata(self, normalizacao: Normalizacao) -> bool:
        """
        Verifica duplicidade na camada de normalização.
    
        Regra:
        - Para vendas/adquirentes: bloqueia duplicidade por empresa + nsu + data + tipo.
        - Para recebimento/pagamento/extrato bancário: NÃO bloqueia na normalização.
          Motivo: o extrato precisa seguir para mov_banco. A duplicidade bancária deve ser
          tratada na tabela final ou por arquivo_origem, não aqui.
        """
    
        if not normalizacao.nsu:
            logger.info(
                f"🧪 [NORMALIZACAO] Sem NSU/FITID. Não será tratado como duplicado. "
                f"arquivo={normalizacao.arquivo_origem_id}, tipo={normalizacao.tipo_movimento}"
            )
            return False
    
        if normalizacao.tipo_movimento in ["recebimento", "pagamento", "extrato"]:
            logger.info(
                f"🧪 [NORMALIZACAO] Duplicidade ignorada para extrato bancário. "
                f"arquivo={normalizacao.arquivo_origem_id}, nsu={normalizacao.nsu}, "
                f"data={normalizacao.data_movimento}, valor={normalizacao.valor_bruto}"
            )
            return False
    
        try:
            duplicata = Normalizacao.query.filter(
                Normalizacao.empresa_id == self.empresa_id,
                Normalizacao.nsu == normalizacao.nsu,
                Normalizacao.data_movimento == normalizacao.data_movimento,
                Normalizacao.tipo_movimento == normalizacao.tipo_movimento,
                Normalizacao.arquivo_origem_id != normalizacao.arquivo_origem_id
            ).first()
    
            if duplicata:
                logger.warning(
                    f"⚠️ [NORMALIZACAO] Duplicata encontrada para venda. "
                    f"normalizacao_id={duplicata.id}, nsu={normalizacao.nsu}, "
                    f"data={normalizacao.data_movimento}"
                )
    
            return duplicata is not None
    
        except Exception as e:
            logger.error(
                f"❌ [NORMALIZACAO] Erro ao verificar duplicidade: {str(e)}",
                exc_info=True
            )
            return False
