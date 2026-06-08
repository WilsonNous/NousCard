# services/importer_db.py - VERSÃO CORRIGIDA COM SUPORTE FLOW + PIX + DATAS

from models import db, ArquivoImportado, LogAuditoria, MovAdquirente, MovBanco, Adquirente
from datetime import datetime, timezone, date
from decimal import Decimal, InvalidOperation
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
import logging
import os
import json
from cryptography.fernet import Fernet

logger = logging.getLogger(__name__)

# ============================================================
# CRIPTOGRAFIA
# ============================================================
def criptografar_conteudo(registros):
    """Criptografa registros JSON antes de salvar"""
    try:
        encryption_key = os.getenv("ENCRYPTION_KEY")
        if not encryption_key:
            logger.warning("ENCRYPTION_KEY não configurada, salvando sem criptografia")
            return json.dumps(registros, ensure_ascii=False, default=str)
        
        # Remover aspas se existirem (compatibilidade)
        encryption_key = encryption_key.strip('"')
        
        f = Fernet(encryption_key.encode())
        conteudo = json.dumps(registros, ensure_ascii=False, default=str)
        return f.encrypt(conteudo.encode()).decode()
    except Exception as e:
        logger.error(f"Erro ao criptografar: {str(e)}")
        return json.dumps(registros, ensure_ascii=False, default=str)

def descriptografar_conteudo(conteudo_criptografado):
    """Descriptografa registros JSON do banco"""
    if not conteudo_criptografado:
        return []
    
    try:
        encryption_key = os.getenv("ENCRYPTION_KEY")
        if not encryption_key:
            return json.loads(conteudo_criptografado)
        
        encryption_key = encryption_key.strip('"')
        f = Fernet(encryption_key.encode())
        conteudo = f.decrypt(conteudo_criptografado.encode()).decode()
        return json.loads(conteudo)
    except Exception as e:
        logger.error(f"Erro ao descriptografar: {str(e)}")
        return []

# ============================================================
# UTILITÁRIOS DE CONVERSÃO
# ============================================================

def to_date(value):
    """
    Converte valor para objeto date de forma segura.
    Suporta: date, datetime, string "DD/MM/YYYY", string "YYYY-MM-DD"
    """
    if value is None:
        return None
    
    if isinstance(value, date):
        return value
    
    if isinstance(value, datetime):
        return value.date()
    
    if isinstance(value, str):
        value = value.strip()
        formatos = ["%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%Y/%m/%d"]
        for fmt in formatos:
            try:
                return datetime.strptime(value, fmt).date()
            except ValueError:
                continue
        logger.warning(f"⚠️ Data não reconhecida: '{value}'")
        return None
    
    return None

def to_decimal(value, default=Decimal("0")):
    """Converte valor para Decimal de forma segura"""
    if value is None:
        return default
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        logger.warning(f"⚠️ Valor inválido para Decimal: {value}")
        return default

def resolver_adquirente_id(valor, empresa_id=None):
    """
    Resolve adquirente por ID numérico OU por nome (string).
    Retorna o ID da adquirente ou None se não encontrar.
    """
    if not valor:
        return None
    
    # Se for número, retorna direto
    if isinstance(valor, int):
        return valor
    
    # Se for string numérica, converte e retorna
    if isinstance(valor, str) and valor.strip().isdigit():
        return int(valor.strip())
    
    # Se for nome (string), busca no banco
    if isinstance(valor, str):
        nome_normalizado = valor.strip().lower()
        adquirente = Adquirente.query.filter(
            db.func.lower(Adquirente.nome) == nome_normalizado
        ).first()
        if adquirente:
            return adquirente.id
        # Tenta match parcial
        adquirente = Adquirente.query.filter(
            db.func.lower(Adquirente.nome).contains(nome_normalizado)
        ).first()
        if adquirente:
            return adquirente.id
        logger.warning(f"⚠️ Adquirente não encontrada: '{valor}'")
    
    return None

