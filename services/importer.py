# services/importer.py
# ✅ VERSÃO FINAL AJUSTADA:
# - Detecta tipo corretamente: OFX = recebimento
# - Passa dados_conta do OFX até processador_normalizacao
# - Evita salvar arquivo como desconhecido quando a extensão já define o tipo
# - Logs mais claros do fluxo

import hashlib
import logging
import time
from io import BytesIO

from utils.parsers import (
    parse_csv_generic,
    parse_excel_generic,
    parse_ofx_generic,
    parse_flow_csv,
    is_flow_csv,
    extrair_dados_conta_ofx,
    dividir_ofx_em_partes,
    dividir_csv_em_partes,
)

from services.importer_db import salvar_arquivo_importado, verificar_arquivo_duplicado
from services.importer_normalizacao import ImportadorNormalizado

logger = logging.getLogger(__name__)

MAX_FILE_SIZE = 10 * 1024 * 1024
MAX_TOTAL_SIZE = 50 * 1024 * 1024
MAX_REGISTROS_POR_ARQUIVO = 10000
MAX_TRANSACOES_POR_LOTE = 50
PAUSA_ENTRE_PARTES = 0.5


# ============================================================
# PROCESSAR UM ARQUIVO
# ============================================================

def process_file(file_storage, default_empresa_id=None):
    inicio_total = time.time()
    nome = file_storage.filename.lower()

    logger.info("🚀 ════════════════════════════════════════════════════════════")
    logger.info(f"🚀 INÍCIO PROCESSAMENTO: {nome}")
    logger.info("🚀 ════════════════════════════════════════════════════════════")

    valido, size = validar_tamanho_arquivo(file_storage)

    if not valido:
        logger.error(f"❌ Arquivo excede {MAX_FILE_SIZE / 1024 / 1024}MB: {nome}")
        return {
            "ok": False,
            "arquivo": nome,
            "erro": f"Arquivo excede {MAX_FILE_SIZE / 1024 / 1024}MB",
        }

    logger.info(f"📏 Tamanho do arquivo: {size / 1024:.2f} KB")

    file_storage.seek(0)
    conteudo = file_storage.read()
    file_storage.seek(0)

    hash_arquivo = hashlib.sha256(conteudo).hexdigest()

    logger.info(f"🔐 Hash do arquivo: {hash_arquivo[:16]}...")

    dados_conta = None
    dividido_automaticamente = False
    total_transacoes_original = None
    num_partes = None
    registros = []
    tipo = "desconhecido"

    try:
        sample = (
            conteudo[:1024].decode("utf-8", errors="ignore")
            if isinstance(conteudo, bytes)
            else conteudo[:1024]
        )

        # ============================================================
        # CSV FLOW
        # ============================================================

        if nome.endswith((".csv", ".txt")) and is_flow_csv(nome, sample):
            logger.info(f"📄 ✅ Detectado CSV Flow: {nome}")

            inicio_parse = time.time()
            file_storage.seek(0)
            registros = parse_flow_csv(
                file_storage,
                nome,
                default_empresa_id=default_empresa_id,
            )
            tempo_parse = time.time() - inicio_parse

            logger.info(
                f"⏱️ Parse Flow CSV concluído: {len(registros)} registros "
                f"em {tempo_parse:.2f}s"
            )

            tipo = "venda"

        # ============================================================
        # CSV/TXT GENÉRICO
        # ============================================================

        elif nome.endswith(".csv") or nome.endswith(".txt"):
            logger.info(f"📄 ✅ Detectado CSV Genérico: {nome}")

            content_text = conteudo.decode("utf-8", errors="replace")
            total_linhas = content_text.count("\n")

            logger.info(f"🔍 CSV com {total_linhas} linhas")

            if total_linhas > MAX_TRANSACOES_POR_LOTE:
                dividido_automaticamente = True
                total_transacoes_original = total_linhas

                logger.info(
                    f"🔧 CSV grande ({total_linhas} linhas). "
                    f"Dividindo em lotes de {MAX_TRANSACOES_POR_LOTE}..."
                )

                inicio_divisao = time.time()
                partes = dividir_csv_em_partes(content_text, MAX_TRANSACOES_POR_LOTE)
                num_partes = len(partes)
                tempo_divisao = time.time() - inicio_divisao

                logger.info(f"✅ CSV dividido em {num_partes} partes em {tempo_divisao:.2f}s")

                todos_registros = []

                for i, parte in enumerate(partes, 1):
                    inicio_parte = time.time()

                    logger.info(f"📄 Processando parte CSV {i}/{num_partes}...")

                    stream = BytesIO(parte.encode("utf-8"))
                    regs = parse_csv_generic(stream, f"{nome}_parte_{i}")

                    todos_registros.extend(regs)

                    tempo_parte = time.time() - inicio_parte

                    logger.info(
                        f"✅ Parte CSV {i}/{num_partes} processada: "
                        f"{len(regs)} registros em {tempo_parte:.2f}s"
                    )

                    if i < num_partes:
                        time.sleep(PAUSA_ENTRE_PARTES)

                registros = todos_registros

            else:
                inicio_parse = time.time()
                file_storage.seek(0)
                registros = parse_csv_generic(file_storage)
                tempo_parse = time.time() - inicio_parse

                logger.info(
                    f"⏱️ Parse CSV concluído: {len(registros)} registros "
                    f"em {tempo_parse:.2f}s"
                )

            tipo = identificar_tipo_por_conteudo(registros, nome)
            logger.info(f"🏷️ Tipo identificado: {tipo}")

        # ============================================================
        # EXCEL
        # ============================================================

        elif nome.endswith(".xlsx") or nome.endswith(".xls"):
            logger.info(f"📊 ✅ Detectado Excel: {nome}")

            inicio_parse = time.time()
            file_storage.seek(0)
            registros = parse_excel_generic(file_storage)
            tempo_parse = time.time() - inicio_parse

            logger.info(
                f"⏱️ Parse Excel concluído: {len(registros)} registros "
                f"em {tempo_parse:.2f}s"
            )

            tipo = identificar_tipo_por_conteudo(registros, nome)
            logger.info(f"🏷️ Tipo identificado: {tipo}")

        # ============================================================
        # OFX
        # ============================================================

        elif nome.endswith(".ofx"):
            logger.info(f"🏦 ✅ Detectado OFX: {nome}")

            content_text = conteudo.decode("utf-8", errors="replace")

            try:
                dados_conta = extrair_dados_conta_ofx(content_text) or {}
                logger.info(f"🏦 Dados da conta extraídos do OFX: {dados_conta}")
            except Exception as e:
                dados_conta = {}
                logger.warning(f"⚠️ Erro ao extrair dados da conta OFX: {str(e)}")

            total_transacoes_original = content_text.upper().count("<STMTTRN>")

            logger.info(
                f"🔍 OFX com {total_transacoes_original} transações "
                f"(limite: {MAX_TRANSACOES_POR_LOTE})"
            )

            if total_transacoes_original > MAX_TRANSACOES_POR_LOTE:
                dividido_automaticamente = True

                logger.info(
                    f"🔧 OFX grande ({total_transacoes_original} transações). "
                    f"Dividindo em lotes de {MAX_TRANSACOES_POR_LOTE}..."
                )

                inicio_divisao = time.time()
                partes = dividir_ofx_em_partes(content_text, MAX_TRANSACOES_POR_LOTE)
                num_partes = len(partes)
                tempo_divisao = time.time() - inicio_divisao

                logger.info(f"✅ OFX dividido em {num_partes} partes em {tempo_divisao:.2f}s")

                todos_registros = []

                for i, parte in enumerate(partes, 1):
                    inicio_parte = time.time()

                    logger.info(f"📄 Processando parte OFX {i}/{num_partes}...")

                    stream = BytesIO(parte.encode("utf-8"))
                    regs = parse_ofx_generic(stream, f"{nome}_parte_{i}")

                    todos_registros.extend(regs)

                    tempo_parte = time.time() - inicio_parte

                    logger.info(
                        f"✅ Parte OFX {i}/{num_partes} processada: "
                        f"{len(regs)} registros em {tempo_parte:.2f}s"
                    )

                    if i < num_partes:
                        time.sleep(PAUSA_ENTRE_PARTES)

                registros = todos_registros

            else:
                logger.info("ℹ️ OFX pequeno, processando normalmente")

                inicio_parse = time.time()
                file_storage.seek(0)
                registros = parse_ofx_generic(file_storage)
                tempo_parse = time.time() - inicio_parse

                logger.info(
                    f"⏱️ Parse OFX concluído: {len(registros)} registros "
                    f"em {tempo_parse:.2f}s"
                )

            tipo = "recebimento"
            logger.info(f"🏷️ Tipo identificado: {tipo}")

        else:
            logger.error(f"❌ Formato não suportado: {nome}")
            return {
                "ok": False,
                "arquivo": nome,
                "erro": "Formato não suportado",
            }

    except Exception as e:
        logger.error(f"❌ Erro ao parsear {nome}: {str(e)}", exc_info=True)
        return {
            "ok": False,
            "arquivo": nome,
            "erro": f"Erro ao processar: {str(e)}",
        }

    for reg in registros:
        if default_empresa_id and ("empresa_id" not in reg or not reg["empresa_id"]):
            reg["empresa_id"] = default_empresa_id

    resultado = {
        "ok": True,
        "arquivo": nome,
        "tipo": tipo,
        "registros": registros,
        "hash": hash_arquivo,
        "linhas": len(registros),
        "dados_conta": dados_conta,
        "dividido_automaticamente": dividido_automaticamente,
        "total_transacoes_original": total_transacoes_original,
        "num_partes": num_partes,
    }

    resultado = corrigir_tipo_arquivo(resultado, nome)

    tempo_total = time.time() - inicio_total

    logger.info("✅ ════════════════════════════════════════════════════════════")
    logger.info(
        f"✅ FIM PROCESSAMENTO: {nome} | "
        f"Registros: {len(registros)} | "
        f"Tipo: {resultado.get('tipo')} | "
        f"Tempo: {tempo_total:.2f}s"
    )
    logger.info("✅ ════════════════════════════════════════════════════════════")

    return resultado


