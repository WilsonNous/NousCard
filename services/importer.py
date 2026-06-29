# services/importer.py - VERSÃO FINAL COM PROCESSAMENTO SEQUENCIAL E LOGS DETALHADOS

import os
import hashlib
import logging
import time
from io import BytesIO
from decimal import Decimal
from sqlalchemy.exc import SQLAlchemyError

from utils.parsers import (
    parse_csv_generic,
    parse_excel_generic,
    parse_ofx_generic,
    parse_flow_csv,
    is_flow_csv,
    extrair_dados_conta_ofx,
    dividir_ofx_em_partes,
    dividir_csv_em_partes
)
from utils.helpers import gerar_hash_arquivo
from services.importer_db import salvar_arquivo_importado, verificar_arquivo_duplicado
from services.importer_db_movimento import salvar_vendas, salvar_recebimentos
from models import db
from services.importer_normalizacao import ImportadorNormalizado

logger = logging.getLogger(__name__)

# ============================================================
# CONFIGURAÇÕES
# ============================================================
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
MAX_TOTAL_SIZE = 50 * 1024 * 1024  # 50MB
MAX_REGISTROS_POR_ARQUIVO = 10000
MAX_TRANSACOES_POR_LOTE = 50  # ✅ Reduzido para 50 (mais seguro)
PAUSA_ENTRE_PARTES = 0.5  # ✅ Pausa de 0.5s entre partes (respiro para o Gunicorn)

