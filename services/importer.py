import os
import hashlib
import logging
import re
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

# ============================================================
# 🧠 MAPEAMENTO INTELIGENTE DE COLUNAS (NOVO - CRÍTICO)
# ============================================================
# Mapeia variações de nomes de colunas para nomes padrão internos
# Formato: {nome_padrao: [variação1, variação2, ...]}

COLUNAS_PADRAO_VENDA = {
    'valor_bruto': ['valor_bruto', 'vl_bruto', 'valor', 'bruto', 'gross_value', 'gross_amount', 'vlr_bruto', 'vlr_bruto'],
    'data_venda': ['data_venda', 'data', 'dt_venda', 'dt', 'sale_date', 'transaction_date', 'data_transacao', 'dt_transacao'],
    'nsu': ['nsu', 'cod_nsu', 'numero_nsu', 'nsu_code', 'transaction_id', 'id_transacao', 'cod_transacao'],
    'adquirente': ['adquirente', 'acquirer', 'operadora', 'maquininha', 'gateway'],
    'bandeira': ['bandeira', 'flag', 'card_flag', 'brand', 'carteira'],
    'taxa': ['taxa', 'fee', 'taxa_cobrada', 'commission', 'custo', 'vlr_taxa'],
    'valor_liquido': ['valor_liquido', 'vl_liquido', 'net_value', 'net_amount', 'valor_recebido', 'vlr_liquido'],
    'parcela': ['parcela', 'installment', 'parcel', 'num_parcela'],
    'total_parcelas': ['total_parcelas', 'total_installments', 'qtd_parcelas', 'num_parcelas'],
    'autorizacao': ['autorizacao', 'auth_code', 'codigo_autorizacao', 'cod_autorizacao'],
    'produto': ['produto', 'product', 'description', 'descricao', 'item'],
}

COLUNAS_PADRAO_RECEBIMENTO = {
    'valor': ['valor', 'vl_movimento', 'vl_credito', 'credito', 'amount', 'value', 'vlr_credito', 'vlr_movimento'],
    'data_movimento': ['data_movimento', 'data', 'dt_movimento', 'dt_credito', 'movement_date', 'credit_date', 'data_credito', 'dt_lancamento'],
    'documento': ['documento', 'doc', 'nsu', 'cod_documento', 'reference', 'ref', 'id_documento'],
    'banco': ['banco', 'bank', 'instituicao', 'financial_institution'],
    'tipo_movimento': ['tipo_movimento', 'tipo', 'movement_type', 'transaction_type'],
    'saldo': ['saldo', 'balance', 'vl_saldo'],
}

# Colunas mínimas necessárias para identificar o tipo do arquivo
COLUNAS_MINIMAS_VENDA = ['valor_bruto', 'data_venda', 'nsu']
COLUNAS_MINIMAS_RECEBIMENTO = ['valor', 'data_movimento', 'documento']

# ============================================================
# 🧰 UTILITÁRIOS DE NORMALIZAÇÃO E MAPEAMENTO
# ============================================================

def normalizar_chave(key):
    """Remove BOM, espaços, normaliza case e remove caracteres especiais para comparação"""
    if not isinstance(key, str):
        return key
    # Remove BOM, espaços, converte para minúsculo, remove acentos e caracteres especiais
    key = key.strip().replace('\ufeff', '').lower()
    key = re.sub(r'[^a-z0-9_]', '', key)  # Mantém apenas letras, números e underscore
    return key

def encontrar_coluna_padrao(chave_disponivel, mapeamento):
    """
    Encontra o nome padrão para uma chave disponível no arquivo.
    Retorna o nome padrão ou None se não encontrar correspondência.
    """
    chave_normalizada = normalizar_chave(chave_disponivel)
    
    for nome_padrao, variacoes in mapeamento.items():
        for variacao in variacoes:
            if normalizar_chave(variacao) == chave_normalizada:
                return nome_padrao
    return None

def normalizar_registro(registro, mapeamento):
    """
    Normaliza as chaves de um registro para os nomes padrão definidos no mapeamento.
    Mantém colunas não mapeadas como estão.
    """
    if not isinstance(registro, dict):
        return registro
    
    registro_normalizado = {}
    for key, value in registro.items():
        if key and isinstance(key, str):
            # Tenta encontrar o nome padrão para esta chave
            nome_padrao = encontrar_coluna_padrao(key, mapeamento)
            if nome_padrao:
                registro_normalizado[nome_padrao] = value
            else:
                # Mantém a chave original (normalizada) se não houver mapeamento
                registro_normalizado[normalizar_chave(key)] = value
    return registro_normalizado

def normalizar_registros(registros, mapeamento):
    """Normaliza uma lista de registros usando o mapeamento fornecido"""
    return [normalizar_registro(r, mapeamento) for r in registros]

# ============================================================
# 🔍 VALIDAÇÕES INTELIGENTES
# ============================================================

def validar_tamanho_arquivo(file_storage):
    file_storage.seek(0, 2)
    size = file_storage.tell()
    file_storage.seek(0)
    return size <= MAX_FILE_SIZE, size

