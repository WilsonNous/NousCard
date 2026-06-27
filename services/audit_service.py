from models.base import db
from models.log_auditoria import LogAuditoria


class AuditService:

    @staticmethod
    def registrar(
        usuario_id=None,
        empresa_id=None,
        acao=None,
        detalhes=None,
        entidade=None,
        entidade_id=None,
        payload=None,
        correlation_id=None,
        nivel="info",
        status="success",
        ip=None,
        user_agent=None,
        duracao_ms=None
    ):

        log = LogAuditoria(
            usuario_id=usuario_id,
            empresa_id=empresa_id,
            acao=acao,
            detalhes=detalhes,
            entidade=entidade,
            entidade_id=entidade_id,
            payload_json=payload,
            correlation_id=correlation_id,
            nivel=nivel,
            status=status,
            ip=ip,
            user_agent=user_agent,
            duracao_ms=duracao_ms
        )

        db.session.add(log)

        db.session.flush()

        log.hash_registro = log.gerar_hash_integridade()

        return log