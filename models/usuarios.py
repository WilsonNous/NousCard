# ============================================================
#  MODELS • Usuario (Autenticação e Acesso)
#  Compatível com SQLAlchemy 1.4.x + Flask-SQLAlchemy 3.0.x
# ============================================================

from .base import db, TimestampMixin, SoftDeleteMixin
from datetime import datetime, timezone
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin

class Usuario(db.Model, UserMixin, TimestampMixin, SoftDeleteMixin):
    """
    Representa um usuário do sistema.
    
    Tipos de acesso:
    - master: Acesso global a todas as empresas (admin do sistema)
    - admin: Acesso administrativo à sua empresa
    - user: Acesso padrão à sua empresa
    
    Nota: empresa_id é nullable para usuários master.
    """
    __tablename__ = "usuarios"

    id = db.Column(db.Integer, primary_key=True)
    
    # ✅ empresa_id manual (nullable para master users)
    # Se fosse BaseMixin, seria nullable=False por padrão
    empresa_id = db.Column(
        db.Integer,
        db.ForeignKey("empresas.id", ondelete="CASCADE"),
        nullable=True,  # ✅ Master users não têm empresa vinculada
        index=True
    )

    # ============================================================
    # DADOS DO USUÁRIO
    # ============================================================
    
    nome = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(150), nullable=False, unique=True, index=True)
    senha_hash = db.Column(db.String(255), nullable=False)

    # Permissões
    admin = db.Column(db.Boolean, default=False, index=True)
    master = db.Column(db.Boolean, default=False, index=True)

    # ============================================================
    # SEGURANÇA E AUDITORIA
    # ============================================================
    
    # Último login bem-sucedido
    ultimo_login = db.Column(db.DateTime(timezone=True), nullable=True)
    
    # Proteção contra brute force
    tentativas_login_falhas = db.Column(db.Integer, default=0)
    bloqueado_ate = db.Column(db.DateTime(timezone=True), nullable=True)
    
    # Recuperação de senha
    token_recuperacao = db.Column(db.String(255), nullable=True, unique=True)
    token_expiracao = db.Column(db.DateTime(timezone=True), nullable=True)
    
    # Preferências (JSON para flexibilidade)
    preferencias = db.Column(db.JSON, nullable=True, default=dict)

    # ============================================================
    # RELACIONAMENTOS (com back_populates CONSISTENTE)
    # ============================================================
    
    # ✅ Empresa: back_populates deve bater com Empresa.usuarios
    empresa = db.relationship(
        "Empresa",
        back_populates="usuarios",  # ✅ Deve existir em Empresa
        lazy="select",
        foreign_keys=[empresa_id]
    )
    
    # ⚠️ ARQUIVOS IMPORTADOS: COMENTADO para evitar conflito com ArquivoImportado minimalista
    # Para acessar arquivos de um usuário, use query direta:
    # ArquivoImportado.query.filter_by(usuario_id=usuario.id).all()
    #
    # arquivos_importados = db.relationship(
    #     "ArquivoImportado",
    #     back_populates="usuario",
    #     lazy="dynamic",
    #     cascade="all, delete-orphan"
    # )
    
    # ✅ Logs de auditoria deste usuário
    logs_auditoria = db.relationship(
        "LogAuditoria",
        back_populates="usuario",
        lazy="dynamic",
        cascade="all, delete-orphan"
    )
    
    # ✅ Conciliações manuais realizadas por este usuário
    conciliacoes = db.relationship(
        "Conciliacao",
        back_populates="usuario",  # ✅ Deve bater com Conciliacao.usuario.back_populates
        lazy="dynamic",
        cascade="all, delete-orphan"
    )

    # ============================================================
    # ÍNDICES PARA PERFORMANCE
    # ============================================================
    
    __table_args__ = (
        db.Index('idx_usuario_email', 'email', unique=True),
        db.Index('idx_usuario_empresa_ativo', 'empresa_id', 'ativo'),
        db.Index('idx_usuario_master', 'master', 'ativo'),
    )

    # ============================================================
    # MÉTODOS DE SENHA (Flask-Login compatible)
    # ============================================================
    
    def set_password(self, password: str):
        """Gera hash seguro para a senha"""
        self.senha_hash = generate_password_hash(password, method='pbkdf2:sha256', salt_length=16)
    
    def check_password(self, password: str) -> bool:
        """Verifica se a senha corresponde ao hash"""
        return check_password_hash(self.senha_hash, password)
    
    def force_password_reset(self):
        """Invalida a senha atual, forçando redefinição"""
        self.senha_hash = f"!reset_{datetime.now(timezone.utc).isoformat()}"
        self.token_recuperacao = None
        self.token_expiracao = None

    # ============================================================
    # MÉTODOS DE SEGURANÇA
    # ============================================================
    
    def registrar_tentativa_falha(self, max_tentativas: int = 5, lockout_minutes: int = 15):
        """
        Registra tentativa de login falha e bloqueia se exceder limite.
        
        Args:
            max_tentativas: Número máximo de tentativas antes do bloqueio
            lockout_minutes: Tempo de bloqueio em minutos
        """
        self.tentativas_login_falhas += 1
        
        if self.tentativas_login_falhas >= max_tentativas:
            self.bloqueado_ate = datetime.now(timezone.utc).replace(
                microsecond=0
            ) + timezone.timedelta(minutes=lockout_minutes)
        
        return self.bloqueado_ate is not None
    
    def resetar_tentativas_falhas(self):
        """Reseta contador de tentativas após login bem-sucedido"""
        self.tentativas_login_falhas = 0
        self.bloqueado_ate = None
    
    def esta_bloqueado(self) -> bool:
        """Verifica se usuário está temporariamente bloqueado"""
        if not self.bloqueado_ate:
            return False
        return datetime.now(timezone.utc) < self.bloqueado_ate
    
    def gerar_token_recuperacao(self, horas_validade: int = 2) -> str:
        """
        Gera token seguro para recuperação de senha.
        
        Args:
            horas_validade: Tempo de validade do token em horas
            
        Returns:
            str: Token gerado (salvar em self.token_recuperacao)
        """
        import secrets
        token = secrets.token_urlsafe(32)
        self.token_recuperacao = token
        self.token_expiracao = datetime.now(timezone.utc).replace(
            microsecond=0
        ) + timezone.timedelta(hours=horas_validade)
        return token
    
    def validar_token_recuperacao(self, token: str) -> bool:
        """
        Verifica se token de recuperação é válido e não expirou.
        
        Args:
            token: Token a validar
            
        Returns:
            bool: True se token for válido
        """
        if not self.token_recuperacao or not self.token_expiracao:
            return False
        
        if self.token_recuperacao != token:
            return False
        
        if datetime.now(timezone.utc) > self.token_expiracao:
            self.token_recuperacao = None
            self.token_expiracao = None
            return False
        
        return True
    
    def invalidar_token_recuperacao(self):
        """Invalida token de recuperação após uso"""
        self.token_recuperacao = None
        self.token_expiracao = None

    # ============================================================
    # PROPRIEDADES E MÉTODOS DE ACESSO
    # ============================================================
    
    @property
    def is_master(self) -> bool:
        """Compatível com Flask-Login: usuário é master?"""
        return bool(self.master)
    
    @property
    def is_admin(self) -> bool:
        """Compatível com Flask-Login: usuário é admin?"""
        return bool(self.admin)
    
    @property
    def is_empresa_user(self) -> bool:
        """Usuário está vinculado a uma empresa específica?"""
        return self.empresa_id is not None and not self.master
    
    @property
    def nome_exibicao(self) -> str:
        """Nome para exibição na UI (fallback para email)"""
        return self.nome or self.email.split('@')[0]
    
    def pode_acessar_empresa(self, empresa_id: int) -> bool:
        """
        Verifica se usuário pode acessar uma empresa específica.
        
        Args:
            empresa_id: ID da empresa a verificar
            
        Returns:
            bool: True se usuário tem acesso
        """
        if self.master:
            return True  # Master acessa todas
        return self.empresa_id == empresa_id

    # ============================================================
    # Flask-Login: OVERRIDES
    # ============================================================
    
    def is_active(self) -> bool:
        """
        Flask-Login: usuário está ativo e não bloqueado?
        
        Returns:
            bool: True se usuário pode fazer login
        """
        # Verificar soft delete
        if not getattr(self, 'ativo', True):
            return False
        
        # Verificar bloqueio temporário
        if self.esta_bloqueado():
            return False
        
        return True
    
    def get_id(self) -> str:
        """Flask-Login: retorna ID como string"""
        return str(self.id)

    # ============================================================
    # UTILITÁRIOS PARA APIs
    # ============================================================
    
    def to_dict(self, include_sensitive: bool = False) -> dict:
        """
        Serializa usuário para dict (útil para APIs).
        
        Args:
            include_sensitive: Incluir dados sensíveis como email?
            
        Returns:
            dict: Dados do usuário (sem senha)
        """
        data = {
            "id": self.id,
            "nome": self.nome,
            "nome_exibicao": self.nome_exibicao,
            "admin": self.admin,
            "master": self.master,
            "empresa_id": self.empresa_id,
            "empresa_nome": self.empresa.nome if self.empresa else None,
            "ultimo_login": self.ultimo_login.isoformat() if self.ultimo_login else None,
            "criado_em": self.criado_em.isoformat() if self.criado_em else None,
            "ativo": getattr(self, 'ativo', True),
        }
        
        if include_sensitive:
            data["email"] = self.email
        
        return data
    
    def to_public_dict(self) -> dict:
        """Versão segura para exposição pública (sem dados sensíveis)"""
        return self.to_dict(include_sensitive=False)

    # ============================================================
    # REPRESENTAÇÃO
    # ============================================================
    
    def __repr__(self):
        return f"<Usuario id={self.id} email={self.email} master={self.master}>"
