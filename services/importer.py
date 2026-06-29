# services/importer.py
# ✅ DEBUG PIPELINE: Importação → Normalização → MovBanco

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


def process_file(file_storage, default_empresa_id=None):
    inicio_total = time.time()
    nome = file_storage.filename.lower()

    logger.info("🚀 [IMPORTER] INÍCIO PROCESSAMENTO")
    logger.info(f"🧪 [IMPORTER] arquivo={nome}, empresa_default={default_empresa_id}")

    valido, size = validar_tamanho_arquivo(file_storage)
    if not valido:
        logger.error(f"❌ [IMPORTER] Arquivo excede limite: {nome}, size={size}")
        return {"ok": False, "arquivo": nome, "erro": "Arquivo excede limite"}

    file_storage.seek(0)
    conteudo = file_storage.read()
    file_storage.seek(0)

    hash_arquivo = hashlib.sha256(conteudo).hexdigest()

    logger.info(f"🧪 [IMPORTER] size_kb={size / 1024:.2f}, hash={hash_arquivo}")

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

        if nome.endswith((".csv", ".txt")) and is_flow_csv(nome, sample):
            logger.info("📄 [IMPORTER] Detectado CSV Flow")
            file_storage.seek(0)
            registros = parse_flow_csv(file_storage, nome, default_empresa_id=default_empresa_id)
            tipo = "venda"

        elif nome.endswith(".csv") or nome.endswith(".txt"):
            logger.info("📄 [IMPORTER] Detectado CSV/TXT genérico")
            content_text = conteudo.decode("utf-8", errors="replace")
            total_linhas = content_text.count("\n")
            logger.info(f"🧪 [IMPORTER] total_linhas_csv={total_linhas}")

            if total_linhas > MAX_TRANSACOES_POR_LOTE:
                dividido_automaticamente = True
                total_transacoes_original = total_linhas
                partes = dividir_csv_em_partes(content_text, MAX_TRANSACOES_POR_LOTE)
                num_partes = len(partes)
                todos_registros = []

                for i, parte in enumerate(partes, 1):
                    logger.info(f"📄 [IMPORTER] CSV parte {i}/{num_partes}")
                    stream = BytesIO(parte.encode("utf-8"))
                    regs = parse_csv_generic(stream, f"{nome}_parte_{i}")
                    logger.info(f"🧪 [IMPORTER] CSV parte {i} registros={len(regs)}")
                    todos_registros.extend(regs)
                    if i < num_partes:
                        time.sleep(PAUSA_ENTRE_PARTES)

                registros = todos_registros
            else:
                file_storage.seek(0)
                registros = parse_csv_generic(file_storage)

            tipo = identificar_tipo_por_conteudo(registros, nome)

        elif nome.endswith(".xlsx") or nome.endswith(".xls"):
            logger.info("📊 [IMPORTER] Detectado Excel")
            file_storage.seek(0)
            registros = parse_excel_generic(file_storage)
            tipo = identificar_tipo_por_conteudo(registros, nome)

        elif nome.endswith(".ofx"):
            logger.info("🏦 [IMPORTER] Detectado OFX")
            content_text = conteudo.decode("utf-8", errors="replace")

            try:
                dados_conta = extrair_dados_conta_ofx(content_text) or {}
                logger.info(f"🧪 [IMPORTER] dados_conta_extraidos={dados_conta}")
            except Exception as e:
                dados_conta = {}
                logger.error(f"❌ [IMPORTER] erro_extraindo_dados_conta={str(e)}", exc_info=True)

            total_transacoes_original = content_text.upper().count("<STMTTRN>")
            logger.info(f"🧪 [IMPORTER] total_transacoes_ofx={total_transacoes_original}")

            if total_transacoes_original > MAX_TRANSACOES_POR_LOTE:
                dividido_automaticamente = True
                partes = dividir_ofx_em_partes(content_text, MAX_TRANSACOES_POR_LOTE)
                num_partes = len(partes)
                todos_registros = []

                for i, parte in enumerate(partes, 1):
                    logger.info(f"📄 [IMPORTER] OFX parte {i}/{num_partes}")
                    stream = BytesIO(parte.encode("utf-8"))
                    regs = parse_ofx_generic(stream, f"{nome}_parte_{i}")
                    logger.info(f"🧪 [IMPORTER] OFX parte {i} registros={len(regs)}")
                    todos_registros.extend(regs)
                    if i < num_partes:
                        time.sleep(PAUSA_ENTRE_PARTES)

                registros = todos_registros
            else:
                file_storage.seek(0)
                registros = parse_ofx_generic(file_storage)

            tipo = "recebimento"

        else:
            logger.error(f"❌ [IMPORTER] Formato não suportado: {nome}")
            return {"ok": False, "arquivo": nome, "erro": "Formato não suportado"}

    except Exception as e:
        logger.error(f"❌ [IMPORTER] Erro ao parsear {nome}: {str(e)}", exc_info=True)
        return {"ok": False, "arquivo": nome, "erro": f"Erro ao processar: {str(e)}"}

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

    logger.info("🧪 [IMPORTER RESULTADO]")
    logger.info(f"🧪 arquivo={nome}")
    logger.info(f"🧪 ok={resultado.get('ok')}")
    logger.info(f"🧪 tipo={resultado.get('tipo')}")
    logger.info(f"🧪 linhas={resultado.get('linhas')}")
    logger.info(f"🧪 dados_conta={resultado.get('dados_conta')}")
    logger.info(f"🧪 hash={resultado.get('hash')}")
    logger.info(
        f"🧪 primeiro_registro={resultado.get('registros', [None])[0] if resultado.get('registros') else None}"
    )

    logger.info(f"✅ [IMPORTER] FIM PROCESSAMENTO tempo={time.time() - inicio_total:.2f}s")
    return resultado


