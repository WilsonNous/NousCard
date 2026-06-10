# routes/debug_routes.py
# Rota de diagnóstico para problemas de performance (acessar via browser)

from flask import Blueprint, request, jsonify, g
from utils.auth_middleware import master_required
from io import BytesIO
import time
import logging

logger = logging.getLogger(__name__)

debug_bp = Blueprint("debug", __name__, url_prefix="/debug")


@debug_bp.route("/test-ofx", methods=["GET"])
@master_required
def test_ofx():
    """
    Testa parser OFX e salvamento no banco.
    Acessível apenas pelo MASTER via browser.
    
    Uso: https://www.nouscard.com.br/debug/test-ofx
    """
    resultados = {}
    
    try:
        from models import db, Empresa, ContaBancaria, MovBanco
        
        # TESTE 1: Verificar empresa
        inicio = time.time()
        empresa = Empresa.query.get(5)
        resultados["empresa"] = {
            "ok": empresa is not None,
            "nome": empresa.nome if empresa else "NÃO ENCONTRADA",
            "tempo": f"{(time.time() - inicio)*1000:.0f}ms"
        }
        
        # TESTE 2: Contas bancárias
        inicio = time.time()
        contas = ContaBancaria.query.filter_by(empresa_id=5, ativo=True).all()
        resultados["contas"] = {
            "ok": True,
            "total": len(contas),
            "contas": [{"id": c.id, "nome": c.nome, "banco": c.banco} for c in contas],
            "tempo": f"{(time.time() - inicio)*1000:.0f}ms"
        }
        
        # TESTE 3: Parser OFX (arquivo pequeno - 5 transações)
        ofx_teste = """<?xml version="1.0" encoding="UTF-8"?>
<OFX>
<BANKMSGSRSV1><STMTTRNRS><STMTRS><BANKTRANLIST>
<STMTTRN><DTPOSTED>20260601</DTPOSTED><TRNAMT>-100.00</TRNAMT><MEMO>Teste 1</MEMO></STMTTRN>
<STMTTRN><DTPOSTED>20260602</DTPOSTED><TRNAMT>-200.00</TRNAMT><MEMO>Teste 2</MEMO></STMTTRN>
<STMTTRN><DTPOSTED>20260603</DTPOSTED><TRNAMT>-300.00</TRNAMT><MEMO>Teste 3</MEMO></STMTTRN>
<STMTTRN><DTPOSTED>20260604</DTPOSTED><TRNAMT>-400.00</TRNAMT><MEMO>Teste 4</MEMO></STMTTRN>
<STMTTRN><DTPOSTED>20260605</DTPOSTED><TRNAMT>-500.00</TRNAMT><MEMO>Teste 5</MEMO></STMTTRN>
</BANKTRANLIST></STMTRS></STMTTRNRS></BANKMSGSRSV1>
</OFX>"""
        
        inicio = time.time()
        try:
            from utils.parsers import parse_ofx_generic
            stream = BytesIO(ofx_teste.encode('utf-8'))
            registros = parse_ofx_generic(stream, "teste.ofx")
            tempo_parser = time.time() - inicio
            
            resultados["parser_ofx_pequeno"] = {
                "ok": True,
                "registros": len(registros),
                "tempo": f"{tempo_parser:.2f}s",
                "amostra": [
                    {"data": str(r.get('data')), "valor": str(r.get('valor')), "descricao": r.get('descricao')}
                    for r in registros[:3]
                ]
            }
        except Exception as e:
            resultados["parser_ofx_pequeno"] = {
                "ok": False,
                "erro": str(e),
                "tempo": f"{(time.time() - inicio):.2f}s"
            }
        
        # TESTE 4: Parser OFX (arquivo GRANDE - 500 transações)
        inicio = time.time()
        try:
            transacoes_grandes = "\n".join([
                f"<STMTTRN><DTPOSTED>20260601</DTPOSTED><TRNAMT>-{i}.00</TRNAMT><MEMO>Teste {i}</MEMO></STMTTRN>"
                for i in range(1, 501)
            ])
            ofx_grande = f"""<?xml version="1.0" encoding="UTF-8"?>
<OFX><BANKMSGSRSV1><STMTTRNRS><STMTRS><BANKTRANLIST>
{transacoes_grandes}
</BANKTRANLIST></STMTRS></STMTTRNRS></BANKMSGSRSV1></OFX>"""
            
            stream = BytesIO(ofx_grande.encode('utf-8'))
            registros_grandes = parse_ofx_generic(stream, "grande.ofx")
            tempo_parser_grande = time.time() - inicio
            
            resultados["parser_ofx_grande"] = {
                "ok": True,
                "registros": len(registros_grandes),
                "tempo": f"{tempo_parser_grande:.2f}s"
            }
        except Exception as e:
            resultados["parser_ofx_grande"] = {
                "ok": False,
                "erro": str(e),
                "tempo": f"{(time.time() - inicio):.2f}s"
            }
        
        # TESTE 5: Salvamento no banco
        inicio = time.time()
        try:
            from services.importer_db_movimento import salvar_recebimentos
            stats = salvar_recebimentos(registros, 5, None)
            tempo_save = time.time() - inicio
            
            resultados["salvamento_banco"] = {
                "ok": True,
                "stats": stats,
                "tempo": f"{tempo_save:.2f}s"
            }
            
            # ROLLBACK para não salvar dados de teste
            db.session.rollback()
            
        except Exception as e:
            db.session.rollback()
            resultados["salvamento_banco"] = {
                "ok": False,
                "erro": str(e),
                "tempo": f"{(time.time() - inicio):.2f}s"
            }
        
        # TESTE 6: Contar MovBanco existentes
        inicio = time.time()
        total_mov = MovBanco.query.filter_by(empresa_id=5).count()
        resultados["movimentos_existentes"] = {
            "total": total_mov,
            "tempo": f"{(time.time() - inicio)*1000:.0f}ms"
        }
        
    except Exception as e:
        resultados["erro_geral"] = str(e)
        import traceback
        resultados["traceback"] = traceback.format_exc()
    
    return jsonify({
        "status": "ok",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "resultados": resultados
    }), 200