# ============================================================
# PROCESSAR MÚLTIPLOS ARQUIVOS
# ============================================================

def process_uploaded_files(files, empresa_id, usuario_id):
    inicio_total = time.time()

    logger.info("🚀 ╔═══════════════════════════════════════════════════════════╗")
    logger.info("🚀 ║ INÍCIO UPLOAD (NORMALIZADO)                              ║")
    logger.info("🚀 ╚═══════════════════════════════════════════════════════════╝")
    logger.info(f"🚀 Usuário: {usuario_id} | Empresa: {empresa_id} | Arquivos: {len(files)}")

    resultados = []

    for i, file_storage in enumerate(files, 1):
        inicio_arquivo = time.time()
        nome = file_storage.filename.lower()

        logger.info("")
        logger.info(f"📄 [{i}/{len(files)}] ═══════════════════════════════════════════════")
        logger.info(f"📄 [{i}/{len(files)}] Processando: {nome}")
        logger.info(f"📄 [{i}/{len(files)}] ═══════════════════════════════════════════════")

        try:
            logger.info("🔍 [ETAPA 1/5] Parseando arquivo...")

            inicio_parse = time.time()
            resultado = process_file(file_storage, default_empresa_id=empresa_id)
            tempo_parse = time.time() - inicio_parse

            if not resultado.get("ok"):
                logger.error(f"❌ [ETAPA 1/5] Falha no parse: {resultado.get('erro')}")
                resultados.append(resultado)
                continue

            resultado = corrigir_tipo_arquivo(resultado, nome)

            logger.info(
                f"✅ [ETAPA 1/5] Parse concluído em {tempo_parse:.2f}s | "
                f"Registros={resultado.get('linhas')} | "
                f"Tipo={resultado.get('tipo')} | "
                f"DadosConta={resultado.get('dados_conta')}"
            )

            if resultado.get("tipo") in [None, "", "desconhecido"]:
                erro = "Tipo de arquivo não identificado"
                logger.error(f"❌ {erro}: {nome}")
                resultados.append({
                    "ok": False,
                    "arquivo": nome,
                    "erro": erro,
                })
                continue

            logger.info("🔍 [ETAPA 2/5] Verificando duplicata...")

            if verificar_arquivo_duplicado(empresa_id, resultado["hash"]):
                logger.warning("⚠️ [ETAPA 2/5] Arquivo já importado anteriormente")
                resultados.append({
                    "ok": False,
                    "arquivo": nome,
                    "erro": "Arquivo já importado anteriormente",
                })
                continue

            logger.info("✅ [ETAPA 2/5] Arquivo não é duplicado")

            logger.info("💾 [ETAPA 3/5] Salvando arquivo no banco...")

            inicio_save = time.time()

            arquivo_id = salvar_arquivo_importado(
                empresa_id=empresa_id,
                usuario_id=usuario_id,
                nome_arquivo=nome,
                tipo=resultado["tipo"],
                hash_arquivo=resultado["hash"],
                registros=resultado["registros"],
            )

            tempo_save = time.time() - inicio_save

            logger.info(f"✅ [ETAPA 3/5] Arquivo salvo ID={arquivo_id} em {tempo_save:.2f}s")

            logger.info("🔄 [ETAPA 4/5] Normalizando dados...")

            inicio_norm = time.time()

            tipo_origem = _determinar_tipo_origem(resultado, nome)

            logger.info(
                f"🏷️ Normalização: tipo_origem={tipo_origem}, "
                f"tipo_movimento={resultado['tipo']}"
            )

            importador = ImportadorNormalizado(empresa_id, usuario_id)

            stats_normalizacao = importador.importar_arquivo(
                arquivo_id=arquivo_id,
                registros=resultado["registros"],
                tipo_origem=tipo_origem,
                tipo_movimento=resultado["tipo"],
            )

            tempo_norm = time.time() - inicio_norm

            logger.info(
                f"✅ [ETAPA 4/5] Normalização concluída em {tempo_norm:.2f}s | "
                f"Sucesso={stats_normalizacao.get('sucesso', 0)} | "
                f"Falhas={stats_normalizacao.get('falhas', 0)} | "
                f"Duplicados={stats_normalizacao.get('duplicados', 0)}"
            )

            logger.info("🔄 [ETAPA 5/5] Processando para tabelas finais...")

            inicio_final = time.time()

            from services.processador_normalizacao import processar_normalizacoes

            stats_final = processar_normalizacoes(
                empresa_id,
                arquivo_id,
                dados_conta=resultado.get("dados_conta"),
            )

            tempo_final = time.time() - inicio_final

            logger.info(
                f"✅ [ETAPA 5/5] Processamento final concluído em {tempo_final:.2f}s | "
                f"Stats={stats_final}"
            )

            resultado_final = {
                "ok": True,
                "arquivo": nome,
                "tipo": resultado["tipo"],
                "linhas": resultado["linhas"],
                "dados_conta": resultado.get("dados_conta"),
                "stats_normalizacao": stats_normalizacao,
                "stats_final": stats_final,
            }

            resultados.append(resultado_final)

            tempo_arquivo = time.time() - inicio_arquivo

            logger.info("")
            logger.info(f"✅ [{i}/{len(files)}] CONCLUÍDO: {nome}")
            logger.info(f"✅ [{i}/{len(files)}] Tempo total: {tempo_arquivo:.2f}s")
            logger.info("")

        except Exception as e:
            tempo_arquivo = time.time() - inicio_arquivo

            logger.error(
                f"❌ [{i}/{len(files)}] Erro ao importar {nome}: {str(e)}",
                exc_info=True,
            )
            logger.error(f"❌ [{i}/{len(files)}] Tempo até o erro: {tempo_arquivo:.2f}s")

            resultados.append({
                "ok": False,
                "arquivo": nome,
                "erro": f"Erro interno: {str(e)}",
            })

    tempo_total = time.time() - inicio_total

    logger.info("")
    logger.info("🏁 ╔═══════════════════════════════════════════════════════════╗")
    logger.info("🏁 ║ FIM UPLOAD (NORMALIZADO)                                 ║")
    logger.info("🏁 ╚═══════════════════════════════════════════════════════════╝")
    logger.info(f"🏁 Arquivos processados: {len(files)}")
    logger.info(f"🏁 Sucessos: {sum(1 for r in resultados if r.get('ok'))}")
    logger.info(f"🏁 Falhas: {sum(1 for r in resultados if not r.get('ok'))}")
    logger.info(f"🏁 Tempo total: {tempo_total:.2f}s")
    logger.info("🏁 ════════════════════════════════════════════════════════════")

    return resultados