# ============================================================
# VALIDAÇÕES
# ============================================================
def validar_usuario_empresa(usuario_id, empresa_id):
    """Valida se usuário pertence à empresa"""
    from models import Usuario
    usuario = Usuario.query.filter_by(id=usuario_id, empresa_id=empresa_id).first()
    return usuario is not None

def verificar_arquivo_duplicado(empresa_id, hash_arquivo):
    """Verifica se arquivo já foi importado"""
    if not hash_arquivo:
        return False
    try:
        arquivo = ArquivoImportado.query.filter_by(
            empresa_id=empresa_id,
            hash_arquivo=hash_arquivo,
            ativo=True
        ).first()
        return arquivo is not None
    except:
        return False

# ============================================================
# SALVAR ARQUIVO IMPORTADO
# ============================================================
def salvar_arquivo_importado(empresa_id, usuario_id, nome_arquivo, tipo, hash_arquivo, registros):
    """Salva arquivo importado com criptografia e auditoria"""
    
    if not validar_usuario_empresa(usuario_id, empresa_id):
        raise ValueError("Usuário não pertence a esta empresa")
    
    if hash_arquivo and verificar_arquivo_duplicado(empresa_id, hash_arquivo):
        raise IntegrityError("Arquivo duplicado", None, None)
    
    # Calcular totais com Decimal
    total_registros = len(registros)
    total_valor = Decimal("0")
    for r in registros:
        try:
            valor = r.get("valor") or r.get("valor_bruto") or 0
            total_valor += to_decimal(valor)
        except:
            pass
    
    conteudo_json = criptografar_conteudo(registros)
    
    try:
        arquivo = ArquivoImportado(
            empresa_id=empresa_id,
            usuario_id=usuario_id,
            nome_arquivo=nome_arquivo,
            tipo_arquivo=tipo,
            hash_arquivo=hash_arquivo,
            total_registros=total_registros,
            total_valor=total_valor,
            conteudo_json=conteudo_json,
            status="processado",
            caminho_arquivo=f"/uploads/{nome_arquivo}",
        )
        
        db.session.add(arquivo)
        db.session.flush()
        
        try:
            log = LogAuditoria(
                usuario_id=usuario_id,
                empresa_id=empresa_id,
                acao="arquivo_importado",
                detalhes=f"Nome: {nome_arquivo}, Tipo: {tipo}, Registros: {total_registros}",
                ip=None,
                criado_em=datetime.now(timezone.utc)
            )
            db.session.add(log)
        except Exception as log_err:
            logger.warning(f"Erro ao salvar log de auditoria: {str(log_err)}")
        
        db.session.commit()
        logger.info(f"✅ Arquivo salvo: id={arquivo.id}, nome={nome_arquivo}, empresa={empresa_id}")
        return arquivo.id
        
    except IntegrityError as e:
        db.session.rollback()
        logger.warning(f"⚠️ Arquivo duplicado ou erro de integridade: {nome_arquivo}, erro={str(e)}")
        raise
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error(f"❌ Erro de banco ao salvar arquivo {nome_arquivo}: {str(e)}")
        raise
    except Exception as e:
        db.session.rollback()
        logger.error(f"❌ Erro desconhecido ao salvar arquivo {nome_arquivo}: {str(e)}")
        raise

# ============================================================
# LISTAR ARQUIVOS IMPORTADOS (COM PAGINAÇÃO)
# ============================================================
def listar_arquivos_importados(empresa_id: int, page=1, per_page=50):
    """Lista arquivos com paginação - usando getattr para segurança"""
    
    try:
        pagination = ArquivoImportado.query.filter_by(empresa_id=empresa_id, ativo=True)\
            .order_by(ArquivoImportado.criado_em.desc())\
            .paginate(page=page, per_page=per_page, error_out=False)
        
        return {
            "page": page,
            "per_page": per_page,
            "total": pagination.total,
            "pages": pagination.pages,
            "arquivos": [{
                "id": a.id,
                "nome_arquivo": a.nome_arquivo,
                "tipo": getattr(a, 'tipo_arquivo', 'desconhecido'),
                "hash": getattr(a, 'hash_arquivo', None),
                "total_registros": getattr(a, 'total_registros', 0),
                "total_valor": str(getattr(a, 'total_valor', 0)),
                "status": getattr(a, 'status', 'pendente'),
                "created_at": a.criado_em.strftime("%d/%m/%Y %H:%M") if a.criado_em else ""
            } for a in pagination.items]
        }
    except Exception as e:
        logger.error(f"Erro ao listar arquivos: {str(e)}")
        return {
            "page": page,
            "per_page": per_page,
            "total": 0,
            "pages": 0,
            "arquivos": []
        }

