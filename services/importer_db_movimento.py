# services/importer_db_movimento.py
# ✅ DEBUG PIPELINE: salvar_vendas / salvar_recebimentos / MovBanco

from models import db, MovAdquirente, MovBanco, Adquirente, ContaBancaria
from datetime import datetime, date, timezone
from decimal import Decimal, InvalidOperation
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import func
import logging
import time

logger = logging.getLogger(__name__)

BATCH_SIZE = 200


# ============================================================
# CONVERTERS SEGUROS
# ============================================================

def to_date(valor):
    if not valor:
        return None

    if isinstance(valor, date) and not isinstance(valor, datetime):
        return valor

    if isinstance(valor, datetime):
        return valor.date()

    if isinstance(valor, str):
        valor = valor.strip()

        formatos = [
            "%Y-%m-%d",
            "%d/%m/%Y",
            "%Y-%m-%d %H:%M:%S",
            "%d/%m/%Y %H:%M:%S",
            "%Y%m%d",
        ]

        for fmt in formatos:
            try:
                return datetime.strptime(valor, fmt).date()
            except (ValueError, TypeError):
                continue

    return None


def to_decimal(valor, default=Decimal("0")):
    try:
        if valor is None:
            return default

        if isinstance(valor, Decimal):
            return valor

        return Decimal(str(valor))

    except (InvalidOperation, ValueError, TypeError):
        logger.warning(f"⚠️ [MOVIMENTO] Valor decimal inválido: {valor}")
        return default


def set_if_exists(obj, campo, valor):
    if hasattr(obj, campo):
        setattr(obj, campo, valor)
        logger.debug(f"🧪 [MOVIMENTO] Campo extra setado: {campo}={valor}")
    else:
        logger.debug(f"🧪 [MOVIMENTO] Campo extra ignorado, não existe na model: {campo}")


# ============================================================
# CONTA BANCÁRIA
# ============================================================

def _normalizar_dados_conta(dados_conta):
    logger.info(f"🧪 [MOVIMENTO] _normalizar_dados_conta entrada={dados_conta}")

    if not dados_conta:
        logger.warning("⚠️ [MOVIMENTO] dados_conta vazio ou None")
        return {}

    banco = (
        dados_conta.get("banco")
        or dados_conta.get("bankid")
        or dados_conta.get("bank_id")
        or "OFX"
    )

    agencia = (
        dados_conta.get("agencia")
        or dados_conta.get("branchid")
        or dados_conta.get("branch_id")
        or "0000"
    )

    conta = (
        dados_conta.get("conta")
        or dados_conta.get("acctid")
        or dados_conta.get("account_id")
        or dados_conta.get("numero")
    )

    tipo = (
        dados_conta.get("tipo")
        or dados_conta.get("accttype")
        or "corrente"
    )

    nome = (
        dados_conta.get("nome")
        or f"Conta OFX {banco} {agencia} {conta or ''}".strip()
    )

    normalizado = {
        "banco": str(banco).strip()[:50] if banco else "OFX",
        "agencia": str(agencia).strip()[:20] if agencia else "0000",
        "conta": str(conta).strip()[:50] if conta else None,
        "tipo": str(tipo).strip()[:30] if tipo else "corrente",
        "nome": str(nome).strip()[:120] if nome else "Conta OFX",
    }

    logger.info(f"🧪 [MOVIMENTO] dados_conta_normalizado={normalizado}")
    return normalizado


