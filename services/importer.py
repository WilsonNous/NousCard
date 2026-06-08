# services/importer.py - VERSÃO CORRIGIDA COM SUPORTE FLOW + PIX

import os
import hashlib
import logging
import re
from decimal import Decimal
from sqlalchemy.exc import SQLAlchemyError
from utils.parsers import (
    parse_csv_generic,
    parse_excel_generic,
    parse_ofx_generic,
    parse_flow_csv,  # ← NOVO: Importar parser específico do Flow
    is_flow_csv      # ← NOVO: Importar detector do Flow
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
# 🧠 MAPEAMENTO INTELIGENTE DE COLUNAS (ATUALIZADO)
# ============================================================

COLUNAS_PADRAO_VENDA = {
    'valor_bruto': [
        'valor_bruto', 'vl_bruto', 'valor', 'bruto', 'gross_value', 
        'gross_amount', 'vlr_bruto', 'valor bruto', 'valorbruto'
    ],
    'data_venda': [
        'data_venda', 'data', 'dt_venda', 'dt', 'sale_date', 
        'transaction_date', 'data_transacao', 'dt_transacao',
        'data do pagamento', 'datapagamento', 'data_pagamento'  # ← NOVO: Flow CSV
    ],
    'nsu': [
        'nsu', 'cod_nsu', 'numero_nsu', 'nsu_code', 'transaction_id', 
        'id_transacao', 'cod_transacao'
    ],
    'adquirente': [
        'adquirente', 'acquirer', 'operadora', 'maquininha', 'gateway',
        'estabelecimento', 'no estabelecimento', 'noestabelecimento'  # ← NOVO: Flow
    ],
    'bandeira': [
        'bandeira', 'flag', 'card_flag', 'brand', 'carteira'
    ],
    'taxa': [
        'taxa', 'fee', 'taxa_cobrada', 'commission', 'custo', 
        'vlr_taxa', 'desconto', 'discount'  # ← NOVO: Flow usa "Desconto"
    ],
    'valor_liquido': [
        'valor_liquido', 'vl_liquido', 'net_value', 'net_amount', 
        'valor_recebido', 'vlr_liquido', 'valor líquido', 'valorliquido'  # ← NOVO
    ],
    'parcela': [
        'parcela', 'installment', 'parcel', 'num_parcela'
    ],
    'total_parcelas': [
        'total_parcelas', 'total_installments', 'qtd_parcelas', 'num_parcelas'
    ],
    'autorizacao': [
        'autorizacao', 'auth_code', 'codigo_autorizacao', 'cod_autorizacao'
    ],
    'produto': [
        'produto', 'product', 'description', 'descricao', 'item',
        'tipo_pagamento', 'formapagamento', 'payment_type'  # ← NOVO: Para detectar PIX
    ],
    'quantidade': [  # ← NOVO: Flow CSV tem esta coluna
        'quantidade', 'quantity', 'qtd', 'qtde'
    ],
}

COLUNAS_PADRAO_RECEBIMENTO = {
    'valor': [
        'valor', 'vl_movimento', 'vl_credito', 'credito', 'amount', 
        'value', 'vlr_credito', 'vlr_movimento'
    ],
    'data_movimento': [
        'data_movimento', 'data', 'dt_movimento', 'dt_credito', 
        'movement_date', 'credit_date', 'data_credito', 'dt_lancamento'
    ],
    'documento': [
        'documento', 'doc', 'nsu', 'cod_documento', 'reference', 
        'ref', 'id_documento'
    ],
    'banco': [
        'banco', 'bank', 'instituicao', 'financial_institution'
    ],
    'tipo_movimento': [
        'tipo_movimento', 'tipo', 'movement_type', 'transaction_type'
    ],
    'saldo': [
        'saldo', 'balance', 'vl_saldo'
    ],
}

# Colunas mínimas necessárias
COLUNAS_MINIMAS_VENDA = ['valor_bruto', 'data_venda', 'nsu']
COLUNAS_MINIMAS_RECEBIMENTO = ['valor', 'data_movimento', 'documento']

# ============================================================
# 🧰 UTILITÁRIOS DE NORMALIZAÇÃO (CORRIGIDO)
# ============================================================

def normalizar_chave(key):
    """
    Normaliza chave para comparação: remove BOM, espaços extras, 
    converte para minúsculo, remove acentos, mas PRESERVA palavras separadas.
    """
    if not isinstance(key, str):
        return key
    
    # Remove BOM e espaços extras nas extremidades
    key = key.strip().replace('\ufeff', '').lower()
    
    # Remove acentos (opcional, mas útil para comparação)
    import unicodedata
    key = ''.join(
        c for c in unicodedata.normalize('NFD', key)
        if unicodedata.category(c) != 'Mn'
    )
    
    # Substitui espaços e hífens por underscore para padronizar
    key = re.sub(r'[\s\-]+', '_', key)
    
    # Remove caracteres especiais, mas mantém letras, números e underscore
    key = re.sub(r'[^a-z0-9_]', '', key)
    
    return key

def encontrar_coluna_padrao(chave_disponivel, mapeamento):
    """Encontra o nome padrão para uma chave disponível no arquivo"""
    chave_normalizada = normalizar_chave(chave_disponivel)
    
    for nome_padrao, variacoes in mapeamento.items():
        for variacao in variacoes:
            if normalizar_chave(variacao) == chave_normalizada:
                return nome_padrao
    return None

def normalizar_registro(registro, mapeamento):
    """Normaliza as chaves de um registro para os nomes padrão"""
    if not isinstance(registro, dict):
        return registro
    
    registro_normalizado = {}
    for key, value in registro.items():
        if key and isinstance(key, str):
            nome_padrao = encontrar_coluna_padrao(key, mapeamento)
            if nome_padrao:
                registro_normalizado[nome_padrao] = value
            else:
                # Mantém a chave original normalizada se não houver mapeamento
                registro_normalizado[normalizar_chave(key)] = value
    return registro_normalizado

def normalizar_registros(registros, mapeamento):
    """Normaliza uma lista de registros"""
    return [normalizar_registro(r, mapeamento) for r in registros]

def inferir_tipo_pagamento(registro):
    """
    Infere o tipo de pagamento (cartao, pix, boleto, outros) baseado nos campos.
    ✅ Suporta detecção de PIX no CSV Flow
    """
    produto = str(registro.get('produto') or '').strip().lower()
    bandeira = str(registro.get('bandeira') or '').strip().lower()
    
    # Detectar PIX
    if 'pix' in produto or bandeira == 'pix':
        return 'pix'
    
    # Detectar boleto
    if 'boleto' in produto or 'billet' in produto:
        return 'boleto'
    
    # Detectar cartão (Crédito/Débito)
    if any(kw in produto for kw in ['crédito', 'credito', 'débito', 'debito', 'credit', 'debit']):
        return 'cartao'
    
    # Default: cartão (maioria dos casos)
    return 'cartao'

# ============================================================
# 🔍 VALIDAÇÕES INTELIGENTES
# ============================================================

def validar_tamanho_arquivo(file_storage):
    file_storage.seek(0, 2)
    size = file_storage.tell()
    file_storage.seek(0)
    return size <= MAX_FILE_SIZE, size

def validar_registros(registros, tipo):
    """Valida registros verificando colunas mínimas"""
    if not registros or len(registros) == 0:
        return False, "Arquivo vazio"
    
    if len(registros) > MAX_REGISTROS_POR_ARQUIVO:
        return False, f"Excede {MAX_REGISTROS_POR_ARQUIVO} registros"
    
    primeira_linha = registros[0] if isinstance(registros[0], dict) else {}
    mapeamento = COLUNAS_PADRAO_VENDA if tipo == "venda" else COLUNAS_PADRAO_RECEBIMENTO
    colunas_minimas = COLUNAS_MINIMAS_VENDA if tipo == "venda" else COLUNAS_MINIMAS_RECEBIMENTO
    
    chaves_disponiveis = set(primeira_linha.keys())
    
    for col_minima in colunas_minimas:
        if col_minima not in chaves_disponiveis:
            found = False
            for key in primeira_linha.keys():
                if encontrar_coluna_padrao(key, mapeamento) == col_minima:
                    found = True
                    break
            if not found:
                return False, f"Coluna obrigatória ausente: {col_minima}"
    
    return True, "OK"

def identificar_tipo_por_conteudo(registros, nome_arquivo):
    """Identifica se o arquivo é de venda ou recebimento"""
    nome = nome_arquivo.lower()
    
    # Heurística por nome
    if any(kw in nome for kw in ['receb', 'extrato', 'ofx', 'banco', 'credito', 'deposito', 'movimento']):
        return "recebimento"
    if any(kw in nome for kw in ['venda', 'transacao', 'adquirente', 'cielo', 'rede', 'stone', 'pagseguro', 'getnet', 'maquininha']):
        return "venda"
    
    # Análise de conteúdo
    if not registros:
        return "desconhecido"
    
    primeira_linha = registros[0] if isinstance(registros[0], dict) else {}
    chaves = set(primeira_linha.keys())
    
    score_venda = sum(1 for col in COLUNAS_MINIMAS_VENDA if col in chaves)
    score_receb = sum(1 for col in COLUNAS_MINIMAS_RECEBIMENTO if col in chaves)
    
    if 'adquirente' in chaves or 'bandeira' in chaves or 'nsu' in chaves:
        score_venda += 1
    if 'banco' in chaves or 'documento' in chaves:
        score_receb += 1
    
    if score_venda >= 2 and score_venda > score_receb:
        return "venda"
    elif score_receb >= 2 and score_receb > score_venda:
        return "recebimento"
    elif score_venda > 0 or score_receb > 0:
        return "venda" if score_venda >= score_receb else "recebimento"
    
    return "desconhecido"

# ============================================================
# 📦 PROCESSAR UM ARQUIVO (CORRIGIDO)
# ============================================================

def process_file(file_storage, default_empresa_id=None):
    """
    Processa um arquivo e retorna registros normalizados.
    
    ✅ NOVO: Suporte a CSV Flow com detecção automática
    ✅ NOVO: Inferência de tipo_pagamento (PIX/cartão/boleto)
    """
    nome = file_storage.filename.lower()
    
    # Validar tamanho
    valido, size = validar_tamanho_arquivo(file_storage)
    if not valido:
        return {
            "ok": False,
            "arquivo": nome,
            "erro": f"Arquivo excede {MAX_FILE_SIZE/1024/1024}MB"
        }
    
    # Gerar hash
    file_storage.seek(0)
    conteudo = file_storage.read()
    file_storage.seek(0)
    hash_arquivo = hashlib.sha256(conteudo).hexdigest()
    
    try:
        # 🔹 Detectar CSV Flow ANTES de parsear
        sample = conteudo[:1024].decode('utf-8', errors='ignore') if isinstance(conteudo, bytes) else conteudo[:1024]
        
        if nome.endswith(('.csv', '.txt')) and is_flow_csv(nome, sample):
            # ✅ Usar parser específico do Flow
            file_storage.seek(0)
            registros = parse_flow_csv(file_storage, nome, default_empresa_id=default_empresa_id)
            tipo = "venda"  # Flow CSV é sempre de vendas
            mapeamento = COLUNAS_PADRAO_VENDA
        elif nome.endswith(".csv") or nome.endswith(".txt"):
            registros = parse_csv_generic(file_storage)
            tipo = identificar_tipo_por_conteudo(registros, nome)
            mapeamento = COLUNAS_PADRAO_VENDA if tipo == "venda" else COLUNAS_PADRAO_RECEBIMENTO
            # Normalizar registros genéricos
            registros = normalizar_registros(registros, mapeamento)
        elif nome.endswith(".xlsx") or nome.endswith(".xls"):
            registros = parse_excel_generic(file_storage)
            tipo = identificar_tipo_por_conteudo(registros, nome)
            mapeamento = COLUNAS_PADRAO_VENDA if tipo == "venda" else COLUNAS_PADRAO_RECEBIMENTO
            registros = normalizar_registros(registros, mapeamento)
        elif nome.endswith(".ofx"):
            registros = parse_ofx_generic(file_storage)
            tipo = "recebimento"  # OFX é geralmente extrato bancário
            mapeamento = {}
        else:
            return {
                "ok": False,
                "arquivo": nome,
                "erro": "Formato não suportado"
            }
        
        if tipo == "desconhecido":
            return {
                "ok": False,
                "arquivo": nome,
                "erro": "Não foi possível identificar o tipo do arquivo"
            }
        
    except Exception as e:
        logger.error(f"Erro ao parsear arquivo {nome}: {str(e)}")
        return {
            "ok": False,
            "arquivo": nome,
            "erro": f"Erro ao processar: {str(e)}"
        }
    
    # Validar registros
    valido, msg = validar_registros(registros, tipo)
    if not valido:
        return {
            "ok": False,
            "arquivo": nome,
            "erro": msg
        }
    
    # ✅ INFERIR tipo_pagamento para cada registro (se não estiver definido)
    for reg in registros:
        if 'tipo_pagamento' not in reg or not reg['tipo_pagamento']:
            reg['tipo_pagamento'] = inferir_tipo_pagamento(reg)
        # Garantir empresa_id se fornecido
        if default_empresa_id and ('empresa_id' not in reg or not reg['empresa_id']):
            reg['empresa_id'] = default_empresa_id
    
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
            # ✅ PASSAR empresa_id para o parser (necessário para Flow CSV)
            resultado = process_file(file_storage, default_empresa_id=empresa_id)
            
            if not resultado["ok"]:
                logger.warning(f"Arquivo rejeitado: {nome}, erro={resultado.get('erro')}")
                resultados.append(resultado)
                continue
            
            # Verificar duplicata
            if verificar_arquivo_duplicado(empresa_id, resultado["hash"]):
                resultados.append({
                    "ok": False,
                    "arquivo": nome,
                    "erro": "Arquivo já importado anteriormente"
                })
                continue
            
            # Salvar em transação
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
