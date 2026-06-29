# services/importer_db_movimento.py
# ✅ VERSÃO FINAL AJUSTADA: Integrado com Classificador Financeiro + Campos extras MovBanco

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
    """Converte valor para date de forma segura."""
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
    """Converte valor para Decimal de forma segura."""
    try:
        if valor is None:
            return default
        if isinstance(valor, Decimal):
            return valor
        return Decimal(str(valor))
    except (InvalidOperation, ValueError, TypeError):
        return default


def set_if_exists(obj, campo, valor):
    """
    Define atributo somente se a model possuir o campo.
    Evita quebrar se a migration ainda não foi aplicada.
    """
    if hasattr(obj, campo):
        setattr(obj, campo, valor)


# ============================================================
# SALVAR VENDAS (MovAdquirente)
# ============================================================

def salvar_vendas(registros: list, empresa_id: int, arquivo_id: int = None) -> dict:
    """Salva registros de vendas em MovAdquirente."""

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
        return stats

    logger.info(f"💾 Salvando {len(registros)} vendas para empresa {empresa_id}")

    adquirentes_cache = {}
    nomes_adquirentes = set()

    for reg in registros:
        nome = reg.get("adquirente") or reg.get("nome_adquirente") or "Flow"
        nomes_adquirentes.add(nome)

    for nome in nomes_adquirentes:
        try:
            adquirente = Adquirente.query.filter(
                func.lower(Adquirente.nome) == nome.lower()
            ).first()

            if not adquirente:
                adquirente = Adquirente(
                    nome=nome[:100],
                    codigo=nome[:20].upper().replace(" ", "_"),
                    ativo=True,
                )
                db.session.add(adquirente)
                db.session.commit()

                stats["adquirente_criada"] = True
                logger.info(f"✅ Adquirente criada: {nome}")

            adquirentes_cache[nome.lower()] = adquirente
            stats["adquirentes_processadas"].add(nome)

        except Exception as e:
            logger.error(f"❌ Erro ao resolver adquirente '{nome}': {str(e)}", exc_info=True)
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
                        batch_falhas += 1
                        continue

                    if nsu:
                        duplicata = MovAdquirente.query.filter_by(
                            empresa_id=empresa_id,
                            nsu=nsu,
                            ativo=True,
                        ).first()

                        if duplicata:
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
                        f"❌ Erro ao processar venda {inicio + idx + 1}: {str(e)}",
                        exc_info=True,
                    )
                    batch_falhas += 1
                    continue

            if batch_sucesso > 0:
                db.session.commit()
                logger.info(f"✅ Batch vendas {batch_num + 1}/{total_batches}: {batch_sucesso} OK")
            else:
                db.session.rollback()

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
            logger.error(f"❌ Erro no batch vendas {batch_num + 1}: {str(e)}", exc_info=True)
            db.session.rollback()
            stats["falhas"] += len(batch)
            continue

    if isinstance(stats.get("adquirentes_processadas"), set):
        stats["adquirentes_processadas"] = list(stats["adquirentes_processadas"])

    logger.info(
        f"✅ Vendas: {stats['sucesso']} OK, "
        f"{stats['falhas']} falhas, {stats['duplicados']} duplicados"
    )

    return stats


# ============================================================
# SALVAR RECEBIMENTOS (MovBanco)
# ============================================================

def salvar_recebimentos(registros, empresa_id, arquivo_id, usuario_id=None, dados_conta=None):
    """
    Salva registros bancários em mov_banco.
    ✅ Recebe dados já classificados pelo processador_normalizacao.
    ✅ Persiste campos extras se existirem na model.
    """

    inicio_total = time.time()

    logger.info(
        f"🔍 Início importação recebimentos: "
        f"empresa={empresa_id}, registros={len(registros)}"
    )

    estatisticas = {
        "total": len(registros),
        "sucesso": 0,
        "falhas": 0,
        "invalidos": 0,
        "conta_criada": False,
        "conta_id": None,
    }

    # ============================================================
    # 1. GARANTIR CONTA BANCÁRIA
    # ============================================================

    conta_id = None

    if dados_conta and (dados_conta.get("banco") or dados_conta.get("conta")):
        try:
            conta = ContaBancaria.query.filter_by(
                empresa_id=empresa_id,
                banco=dados_conta.get("banco"),
                agencia=dados_conta.get("agencia"),
                conta=dados_conta.get("conta"),
                ativo=True,
            ).first()

            if not conta:
                conta = ContaBancaria(
                    empresa_id=empresa_id,
                    nome=dados_conta.get("nome", "Conta OFX"),
                    banco=dados_conta.get("banco"),
                    agencia=dados_conta.get("agencia"),
                    conta=dados_conta.get("conta"),
                    tipo=dados_conta.get("tipo", "corrente"),
                    ativo=True,
                )

                db.session.add(conta)
                db.session.flush()

                estatisticas["conta_criada"] = True
                logger.info(f"✅ Conta bancária criada: {conta.nome}")

            conta_id = conta.id
            estatisticas["conta_id"] = conta_id

        except Exception as e:
            logger.error(f"❌ Erro ao criar/verificar conta: {str(e)}", exc_info=True)
            db.session.rollback()

    if not conta_id:
        conta_fallback = ContaBancaria.query.filter_by(
            empresa_id=empresa_id,
            ativo=True,
        ).first()

        if conta_fallback:
            conta_id = conta_fallback.id
            estatisticas["conta_id"] = conta_id
        else:
            logger.error(f"❌ Nenhuma conta bancária ativa encontrada para empresa {empresa_id}")

    # ============================================================
    # 2. PROCESSAR EM BATCHES
    # ============================================================

    for i in range(0, len(registros), BATCH_SIZE):
        batch = registros[i:i + BATCH_SIZE]

        try:
            for r in batch:
                try:
                    valor = to_decimal(r.get("valor"))

                    if valor == 0:
                        estatisticas["invalidos"] += 1
                        continue

                    data_movimento = to_date(r.get("data") or r.get("data_movimento"))

                    if not data_movimento:
                        estatisticas["invalidos"] += 1
                        logger.warning(f"⚠️ Movimento sem data válida: {r}")
                        continue

                    categoria = str(r.get("categoria") or "outros").strip()[:100]
                    tipo_pagamento = str(r.get("tipo_pagamento") or "outros").strip()[:50]

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

                    # ====================================================
                    # CAMPOS EXTRAS DO CLASSIFICADOR FINANCEIRO
                    # Só seta se a coluna existir na model.
                    # ====================================================

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
                    logger.error(f"⚠️ Erro ao processar recebimento: {str(e)}", exc_info=True)
                    estatisticas["falhas"] += 1
                    continue

            db.session.commit()

            logger.info(
                f"✅ Batch recebimentos {i // BATCH_SIZE + 1}: "
                f"{len(batch)} registros processados"
            )

        except SQLAlchemyError as e:
            db.session.rollback()
            logger.error(f"❌ Erro SQL no batch recebimentos {i // BATCH_SIZE + 1}: {str(e)}", exc_info=True)
            estatisticas["falhas"] += len(batch)

        except Exception as e:
            db.session.rollback()
            logger.error(f"❌ Erro inesperado no batch recebimentos {i // BATCH_SIZE + 1}: {str(e)}", exc_info=True)
            estatisticas["falhas"] += len(batch)

    tempo_total = time.time() - inicio_total

    logger.info(
        f"✅ Fim importação recebimentos: {estatisticas} "
        f"em {tempo_total:.2f}s"
    )

    return estatisticas