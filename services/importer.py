import os
import hashlib
import logging
from decimal import Decimal
from sqlalchemy.exc import SQLAlchemyError
from utils.parsers import (
    parse_csv_generic,
    parse_excel_generic,
    parse_ofx_generic
)
from utils.helpers import gerar_hash_arquivo
from services.importer_db import (
    salvar_arquivo_importado,
    verificar_arquivo_duplicado
)
from services.importer_db_movimento import (
    salvar_vendas,
    salvar_recebimentos
)
from models import db

logger = logging.getLogger(__name__)

# ============================================================
# CONFIGURAÇÕES
# ============================================================
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
MAX_TOTAL_SIZE = 50 * 1024 * 1024  # 50MB
MAX_REGISTROS_POR_ARQUIVO = 10000

COLUNAS_VENDA = ['valor_bruto', 'data_venda', 'nsu']
COLUNAS_RECEBIMENTO = ['valor', 'data_movimento', 'documento']

# ============================================================
# VALIDAÇÕES
# ============================================================
def validar_tamanho_arquivo(file_storage):
    file_storage.seek(0, 2)
    size = file_storage.tell()
    file_storage.seek(0)
    return size <= MAX_FILE_SIZE, size

def validar_registros(registros, tipo):
    if not registros or len(registros) == 0:
        return False, "Arquivo vazio"
    
    if len(registros) > MAX_REGISTROS_POR_ARQUIVO:
        return False, f"Excede {MAX_REGISTROS_POR_ARQUIVO} registros"
    
    primeira_linha = registros[0] if isinstance(registros[0], dict) else {}
    colunas = COLUNAS_VENDA if tipo == "venda" else COLUNAS_RECEBIMENTO
    
    for col in colunas:
        if col not in primeira_linha:
            return False, f"Coluna ausente: {col}"
    
    return True, "OK"

def identificar_tipo_por_conteudo(registros, nome_arquivo):
    # Primeiro tenta por nome (fallback rápido)
    nome = nome_arquivo.lower()
    if "receb" in nome or "extrato" in nome or "ofx" in nome:
        return "recebimento"
    if "venda" in nome or "transacao" in nome:
        return "venda"
    
    # Se ambíguo, verifica conteúdo
    if not registros:
        return "desconhecido"
    
    primeira_linha = registros[0] if isinstance(registros[0], dict) else {}
    
    match_venda = sum(1 for col in COLUNAS_VENDA if col in primeira_linha)
    match_receb = sum(1 for col in COLUNAS_RECEBIMENTO if col in primeira_linha)
    
    if match_venda > match_receb:
        return "venda"
    elif match_receb > match_venda:
        return "recebimento"
    
    return "desconhecido"

# ============================================================
# PROCESSAR UM ARQUIVO
# ============================================================
def process_file(file_storage):
    nome = file_storage.filename.lower()
    
    # Validar tamanho
    valido, size = validar_tamanho_arquivo(file_storage)
    if not valido:
        return {
            "ok": False,
            "arquivo": nome,
            "erro": f"Arquivo excede {MAX_FILE_SIZE/1024/1024}MB"
        }
    
    # Gerar hash ANTES de processar (leitura única)
    file_storage.seek(0)
    conteudo = file_storage.read()
    file_storage.seek(0)
    hash_arquivo = hashlib.sha256(conteudo).hexdigest()
    
    try:
        # Parse baseado na extensão
        if nome.endswith(".csv") or nome.endswith(".txt"):
            registros = parse_csv_generic(file_storage)
        elif nome.endswith(".xlsx") or nome.endswith(".xls"):
            registros = parse_excel_generic(file_storage)
        elif nome.endswith(".ofx"):
            registros = parse_ofx_generic(file_storage)
        else:
            return {
                "ok": False,
                "arquivo": nome,
                "erro": "Formato não suportado"
            }
        
    except Exception as e:
        logger.error(f"Erro ao parsear arquivo {nome}: {str(e)}")
        return {
            "ok": False,
            "arquivo": nome,
            "erro": f"Erro ao processar: {str(e)}"
        }
    
    # Identificar tipo
    tipo = identificar_tipo_por_conteudo(registros, nome)
    if tipo == "desconhecido":
        return {
            "ok": False,
            "arquivo": nome,
            "erro": "Não foi possível identificar o tipo do arquivo"
        }
    
    # Validar registros
    valido, msg = validar_registros(registros, tipo)
    if not valido:
        return {
            "ok": False,
            "arquivo": nome,
            "erro": msg
        }
    
    return {
        "ok": True,
        "arquivo": nome,
        "tipo": tipo,
        "registros": registros,
        "hash": hash_arquivo,
        "linhas": len(registros)
    }