# ============================================================
# 📦 PROCESSAR UM ARQUIVO (COM PROCESSAMENTO SEQUENCIAL)
# ============================================================
def process_file(file_storage, default_empresa_id=None):
    """
    Processa um arquivo com divisão automática e processamento sequencial com pausas.
    Totalmente transparente para o cliente.
    """
    inicio_total = time.time()
    nome = file_storage.filename.lower()
    logger.info(f"🚀 ════════════════════════════════════════════════════════════")
    logger.info(f"🚀 INÍCIO PROCESSAMENTO: {nome}")
    logger.info(f"🚀 ════════════════════════════════════════════════════════════")
    
    valido, size = validar_tamanho_arquivo(file_storage)
    if not valido:
        logger.error(f"❌ Arquivo excede {MAX_FILE_SIZE/1024/1024}MB: {nome}")
        return {"ok": False, "arquivo": nome, "erro": f"Arquivo excede {MAX_FILE_SIZE/1024/1024}MB"}
    
    logger.info(f"📏 Tamanho do arquivo: {size/1024:.2f} KB")
    
    file_storage.seek(0)
    conteudo = file_storage.read()
    file_storage.seek(0)
    hash_arquivo = hashlib.sha256(conteudo).hexdigest()
    logger.info(f"🔐 Hash do arquivo: {hash_arquivo[:16]}...")
    
    dados_conta = None
    dividido_automaticamente = False
    total_transacoes_original = None
    num_partes = None
    
    try:
        sample = conteudo[:1024].decode('utf-8', errors='ignore') if isinstance(conteudo, bytes) else conteudo[:1024]
        
        # ============================================================
        # CSV FLOW (relatório de vendas)
        # ============================================================
        if nome.endswith(('.csv', '.txt')) and is_flow_csv(nome, sample):
            logger.info(f"📄 ✅ Detectado CSV Flow: {nome}")
            inicio_parse = time.time()
            file_storage.seek(0)
            registros = parse_flow_csv(file_storage, nome, default_empresa_id=default_empresa_id)
            tempo_parse = time.time() - inicio_parse
            logger.info(f"⏱️ Parse Flow CSV concluído: {len(registros)} registros em {tempo_parse:.2f}s")
            tipo = "venda"
            
        # ============================================================
        # CSV GENÉRICO (pode ser grande)
        # ============================================================
        elif nome.endswith(".csv") or nome.endswith(".txt"):
            logger.info(f"📄 ✅ Detectado CSV Genérico: {nome}")
            
            # ✅ Verificar tamanho do CSV
            content_text = conteudo.decode('utf-8', errors='replace')
            total_linhas = content_text.count('\n')
            logger.info(f"🔍 CSV com {total_linhas} linhas")
            
            if total_linhas > MAX_TRANSACOES_POR_LOTE:
                dividido_automaticamente = True
                total_transacoes_original = total_linhas
                logger.info(f"🔧 CSV grande ({total_linhas} linhas). Dividindo em lotes de {MAX_TRANSACOES_POR_LOTE}...")
                
                # Dividir CSV em partes
                inicio_divisao = time.time()
                partes = dividir_csv_em_partes(content_text, MAX_TRANSACOES_POR_LOTE)
                num_partes = len(partes)
                tempo_divisao = time.time() - inicio_divisao
                logger.info(f"✅ CSV dividido em {num_partes} partes em {tempo_divisao:.2f}s")
                
                # ✅ Processar cada parte SEQUENCIALMENTE com pausas
                todos_registros = []
                for i, parte in enumerate(partes, 1):
                    inicio_parte = time.time()
                    logger.info(f"📄 Processando parte CSV {i}/{num_partes}...")
                    
                    stream = BytesIO(parte.encode('utf-8'))
                    regs = parse_csv_generic(stream, f"{nome}_parte_{i}")
                    todos_registros.extend(regs)
                    
                    tempo_parte = time.time() - inicio_parte
                    logger.info(f"✅ Parte CSV {i}/{num_partes} processada: {len(regs)} registros em {tempo_parte:.2f}s")
                    
                    # ✅ PAUSA entre partes (respiro para o Gunicorn)
                    if i < num_partes:  # Não pausa na última parte
                        logger.info(f"⏸️ Pausa de {PAUSA_ENTRE_PARTES}s antes da próxima parte...")
                        time.sleep(PAUSA_ENTRE_PARTES)
                
                registros = todos_registros
                logger.info(f"✅ Total consolidado: {len(registros)} registros de {num_partes} partes")
            else:
                inicio_parse = time.time()
                file_storage.seek(0)
                registros = parse_csv_generic(file_storage)
                tempo_parse = time.time() - inicio_parse
                logger.info(f"⏱️ Parse CSV concluído: {len(registros)} registros em {tempo_parse:.2f}s")
            
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
            logger.info(f"⏱️ Parse Excel concluído: {len(registros)} registros em {tempo_parse:.2f}s")
            tipo = identificar_tipo_por_conteudo(registros, nome)
            logger.info(f"🏷️ Tipo identificado: {tipo}")
            
        # ============================================================
        # OFX (extrato bancário - pode ser grande)
        # ============================================================
        elif nome.endswith(".ofx"):
            logger.info(f"🏦 ✅ Detectado OFX: {nome}")
            
            # 1. Extrair dados da conta
            try:
                content_text = conteudo.decode('utf-8', errors='replace')
                dados_conta = extrair_dados_conta_ofx(content_text)
                logger.info(f"🏦 Dados da conta extraídos: {dados_conta.get('nome')}")
            except Exception as e:
                logger.warning(f"⚠️ Erro ao extrair dados da conta: {str(e)}")
            
            # 2. Verificar se precisa dividir
            content_text = conteudo.decode('utf-8', errors='replace')
            total_transacoes_original = content_text.upper().count('<STMTTRN>')
            
            logger.info(f"🔍 OFX com {total_transacoes_original} transações (limite: {MAX_TRANSACOES_POR_LOTE})")
            
            if total_transacoes_original > MAX_TRANSACOES_POR_LOTE:
                dividido_automaticamente = True
                logger.info(f"🔧 OFX grande ({total_transacoes_original} transações). Dividindo em lotes de {MAX_TRANSACOES_POR_LOTE}...")
                
                inicio_divisao = time.time()
                partes = dividir_ofx_em_partes(content_text, MAX_TRANSACOES_POR_LOTE)
                num_partes = len(partes)
                tempo_divisao = time.time() - inicio_divisao
                
                logger.info(f"✅ OFX dividido em {num_partes} partes em {tempo_divisao:.2f}s")
                
                # ✅ Processar cada parte SEQUENCIALMENTE com pausas
                todos_registros = []
                for i, parte in enumerate(partes, 1):
                    inicio_parte = time.time()
                    logger.info(f"📄 Processando parte OFX {i}/{num_partes}...")
                    
                    stream = BytesIO(parte.encode('utf-8'))
                    regs = parse_ofx_generic(stream, f"{nome}_parte_{i}")
                    todos_registros.extend(regs)
                    
                    tempo_parte = time.time() - inicio_parte
                    logger.info(f"✅ Parte OFX {i}/{num_partes} processada: {len(regs)} registros em {tempo_parte:.2f}s")
                    
                    # ✅ PAUSA entre partes (respiro para o Gunicorn)
                    if i < num_partes:  # Não pausa na última parte
                        logger.info(f"⏸️ Pausa de {PAUSA_ENTRE_PARTES}s antes da próxima parte...")
                        time.sleep(PAUSA_ENTRE_PARTES)
                
                registros = todos_registros
                logger.info(f"✅ Total consolidado: {len(registros)} registros de {num_partes} partes")
            else:
                logger.info(f"ℹ️ OFX pequeno ({total_transacoes_original} transações), processando normalmente")
                inicio_parse = time.time()
                file_storage.seek(0)
                registros = parse_ofx_generic(file_storage)
                tempo_parse = time.time() - inicio_parse
                logger.info(f"⏱️ Parse OFX concluído: {len(registros)} registros em {tempo_parse:.2f}s")
            
            tipo = "recebimento"
            logger.info(f"🏷️ Tipo identificado: {tipo}")
            
        else:
            logger.error(f"❌ Formato não suportado: {nome}")
            return {"ok": False, "arquivo": nome, "erro": "Formato não suportado"}
        
    except Exception as e:
        logger.error(f"❌ Erro ao parsear {nome}: {str(e)}", exc_info=True)
        return {"ok": False, "arquivo": nome, "erro": f"Erro ao processar: {str(e)}"}
    
    # Inferir tipo e categoria
    for reg in registros:
        if default_empresa_id and ('empresa_id' not in reg or not reg['empresa_id']):
            reg['empresa_id'] = default_empresa_id
    
    tempo_total = time.time() - inicio_total
    logger.info(f"✅ ════════════════════════════════════════════════════════════")
    logger.info(f"✅ FIM PROCESSAMENTO: {nome}")
    logger.info(f"✅ Registros: {len(registros)} | Tipo: {tipo} | Tempo: {tempo_total:.2f}s")
    logger.info(f"✅ ════════════════════════════════════════════════════════════")
    
    return {
        "ok": True,
        "arquivo": nome,
        "tipo": tipo,
        "registros": registros,
        "hash": hash_arquivo,
        "linhas": len(registros),
        "dados_conta": dados_conta,
        "dividido_automaticamente": dividido_automaticamente,
        "total_transacoes_original": total_transacoes_original,
        "num_partes": num_partes
    }