def process_uploaded_files(files, empresa_id, usuario_id):
    inicio_total = time.time()
    resultados = []

    logger.info("🚀 [UPLOAD] INÍCIO UPLOAD NORMALIZADO")
    logger.info(f"🧪 [UPLOAD] usuario_id={usuario_id}, empresa_id={empresa_id}, arquivos={len(files)}")

    for i, file_storage in enumerate(files, 1):
        inicio_arquivo = time.time()
        nome = file_storage.filename.lower()

        logger.info(f"📄 [UPLOAD] ARQUIVO {i}/{len(files)}: {nome}")

        try:
            resultado = process_file(file_storage, default_empresa_id=empresa_id)

            logger.info("🧪 [UPLOAD] RESULTADO PROCESS_FILE")
            logger.info(f"🧪 arquivo={nome}")
            logger.info(f"🧪 resultado={resultado}")

            if not resultado.get("ok"):
                logger.error(f"❌ [UPLOAD] Falha no parse: {resultado.get('erro')}")
                resultados.append(resultado)
                continue

            resultado = corrigir_tipo_arquivo(resultado, nome)

            if resultado.get("tipo") in [None, "", "desconhecido"]:
                logger.error(f"❌ [UPLOAD] Tipo não identificado: {nome}")
                resultados.append({
                    "ok": False,
                    "arquivo": nome,
                    "erro": "Tipo de arquivo não identificado",
                })
                continue

            logger.info("🔍 [UPLOAD] Verificando duplicidade")
            if verificar_arquivo_duplicado(empresa_id, resultado["hash"]):
                logger.warning(f"⚠️ [UPLOAD] Arquivo duplicado: {nome}, hash={resultado['hash']}")
                resultados.append({
                    "ok": False,
                    "arquivo": nome,
                    "erro": "Arquivo já importado anteriormente",
                })
                continue

            logger.info("💾 [UPLOAD] Salvando arquivo_importado")
            arquivo_id = salvar_arquivo_importado(
                empresa_id=empresa_id,
                usuario_id=usuario_id,
                nome_arquivo=nome,
                tipo=resultado["tipo"],
                hash_arquivo=resultado["hash"],
                registros=resultado["registros"],
            )

            logger.info(f"🧪 [UPLOAD] ARQUIVO SALVO: arquivo_id={arquivo_id}, tipo={resultado.get('tipo')}")

            tipo_origem = _determinar_tipo_origem(resultado, nome)

            logger.info("🔄 [UPLOAD] Normalizando")
            logger.info(f"🧪 arquivo_id={arquivo_id}, tipo_origem={tipo_origem}, tipo_movimento={resultado['tipo']}")

            importador = ImportadorNormalizado(empresa_id, usuario_id)

            stats_normalizacao = importador.importar_arquivo(
                arquivo_id=arquivo_id,
                registros=resultado["registros"],
                tipo_origem=tipo_origem,
                tipo_movimento=resultado["tipo"],
            )

            logger.info(f"🧪 [UPLOAD] STATS NORMALIZACAO: {stats_normalizacao}")

            logger.info("🔄 [UPLOAD] Processando para tabelas finais")
            from services.processador_normalizacao import processar_normalizacoes

            stats_final = processar_normalizacoes(
                empresa_id,
                arquivo_id,
                dados_conta=resultado.get("dados_conta"),
            )

            logger.info(f"🧪 [UPLOAD] STATS FINAL COMPLETO: {stats_final}")

            resultados.append({
                "ok": True,
                "arquivo": nome,
                "tipo": resultado["tipo"],
                "linhas": resultado["linhas"],
                "dados_conta": resultado.get("dados_conta"),
                "stats_normalizacao": stats_normalizacao,
                "stats_final": stats_final,
            })

            logger.info(f"✅ [UPLOAD] ARQUIVO CONCLUÍDO: {nome}, tempo={time.time() - inicio_arquivo:.2f}s")

        except Exception as e:
            logger.error(f"❌ [UPLOAD] Erro inesperado em {nome}: {str(e)}", exc_info=True)
            resultados.append({
                "ok": False,
                "arquivo": nome,
                "erro": f"Erro interno: {str(e)}",
            })

    logger.info(f"🏁 [UPLOAD] FIM tempo_total={time.time() - inicio_total:.2f}s resultados={resultados}")
    return resultados


