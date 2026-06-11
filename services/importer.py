# services/importer.py - VERSÃO COM DIVISÃO AUTOMÁTICA DE OFX

import os
import hashlib
import logging
import re
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
    dividir_ofx_em_partes
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
MAX_TRANSACOES_OFX = 1000  # ✅ Limite para divisão automática

# ============================================================
# 🧠 MAPEAMENTO INTELIGENTE DE COLUNAS
# ============================================================

COLUNAS_PADRAO_VENDA = {
    'valor_bruto': [
        'valor_bruto', 'vl_bruto', 'valor', 'bruto', 'gross_value', 
        'gross_amount', 'vlr_bruto', 'valor bruto', 'valorbruto'
    ],
    'data_venda': [
        'data_venda', 'data', 'dt_venda', 'dt', 'sale_date', 
        'transaction_date', 'data_transacao', 'dt_transacao',
        'data do pagamento', 'datapagamento', 'data_pagamento'
    ],
    'nsu': [
        'nsu', 'cod_nsu', 'numero_nsu', 'nsu_code', 'transaction_id', 
        'id_transacao', 'cod_transacao'
    ],
    'adquirente': [
        'adquirente', 'acquirer', 'operadora', 'maquininha', 'gateway',
        'estabelecimento', 'no estabelecimento', 'noestabelecimento'
    ],
    'bandeira': [
        'bandeira', 'flag', 'card_flag', 'brand', 'carteira'
    ],
    'taxa': [
        'taxa', 'fee', 'taxa_cobrada', 'commission', 'custo', 
        'vlr_taxa', 'desconto', 'discount'
    ],
    'valor_liquido': [
        'valor_liquido', 'vl_liquido', 'net_value', 'net_amount', 
        'valor_recebido', 'vlr_liquido', 'valor líquido', 'valorliquido'
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
        'tipo_pagamento', 'formapagamento', 'payment_type'
    ],
    'quantidade': [
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

COLUNAS_MINIMAS_VENDA = ['valor_bruto', 'data_venda', 'nsu']
COLUNAS_MINIMAS_RECEBIMENTO = ['valor', 'data_movimento', 'documento']

# ============================================================
# 🧰 UTILITÁRIOS DE NORMALIZAÇÃO
# ============================================================

def normalizar_chave(key):
    """Normaliza chave para comparação."""
    if not isinstance(key, str):
        return key
    
    key = key.strip().replace('\ufeff', '').lower()
    
    import unicodedata
    key = ''.join(
        c for c in unicodedata.normalize('NFD', key)
        if unicodedata.category(c) != 'Mn'
    )
    
    key = re.sub(r'[\s\-]+', '_', key)
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
                registro_normalizado[normalizar_chave(key)] = value
    return registro_normalizado


def normalizar_registros(registros, mapeamento):
    """Normaliza uma lista de registros"""
    return [normalizar_registro(r, mapeamento) for r in registros]


def inferir_tipo_pagamento(registro):
    """Infere o tipo de pagamento baseado nos campos."""
    produto = str(registro.get('produto') or '').strip().lower()
    bandeira = str(registro.get('bandeira') or '').strip().lower()
    
    if 'pix' in produto or bandeira == 'pix':
        return 'pix'
    if 'boleto' in produto or 'billet' in produto:
        return 'boleto'
    if any(kw in produto for kw in ['crédito', 'credito', 'débito', 'debito', 'credit', 'debit']):
        return 'cartao'
    return 'cartao'


# ============================================================
# 🔍 VALIDAÇÕES
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
    
    if any(kw in nome for kw in ['receb', 'extrato', 'ofx', 'banco', 'credito', 'deposito', 'movimento']):
        return "recebimento"
    if any(kw in nome for kw in ['venda', 'transacao', 'adquirente', 'cielo', 'rede', 'stone', 'pagseguro', 'getnet', 'maquininha']):
        return "venda"
    
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
# 📦 PROCESSAR UM ARQUIVO (✅ COM DIVISÃO AUTOMÁTICA DE OFX)
# ============================================================

def process_file(file_storage, default_empresa_id=None):
    """
    Processa um arquivo e retorna registros normalizados.
    
    ✅ NOVO: Se for OFX grande, divide automaticamente em partes menores
    ✅ NOVO: Extrai dados da conta do OFX automaticamente
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
    
    # Variáveis para metadados
    dados_conta = None
    dividido_automaticamente = False
    total_transacoes_original = None
    num_partes = None
    
    try:
        sample = conteudo[:1024].decode('utf-8', errors='ignore') if isinstance(conteudo, bytes) else conteudo[:1024]
        
        if nome.endswith(('.csv', '.txt')) and is_flow_csv(nome, sample):
            file_storage.seek(0)
            registros = parse_flow_csv(file_storage, nome, default_empresa_id=default_empresa_id)
            tipo = "venda"
            mapeamento = COLUNAS_PADRAO_VENDA
            
        elif nome.endswith(".csv") or nome.endswith(".txt"):
            registros = parse_csv_generic(file_storage)
            tipo = identificar_tipo_por_conteudo(registros, nome)
            mapeamento = COLUNAS_PADRAO_VENDA if tipo == "venda" else COLUNAS_PADRAO_RECEBIMENTO
            registros = normalizar_registros(registros, mapeamento)
            
        elif nome.endswith(".xlsx") or nome.endswith(".xls"):
            registros = parse_excel_generic(file_storage)
            tipo = identificar_tipo_por_conteudo(registros, nome)
            mapeamento = COLUNAS_PADRAO_VENDA if tipo == "venda" else COLUNAS_PADRAO_RECEBIMENTO
            registros = normalizar_registros(registros, mapeamento)
            
        elif nome.endswith(".ofx"):
            # ✅ Extrair dados da conta do OFX
            try:
                content_text = conteudo.decode('utf-8', errors='replace')
                dados_conta = extrair_dados_conta_ofx(content_text)
                logger.info(f"🏦 Dados da conta extraídos do OFX: {dados_conta}")
            except Exception as e:
                logger.warning(f"⚠️ Erro ao extrair dados da conta do OFX: {str(e)}")
                dados_conta = None
            
            # ✅ Verificar se precisa dividir automaticamente
            content_text = conteudo.decode('utf-8', errors='replace')
            total_transacoes_original = content_text.upper().count('<STMTTRN>')
            
            logger.info(f"🔍 OFX com {total_transacoes_original} transações (limite: {MAX_TRANSACOES_OFX})")
            
            if total_transacoes_original > MAX_TRANSACOES_OFX:
                # ✅ DIVIDIR AUTOMATICAMENTE
                dividido_automaticamente = True
                logger.info(f"🔧 OFX grande detectado! Dividindo em partes de {MAX_TRANSACOES_OFX} transações...")
                
                partes = dividir_ofx_em_partes(content_text, MAX_TRANSACOES_OFX)
                num_partes = len(partes)
                logger.info(f"✅ OFX dividido em {num_partes} partes")
                
                # Processar cada parte
                todos_registros = []
                for i, parte in enumerate(partes, 1):
                    inicio_parte = time.time()
                    logger.info(f"📄 Processando parte {i}/{num_partes}...")
                    
                    stream = BytesIO(parte.encode('utf-8'))
                    registros_parte = parse_ofx_generic(stream, f"{nome}_parte_{i}")
                    todos_registros.extend(registros_parte)
                    
                    tempo_parte = time.time() - inicio_parte
                    logger.info(f"✅ Parte {i}/{num_partes} processada: {len(registros_parte)} registros em {tempo_parte:.2f}s")
                
                registros = todos_registros
                logger.info(f"✅ Total consolidado: {len(registros)} registros de {num_partes} partes")
                
            else:
                # OFX pequeno, processar normalmente
                file_storage.seek(0)
                registros = parse_ofx_generic(file_storage)
            
            tipo = "recebimento"
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
    
    # Inferir tipo_pagamento
    for reg in registros:
        if 'tipo_pagamento' not in reg or not reg['tipo_pagamento']:
            reg['tipo_pagamento'] = inferir_tipo_pagamento(reg)
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
    """
    Processa múltiplos arquivos com logs de performance detalhados.
    """
    inicio_total = time.time()
    logger.info(f"🚀 INÍCIO UPLOAD: usuario={usuario_id}, empresa={empresa_id}, arquivos={len(files)}")
    
    # Validar tamanho total
    inicio_validacao = time.time()
    total_size = sum(f.seek(0, 2) for f in files)
    for f in files:
        f.seek(0)
    
    if total_size > MAX_TOTAL_SIZE:
        return [{
            "ok": False,
            "erro": f"Total excede {MAX_TOTAL_SIZE/1024/1024}MB"
        }]
    
    tempo_validacao = time.time() - inicio_validacao
    logger.info(f"⏱️ Validação: {tempo_validacao:.2f}s")
    
    resultados = []
    
    for i, file_storage in enumerate(files, 1):
        inicio_arquivo = time.time()
        nome = file_storage.filename.lower()
        
        logger.info(f"📄 [{i}/{len(files)}] Processando: {nome}")
        
        try:
            # Parse do arquivo (com divisão automática se OFX grande)
            inicio_parse = time.time()
            resultado = process_file(file_storage, default_empresa_id=empresa_id)
            tempo_parse = time.time() - inicio_parse
            
            logger.info(f"⏱️ Parse de {nome}: {tempo_parse:.2f}s")
            
            if not resultado["ok"]:
                logger.warning(f"❌ Arquivo rejeitado: {nome}, erro={resultado.get('erro')}")
                resultados.append(resultado)
                continue
            
            # Capturar metadados
            dados_conta = resultado.get("dados_conta")
            if dados_conta:
                logger.info(f"🏦 Dados da conta: {dados_conta}")
            
            if resultado.get("dividido_automaticamente"):
                logger.info(f"🔧 OFX dividido automaticamente: {resultado.get('total_transacoes_original')} transações em {resultado.get('num_partes')} partes")
            
            # Verificar duplicata
            inicio_duplicata = time.time()
            if verificar_arquivo_duplicado(empresa_id, resultado["hash"]):
                tempo_duplicata = time.time() - inicio_duplicata
                logger.info(f"⏱️ Verificação duplicata: {tempo_duplicata:.2f}s")
                resultados.append({
                    "ok": False,
                    "arquivo": nome,
                    "erro": "Arquivo já importado anteriormente"
                })
                continue
            
            # Salvar no banco
            inicio_save = time.time()
            db.session.begin_nested()
            
            arquivo_id = salvar_arquivo_importado(
                empresa_id=empresa_id,
                usuario_id=usuario_id,
                nome_arquivo=nome,
                tipo=resultado["tipo"],
                hash_arquivo=resultado["hash"],
                registros=resultado["registros"]
            )
            
            # Salvar movimentos
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
            
            tempo_save = time.time() - inicio_save
            logger.info(f"⏱️ Save no banco: {tempo_save:.2f}s")
            
            # Construir resultado
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
            
            # Mensagem especial se foi dividido automaticamente
            if resultado.get("dividido_automaticamente"):
                mensagens.append(
                    f"🔧 Arquivo grande detectado: {resultado.get('total_transacoes_original')} transações "
                    f"divididas automaticamente em {resultado.get('num_partes')} partes para processamento."
                )
            
            if stats:
                if stats.get("conta_criada"):
                    nome_conta = dados_conta.get("nome", "Conta OFX") if dados_conta else "Conta OFX"
                    mensagens.append(f"✅ Conta bancária criada automaticamente: {nome_conta}")
                
                if stats.get("falhas", 0) > 0:
                    mensagens.append(f"⚠️ {stats['falhas']} registros não puderam ser importados.")
                
                if stats.get("sucesso", 0) == 0:
                    resultado_final["ok"] = False
                    resultado_final["erro"] = "Nenhum registro foi importado."
                    mensagens.append("❌ Nenhum registro foi importado.")
                
                if mensagens:
                    resultado_final["mensagens"] = mensagens
            
            resultados.append(resultado_final)
            
            tempo_arquivo = time.time() - inicio_arquivo
            logger.info(f"✅ [{i}/{len(files)}] {nome}: {resultado['linhas']} registros em {tempo_arquivo:.2f}s")
            
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
    
    tempo_total = time.time() - inicio_total
    sucesso = sum(1 for r in resultados if r['ok'])
    logger.info(f"🏁 FIM UPLOAD: {tempo_total:.2f}s total, {sucesso}/{len(files)} arquivos com sucesso")
    
    return resultados


# ============================================================
# 📋 LISTAR
# ============================================================

def listar_importados(empresa_id: int):
    from services.importer_db import listar_arquivos_importados
    return listar_arquivos_importados(empresa_id)