def obter_ou_criar_conta_bancaria(empresa_id, dados_conta=None):
    logger.info("🏦 [MOVIMENTO] obter_ou_criar_conta_bancaria")
    logger.info(f"🧪 [MOVIMENTO] empresa_id={empresa_id}, dados_conta={dados_conta}")

    dados = _normalizar_dados_conta(dados_conta)

    if dados.get("conta"):
        logger.info(
            f"🔍 [MOVIMENTO] Buscando conta OFX: "
            f"empresa={empresa_id}, banco={dados['banco']}, "
            f"agencia={dados['agencia']}, conta={dados['conta']}"
        )

        conta = ContaBancaria.query.filter_by(
            empresa_id=empresa_id,
            banco=dados["banco"],
            agencia=dados["agencia"],
            conta=dados["conta"],
            ativo=True,
        ).first()

        if conta:
            logger.info(
                f"✅ [MOVIMENTO] Conta OFX localizada: "
                f"id={conta.id}, banco={getattr(conta, 'banco', None)}, "
                f"agencia={getattr(conta, 'agencia', None)}, conta={getattr(conta, 'conta', None)}"
            )
            return conta

        logger.info("➕ [MOVIMENTO] Conta OFX não existe. Criando...")

        conta = ContaBancaria(
            empresa_id=empresa_id,
            nome=dados["nome"],
            banco=dados["banco"],
            agencia=dados["agencia"],
            conta=dados["conta"],
            tipo=dados["tipo"],
            ativo=True,
        )

        db.session.add(conta)
        db.session.flush()

        logger.info(
            f"✅ [MOVIMENTO] Conta OFX criada: "
            f"id={conta.id}, banco={dados['banco']}, agencia={dados['agencia']}, conta={dados['conta']}"
        )

        return conta

    logger.warning("⚠️ [MOVIMENTO] dados_conta sem número de conta. Tentando fallback.")

    conta = ContaBancaria.query.filter_by(
        empresa_id=empresa_id,
        ativo=True,
    ).first()

    if conta:
        logger.warning(
            f"⚠️ [MOVIMENTO] Usando primeira conta ativa: "
            f"id={conta.id}, banco={getattr(conta, 'banco', None)}, "
            f"agencia={getattr(conta, 'agencia', None)}, conta={getattr(conta, 'conta', None)}"
        )
        return conta

    logger.warning("⚠️ [MOVIMENTO] Nenhuma conta ativa. Criando conta técnica OFX.")

    conta = ContaBancaria(
        empresa_id=empresa_id,
        nome="Conta OFX não identificada",
        banco="OFX",
        agencia="0000",
        conta=f"OFX-{empresa_id}",
        tipo="corrente",
        ativo=True,
    )

    db.session.add(conta)
    db.session.flush()

    logger.warning(
        f"⚠️ [MOVIMENTO] Conta técnica criada: id={conta.id}, empresa={empresa_id}"
    )

    return conta


# ============================================================
# SALVAR VENDAS
# ============================================================

