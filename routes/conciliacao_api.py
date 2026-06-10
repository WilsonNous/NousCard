# routes/conciliacao_api.py - VERSÃO CONSOLIDADA E FINAL

from flask import Blueprint, request, jsonify, g
from utils.auth_middleware import login_required, empresa_required
from services.conciliacao import executar_conciliacao
from models import db, MovAdquirente, MovBanco, Conciliacao, LogAuditoria
from sqlalchemy.orm import joinedload
from sqlalchemy import func, case
from datetime import datetime, timezone
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)

bp_conc = Blueprint("conciliacao_api", __name__, url_prefix="/api/v1/conciliacao")

# ============================================================
# 1️⃣ PROCESSAR CONCILIAÇÃO AUTOMÁTICA
# ============================================================
@bp_conc.route("/processar", methods=["POST"])
@login_required
@empresa_required
def api_processar_conciliacao():
    """
    Executa conciliação automática para a empresa do usuário.
    
    ✅ Segurança:
        - @login_required: usuário autenticado
        - @empresa_required: usuário tem empresa vinculada
        - empresa_id vem de g.user.empresa_id (não do request)
    
    ✅ JSON opcional:
        - tipo_pagamento: 'pix', 'cartao', 'boleto', ou null para todos
    """
    empresa_id = g.user.empresa_id
    
    # Obter parâmetros opcionais
    data = request.get_json(silent=True) or {}
    tipo_pagamento = data.get('tipo_pagamento')
    
    try:
        resultado = executar_conciliacao(
            empresa_id=empresa_id,
            usuario_id=g.user.id,
            tipo_pagamento=tipo_pagamento
        )
        
        # Log de auditoria (isolado para não afetar resposta)
        try:
            log = LogAuditoria(
                usuario_id=g.user.id,
                empresa_id=empresa_id,
                acao="conciliacao_executada",
                detalhes=f"Conciliados: {resultado.get('conciliados', 0)}, Parciais: {resultado.get('parciais', 0)}, Multivendas: {resultado.get('multivendas', 0)}, tipo={tipo_pagamento or 'todos'}",
                ip=request.remote_addr,
                criado_em=datetime.now(timezone.utc)
            )
            db.session.add(log)
            db.session.commit()
        except Exception as log_err:
            logger.warning(f"Erro ao logar auditoria (não crítico): {str(log_err)}")
            db.session.rollback()
        
        logger.info(f"✅ Conciliação: empresa={empresa_id}, usuario={g.user.id}, tipo={tipo_pagamento or 'todos'}")
        
        return jsonify({
            "status": "success",
            "message": "Conciliação executada com sucesso",
            "resultado": resultado,
            "timestamp": datetime.now(timezone.utc).isoformat()
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
@empresa_required
def api_status_conciliacao():
    """
    Retorna status resumido da conciliação para a empresa.
    Útil para dashboard mostrar contadores sem carregar todos os detalhes.
    
    ✅ Query params:
        - tipo_pagamento: filtrar por 'pix', 'cartao', 'boleto'
    """
    empresa_id = g.user.empresa_id
    tipo_pagamento = request.args.get('tipo_pagamento')
    
    try:
        # Query base
        query_base = MovAdquirente.query.filter(
            MovAdquirente.empresa_id == empresa_id,
            MovAdquirente.ativo == True
        )
        
        # Aplicar filtro por tipo se especificado
        if tipo_pagamento and tipo_pagamento != 'todos':
            query_base = query_base.filter(MovAdquirente.tipo_pagamento == tipo_pagamento)
        
        # 1 query otimizada para contar todos os status
        totais_query = query_base.with_entities(
            func.sum(case((MovAdquirente.status_conciliacao == "conciliado", 1), else_=0)).label("conciliado"),
            func.sum(case((MovAdquirente.status_conciliacao == "parcial", 1), else_=0)).label("parcial"),
            func.sum(case((MovAdquirente.status_conciliacao == "pendente", 1), else_=0)).label("pendente"),
            func.sum(case((MovAdquirente.status_conciliacao == "nao_recebido", 1), else_=0)).label("nao_recebido")
        ).first()
        
        # Créditos sem origem (recebimentos não conciliados)
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
            },
            "timestamp": datetime.now(timezone.utc).isoformat()
        }), 200
        
    except Exception as e:
        logger.error(f"Erro ao buscar status: empresa={empresa_id}, erro={str(e)}", exc_info=True)
        return jsonify({
            "status": "error",
            "message": "Erro ao carregar status"
        }), 500