@debug_bp.route("/test-csv", methods=["GET"])
@master_required
def test_csv():
    """
    Testa parser CSV e salvamento no banco.
    Uso: https://www.nouscard.com.br/debug/test-csv
    """
    resultados = {}
    
    try:
        import csv
        from io import StringIO
        from utils.parsers import parse_csv_generic
        
        # CSV sintético com 100 transações
        csv_content = "data;valor;descricao;documento\n"
        for i in range(1, 101):
            csv_content += f"01/06/2026;-{i}.00;Teste {i};DOC{i}\n"
        
        inicio = time.time()
        stream = BytesIO(csv_content.encode('utf-8'))
        registros = parse_csv_generic(stream, "teste.csv")
        tempo = time.time() - inicio
        
        resultados["parser_csv"] = {
            "ok": True,
            "registros": len(registros),
            "tempo": f"{tempo:.2f}s"
        }
        
        # Testar salvamento
        inicio = time.time()
        try:
            from services.importer_db_movimento import salvar_recebimentos
            stats = salvar_recebimentos(registros, 5, None)
            tempo_save = time.time() - inicio
            
            resultados["salvamento_csv"] = {
                "ok": True,
                "stats": stats,
                "tempo": f"{tempo_save:.2f}s"
            }
            
            from models import db
            db.session.rollback()
            
        except Exception as e:
            from models import db
            db.session.rollback()
            resultados["salvamento_csv"] = {
                "ok": False,
                "erro": str(e)
            }
        
    except Exception as e:
        resultados["erro"] = str(e)
        import traceback
        resultados["traceback"] = traceback.format_exc()
    
    return jsonify(resultados), 200
