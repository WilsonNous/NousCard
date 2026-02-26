from models import db, ArquivoImportado, LogAuditoria, MovAdquirente, MovBanco
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
import logging
import os
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
            import json
            return json.dumps(registros, ensure_ascii=False, default=str)
        
        # Remover aspas se existirem (compatibilidade)
        encryption_key = encryption_key.strip('"')
        
        f = Fernet(encryption_key.encode())
        import json
        conteudo = json.dumps(registros, ensure_ascii=False, default=str)
        return f.encrypt(conteudo.encode()).decode()
    except Exception as e:
        logger.error(f"Erro ao criptografar: {str(e)}")
        import json
        return json.dumps(registros, ensure_ascii=False, default=str)

def descriptografar_conteudo(conteudo_criptografado):
    """Descriptografa registros JSON do banco"""
    if not conteudo_criptografado:
        return []
    
    try:
        encryption_key = os.getenv("ENCRYPTION_KEY")
        if not encryption_key:
            import json
            return json.loads(conteudo_criptografado)
        
        # Remover aspas se existirem
        encryption_key = encryption_key.strip('"')
        
        f = Fernet(encryption_key.encode())
        conteudo = f.decrypt(conteudo_criptografado.encode()).decode()
        import json
        return json.loads(conteudo)
    except Exception as e:
        logger.error(f"Erro ao descriptografar: {str(e)}")
        return []

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
    
    # Validar usuário × empresa
    if not validar_usuario_empresa(usuario_id, empresa_id):
        raise ValueError("Usuário não pertence a esta empresa")
    
    # Verificar duplicata
    if hash_arquivo and verificar_arquivo_duplicado(empresa_id, hash_arquivo):
        raise IntegrityError("Arquivo duplicado", None, None)
    
    # Calcular totais com Decimal
    total_registros = len(registros)
    total_valor = Decimal("0")
    for r in registros:
        try:
            # Suporta tanto 'valor' quanto 'valor_bruto'
            valor = r.get("valor") or r.get("valor_bruto") or 0
            total_valor += Decimal(str(valor))
        except:
            pass
    
    # Criptografar conteúdo
    conteudo_json = criptografar_conteudo(registros)
    
    try:
        # Criar registro ORM com TODOS os campos que o modelo espera
        arquivo = ArquivoImportado(
            empresa_id=empresa_id,
            usuario_id=usuario_id,
            nome_arquivo=nome_arquivo,
            tipo_arquivo=tipo,  # ← Nome correto do campo
            hash_arquivo=hash_arquivo,
            total_registros=total_registros,
            total_valor=total_valor,
            conteudo_json=conteudo_json,
            status="processado",
            caminho_arquivo=f"/uploads/{nome_arquivo}",  # placeholder
            # Campos do mixin (se ainda não existirem, o SQLAlchemy ignora)
            # criado_em=datetime.now(timezone.utc),
            # ativo=True,
        )
        
        db.session.add(arquivo)
        db.session.flush()  # Garante que o ID seja gerado
        
        # Log de auditoria (não crítico - se falhar, não rollback do arquivo)
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
            # Não faz rollback por erro de log
        
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
                "tipo": getattr(a, 'tipo_arquivo', 'desconhecido'),  # ← Seguro
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
        
        # Descriptografar conteúdo com fallback
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
# SALVAR VENDAS (mov_adquirente)
# ============================================================
def salvar_vendas(registros, empresa_id, arquivo_id=None):
    """Salva registros de vendas na tabela mov_adquirente"""
    if not registros:
        return 0
    
    salvos = 0
    for r in registros:
        try:
            mov = MovAdquirente(
                empresa_id=empresa_id,
                arquivo_origem=arquivo_id,
                # Mapeamento flexível de colunas
                data_venda=r.get('data') or r.get('data_venda'),
                data_prevista_pagamento=r.get('data_prevista'),
                nsu=r.get('nsu'),
                autorizacao=r.get('autorizacao'),
                bandeira=r.get('bandeira'),
                produto=r.get('produto', 'Venda'),
                parcela=r.get('parcela', 1),
                total_parcelas=r.get('total_parcelas', 1),
                valor_bruto=Decimal(str(r.get('valor_bruto') or r.get('valor') or 0)),
                taxa_cobrada=Decimal(str(r.get('taxa') or r.get('taxa_cobrada') or 0)),
                valor_liquido=Decimal(str(r.get('valor_liquido') or 0)),
                adquirente_id=r.get('adquirente_id'),
                # Campos do mixin
                # criado_em=datetime.now(timezone.utc),
                # ativo=True,
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
# SALVAR RECEBIMENTOS (mov_banco)
# ============================================================
def salvar_recebimentos(registros, empresa_id, arquivo_id=None):
    """Salva registros de recebimentos na tabela mov_banco"""
    if not registros:
        return 0
    
    salvos = 0
    for r in registros:
        try:
            mov = MovBanco(
                empresa_id=empresa_id,
                arquivo_origem=arquivo_id,
                # Mapeamento flexível
                data_movimento=r.get('data') or r.get('data_movimento'),
                data_prevista=r.get('data_prevista'),
                documento=r.get('documento') or r.get('nsu'),
                banco=r.get('banco'),
                valor=Decimal(str(r.get('valor') or 0)),
                # Campos do mixin
                # criado_em=datetime.now(timezone.utc),
                # ativo=True,
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
