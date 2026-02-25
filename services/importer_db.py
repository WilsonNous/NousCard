from models import db, ArquivoImportado, LogAuditoria
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
    if not os.getenv("ENCRYPTION_KEY"):
        import json
        return json.dumps(registros, ensure_ascii=False)
    
    f = Fernet(os.getenv("ENCRYPTION_KEY"))
    import json
    conteudo = json.dumps(registros, ensure_ascii=False)
    return f.encrypt(conteudo.encode()).decode()

def descriptografar_conteudo(conteudo_criptografado):
    """Descriptografa registros JSON do banco"""
    if not conteudo_criptografado:
        return []
    
    if not os.getenv("ENCRYPTION_KEY"):
        import json
        try:
            return json.loads(conteudo_criptografado)
        except:
            return []
    
    f = Fernet(os.getenv("ENCRYPTION_KEY"))
    conteudo = f.decrypt(conteudo_criptografado.encode()).decode()
    import json
    return json.loads(conteudo)

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
    arquivo = ArquivoImportado.query.filter_by(
        empresa_id=empresa_id,
        hash_arquivo=hash_arquivo
    ).first()
    return arquivo is not None

# ============================================================
# SALVAR ARQUIVO IMPORTADO
# ============================================================
def salvar_arquivo_importado(empresa_id, usuario_id, nome_arquivo, tipo, hash_arquivo, registros):
    """Salva arquivo importado com criptografia e auditoria"""
    
    # Validar usuário × empresa
    if not validar_usuario_empresa(usuario_id, empresa_id):
        raise ValueError("Usuário não pertence a esta empresa")
    
    # Verificar duplicata
    if verificar_arquivo_duplicado(empresa_id, hash_arquivo):
        raise IntegrityError("Arquivo duplicado", None, None)
    
    # Calcular total com Decimal
    total_registros = len(registros)
    total_valor = Decimal("0")
    for r in registros:
        try:
            valor = Decimal(str(r.get("valor", 0)))
            total_valor += valor
        except:
            pass
    
    # Criptografar conteúdo
    conteudo_json = criptografar_conteudo(registros)
    
    try:
        # Criar registro ORM
        arquivo = ArquivoImportado(
            empresa_id=empresa_id,
            usuario_id=usuario_id,
            nome_arquivo=nome_arquivo,
            tipo=tipo,
            hash_arquivo=hash_arquivo,
            total_registros=total_registros,
            total_valor=total_valor,
            conteudo_json=conteudo_json
        )
        
        db.session.add(arquivo)
        db.session.flush()
        
        # Log de auditoria
        log = LogAuditoria(
            usuario_id=usuario_id,
            empresa_id=empresa_id,
            acao="arquivo_importado",
            detalhes=f"Nome: {nome_arquivo}, Tipo: {tipo}, Registros: {total_registros}",
            ip=None,
            criado_em=datetime.now(timezone.utc)
        )
        db.session.add(log)
        
        db.session.commit()
        
        logger.info(f"Arquivo salvo: id={arquivo.id}, nome={nome_arquivo}, empresa={empresa_id}")
        
        return arquivo.id
        
    except IntegrityError as e:
        db.session.rollback()
        logger.warning(f"Arquivo duplicado: {nome_arquivo}, empresa={empresa_id}")
        raise
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error(f"Erro de banco ao salvar arquivo {nome_arquivo}: {str(e)}")
        raise
    except Exception as e:
        db.session.rollback()
        logger.error(f"Erro desconhecido ao salvar arquivo {nome_arquivo}: {str(e)}")
        raise

# ============================================================
# LISTAR ARQUIVOS IMPORTADOS (COM PAGINAÇÃO)
# ============================================================
def listar_arquivos_importados(empresa_id: int, page=1, per_page=50):
    """Lista arquivos com paginação"""
    
    pagination = ArquivoImportado.query.filter_by(empresa_id=empresa_id)\
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
            "tipo": a.tipo,
            "hash": a.hash_arquivo,
            "total_registros": a.total_registros,
            "total_valor": str(a.total_valor),
            "created_at": a.criado_em.strftime("%d/%m/%Y %H:%M") if a.criado_em else ""
        } for a in pagination.items]
    }

# ============================================================
# BUSCAR ARQUIVO POR ID
# ============================================================
def buscar_arquivo_por_id(arquivo_id, empresa_id):
    """Busca arquivo por ID com descriptografia"""
    
    arquivo = ArquivoImportado.query.filter_by(
        id=arquivo_id,
        empresa_id=empresa_id
    ).first()
    
    if not arquivo:
        return None
    
    # Descriptografar conteúdo
    try:
        registros = descriptografar_conteudo(arquivo.conteudo_json)
    except Exception as e:
        logger.error(f"Erro ao descriptografar arquivo {arquivo_id}: {str(e)}")
        registros = []
    
    return {
        "id": arquivo.id,
        "nome_arquivo": arquivo.nome_arquivo,
        "tipo": arquivo.tipo,
        "total_registros": arquivo.total_registros,
        "total_valor": str(arquivo.total_valor),
        "created_at": arquivo.criado_em.strftime("%d/%m/%Y %H:%M") if arquivo.criado_em else "",
        "conteudo_json": arquivo.conteudo_json,
        "registros": registros,
    }

# ============================================================
# LIMPEZA DE ARQUIVOS ANTIGOS
# ============================================================
def limpar_arquivos_antigos(empresa_id=None, dias_retencao=90):
    """Remove arquivos mais antigos que X dias"""
    
    from datetime import timedelta
    cutoff = datetime.now(timezone.utc) - timedelta(days=dias_retencao)
    
    query = ArquivoImportado.query.filter(ArquivoImportado.criado_em < cutoff)
    
    if empresa_id:
        query = query.filter_by(empresa_id=empresa_id)
    
    count = query.count()
    query.delete()
    db.session.commit()
    
    logger.info(f"Limpeza concluída: {count} arquivos removidos (>{dias_retencao} dias)")
    
    return count