def corrigir_tipo_arquivo(resultado, nome_arquivo):
    nome = (nome_arquivo or "").lower()
    tipo = resultado.get("tipo")

    if nome.endswith(".ofx"):
        resultado["tipo"] = "recebimento"
        return resultado

    if any(k in nome for k in [
        "flow", "cielo", "rede", "stone", "getnet", "pagseguro",
        "maquininha", "venda", "transacao", "transação",
    ]):
        resultado["tipo"] = "venda"
        return resultado

    if any(k in nome for k in [
        "extrato", "banco", "receb", "movimento", "conta",
        "credito", "crédito",
    ]):
        resultado["tipo"] = "recebimento"
        return resultado

    if tipo in [None, "", "desconhecido"]:
        resultado["tipo"] = identificar_tipo_por_conteudo(resultado.get("registros", []), nome)

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
        "flow", "venda", "transacao", "transação", "adquirente",
        "cielo", "rede", "stone", "pagseguro", "getnet", "maquininha",
    ]):
        return "venda"

    if any(k in nome for k in [
        "receb", "extrato", "banco", "credito", "crédito",
        "deposito", "depósito", "movimento", "conta",
    ]):
        return "recebimento"

    amostra = registros[:10] if registros else []
    campos_venda = {"nsu", "autorizacao", "bandeira", "parcelas", "valor_bruto", "valor_liquido", "adquirente"}
    campos_banco = {"historico", "descricao", "memo", "valor", "data_movimento", "fitid", "tipo_pagamento"}

    score_venda = 0
    score_banco = 0

    for reg in amostra:
        if not isinstance(reg, dict):
            continue
        chaves = set(reg.keys())
        score_venda += len(chaves.intersection(campos_venda))
        score_banco += len(chaves.intersection(campos_banco))

    logger.info(f"🧪 [TIPO CONTEUDO] arquivo={nome}, score_venda={score_venda}, score_banco={score_banco}")

    if score_venda > score_banco:
        return "venda"
    if score_banco > 0:
        return "recebimento"
    return "desconhecido"


def validar_tamanho_arquivo(file_storage):
    file_storage.seek(0, 2)
    size = file_storage.tell()
    file_storage.seek(0)
    return size <= MAX_FILE_SIZE, size


def listar_importados(empresa_id: int):
    from services.importer_db import listar_arquivos_importados
    return listar_arquivos_importados(empresa_id)
