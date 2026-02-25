# ============================================================
#  MODELS • LogAuditoria (Auditoria e Compliance)
#  Compatível com SQLAlchemy 1.4.x + Flask-SQLAlchemy 3.0.x
# ============================================================

from .base import db, TimestampMixin
from datetime import datetime, timezone

class LogAuditoria(db.Model, TimestampMixin):
    """
    Registra ações de usuários para auditoria e compliance (LGPD).
    
    Tipos de ações registradas:
    - login_success / login_fail
    - logout
    - arquivo_importado
    - conciliacao_executada
    - empresa_criada / empresa_editada / empresa_excluida
    - usuario_criado / usuario_editado / usuario_excluido
    - dados_exportados
    - senha_alterada
    - acesso_negado
    
    Nota: Não herda SoftDeleteMixin (logs nunca são deletados)
          e não herda MultiTenantMixin (empresa_id é nullable).
    """
    __tablename__ = "log_auditoria"

    id = db.Column(db.Integer, primary_key=True)
    
    # ============================================================
    # CHAVES ESTRANGEIRAS (nullable para ações do sistema)
    # ============================================================
    
    usuario_id = db.Column(
        db.Integer,
        db.ForeignKey("usuarios.id", ondelete="SET NULL"),
        nullable=True,  # Ações do sistema podem não ter usuário
        index=True
    )
    
    empresa_id = db.Column(
        db.Integer,
        db.ForeignKey("empresas.id", ondelete="CASCADE"),
        nullable=True,  # Master actions podem não ter empresa
        index=True
    )
    
    # ============================================================
    # DADOS DO LOG
    # ============================================================
    
    # Ação realizada (padronizar nomes em snake_case)
    acao = db.Column(db.String(50), nullable=False, index=True)
    
    # Detalhes em JSON ou texto livre
    detalhes = db.Column(db.Text, nullable=True)
    
    # IP do cliente (IPv4 ou IPv6)
    ip = db.Column(db.String(45), nullable=True)  # IPv6 tem até 45 chars
    
    # User-Agent para auditoria de dispositivo
    user_agent = db.Column(db.String(255), nullable=True)
    
    # Nível de severidade (info, warning, error, critical)
    nivel = db.Column(
        db.String(20),
        default="info",
        index=True
    )
    
    # Duração da ação em ms (para performance tracking)
    duracao_ms = db.Column(db.Integer, nullable=True)
    
    # Status da operação (success, failure, partial)
    status = db.Column(
        db.String(20),
        default="success",
        index=True
    )
    
    # Hash do registro para integridade (anti-tampering)
    hash_registro = db.Column(db.String(64), nullable=True, index=True)

    # ============================================================
    # RELACIONAMENTOS (com back_populates CONSISTENTE)
    # ============================================================
    
    # ✅ Usuario: back_populates deve bater com Usuario.logs_auditoria
    usuario = db.relationship(
        "Usuario",
        back_populates="logs_auditoria",  # ✅ Deve existir em Usuario
        lazy=True
    )
    
    # ✅ Empresa: back_populates deve bater com Empresa.logs_auditoria
    empresa = db.relationship(
        "Empresa",
        back_populates="logs_auditoria",  # ✅ Deve existir em Empresa
        lazy=True
    )

    # ============================================================
    # ÍNDICES PARA PERFORMANCE
    # ============================================================
    
    __table_args__ = (
        db.Index('idx_log_empresa_data', 'empresa_id', 'criado_em'),
        db.Index('idx_log_usuario_data', 'usuario_id', 'criado_em'),
        db.Index('idx_log_acao_data', 'acao', 'criado_em'),
        db.Index('idx_log_status', 'status'),
        db.Index('idx_log_nivel', 'nivel'),
    )

    # ============================================================
    # MÉTODOS ÚTEIS
    # ============================================================
    
    @property
    def acao_formatada(self) -> str:
        """Retorna ação formatada para exibição (snake_case → Title Case)"""
        return self.acao.replace("_", " ").title()
    
    @property
    def esta_sucesso(self) -> bool:
        """Verifica se ação foi bem-sucedida"""
        return self.status == "success"
    
    @property
    def esta_falha(self) -> bool:
        """Verifica se ação falhou"""
        return self.status in ("failure", "error")
    
    def gerar_hash_integridade(self) -> str:
        """
        Gera hash SHA256 do registro para prevenir tampering.
        Útil para compliance e auditoria forense.
        """
        import hashlib
        conteudo = f"{self.id}:{self.acao}:{self.criado_em}:{self.detalhes}"
        return hashlib.sha256(conteudo.encode()).hexdigest()
    
    def validar_integridade(self) -> bool:
        """Verifica se hash do registro corresponde ao conteúdo atual"""
        if not self.hash_registro:
            return False
        return self.gerar_hash_integridade() == self.hash_registro

    # ============================================================
    # MÉTODOS DE CLASSE (QUERIES COMUNS)
    # ============================================================
    
    @classmethod
    def logar_acao(cls, db_session, usuario_id, empresa_id, acao, detalhes=None, 
                   ip=None, user_agent=None, nivel="info", status="success", duracao_ms=None):
        """
        Método conveniente para criar log de auditoria.
        
        Args:
            db_session: Sessão do SQLAlchemy
            usuario_id: ID do usuário (nullable)
            empresa_id: ID da empresa (nullable)
            acao: Nome da ação (ex: "login_success")
            detalhes: Detalhes em texto ou JSON
            ip: IP do cliente
            user_agent: User-Agent do browser
            nivel: Nível de severidade (info, warning, error)
            status: Status da operação (success, failure)
            duracao_ms: Duração em milissegundos
            
        Returns:
            LogAuditoria: Instância criada (não commitada)
        """
        log = cls(
            usuario_id=usuario_id,
            empresa_id=empresa_id,
            acao=acao,
            detalhes=detalhes,
            ip=ip,
            user_agent=user_agent,
            nivel=nivel,
            status=status,
            duracao_ms=duracao_ms
        )
        log.hash_registro = log.gerar_hash_integridade()
        
        db_session.add(log)
        return log
    
    @classmethod
    def buscar_por_empresa(cls, empresa_id, dias=30, limite=100):
        """
        Busca logs de uma empresa nos últimos X dias.
        
        Args:
            empresa_id: ID da empresa
            dias: Período em dias (default: 30)
            limite: Máximo de registros (default: 100)
            
        Returns:
            Query de LogAuditoria
        """
        from datetime import timedelta
        data_inicio = datetime.now(timezone.utc) - timedelta(days=dias)
        
        return cls.query.filter(
            cls.empresa_id == empresa_id,
            cls.criado_em >= data_inicio
        ).order_by(cls.criado_em.desc()).limit(limite)
    
    @classmethod
    def buscar_por_usuario(cls, usuario_id, dias=30, limite=100):
        """
        Busca logs de um usuário nos últimos X dias.
        
        Args:
            usuario_id: ID do usuário
            dias: Período em dias (default: 30)
            limite: Máximo de registros (default: 100)
            
        Returns:
            Query de LogAuditoria
        """
        from datetime import timedelta
        data_inicio = datetime.now(timezone.utc) - timedelta(days=dias)
        
        return cls.query.filter(
            cls.usuario_id == usuario_id,
            cls.criado_em >= data_inicio
        ).order_by(cls.criado_em.desc()).limit(limite)
    
    @classmethod
    def buscar_acoes_suspeitas(cls, empresa_id=None, usuario_id=None, limite=50):
        """
        Busca ações potencialmente suspeitas (múltiplas falhas, acessos negados, etc.).
        
        Args:
            empresa_id: Filtrar por empresa (opcional)
            usuario_id: Filtrar por usuário (opcional)
            limite: Máximo de registros
            
        Returns:
            Query de LogAuditoria
        """
        query = cls.query.filter(
            cls.nivel.in_(["warning", "error", "critical"]),
        )
        
        if empresa_id:
            query = query.filter(cls.empresa_id == empresa_id)
        if usuario_id:
            query = query.filter(cls.usuario_id == usuario_id)
        
        return query.order_by(cls.criado_em.desc()).limit(limite)
    
    @classmethod
    def limpar_logs_antigos(cls, db_session, dias_retencao=365):
        """
        Remove logs mais antigos que X dias (compliance LGPD).
        
        Args:
            db_session: Sessão do SQLAlchemy
            dias_retencao: Período de retenção em dias (default: 1 ano)
            
        Returns:
            int: Número de registros removidos
        """
        from datetime import timedelta
        data_corte = datetime.now(timezone.utc) - timedelta(days=dias_retencao)
        
        count = cls.query.filter(cls.criado_em < data_corte).count()
        cls.query.filter(cls.criado_em < data_corte).delete(synchronize_session=False)
        db_session.commit()
        
        return count

    # ============================================================
    # UTILITÁRIOS PARA APIs
    # ============================================================
    
    def to_dict(self) -> dict:
        """Serializa para dict (útil para APIs)"""
        return {
            "id": self.id,
            "usuario_id": self.usuario_id,
            "usuario_nome": self.usuario.nome if self.usuario else None,
            "empresa_id": self.empresa_id,
            "acao": self.acao,
            "acao_formatada": self.acao_formatada,
            "detalhes": self.detalhes,
            "ip": self.ip,
            "user_agent": self.user_agent,
            "nivel": self.nivel,
            "status": self.status,
            "duracao_ms": self.duracao_ms,
            "criado_em": self.criado_em.isoformat() if self.criado_em else None,
            "hash_registro": self.hash_registro,
            "integridade_valida": self.validar_integridade(),
        }
    
    def to_public_dict(self) -> dict:
        """Versão segura para exposição pública (sem dados sensíveis)"""
        data = self.to_dict()
        # Remover IP completo para privacidade (manter apenas prefixo)
        if data["ip"]:
            data["ip"] = data["ip"].rsplit(".", 1)[0] + ".xxx"
        return data

    # ============================================================
    # REPRESENTAÇÃO
    # ============================================================
    
    def __repr__(self):
        return f"<LogAuditoria id={self.id} acao={self.acao} usuario={self.usuario_id} empresa={self.empresa_id}>"