# ============================================================
# TIPO DO ARQUIVO
# ============================================================

def corrigir_tipo_arquivo(resultado, nome_arquivo):
    nome = (nome_arquivo or "").lower()
    tipo = resultado.get("tipo")

    if nome.endswith(".ofx"):
        resultado["tipo"] = "recebimento"
        return resultado

    if any(k in nome for k in [
        "flow",
        "cielo",
        "rede",
        "stone",
        "getnet",
        "pagseguro",
        "maquininha",
        "venda",
        "transacao",
        "transação",
    ]):
        resultado["tipo"] = "venda"
        return resultado

    if any(k in nome for k in [
        "extrato",
        "banco",
        "receb",
        "movimento",
        "conta",
        "credito",
        "crédito",
    ]):
        resultado["tipo"] = "recebimento"
        return resultado

    if tipo in [None, "", "desconhecido"]:
        resultado["tipo"] = identificar_tipo_por_conteudo(
            resultado.get("registros", []),
            nome,
        )

    return resultado


def _determinar_tipo_origem(resultado: dict, nome_arquivo: str) -> str:
    tipo = resultado.get("tipo")
    nome_lower = nome_arquivo.lower()

    if tipo == "venda":
        if "flow" in nome_lower:
            return "csv_flow"
        if "cielo" in nome_lower:
            return "csv_cielo"
        if "rede" in nome_lower:
            return "csv_rede"
        if "stone" in nome_lower:
            return "csv_stone"
        if nome_lower.endswith((".xlsx", ".xls")):
            return "excel_adquirente"
        return "csv_adquirente"

    if tipo == "recebimento":
        if nome_lower.endswith(".ofx"):
            return "ofx_banco"
        if nome_lower.endswith((".xlsx", ".xls")):
            return "excel_banco"
        return "csv_banco"

    return "desconhecido"