def salvar_vendas(registros: list, empresa_id: int, arquivo_id: int = None) -> dict:
    inicio_total = time.time()

    logger.info("💳 [MOVIMENTO] INÍCIO salvar_vendas")
    logger.info(
        f"🧪 [MOVIMENTO] empresa_id={empresa_id}, arquivo_id={arquivo_id}, "
        f"total_registros={len(registros)}"
    )
    logger.info(f"🧪 [MOVIMENTO] primeira_venda={registros[0] if registros else None}")

    stats = {
        "sucesso": 0,
        "falhas": 0,
        "duplicados": 0,
        "total_valor_bruto": Decimal("0"),
        "total_valor_liquido": Decimal("0"),
        "adquirente_criada": False,
        "adquirentes_processadas": set(),
    }

    if not registros:
        logger.warning("⚠️ [MOVIMENTO] salvar_vendas chamado sem registros")
        return stats

    adquirentes_cache = {}
    nomes_adquirentes = set()

    for reg in registros:
        nome = reg.get("adquirente") or reg.get("nome_adquirente") or "Flow"
        nomes_adquirentes.add(nome)

    logger.info(f"🧪 [MOVIMENTO] adquirentes_unicas={nomes_adquirentes}")

    for nome in nomes_adquirentes:
        try:
            adquirente = Adquirente.query.filter(
                func.lower(Adquirente.nome) == nome.lower()
            ).first()

            if not adquirente:
                logger.info(f"➕ [MOVIMENTO] Criando adquirente: {nome}")
                adquirente = Adquirente(
                    nome=nome[:100],
                    codigo=nome[:20].upper().replace(" ", "_"),
                    ativo=True,
                )
                db.session.add(adquirente)
                db.session.commit()
                stats["adquirente_criada"] = True

            adquirentes_cache[nome.lower()] = adquirente
            stats["adquirentes_processadas"].add(nome)

        except Exception as e:
            logger.error(f"❌ [MOVIMENTO] Erro ao resolver adquirente '{nome}': {str(e)}", exc_info=True)
            db.session.rollback()

    batch_size = 20
    total_batches = (len(registros) + batch_size - 1) // batch_size

    for batch_num in range(total_batches):
        inicio = batch_num * batch_size
        fim = min((batch_num + 1) * batch_size, len(registros))
        batch = registros[inicio:fim]

        batch_sucesso = 0
        batch_falhas = 0
        batch_duplicados = 0

        logger.info(f"📦 [MOVIMENTO] Batch vendas {batch_num + 1}/{total_batches}, registros={len(batch)}")

        try:
            for idx, reg in enumerate(batch):
                try:
                    adquirente_nome = (
                        reg.get("adquirente")
                        or reg.get("nome_adquirente")
                        or "Flow"
                    ).lower()

                    adquirente = adquirentes_cache.get(adquirente_nome)

                    if not adquirente:
                        logger.warning(f"⚠️ [MOVIMENTO] Adquirente não encontrada cache: {adquirente_nome}")
                        batch_falhas += 1
                        continue

                    nsu = (
                        reg.get("nsu")
                        or reg.get("id")
                        or f"AUTO-{stats['sucesso'] + batch_sucesso}-{empresa_id}"
                    )

                    data_venda_raw = (
                        reg.get("data_venda")
                        or reg.get("data_transacao")
                        or reg.get("data")
                    )

                    valor_bruto = to_decimal(reg.get("valor_bruto") or reg.get("valor"))
                    valor_liquido = to_decimal(reg.get("valor_liquido"), valor_bruto)
                    taxa_cobrada = to_decimal(reg.get("desconto") or reg.get("taxa_cobrada"))

                    if valor_bruto <= 0:
                        logger.warning(
                            f"⚠️ [MOVIMENTO] Venda ignorada valor_bruto<=0: "
                            f"idx={inicio + idx + 1}, valor={valor_bruto}, reg={reg}"
                        )
                        batch_falhas += 1
                        continue

                    if nsu:
                        duplicata = MovAdquirente.query.filter_by(
                            empresa_id=empresa_id,
                            nsu=nsu,
                            ativo=True,
                        ).first()

                        if duplicata:
                            logger.info(f"🔁 [MOVIMENTO] Venda duplicada nsu={nsu}")
                            batch_duplicados += 1
                            continue

                    data_venda = to_date(data_venda_raw) or date.today()

                    tipo_pagamento = reg.get("tipo_pagamento") or "cartao"

                    if tipo_pagamento not in ["cartao", "pix", "boleto", "outros", "debito", "credito"]:
                        tipo_pagamento = "cartao"

                    mov = MovAdquirente(
                        empresa_id=empresa_id,
                        adquirente_id=adquirente.id,
                        data_venda=data_venda,
                        valor_bruto=valor_bruto,
                        valor_liquido=valor_liquido,
                        taxa_cobrada=taxa_cobrada,
                        arquivo_origem=str(arquivo_id) if arquivo_id else None,
                        bandeira=reg.get("bandeira", "")[:50] if reg.get("bandeira") else None,
                        tipo_pagamento=tipo_pagamento,
                        produto=reg.get("produto", "")[:50] if reg.get("produto") else None,
                        nsu=nsu[:50] if nsu else None,
                        status_conciliacao="pendente",
                        valor_conciliado=Decimal("0"),
                        observacoes=reg.get("observacoes", "")[:2000] if reg.get("observacoes") else None,
                        ativo=True,
                        criado_em=datetime.now(timezone.utc),
                    )

                    db.session.add(mov)
                    batch_sucesso += 1

                except Exception as e:
                    logger.error(
                        f"❌ [MOVIMENTO] Erro ao processar venda {inicio + idx + 1}: {str(e)}",
                        exc_info=True,
                    )
                    batch_falhas += 1
                    continue

            if batch_sucesso > 0:
                db.session.commit()
                logger.info(
                    f"✅ [MOVIMENTO] Commit vendas batch {batch_num + 1}: "
                    f"sucesso={batch_sucesso}, falhas={batch_falhas}, duplicados={batch_duplicados}"
                )
            else:
                db.session.rollback()
                logger.warning(f"⚠️ [MOVIMENTO] Batch vendas sem sucesso. Rollback batch={batch_num + 1}")

            stats["sucesso"] += batch_sucesso
            stats["falhas"] += batch_falhas
            stats["duplicados"] += batch_duplicados

            for reg in batch:
                try:
                    vb = to_decimal(reg.get("valor_bruto") or reg.get("valor"))
                    vl = to_decimal(reg.get("valor_liquido"), vb)

                    if vb > 0:
                        stats["total_valor_bruto"] += vb
                        stats["total_valor_liquido"] += vl
                except Exception:
                    pass

        except Exception as e:
            logger.error(f"❌ [MOVIMENTO] Erro no batch vendas {batch_num + 1}: {str(e)}", exc_info=True)
            db.session.rollback()
            stats["falhas"] += len(batch)
            continue

    if isinstance(stats.get("adquirentes_processadas"), set):
        stats["adquirentes_processadas"] = list(stats["adquirentes_processadas"])

    logger.info(f"🏁 [MOVIMENTO] FIM salvar_vendas tempo={time.time() - inicio_total:.2f}s stats={stats}")
    return stats


