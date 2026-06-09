# routes/conciliacao_api.py - VERSÃO CORRIGIDA E COMPLETA

from flask import Blueprint, request, jsonify, g
from utils.auth_middleware import login_required
from services.conciliacao import executar_conciliacao  # ✅ CORREÇÃO: importar de concilia.py
from models import db, MovAdquirente, MovBanco, Conciliacao, LogAuditoria
from sqlalchemy.orm import joinedload
from sqlalchemy import func, case
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)

bp_conc = Blueprint("conciliacao_api", __name__, url_prefix="/api/v1/conciliacao")

# ============================================================
# 1️⃣ PROCESSAR CONCILIAÇÃO
# ============================================================
@bp_conc.route("/processar", methods=["POST"])
@login_required
def api_processar_conciliacao():
    empresa_id = g.user.empresa_id
    
    if not empresa_id:
        return jsonify({"status": "error", "message": "Usuário sem empresa vinculada"}), 400
    
    # ✅ NOVO: Suporte a filtro por tipo_pagamento
    data = request.json or {}
    tipo_pagamento = data.get('tipo_pagamento')  # 'pix', 'cartao', 'boleto', ou None para todos
    
    try:
        resultado = executar_conciliacao(
            empresa_id=empresa_id, 
            usuario_id=g.user.id,
            tipo_pagamento=tipo_pagamento  # ✅ Passar filtro para o serviço
        )
        
        # ✅ Log de auditoria com try/except isolado (não afeta resposta principal)
        try:
            log = LogAuditoria(
                usuario_id=g.user.id,
                empresa_id=empresa_id,
                acao="conciliacao_executada",
                detalhes=f"Conciliados: {resultado.get('conciliados', 0)}, tipo={tipo_pagamento or 'todos'}",
                ip=request.remote_addr,
                criado_em=datetime.now(timezone.utc)
            )
            db.session.add(log)
            db.session.commit()
        except Exception as log_err:
            # Não falhar a resposta por erro de log
            logger.warning(f"Erro ao logar auditoria (não crítico): {str(log_err)}")
            db.session.rollback()  # Apenas rollback do log, não da conciliação
        
        logger.info(f"✅ Conciliação: empresa={empresa_id}, usuario={g.user.id}, tipo={tipo_pagamento or 'todos'}")
        
        return jsonify({
            "status": "success",
            "message": "Conciliação executada com sucesso",
            "resultado": resultado
        }), 200
        
    except TimeoutError:
        logger.warning(f"⏱️ Timeout na conciliação: empresa={empresa_id}")
        return jsonify({
            "status": "error",
            "message": "Processamento demorou muito. Tente com menos dados ou um período menor."
        }), 408
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"❌ Erro na conciliação: empresa={empresa_id}, erro={str(e)}", exc_info=True)
        return jsonify({
            "status": "error",
            "message": "Erro ao processar conciliação. Tente novamente."
        }), 500

# ============================================================
# 2️⃣ STATUS GERAL (OTIMIZADO + FILTRO POR TIPO)
# ============================================================
@bp_conc.route("/status", methods=["GET"])
@login_required
def api_status_conciliacao():
    empresa_id = g.user.empresa_id
    
    # ✅ NOVO: Filtro por tipo_pagamento
    tipo_pagamento = request.args.get('tipo_pagamento')
    
    # Query base
    query_base = MovAdquirente.query.filter(MovAdquirente.empresa_id == empresa_id)
    
    # Aplicar filtro por tipo se especificado
    if tipo_pagamento and tipo_pagamento != 'todos':
        query_base = query_base.filter(MovAdquirente.tipo_pagamento == tipo_pagamento)
    
    # 1 query em vez de 5 para contar status
    totais_query = query_base.with_entities(
        func.sum(case((MovAdquirente.status_conciliacao == "conciliado", 1), else_=0)).label("conciliado"),
        func.sum(case((MovAdquirente.status_conciliacao == "parcial", 1), else_=0)).label("parcial"),
        func.sum(case((MovAdquirente.status_conciliacao == "pendente", 1), else_=0)).label("pendente"),
        func.sum(case((MovAdquirente.status_conciliacao == "nao_recebido", 1), else_=0)).label("nao_recebido")
    ).first()
    
    # Créditos sem origem (também filtrar por tipo se aplicável)
    query_recebimentos = MovBanco.query.filter(
        MovBanco.empresa_id == empresa_id,
        MovBanco.conciliado == False,
        MovBanco.valor > 0
    )
    
    creditos_sem_origem = query_recebimentos.count()
    
    return jsonify({
        "status": "success",
        "tipo_pagamento": tipo_pagamento or "todos",
        "totais": {
            "conciliado": totais_query.conciliado or 0,
            "parcial": totais_query.parcial or 0,
            "pendente": totais_query.pendente or 0,
            "nao_recebido": totais_query.nao_recebido or 0,
            "creditos_sem_origem": creditos_sem_origem
        }
    }), 200