# ============================================================
# 📦 PROCESSAR MÚLTIPLOS ARQUIVOS (COM ARQUITETURA DE NORMALIZAÇÃO)
# ============================================================
def process_uploaded_files(files, empresa_id, usuario_id):
    """
    Processa arquivos usando a nova arquitetura de normalização.
    Fluxo: Parse → Normalização → Processamento Final
    """
    inicio_total = time.time()
    logger.info(f"🚀 ╔═══════════════════════════════════════════════════════════╗")
    logger.info(f"🚀 ║ INÍCIO UPLOAD (NORMALIZADO)                              ║")
    logger.info(f"🚀 ╚═══════════════════════════════════════════════════════════╝")
    logger.info(f"🚀 Usuário: {usuario_id} | Empresa: {empresa_id} | Arquivos: {len(files)}")
    
    resultados = []
    
    for i, file_storage in enumerate(files, 1):
        inicio_arquivo = time.time()
        nome = file_storage.filename.lower()
        logger.info(f"")
        logger.info(f"📄 [{i}/{len(files)}] ═══════════════════════════════════════════════")
        logger.info(f"📄 [{i}/{len(files)}] Processando: {nome}")
        logger.info(f"📄 [{i}/{len(files)}] ═══════════════════════════════════════════════")
        
        try:
            # ============================================================
            # ETAPA 1: PARSEAR ARQUIVO
            # ============================================================
            logger.info(f"🔍 [ETAPA 1/4] Parseando arquivo...")
            inicio_parse = time.time()
            resultado = process_file(file_storage, default_empresa_id=empresa_id)
            tempo_parse = time.time() - inicio_parse
            
            if not resultado["ok"]:
                logger.error(f"❌ [ETAPA 1/4] Falha no parse: {resultado.get('erro')}")
                resultados.append(resultado)
                continue
            
            logger.info(f"✅ [ETAPA 1/4] Parse concluído em {tempo_parse:.2f}s")
            logger.info(f"   📊 Registros: {resultado['linhas']} | Tipo: {resultado['tipo']}")
            
            # ============================================================
            # ETAPA 2: VERIFICAR DUPLICATA
            # ============================================================
            logger.info(f"🔍 [ETAPA 2/4] Verificando duplicata...")
            if verificar_arquivo_duplicado(empresa_id, resultado["hash"]):
                logger.warning(f"⚠️ [ETAPA 2/4] Arquivo já importado anteriormente")
                resultados.append({"ok": False, "arquivo": nome, "erro": "Arquivo já importado anteriormente"})
                continue
            
            logger.info(f"✅ [ETAPA 2/4] Arquivo não é duplicado")
            
            # ============================================================
            # ETAPA 3: SALVAR ARQUIVO NO BANCO
            # ============================================================
            logger.info(f"💾 [ETAPA 3/4] Salvando arquivo no banco...")
            inicio_save = time.time()
            arquivo_id = salvar_arquivo_importado(
                empresa_id=empresa_id,
                usuario_id=usuario_id,
                nome_arquivo=nome,
                tipo=resultado["tipo"],
                hash_arquivo=resultado["hash"],
                registros=resultado["registros"]
            )
            tempo_save = time.time() - inicio_save
            logger.info(f"✅ [ETAPA 3/4] Arquivo salvo (ID: {arquivo_id}) em {tempo_save:.2f}s")
            
            # ============================================================
            # ETAPA 4: NORMALIZAR DADOS
            # ============================================================
            logger.info(f"🔄 [ETAPA 4/5] Normalizando dados...")
            inicio_norm = time.time()
            
            tipo_origem = _determinar_tipo_origem(resultado, nome)
            logger.info(f"   🏷️ Tipo origem: {tipo_origem} | Tipo movimento: {resultado['tipo']}")
            
            importador = ImportadorNormalizado(empresa_id, usuario_id)
            stats_normalizacao = importador.importar_arquivo(
                arquivo_id=arquivo_id,
                registros=resultado["registros"],
                tipo_origem=tipo_origem,
                tipo_movimento=resultado["tipo"]
            )
            
            tempo_norm = time.time() - inicio_norm
            logger.info(f"✅ [ETAPA 4/5] Normalização concluída em {tempo_norm:.2f}s")
            logger.info(f"   📊 Sucesso: {stats_normalizacao.get('sucesso', 0)}")
            logger.info(f"   📊 Falhas: {stats_normalizacao.get('falhas', 0)}")
            logger.info(f"   📊 Duplicados: {stats_normalizacao.get('duplicados', 0)}")
            
            # ============================================================
            # ETAPA 5: PROCESSAR PARA TABELAS FINAIS
            # ============================================================
            logger.info(f"🔄 [ETAPA 5/5] Processando para tabelas finais...")
            inicio_final = time.time()
            
            from services.processador_normalizacao import processar_normalizacoes
            stats_final = processar_normalizacoes(
                empresa_id,
                arquivo_id,
                dados_conta=resultado.get("dados_conta")
            )
            
            tempo_final = time.time() - inicio_final
            logger.info(f"✅ [ETAPA 5/5] Processamento final concluído em {tempo_final:.2f}s")
            
            # Log detalhado das estatísticas finais
            if stats_final:
                vendas = stats_final.get('vendas', {})
                recebimentos = stats_final.get('recebimentos', {})
                
                if vendas:
                    logger.info(f"   💳 Vendas: {vendas.get('sucesso', 0)} sucesso, {vendas.get('falhas', 0)} falhas")
                    if vendas.get('total_valor_bruto'):
                        logger.info(f"   💰 Valor bruto: R$ {vendas.get('total_valor_bruto', 0):.2f}")
                    if vendas.get('total_valor_liquido'):
                        logger.info(f"   💰 Valor líquido: R$ {vendas.get('total_valor_liquido', 0):.2f}")
                
                if recebimentos:
                    logger.info(f"   🏦 Recebimentos: {recebimentos.get('sucesso', 0)} sucesso, {recebimentos.get('falhas', 0)} falhas")
            
            # ============================================================
            # RESULTADO FINAL
            # ============================================================
            tempo_arquivo = time.time() - inicio_arquivo
            
            resultado_final = {
                "ok": True,
                "arquivo": nome,
                "tipo": resultado["tipo"],
                "linhas": resultado["linhas"],
                "stats_normalizacao": stats_normalizacao,
                "stats_final": stats_final
            }
            
            resultados.append(resultado_final)
            
            logger.info(f"")
            logger.info(f"✅ [{i}/{len(files)}] ═══════════════════════════════════════════════")
            logger.info(f"✅ [{i}/{len(files)}] CONCLUÍDO: {nome}")
            logger.info(f"✅ [{i}/{len(files)}] Tempo total: {tempo_arquivo:.2f}s")
            logger.info(f"✅ [{i}/{len(files)}] ═══════════════════════════════════════════════")
            logger.info(f"")
            
        except Exception as e:
            tempo_arquivo = time.time() - inicio_arquivo
            logger.error(f"❌ [{i}/{len(files)}] Erro ao importar {nome}: {str(e)}", exc_info=True)
            logger.error(f"❌ [{i}/{len(files)}] Tempo até o erro: {tempo_arquivo:.2f}s")
            resultados.append({"ok": False, "arquivo": nome, "erro": f"Erro interno: {str(e)}"})
    
    tempo_total = time.time() - inicio_total
    
    logger.info(f"")
    logger.info(f"🏁 ╔═══════════════════════════════════════════════════════════╗")
    logger.info(f"🏁 ║ FIM UPLOAD (NORMALIZADO)                                 ║")
    logger.info(f"🏁 ╚═══════════════════════════════════════════════════════════╝")
    logger.info(f"🏁 Arquivos processados: {len(files)}")
    logger.info(f"🏁 Sucessos: {sum(1 for r in resultados if r.get('ok'))}")
    logger.info(f"🏁 Falhas: {sum(1 for r in resultados if not r.get('ok'))}")
    logger.info(f"🏁 Tempo total: {tempo_total:.2f}s")
    logger.info(f"🏁 ════════════════════════════════════════════════════════════")
    
    return resultados