def validar_registros(registros, tipo):
    """
    Valida registros verificando se pelo menos as colunas mínimas estão presentes
    (considerando todas as variações possíveis de nomenclatura).
    """
    if not registros or len(registros) == 0:
        return False, "Arquivo vazio"
    
    if len(registros) > MAX_REGISTROS_POR_ARQUIVO:
        return False, f"Excede {MAX_REGISTROS_POR_ARQUIVO} registros"
    
    primeira_linha = registros[0] if isinstance(registros[0], dict) else {}
    mapeamento = COLUNAS_PADRAO_VENDA if tipo == "venda" else COLUNAS_PADRAO_RECEBIMENTO
    colunas_minimas = COLUNAS_MINIMAS_VENDA if tipo == "venda" else COLUNAS_MINIMAS_RECEBIMENTO
    
    # Conjunto de chaves disponíveis (já normalizadas pelo normalizar_registros)
    chaves_disponiveis = set(primeira_linha.keys())
    
    # Verifica se todas as colunas mínimas estão presentes (já devem estar no padrão)
    for col_minima in colunas_minimas:
        if col_minima not in chaves_disponiveis:
            # Tenta encontrar se alguma variação estava presente antes da normalização
            # (caso o registro não tenha sido normalizado ainda)
            found = False
            for key in primeira_linha.keys():
                if encontrar_coluna_padrao(key, mapeamento) == col_minima:
                    found = True
                    break
            if not found:
                return False, f"Coluna obrigatória ausente: {col_minima}"
    
    return True, "OK"

def identificar_tipo_por_conteudo(registros, nome_arquivo):
    """
    Identifica se o arquivo é de venda ou recebimento com base em:
    1. Nome do arquivo (heurística rápida)
    2. Presença de colunas características de cada tipo
    """
    # Heurística por nome do arquivo (fallback rápido)
    nome = nome_arquivo.lower()
    
    # Palavras-chave que indicam recebimento/extrato bancário
    if any(kw in nome for kw in ['receb', 'extrato', 'ofx', 'banco', 'credito', 'deposito', 'movimento']):
        return "recebimento"
    
    # Palavras-chave que indicam venda/adquirente
    if any(kw in nome for kw in ['venda', 'transacao', 'adquirente', 'cielo', 'rede', 'stone', 'pagseguro', 'getnet', 'maquininha']):
        return "venda"
    
    # Se ambíguo pelo nome, analisa o conteúdo
    if not registros:
        return "desconhecido"
    
    primeira_linha = registros[0] if isinstance(registros[0], dict) else {}
    chaves = set(primeira_linha.keys())  # Já devem estar normalizadas
    
    # Conta quantas colunas características de cada tipo estão presentes
    score_venda = sum(1 for col in COLUNAS_MINIMAS_VENDA if col in chaves)
    score_receb = sum(1 for col in COLUNAS_MINIMAS_RECEBIMENTO if col in chaves)
    
    # Bônus por colunas adicionais características
    if 'adquirente' in chaves or 'bandeira' in chaves or 'nsu' in chaves:
        score_venda += 1
    if 'banco' in chaves or 'documento' in chaves:
        score_receb += 1
    
    if score_venda >= 2 and score_venda > score_receb:
        return "venda"
    elif score_receb >= 2 and score_receb > score_venda:
        return "recebimento"
    elif score_venda > 0 or score_receb > 0:
        # Se tiver pelo menos uma coluna característica, usa como palpite
        return "venda" if score_venda >= score_receb else "recebimento"
    
    return "desconhecido"

# ============================================================
# 📦 PROCESSAR UM ARQUIVO
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
            mapeamento = None  # Será definido após identificar o tipo
        elif nome.endswith(".xlsx") or nome.endswith(".xls"):
            registros = parse_excel_generic(file_storage)
            mapeamento = None
        elif nome.endswith(".ofx"):
            # OFX tem estrutura padrão, não precisa de mapeamento flexível
            registros = parse_ofx_generic(file_storage)
            mapeamento = {}  # OFX já vem padronizado
        else:
            return {
                "ok": False,
                "arquivo": nome,
                "erro": "Formato não suportado"
            }
        
        # Identificar tipo ANTES de normalizar (para saber qual mapeamento usar)
        tipo = identificar_tipo_por_conteudo(registros, nome)
        if tipo == "desconhecido":
            return {
                "ok": False,
                "arquivo": nome,
                "erro": "Não foi possível identificar o tipo do arquivo (venda ou recebimento)"
            }
        
        # Selecionar o mapeamento correto
        mapeamento = COLUNAS_PADRAO_VENDA if tipo == "venda" else COLUNAS_PADRAO_RECEBIMENTO
        
        # ✅ CORREÇÃO CRÍTICA: Normalizar chaves para o padrão interno
        # Isso permite que o sistema entenda arquivos com nomenclaturas variadas
        registros = normalizar_registros(registros, mapeamento)
        
    except Exception as e:
        logger.error(f"Erro ao parsear arquivo {nome}: {str(e)}")
        return {
            "ok": False,
            "arquivo": nome,
            "erro": f"Erro ao processar: {str(e)}"
        }
    
    # Validar registros com as colunas já normalizadas
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
# 📦 PROCESSAR MÚLTIPLOS ARQUIVOS
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
            
            logger.info(f"✅ Arquivo importado: {nome}, tipo={resultado['tipo']}, linhas={resultado['linhas']}")
            
        except SQLAlchemyError as e:
            db.session.rollback()
            logger.error(f"❌ Erro de banco ao importar {nome}: {str(e)}")
            resultados.append({
                "ok": False,
                "arquivo": nome,
                "erro": f"Erro ao salvar dados: {str(e)}"
            })
        except Exception as e:
            db.session.rollback()
            logger.error(f"❌ Erro desconhecido ao importar {nome}: {str(e)}")
            resultados.append({
                "ok": False,
                "arquivo": nome,
                "erro": f"Erro interno: {str(e)}"
            })
    
    logger.info(f"Fim importação: usuario={usuario_id}, sucesso={sum(1 for r in resultados if r['ok'])}")
    
    return resultados

# ============================================================
# 📋 LISTAR
# ============================================================

def listar_importados(empresa_id: int):
    from services.importer_db import listar_arquivos_importados
    return listar_arquivos_importados(empresa_id)