def identificar_tipo_por_conteudo(registros, nome_arquivo):
    nome = (nome_arquivo or "").lower()

    if nome.endswith(".ofx"):
        return "recebimento"

    if any(k in nome for k in [
        "flow",
        "venda",
        "transacao",
        "transação",
        "adquirente",
        "cielo",
        "rede",
        "stone",
        "pagseguro",
        "getnet",
        "maquininha",
    ]):
        return "venda"

    if any(k in nome for k in [
        "receb",
        "extrato",
        "banco",
        "credito",
        "crédito",
        "deposito",
        "depósito",
        "movimento",
        "conta",
    ]):
        return "recebimento"

    amostra = registros[:10] if registros else []

    campos_venda = {
        "nsu",
        "autorizacao",
        "bandeira",
        "parcelas",
        "valor_bruto",
        "valor_liquido",
        "adquirente",
    }

    campos_banco = {
        "historico",
        "descricao",
        "memo",
        "valor",
        "data_movimento",
        "fitid",
        "tipo_pagamento",
    }

    score_venda = 0
    score_banco = 0

    for reg in amostra:
        if not isinstance(reg, dict):
            continue

        chaves = set(reg.keys())

        score_venda += len(chaves.intersection(campos_venda))
        score_banco += len(chaves.intersection(campos_banco))

    if score_venda > score_banco:
        return "venda"

    if score_banco > 0:
        return "recebimento"

    return "desconhecido"


# ============================================================
# UTILITÁRIOS
# ============================================================

def validar_tamanho_arquivo(file_storage):
    file_storage.seek(0, 2)
    size = file_storage.tell()
    file_storage.seek(0)
    return size <= MAX_FILE_SIZE, size


def listar_importados(empresa_id: int):
    from services.importer_db import listar_arquivos_importados
    return listar_arquivos_importados(empresa_id)