# ============================================================
# 🏷️ DETERMINAR TIPO DE ORIGEM
# ============================================================
def _determinar_tipo_origem(resultado: dict, nome_arquivo: str) -> str:
    """Determina o tipo de origem do arquivo"""
    tipo = resultado.get("tipo")
    nome_lower = nome_arquivo.lower()
    
    if tipo == "venda":
        if "flow" in nome_lower:
            return "csv_flow"
        elif "cielo" in nome_lower:
            return "csv_cielo"
        elif "rede" in nome_lower:
            return "csv_rede"
        elif "stone" in nome_lower:
            return "csv_stone"
        return "csv_adquirente"
    
    elif tipo == "recebimento":
        if nome_lower.endswith(".ofx"):
            return "ofx_banco"
        return "csv_banco"
    
    return "desconhecido"


# ============================================================
# 🧰 UTILITÁRIOS
# ============================================================
def validar_tamanho_arquivo(file_storage):
    file_storage.seek(0, 2)
    size = file_storage.tell()
    file_storage.seek(0)
    return size <= MAX_FILE_SIZE, size


def identificar_tipo_por_conteudo(registros, nome_arquivo):
    nome = nome_arquivo.lower()
    if any(kw in nome for kw in ['receb', 'extrato', 'ofx', 'banco', 'credito', 'deposito', 'movimento']):
        return "recebimento"
    if any(kw in nome for kw in ['venda', 'transacao', 'adquirente', 'cielo', 'rede', 'stone', 'pagseguro', 'getnet', 'maquininha']):
        return "venda"
    return "desconhecido"


def listar_importados(empresa_id: int):
    from services.importer_db import listar_arquivos_importados
    return listar_arquivos_importados(empresa_id)