# ============================================================
# BUSCAR ARQUIVO POR ID
# ============================================================
def buscar_arquivo_por_id(arquivo_id, empresa_id):
    """Busca arquivo por ID com descriptografia segura"""
    
    try:
        arquivo = ArquivoImportado.query.filter_by(
            id=arquivo_id,
            empresa_id=empresa_id,
            ativo=True
        ).first()
        
        if not arquivo:
            return None
        
        try:
            registros = descriptografar_conteudo(getattr(arquivo, 'conteudo_json', None))
        except Exception as e:
            logger.error(f"Erro ao descriptografar arquivo {arquivo_id}: {str(e)}")
            registros = []
        
        return {
            "id": arquivo.id,
            "nome_arquivo": arquivo.nome_arquivo,
            "tipo": getattr(arquivo, 'tipo_arquivo', 'desconhecido'),
            "status": getattr(arquivo, 'status', 'pendente'),
            "total_registros": getattr(arquivo, 'total_registros', 0),
            "total_valor": str(getattr(arquivo, 'total_valor', 0)),
            "created_at": arquivo.criado_em.strftime("%d/%m/%Y %H:%M") if arquivo.criado_em else "",
            "conteudo_json": getattr(arquivo, 'conteudo_json', None),
            "registros": registros,
        }
    except Exception as e:
        logger.error(f"Erro ao buscar arquivo {arquivo_id}: {str(e)}")
        return None

# ============================================================
# SALVAR VENDAS (mov_adquirente) - CORRIGIDO
# ============================================================
def salvar_vendas(registros, empresa_id, arquivo_id=None):
    """
    Salva registros de vendas na tabela mov_adquirente.
    
    ✅ CORREÇÕES:
    - Converte datas de string para objeto date
    - Define tipo_pagamento (cartao/pix/boleto/outros)
    - Resolve adquirente por nome se necessário
    """
    if not registros:
        return 0
    
    salvos = 0
    for r in registros:
        try:
            # ✅ Converter data_venda de string para date
            data_venda = to_date(r.get('data') or r.get('data_venda'))
            if not data_venda:
                logger.warning(f"⚠️ Venda sem data válida, pulando: {r}")
                continue
            
            # ✅ Converter data_prevista se existir
            data_prevista = to_date(r.get('data_prevista') or r.get('data_prevista_pagamento'))
            
            # ✅ Resolver adquirente_id por nome se necessário
            adquirente_valor = r.get('adquirente_id') or r.get('adquirente')
            adquirente_id = resolver_adquirente_id(adquirente_valor, empresa_id)
            
            # ✅ Inferir tipo_pagamento se não estiver definido
            tipo_pagamento = r.get('tipo_pagamento')
            if not tipo_pagamento:
                produto = str(r.get('produto') or '').lower()
                bandeira = str(r.get('bandeira') or '').lower()
                if 'pix' in produto or bandeira == 'pix':
                    tipo_pagamento = 'pix'
                elif 'boleto' in produto:
                    tipo_pagamento = 'boleto'
                else:
                    tipo_pagamento = 'cartao'  # Default
            
            mov = MovAdquirente(
                empresa_id=empresa_id,
                arquivo_origem=str(arquivo_id)[:255] if arquivo_id else None,
                
                # ✅ Datas convertidas corretamente
                data_venda=data_venda,
                data_prevista_pagamento=data_prevista,
                
                # Identificadores
                nsu=str(r.get('nsu') or '')[:50] if r.get('nsu') else None,
                autorizacao=str(r.get('autorizacao') or '')[:50] if r.get('autorizacao') else None,
                
                # Produto/Bandeira
                bandeira=str(r.get('bandeira') or '')[:50] if r.get('bandeira') else None,
                produto=str(r.get('produto') or 'Venda')[:50],
                parcela=int(r.get('parcela') or 1) if r.get('parcela') else 1,
                total_parcelas=int(r.get('total_parcelas') or 1) if r.get('total_parcelas') else 1,
                
                # Valores com Decimal seguro
                valor_bruto=to_decimal(r.get('valor_bruto') or r.get('valor')),
                taxa_cobrada=to_decimal(r.get('taxa') or r.get('taxa_cobrada')),
                valor_liquido=to_decimal(r.get('valor_liquido')),
                
                # ✅ Chave estrangeira resolvida
                adquirente_id=adquirente_id,
                
                # ✅ NOVO: Tipo de pagamento
                tipo_pagamento=tipo_pagamento,
                
                # Conciliação (padrão)
                valor_conciliado=Decimal("0"),
                status_conciliacao="pendente",
            )
            db.session.add(mov)
            salvos += 1
        except Exception as e:
            logger.warning(f"Erro ao salvar venda: {str(e)}, registro={r}")
            continue
    
    try:
        db.session.commit()
        logger.info(f"✅ {salvos} vendas salvas para empresa {empresa_id}")
        return salvos
    except Exception as e:
        db.session.rollback()
        logger.error(f"❌ Erro ao commitar vendas: {str(e)}")
        raise

