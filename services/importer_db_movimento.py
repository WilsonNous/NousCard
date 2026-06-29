# services/importer_db_movimento.py
# ✅ VERSÃO FINAL AJUSTADA: Conta bancária extraída do OFX + Classificador Financeiro

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
        return default


def set_if_exists(obj, campo, valor):
    if hasattr(obj, campo):
        setattr(obj, campo, valor)


# ============================================================
# CONTA BANCÁRIA
# ============================================================

def _normalizar_dados_conta(dados_conta):
    """
    Normaliza dados extraídos do OFX.

    Esperado de extrair_dados_conta_ofx():
    {
        banco,
        agencia,
        conta,
        nome,
        tipo
    }
    """

    if not dados_conta:
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

    return {
        "banco": str(banco).strip()[:50] if banco else "OFX",
        "agencia": str(agencia).strip()[:20] if agencia else "0000",
        "conta": str(conta).strip()[:50] if conta else None,
        "tipo": str(tipo).strip()[:30] if tipo else "corrente",
        "nome": str(nome).strip()[:120] if nome else "Conta OFX",
    }


def obter_ou_criar_conta_bancaria(empresa_id, dados_conta=None):
    """
    Busca ou cria conta bancária com base nos dados do OFX.
    Se dados_conta vier vazio, tenta usar primeira conta ativa.
    """

    dados = _normalizar_dados_conta(dados_conta)

    # 1. Se veio conta do OFX, usar ela
    if dados.get("conta"):
        conta = ContaBancaria.query.filter_by(
            empresa_id=empresa_id,
            banco=dados["banco"],
            agencia=dados["agencia"],
            conta=dados["conta"],
            ativo=True,
        ).first()

        if conta:
            logger.info(
                f"🏦 Conta OFX localizada: banco={dados['banco']} "
                f"agencia={dados['agencia']} conta={dados['conta']} id={conta.id}"
            )
            return conta

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
            f"✅ Conta OFX criada: banco={dados['banco']} "
            f"agencia={dados['agencia']} conta={dados['conta']} id={conta.id}"
        )

        return conta

    # 2. Fallback: primeira conta ativa da empresa
    conta = ContaBancaria.query.filter_by(
        empresa_id=empresa_id,
        ativo=True,
    ).first()

    if conta:
        logger.warning(
            f"⚠️ OFX sem conta identificada. Usando conta ativa existente id={conta.id}"
        )
        return conta

    # 3. Último fallback: criar conta técnica
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
        f"⚠️ Conta OFX técnica criada para empresa {empresa_id}: id={conta.id}"
    )

    return conta


# ============================================================
# SALVAR VENDAS
# ============================================================

def salvar_vendas(registros: list, empresa_id: int, arquivo_id: int = None) -> dict:
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

    return stats


# ============================================================
# SALVAR RECEBIMENTOS
# ============================================================

def salvar_recebimentos(registros, empresa_id, arquivo_id, usuario_id=None, dados_conta=None):
    inicio_total = time.time()

    logger.info(
        f"🔍 Início importação recebimentos: empresa={empresa_id}, "
        f"registros={len(registros)}, dados_conta={dados_conta}"
    )

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
    except Exception as e:
        logger.error(f"❌ Erro fatal ao obter/criar conta bancária: {str(e)}", exc_info=True)
        estatisticas["falhas"] = len(registros)
        return estatisticas

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
            logger.error(
                f"❌ Erro SQL no batch recebimentos {i // BATCH_SIZE + 1}: {str(e)}",
                exc_info=True,
            )
            estatisticas["falhas"] += len(batch)

        except Exception as e:
            db.session.rollback()
            logger.error(
                f"❌ Erro inesperado no batch recebimentos {i // BATCH_SIZE + 1}: {str(e)}",
                exc_info=True,
            )
            estatisticas["falhas"] += len(batch)

    tempo_total = time.time() - inicio_total

    logger.info(
        f"✅ Fim importação recebimentos: {estatisticas} em {tempo_total:.2f}s"
    )

    return estatisticas