# ============================================================
# 3️⃣ DETALHES (COM PAGINAÇÃO + FILTROS + DADOS DE RECEBIMENTO)
# ============================================================
@bp_conc.route("/detalhes", methods=["GET"])
@login_required
def api_detalhes_conciliacao():
    empresa_id = g.user.empresa_id
    
    # Paginação com validação
    page = max(1, request.args.get('page', 1, type=int))  # ✅ Garantir page >= 1
    per_page = min(request.args.get('per_page', 50, type=int), 100)  # Limitar a 100
    
    # ✅ NOVOS: Filtros adicionais
    status = request.args.get('status')
    tipo_pagamento = request.args.get('tipo_pagamento')
    data_inicio = request.args.get('data_inicio')  # YYYY-MM-DD
    data_fim = request.args.get('data_fim')
    
    # Query base com joinedload para evitar N+1
    query = MovAdquirente.query.options(
        joinedload(MovAdquirente.adquirente)
    ).filter(
        MovAdquirente.empresa_id == empresa_id,
        MovAdquirente.ativo == True
    )
    
    # Aplicar filtros
    if status and status != 'todos':
        query = query.filter(MovAdquirente.status_conciliacao == status)
    if tipo_pagamento and tipo_pagamento != 'todos':
        query = query.filter(MovAdquirente.tipo_pagamento == tipo_pagamento)
    if data_inicio:
        query = query.filter(MovAdquirente.data_venda >= data_inicio)
    if data_fim:
        query = query.filter(MovAdquirente.data_venda <= data_fim)
    
    # Ordenar por data (mais recente primeiro)
    query = query.order_by(MovAdquirente.data_venda.desc(), MovAdquirente.nsu.desc())
    
    # Paginar
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    
    def venda_json(v):
        # ✅ Buscar dados de recebimento conciliado (via tabela Conciliacao)
        valor_recebido = "0"
        data_recebimento = None
        banco_nome = None
        
        try:
            conc = Conciliacao.query.filter_by(
                mov_adquirente_id=v.id,
                ativo=True
            ).first()
            if conc and conc.mov_banco_id:
                mov_banco = MovBanco.query.get(conc.mov_banco_id)
                if mov_banco:
                    valor_recebido = str(mov_banco.valor or 0)
                    data_recebimento = str(mov_banco.data_movimento) if mov_banco.data_movimento else None
                    banco_nome = mov_banco.banco
        except:
            pass  # Fallback silencioso se não encontrar recebimento
        
        # Calcular diferença
        try:
            from decimal import Decimal
            diff = (Decimal(str(v.valor_liquido or 0)) - Decimal(valor_recebido))
            diferenca = str(diff)
        except:
            diferenca = "0"
        
        return {
            "id": v.id,
            "data_venda": str(v.data_venda) if v.data_venda else None,
            "data_prevista": str(v.data_prevista_pagamento) if v.data_prevista_pagamento else None,
            "nsu": v.nsu,
            "autorizacao": v.autorizacao,
            "valor_bruto": str(v.valor_bruto or 0),
            "valor_liquido": str(v.valor_liquido or 0),
            "valor_recebido": valor_recebido,  # ✅ NOVO
            "diferenca": diferenca,  # ✅ NOVO
            "data_recebimento": data_recebimento,  # ✅ NOVO
            "banco": banco_nome,  # ✅ NOVO
            "status": v.status_conciliacao,
            "bandeira": v.bandeira,
            "produto": v.produto,
            "parcela": f"{v.parcela or 1}/{v.total_parcelas or 1}",  # ✅ NOVO: ex: "1/12"
            "tipo_pagamento": v.tipo_pagamento or "cartao",  # ✅ NOVO: essencial para filtrar
            "adquirente": v.adquirente.nome if v.adquirente else None
        }
    
    return jsonify({
        "status": "success",
        "page": page,
        "per_page": per_page,
        "total": pagination.total,
        "pages": pagination.pages,
        "filtros_aplicados": {
            "status": status,
            "tipo_pagamento": tipo_pagamento,
            "data_inicio": data_inicio,
            "data_fim": data_fim
        },
        "dados": [venda_json(v) for v in pagination.items]
    }), 200

