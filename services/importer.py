# services/importer.py - VERSÃO FINAL COM PROCESSAMENTO SEQUENCIAL E PAUSAS

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
    nome = file_storage.filename.lower()
    
    valido, size = validar_tamanho_arquivo(file_storage)
    if not valido:
        return {"ok": False, "arquivo": nome, "erro": f"Arquivo excede {MAX_FILE_SIZE/1024/1024}MB"}
    
    file_storage.seek(0)
    conteudo = file_storage.read()
    file_storage.seek(0)
    hash_arquivo = hashlib.sha256(conteudo).hexdigest()
    
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
            logger.info(f"📄 Detectado CSV Flow: {nome}")
            file_storage.seek(0)
            registros = parse_flow_csv(file_storage, nome, default_empresa_id=default_empresa_id)
            tipo = "venda"
            
        # ============================================================
        # CSV GENÉRICO (pode ser grande)
        # ============================================================
        elif nome.endswith(".csv") or nome.endswith(".txt"):
            logger.info(f"📄 Detectado CSV: {nome}")
            
            # ✅ Verificar tamanho do CSV
            content_text = conteudo.decode('utf-8', errors='replace')
            total_linhas = content_text.count('\n')
            logger.info(f"🔍 CSV com {total_linhas} linhas")
            
            if total_linhas > MAX_TRANSACOES_POR_LOTE:
                dividido_automaticamente = True
                total_transacoes_original = total_linhas
                logger.info(f"🔧 CSV grande ({total_linhas} linhas). Dividindo em lotes de {MAX_TRANSACOES_POR_LOTE}...")
                
                # Dividir CSV em partes
                partes = dividir_csv_em_partes(content_text, MAX_TRANSACOES_POR_LOTE)
                num_partes = len(partes)
                logger.info(f"✅ CSV dividido em {num_partes} partes")
                
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
                file_storage.seek(0)
                registros = parse_csv_generic(file_storage)
            
            tipo = identificar_tipo_por_conteudo(registros, nome)
            
        # ============================================================
        # EXCEL
        # ============================================================
        elif nome.endswith(".xlsx") or nome.endswith(".xls"):
            logger.info(f"📊 Detectado Excel: {nome}")
            file_storage.seek(0)
            registros = parse_excel_generic(file_storage)
            tipo = identificar_tipo_por_conteudo(registros, nome)
            
        # ============================================================
        # OFX (extrato bancário - pode ser grande)
        # ============================================================
        elif nome.endswith(".ofx"):
            logger.info(f"🏦 Detectado OFX: {nome}")
            
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
                file_storage.seek(0)
                registros = parse_ofx_generic(file_storage)
            
            tipo = "recebimento"
            
        else:
            return {"ok": False, "arquivo": nome, "erro": "Formato não suportado"}
        
    except Exception as e:
        logger.error(f"Erro ao parsear {nome}: {str(e)}", exc_info=True)
        return {"ok": False, "arquivo": nome, "erro": f"Erro ao processar: {str(e)}"}
    
    # Inferir tipo e categoria
    for reg in registros:
        if default_empresa_id and ('empresa_id' not in reg or not reg['empresa_id']):
            reg['empresa_id'] = default_empresa_id
    
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
# 📦 PROCESSAR MÚLTIPLOS ARQUIVOS
# ============================================================
def process_uploaded_files(files, empresa_id, usuario_id):
    inicio_total = time.time()
    logger.info(f"🚀 INÍCIO UPLOAD: usuario={usuario_id}, empresa={empresa_id}, arquivos={len(files)}")
    
    total_size = sum(f.seek(0, 2) for f in files)
    for f in files:
        f.seek(0)
    
    if total_size > MAX_TOTAL_SIZE:
        return [{"ok": False, "erro": f"Total excede {MAX_TOTAL_SIZE/1024/1024}MB"}]
    
    resultados = []
    
    for i, file_storage in enumerate(files, 1):
        inicio_arquivo = time.time()
        nome = file_storage.filename.lower()
        logger.info(f"📄 [{i}/{len(files)}] Processando: {nome}")
        
        try:
            inicio_parse = time.time()
            resultado = process_file(file_storage, default_empresa_id=empresa_id)
            logger.info(f"⏱️ Parse de {nome}: {time.time() - inicio_parse:.2f}s")
            
            if not resultado["ok"]:
                resultados.append(resultado)
                continue
            
            dados_conta = resultado.get("dados_conta")
            
            # Mensagem especial se foi dividido
            if resultado.get("dividido_automaticamente"):
                logger.info(f"🔧 Arquivo dividido automaticamente: {resultado.get('total_transacoes_original')} transações em {resultado.get('num_partes')} partes")
            
            inicio_duplicata = time.time()
            if verificar_arquivo_duplicado(empresa_id, resultado["hash"]):
                resultados.append({"ok": False, "arquivo": nome, "erro": "Arquivo já importado anteriormente"})
                continue
            
            db.session.begin_nested()
            
            arquivo_id = salvar_arquivo_importado(
                empresa_id=empresa_id,
                usuario_id=usuario_id,
                nome_arquivo=nome,
                tipo=resultado["tipo"],
                hash_arquivo=resultado["hash"],
                registros=resultado["registros"]
            )
            
            stats = None
            if resultado["tipo"] == "venda":
                stats = salvar_vendas(resultado["registros"], empresa_id, arquivo_id)
            elif resultado["tipo"] == "recebimento":
                stats = salvar_recebimentos(
                    resultado["registros"], 
                    empresa_id, 
                    arquivo_id,
                    dados_conta=dados_conta
                )
            
            db.session.commit()
            
            resultado_final = {
                "ok": True,
                "arquivo": nome,
                "tipo": resultado["tipo"],
                "linhas": resultado["linhas"],
                "hash": resultado["hash"],
                "estatisticas": stats,
                "dividido_automaticamente": resultado.get("dividido_automaticamente", False),
                "total_transacoes_original": resultado.get("total_transacoes_original"),
                "num_partes": resultado.get("num_partes")
            }
            
            mensagens = []
            
            # Mensagem especial se foi dividido
            if resultado.get("dividido_automaticamente"):
                mensagens.append(
                    f"🔧 Arquivo grande detectado: {resultado.get('total_transacoes_original')} transações "
                    f"divididas automaticamente em {resultado.get('num_partes')} partes para processamento."
                )
            
            if stats:
                if stats.get("conta_criada"):
                    nome_conta = dados_conta.get("nome", "Conta OFX") if dados_conta else "Conta OFX"
                    mensagens.append(f"✅ Conta bancária identificada/criada: {nome_conta}")
                
                if stats.get("falhas", 0) > 0:
                    mensagens.append(f"⚠️ {stats['falhas']} registros ignorados.")
                
                if stats.get("sucesso", 0) == 0:
                    resultado_final["ok"] = False
                    resultado_final["erro"] = "Nenhum registro foi importado."
                    mensagens.append("❌ Nenhum registro foi importado.")
                
                if mensagens:
                    resultado_final["mensagens"] = mensagens
            
            resultados.append(resultado_final)
            logger.info(f"✅ [{i}/{len(files)}] {nome}: {resultado['linhas']} registros em {time.time() - inicio_arquivo:.2f}s")
            
        except SQLAlchemyError as e:
            db.session.rollback()
            logger.error(f"❌ Erro de banco ao importar {nome}: {str(e)}")
            resultados.append({"ok": False, "arquivo": nome, "erro": f"Erro ao salvar dados: {str(e)}"})
        except Exception as e:
            db.session.rollback()
            logger.error(f"❌ Erro desconhecido ao importar {nome}: {str(e)}", exc_info=True)
            resultados.append({"ok": False, "arquivo": nome, "erro": f"Erro interno: {str(e)}"})
    
    logger.info(f"🏁 FIM UPLOAD: {time.time() - inicio_total:.2f}s total")
    return resultados

def process_uploaded_files_novo(files, empresa_id, usuario_id):
    """
    NOVA ABORDAGEM: Importa arquivos usando camada de normalização.
    """
    resultados = []
    
    for file_storage in files:
        # 1. Parsear arquivo (usar parsers existentes)
        resultado_parse = process_file(file_storage, default_empresa_id=empresa_id)
        
        if not resultado_parse["ok"]:
            resultados.append(resultado_parse)
            continue
        
        # 2. Salvar arquivo no banco
        arquivo_id = salvar_arquivo_importado(...)
        
        # 3. Normalizar dados
        importador = ImportadorNormalizado(empresa_id, usuario_id)
        stats_normalizacao = importador.importar_arquivo(
            arquivo_id=arquivo_id,
            registros=resultado_parse["registros"],
            tipo_origem=_determinar_tipo_origem(resultado_parse),
            tipo_movimento=resultado_parse["tipo"]
        )
        
        # 4. Processar para tabelas finais (opcional - pode ser assíncrono)
        importador.processar_para_tabelas_finais()
        
        resultados.append({
            "ok": True,
            "arquivo": file_storage.filename,
            "stats_normalizacao": stats_normalizacao
        })
    
    return resultados

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