# ============================================================
# PROCESSAR MÚLTIPLOS ARQUIVOS
# ============================================================
def process_uploaded_files(files, empresa_id, usuario_id):
    logger.info(f"Início importação: usuario={usuario_id}, empresa={empresa_id}, arquivos={len(files)}")
    
    # Validar tamanho total
    total_size = sum(f.seek(0, 2) for f in files)
    for f in files:
        f.seek(0)
    
    if total_size > MAX_TOTAL_SIZE:
        return [{
            "ok": False,
            "erro": f"Total excede {MAX_TOTAL_SIZE/1024/1024}MB"
        }]
    
    resultados = []
    
    for file_storage in files:
        nome = file_storage.filename.lower()
        
        try:
            # Processar arquivo
            resultado = process_file(file_storage)
            
            if not resultado["ok"]:
                logger.warning(f"Arquivo rejeitado: {nome}, erro={resultado.get('erro')}")
                resultados.append(resultado)
                continue
            
            # Verificar duplicata ANTES de salvar
            if verificar_arquivo_duplicado(empresa_id, resultado["hash"]):
                resultados.append({
                    "ok": False,
                    "arquivo": nome,
                    "erro": "Arquivo já importado anteriormente"
                })
                continue
            
            # Salvar em transação (savepoint)
            db.session.begin_nested()
            
            arquivo_id = salvar_arquivo_importado(
                empresa_id=empresa_id,
                usuario_id=usuario_id,
                nome_arquivo=nome,
                tipo=resultado["tipo"],
                hash_arquivo=resultado["hash"],
                registros=resultado["registros"]
            )
            
            if resultado["tipo"] == "venda":
                salvar_vendas(resultado["registros"], empresa_id, arquivo_id)
            elif resultado["tipo"] == "recebimento":
                salvar_recebimentos(resultado["registros"], empresa_id, arquivo_id)
            
            db.session.commit()
            
            resultados.append({
                "ok": True,
                "arquivo": nome,
                "tipo": resultado["tipo"],
                "linhas": resultado["linhas"],
                "hash": resultado["hash"]
            })
            
            logger.info(f"Arquivo importado: {nome}, tipo={resultado['tipo']}, linhas={resultado['linhas']}")
            
        except SQLAlchemyError as e:
            db.session.rollback()
            logger.error(f"Erro de banco ao importar {nome}: {str(e)}")
            resultados.append({
                "ok": False,
                "arquivo": nome,
                "erro": f"Erro ao salvar dados: {str(e)}"
            })
        except Exception as e:
            db.session.rollback()
            logger.error(f"Erro desconhecido ao importar {nome}: {str(e)}")
            resultados.append({
                "ok": False,
                "arquivo": nome,
                "erro": f"Erro interno: {str(e)}"
            })
    
    logger.info(f"Fim importação: usuario={usuario_id}, sucesso={sum(1 for r in resultados if r['ok'])}")
    
    return resultados

# ============================================================
# LISTAR
# ============================================================
def listar_importados(empresa_id: int):
    from services.importer_db import listar_arquivos_importados
    return listar_arquivos_importados(empresa_id)