# ============================================================
# 4️⃣ NOVO: CONCILIAÇÃO MANUAL (FALLBACK)
# ============================================================
@bp_conc.route("/manual", methods=["POST"])
@login_required
def api_conciliacao_manual():
    """
    Permite conciliação manual quando o match automático falha.
    Útil para casos edge: NSU não bate, valor com diferença mínima, etc.
    """
    empresa_id = g.user.empresa_id
    data = request.json or {}
    
    venda_id = data.get('venda_id')
    recebimento_id = data.get('recebimento_id')
    valor_conciliado = data.get('valor_conciliado')  # Opcional: se diferente do valor da venda
    
    if not venda_id or not recebimento_id:
        return jsonify({
            "status": "error",
            "message": "venda_id e recebimento_id são obrigatórios"
        }), 400
    
    try:
        # Buscar venda e recebimento
        venda = MovAdquirente.query.filter_by(
            id=venda_id, 
            empresa_id=empresa_id,
            ativo=True
        ).first_or_404()
        
        recebimento = MovBanco.query.filter_by(
            id=recebimento_id,
            empresa_id=empresa_id
        ).first_or_404()
        
        # Validar que nenhum já está totalmente conciliado
        if venda.status_conciliacao == "conciliado":
            return jsonify({
                "status": "error",
                "message": "Esta venda já está totalmente conciliada"
            }), 400
        
        if recebimento.conciliado:
            return jsonify({
                "status": "error",
                "message": "Este recebimento já está totalmente conciliado"
            }), 400
        
        # Determinar valor a conciliar
        from decimal import Decimal
        valor = Decimal(str(valor_conciliado)) if valor_conciliado else min(
            Decimal(str(venda.valor_liquido or 0)) - Decimal(str(venda.valor_conciliado or 0)),
            Decimal(str(recebimento.valor or 0)) - Decimal(str(recebimento.valor_conciliado or 0))
        )
        
        if valor <= 0:
            return jsonify({
                "status": "error",
                "message": "Valor de conciliação inválido"
            }), 400
        
        # Criar registro de conciliação
        conc = Conciliacao(
            empresa_id=empresa_id,
            mov_adquirente_id=venda.id,
            mov_banco_id=recebimento.id,
            valor_previsto=venda.valor_liquido,
            valor_conciliado=valor,
            tipo="manual",  # ✅ Marcar como conciliação manual
            status="conciliado"
        )
        db.session.add(conc)
        
        # Atualizar venda
        venda.valor_conciliado = (Decimal(str(venda.valor_conciliado or 0)) + valor)
        venda.data_primeiro_recebimento = venda.data_primeiro_recebimento or recebimento.data_movimento
        venda.data_ultimo_recebimento = recebimento.data_movimento
        
        valor_liq = Decimal(str(venda.valor_liquido or 0))
        if venda.valor_conciliado >= valor_liq:
            venda.status_conciliacao = "conciliado"
        elif venda.valor_conciliado > 0:
            venda.status_conciliacao = "parcial"
        
        # Atualizar recebimento
        recebimento.valor_conciliado = (Decimal(str(recebimento.valor_conciliado or 0)) + valor)
        recebimento.conciliado = recebimento.valor_conciliado >= Decimal(str(recebimento.valor or 0))
        
        db.session.commit()
        
        # Log de auditoria
        try:
            log = LogAuditoria(
                usuario_id=g.user.id,
                empresa_id=empresa_id,
                acao="conciliacao_manual",
                detalhes=f"Venda={venda_id}, Recebimento={recebimento_id}, Valor={valor}",
                ip=request.remote_addr,
                criado_em=datetime.now(timezone.utc)
            )
            db.session.add(log)
            db.session.commit()
        except:
            pass  # Não falhar por erro de log
        
        logger.info(f"✅ Conciliação manual: venda={venda_id}, recebimento={recebimento_id}, valor={valor}")
        
        return jsonify({
            "status": "success",
            "message": "Conciliação manual registrada com sucesso",
            "venda_id": venda.id,
            "recebimento_id": recebimento.id,
            "valor_conciliado": str(valor)
        }), 200
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"❌ Erro na conciliação manual: {str(e)}", exc_info=True)
        return jsonify({
            "status": "error",
            "message": "Erro ao registrar conciliação manual"
        }), 500