# ============================================================
# 3️⃣ DETALHES (COM PAGINAÇÃO + FILTROS + DADOS DE RECEBIMENTO)
# ============================================================
@bp_conc.route("/detalhes", methods=["GET"])
@login_required
@empresa_required
def api_detalhes_conciliacao():
    """
    Retorna detalhes das vendas para conciliação com paginação.
    
    ✅ Query params:
        - page: número da página (default: 1)
        - per_page: itens por página (default: 50, max: 100)
        - status: filtrar por 'pendente', 'parcial', 'conciliado'
        - tipo_pagamento: filtrar por 'pix', 'cartao', 'boleto'
        - data_inicio: YYYY-MM-DD
        - data_fim: YYYY-MM-DD
    """
    empresa_id = g.user.empresa_id
    
    # Parâmetros de paginação e filtro
    page = max(1, request.args.get('page', 1, type=int))
    per_page = min(request.args.get('per_page', 50, type=int), 100)
    status = request.args.get('status')
    tipo_pagamento = request.args.get('tipo_pagamento')
    data_inicio = request.args.get('data_inicio')
    data_fim = request.args.get('data_fim')
    
    try:
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
            # Buscar dados de recebimento conciliado (via tabela Conciliacao)
            valor_recebido = "0"
            data_recebimento = None
            banco_nome = None
            
            try:
                conc = Conciliacao.query.filter_by(
                    mov_adquirente_id=v.id,
                    empresa_id=empresa_id,  # ✅ Garantir isolamento
                    ativo=True
                ).first()
                
                if conc and conc.mov_banco_id:
                    mov_banco = MovBanco.query.filter_by(
                        id=conc.mov_banco_id,
                        empresa_id=empresa_id  # ✅ Garantir isolamento
                    ).first()
                    
                    if mov_banco:
                        valor_recebido = str(mov_banco.valor or 0)
                        data_recebimento = str(mov_banco.data_movimento) if mov_banco.data_movimento else None
                        banco_nome = mov_banco.banco
            except Exception as e:
                logger.debug(f"Fallback ao buscar recebimento: {str(e)}")
            
            # Calcular diferença
            try:
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
                "valor_recebido": valor_recebido,
                "diferenca": diferenca,
                "data_recebimento": data_recebimento,
                "banco": banco_nome,
                "status": v.status_conciliacao,
                "bandeira": v.bandeira,
                "produto": v.produto,
                "parcela": f"{v.parcela or 1}/{v.total_parcelas or 1}",
                "tipo_pagamento": v.tipo_pagamento or "cartao",
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
            "dados": [venda_json(v) for v in pagination.items],
            "timestamp": datetime.now(timezone.utc).isoformat()
        }), 200
        
    except Exception as e:
        logger.error(f"Erro ao buscar detalhes: empresa={empresa_id}, erro={str(e)}", exc_info=True)
        return jsonify({
            "status": "error",
            "message": "Erro ao carregar detalhes"
        }), 500


# ============================================================
# 4️⃣ CONCILIAÇÃO MANUAL (FALLBACK)
# ============================================================
@bp_conc.route("/manual", methods=["POST"])
@login_required
@empresa_required
def api_conciliacao_manual():
    """
    Permite conciliação manual quando o match automático falha.
    Útil para casos edge: NSU não bate, valor com diferença mínima, etc.
    
    ✅ JSON obrigatório:
        - venda_id: ID da venda
        - recebimento_id: ID do recebimento
    
    ✅ JSON opcional:
        - valor_conciliado: valor a conciliar (se diferente do valor da venda)
    """
    empresa_id = g.user.empresa_id
    data = request.get_json(silent=True) or {}
    
    venda_id = data.get('venda_id')
    recebimento_id = data.get('recebimento_id')
    valor_conciliado = data.get('valor_conciliado')
    
    if not venda_id or not recebimento_id:
        return jsonify({
            "status": "error",
            "message": "venda_id e recebimento_id são obrigatórios"
        }), 400
    
    try:
        # Buscar venda e recebimento (garantindo isolamento por empresa)
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
            tipo="manual",
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
        except Exception as log_err:
            logger.warning(f"Erro ao logar auditoria (não crítico): {str(log_err)}")
        
        logger.info(f"✅ Conciliação manual: empresa={empresa_id}, venda={venda_id}, recebimento={recebimento_id}, valor={valor}")
        
        return jsonify({
            "status": "success",
            "message": "Conciliação manual registrada com sucesso",
            "venda_id": venda.id,
            "recebimento_id": recebimento.id,
            "valor_conciliado": str(valor),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"❌ Erro na conciliação manual: empresa={empresa_id}, erro={str(e)}", exc_info=True)
        return jsonify({
            "status": "error",
            "message": "Erro ao registrar conciliação manual"
        }), 500