# ============================================================
# SALVAR RECEBIMENTOS (mov_banco) - CORRIGIDO
# ============================================================
def salvar_recebimentos(registros, empresa_id, arquivo_id=None):
    """
    Salva registros de recebimentos na tabela mov_banco.
    
    ✅ CORREÇÃO: Converte datas de string para objeto date
    """
    if not registros:
        return 0
    
    salvos = 0
    for r in registros:
        try:
            # ✅ Converter data_movimento de string para date
            data_movimento = to_date(r.get('data') or r.get('data_movimento'))
            if not data_movimento:
                logger.warning(f"⚠️ Recebimento sem data válida, pulando: {r}")
                continue
            
            mov = MovBanco(
                empresa_id=empresa_id,
                arquivo_origem=str(arquivo_id)[:255] if arquivo_id else None,
                
                # ✅ Data convertida corretamente
                data_movimento=data_movimento,
                
                # Campos opcionais
                documento=str(r.get('documento') or r.get('nsu') or '')[:100],
                banco=str(r.get('banco') or '')[:50],
                
                # Valor com Decimal seguro
                valor=to_decimal(r.get('valor')),
                
                # Status padrão
                valor_conciliado=Decimal("0"),
                conciliado=False,
            )
            db.session.add(mov)
            salvos += 1
        except Exception as e:
            logger.warning(f"Erro ao salvar recebimento: {str(e)}, registro={r}")
            continue
    
    try:
        db.session.commit()
        logger.info(f"✅ {salvos} recebimentos salvos para empresa {empresa_id}")
        return salvos
    except Exception as e:
        db.session.rollback()
        logger.error(f"❌ Erro ao commitar recebimentos: {str(e)}")
        raise

# ============================================================
# LIMPEZA DE ARQUIVOS ANTIGOS
# ============================================================
def limpar_arquivos_antigos(empresa_id=None, dias_retencao=90):
    """Remove arquivos mais antigos que X dias (soft delete)"""
    
    from datetime import timedelta
    cutoff = datetime.now(timezone.utc) - timedelta(days=dias_retencao)
    
    query = ArquivoImportado.query.filter(ArquivoImportado.criado_em < cutoff)
    
    if empresa_id:
        query = query.filter_by(empresa_id=empresa_id)
    
    # Soft delete: marca como inativo em vez de remover
    count = query.update({ArquivoImportado.ativo: False}, synchronize_session=False)
    db.session.commit()
    
    logger.info(f"🧹 Limpeza concluída: {count} arquivos marcados como inativos (>{dias_retencao} dias)")
    
    return count