# ============================================================
# SALVAR RECEBIMENTOS
# ============================================================

def salvar_recebimentos(registros, empresa_id, arquivo_id, usuario_id=None, dados_conta=None):
    inicio_total = time.time()

    logger.info("🏦 [MOVIMENTO] INÍCIO salvar_recebimentos")
    logger.info(f"🧪 [MOVIMENTO] empresa_id={empresa_id}")
    logger.info(f"🧪 [MOVIMENTO] arquivo_id={arquivo_id}")
    logger.info(f"🧪 [MOVIMENTO] usuario_id={usuario_id}")
    logger.info(f"🧪 [MOVIMENTO] total_registros={len(registros)}")
    logger.info(f"🧪 [MOVIMENTO] dados_conta={dados_conta}")
    logger.info(f"🧪 [MOVIMENTO] primeiro_registro={registros[0] if registros else None}")

    estatisticas = {
        "total": len(registros),
        "sucesso": 0,
        "falhas": 0,
        "invalidos": 0,
        "conta_criada": False,
        "conta_id": None,
    }

    try:
        conta = obter_ou_criar_conta_bancaria(empresa_id, dados_conta)
        conta_id = conta.id
        estatisticas["conta_id"] = conta_id

        logger.info(
            f"🧪 [MOVIMENTO] CONTA USADA: id={conta_id}, "
            f"banco={getattr(conta, 'banco', None)}, "
            f"agencia={getattr(conta, 'agencia', None)}, "
            f"conta={getattr(conta, 'conta', None)}"
        )

    except Exception as e:
        logger.error(f"❌ [MOVIMENTO] Erro fatal ao obter/criar conta bancária: {str(e)}", exc_info=True)
        estatisticas["falhas"] = len(registros)
        return estatisticas

    for i in range(0, len(registros), BATCH_SIZE):
        batch = registros[i:i + BATCH_SIZE]

        logger.info(f"📦 [MOVIMENTO] Batch recebimentos {i // BATCH_SIZE + 1}, registros={len(batch)}")
        logger.info(f"🧪 [MOVIMENTO] Primeiro registro batch={batch[0] if batch else None}")

        try:
            for r_idx, r in enumerate(batch, 1):
                try:
                    valor = to_decimal(r.get("valor"))

                    if valor == 0:
                        logger.warning(f"⚠️ [MOVIMENTO] Recebimento inválido valor=0: {r}")
                        estatisticas["invalidos"] += 1
                        continue

                    data_movimento = to_date(r.get("data") or r.get("data_movimento"))

                    if not data_movimento:
                        logger.warning(f"⚠️ [MOVIMENTO] Recebimento sem data válida: {r}")
                        estatisticas["invalidos"] += 1
                        continue

                    categoria = str(r.get("categoria") or "outros").strip()[:100]
                    tipo_pagamento = str(r.get("tipo_pagamento") or "outros").strip()[:50]

                    if estatisticas["sucesso"] == 0:
                        logger.info(
                            f"🧪 [MOVIMENTO] PRIMEIRO INSERT MOVBANCO: "
                            f"conta_id={conta_id}, data={data_movimento}, valor={valor}, "
                            f"categoria={categoria}, tipo_pagamento={tipo_pagamento}, "
                            f"descricao={str(r.get('descricao') or '')[:150]}"
                        )

                    mov = MovBanco(
                        empresa_id=empresa_id,
                        conta_bancaria_id=conta_id,
                        data_movimento=data_movimento,
                        historico=str(r.get("descricao") or "").strip()[:255],
                        documento=str(r.get("nsu") or r.get("id") or "").strip()[:100],
                        origem=str(r.get("origem") or "OFX").strip()[:50],
                        valor=valor,
                        tipo_pagamento=tipo_pagamento,
                        categoria=categoria,
                        valor_conciliado=Decimal("0"),
                        conciliado=False,
                        arquivo_origem=str(arquivo_id)[:255] if arquivo_id else None,
                    )

                    extras = {
                        "categoria_principal": r.get("categoria_principal"),
                        "subcategoria": r.get("subcategoria"),
                        "score_classificacao": r.get("score_classificacao", 0),
                        "origem_classificacao": r.get("origem_classificacao"),
                        "regra_utilizada": r.get("regra_utilizada"),
                        "classificacao_automatica": r.get("classificacao_automatica", True),
                        "classificacao_manual": r.get("classificacao_manual", False),
                        "palavra_chave": r.get("palavra_chave"),
                    }

                    for campo, valor_extra in extras.items():
                        set_if_exists(mov, campo, valor_extra)

                    db.session.add(mov)
                    estatisticas["sucesso"] += 1

                except Exception as e:
                    logger.error(
                        f"⚠️ [MOVIMENTO] Erro ao preparar recebimento "
                        f"batch_idx={r_idx}, arquivo_id={arquivo_id}: {str(e)}",
                        exc_info=True,
                    )
                    logger.error(f"⚠️ [MOVIMENTO] Registro com erro={r}")
                    estatisticas["falhas"] += 1
                    continue

            db.session.commit()

            logger.info(
                f"🧪 [MOVIMENTO] COMMIT OK BATCH {i // BATCH_SIZE + 1}: "
                f"sucesso={estatisticas['sucesso']}, "
                f"falhas={estatisticas['falhas']}, "
                f"invalidos={estatisticas['invalidos']}"
            )

        except SQLAlchemyError as e:
            db.session.rollback()
            logger.error("❌ [MOVIMENTO] ERRO SQL AO SALVAR MOVBANCO", exc_info=True)
            logger.error(f"❌ [MOVIMENTO] Batch index={i}, arquivo_id={arquivo_id}, empresa_id={empresa_id}")
            logger.error(f"❌ [MOVIMENTO] Conta usada={conta_id}")
            logger.error(f"❌ [MOVIMENTO] Primeiro registro do batch={batch[0] if batch else None}")
            estatisticas["falhas"] += len(batch)

        except Exception as e:
            db.session.rollback()
            logger.error("❌ [MOVIMENTO] ERRO INESPERADO AO SALVAR MOVBANCO", exc_info=True)
            logger.error(f"❌ [MOVIMENTO] Erro={str(e)}")
            logger.error(f"❌ [MOVIMENTO] Batch index={i}, arquivo_id={arquivo_id}, empresa_id={empresa_id}")
            logger.error(f"❌ [MOVIMENTO] Conta usada={conta_id}")
            logger.error(f"❌ [MOVIMENTO] Primeiro registro do batch={batch[0] if batch else None}")
            estatisticas["falhas"] += len(batch)

    logger.info(
        f"🏁 [MOVIMENTO] FIM salvar_recebimentos tempo={time.time() - inicio_total:.2f}s "
        f"stats={estatisticas}"
    )

    return estatisticas
