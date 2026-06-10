# routes/debug_routes.py
# Rota de diagnóstico para problemas de performance (acessar via browser)

from flask import Blueprint, request, jsonify, g
from utils.auth_middleware import master_required
from io import BytesIO
import time
import logging

logger = logging.getLogger(__name__)

debug_bp = Blueprint("debug", __name__)


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
    

@debug_bp.route("/test-ofx-real", methods=["POST"])
@master_required
def test_ofx_real():
    """
    Testa upload de arquivo OFX real em etapas, com logs detalhados.
    
    Uso: Faça upload via form ou use curl:
    curl -X POST -F "file=@extrato.ofx" https://www.nouscard.com.br/debug/test-ofx-real
    """
    import time
    from werkzeug.utils import secure_filename
    
    resultados = {"etapas": [], "total_tempo": 0}
    inicio_total = time.time()
    
    try:
        # ETAPA 1: Receber arquivo
        inicio = time.time()
        if 'file' not in request.files:
            return jsonify({"erro": "Nenhum arquivo enviado"}), 400
        
        file = request.files['file']
        if not file.filename:
            return jsonify({"erro": "Arquivo sem nome"}), 400
        
        # Ler conteúdo
        content = file.read()
        file_size = len(content)
        tempo_receber = time.time() - inicio
        
        resultados["etapas"].append({
            "nome": "1. Receber arquivo",
            "tempo": f"{tempo_receber:.3f}s",
            "detalhes": f"Tamanho: {file_size/1024:.1f} KB"
        })
        
        # ETAPA 2: Decodificar
        inicio = time.time()
        try:
            text = content.decode('utf-8', errors='replace')
        except:
            text = content.decode('latin-1', errors='replace')
        tempo_decode = time.time() - inicio
        
        resultados["etapas"].append({
            "nome": "2. Decodificar",
            "tempo": f"{tempo_decode:.3f}s",
            "detalhes": f"Chars: {len(text)}"
        })
        
        # ETAPA 3: Contar transações (rápido)
        inicio = time.time()
        total_transacoes = text.upper().count('<STMTTRN>')
        tempo_contar = time.time() - inicio
        
        resultados["etapas"].append({
            "nome": "3. Contar transações",
            "tempo": f"{tempo_contar:.3f}s",
            "detalhes": f"Total: {total_transacoes} transações"
        })
        
        # ETAPA 4: Parser OFX
        inicio = time.time()
        try:
            from utils.parsers import parse_ofx_generic
            from io import BytesIO
            
            stream = BytesIO(content)
            registros = parse_ofx_generic(stream, file.filename)
            tempo_parser = time.time() - inicio
            
            resultados["etapas"].append({
                "nome": "4. Parser OFX",
                "tempo": f"{tempo_parser:.2f}s",
                "detalhes": f"Registros parseados: {len(registros)}",
                "ok": True
            })
            
            # Amostra dos primeiros 3 registros
            if registros:
                resultados["amostra"] = [
                    {"data": str(r.get('data')), "valor": str(r.get('valor')), "descricao": r.get('descricao', '')[:50]}
                    for r in registros[:3]
                ]
            
        except Exception as e:
            tempo_parser = time.time() - inicio
            resultados["etapas"].append({
                "nome": "4. Parser OFX",
                "tempo": f"{tempo_parser:.2f}s",
                "detalhes": f"ERRO: {str(e)}",
                "ok": False
            })
            import traceback
            resultados["traceback"] = traceback.format_exc()
            registros = []
        
        # ETAPA 5: Salvamento no banco (SOMENTE SE TIVER REGISTROS)
        if registros:
            inicio = time.time()
            try:
                from services.importer_db_movimento import salvar_recebimentos
                from models import db
                
                # Usar empresa 5 (SALÃO FLOW) para teste
                stats = salvar_recebimentos(registros, 5, None)
                tempo_save = time.time() - inicio
                
                resultados["etapas"].append({
                    "nome": "5. Salvamento no banco",
                    "tempo": f"{tempo_save:.2f}s",
                    "detalhes": stats,
                    "ok": True
                })
                
                # ROLLBACK para não salvar dados de teste
                db.session.rollback()
                
            except Exception as e:
                from models import db
                db.session.rollback()
                tempo_save = time.time() - inicio
                resultados["etapas"].append({
                    "nome": "5. Salvamento no banco",
                    "tempo": f"{tempo_save:.2f}s",
                    "detalhes": f"ERRO: {str(e)}",
                    "ok": False
                })
                import traceback
                resultados["traceback_save"] = traceback.format_exc()
        
        resultados["total_tempo"] = f"{time.time() - inicio_total:.2f}s"
        
    except Exception as e:
        resultados["erro_geral"] = str(e)
        import traceback
        resultados["traceback_geral"] = traceback.format_exc()
    
    return jsonify(resultados), 200

# routes/debug_routes.py - ADICIONE ESTA ROTA

@debug_bp.route("/test-ofx-form", methods=["GET"])
@master_required
def test_ofx_form():
    """
    Retorna formulário HTML para testar upload OFX.
    Acessível apenas pelo MASTER, dentro do próprio site.
    
    Uso: https://www.nouscard.com.br/debug/test-ofx-form
    """
    from flask import session
    
    # Gerar CSRF token se não existir
    if 'csrf_token' not in session:
        import secrets
        session['csrf_token'] = secrets.token_urlsafe(32)
    
    csrf_token = session['csrf_token']
    
    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <title>Teste Upload OFX - Debug</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            max-width: 800px;
            margin: 50px auto;
            padding: 20px;
            background: #f5f7fa;
        }}
        .container {{
            background: white;
            padding: 30px;
            border-radius: 12px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }}
        h1 {{
            color: #1d3469;
            margin-top: 0;
        }}
        .info {{
            background: #e8edf5;
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 20px;
            border-left: 4px solid #1d3469;
        }}
        input[type="file"] {{
            display: block;
            margin: 20px 0;
            padding: 10px;
            border: 2px dashed #1d3469;
            border-radius: 8px;
            width: 100%;
            cursor: pointer;
        }}
        button {{
            background: #1d3469;
            color: white;
            border: none;
            padding: 12px 30px;
            border-radius: 8px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: background 0.2s;
        }}
        button:hover {{
            background: #3d5c95;
        }}
        button:disabled {{
            background: #ccc;
            cursor: not-allowed;
        }}
        #resultado {{
            margin-top: 20px;
            padding: 15px;
            border-radius: 8px;
            display: none;
        }}
        .sucesso {{
            background: #d4edda;
            border: 1px solid #c3e6cb;
            color: #155724;
        }}
        .erro {{
            background: #f8d7da;
            border: 1px solid #f5c6cb;
            color: #721c24;
        }}
        pre {{
            background: #f8f9fa;
            padding: 15px;
            border-radius: 6px;
            overflow-x: auto;
            font-size: 12px;
            max-height: 400px;
        }}
        .loading {{
            display: none;
            margin-top: 20px;
            color: #1d3469;
            font-weight: 600;
        }}
        .spinner {{
            display: inline-block;
            width: 20px;
            height: 20px;
            border: 3px solid #e8edf5;
            border-top-color: #1d3469;
            border-radius: 50%;
            animation: spin 1s linear infinite;
            vertical-align: middle;
            margin-right: 10px;
        }}
        @keyframes spin {{
            to {{ transform: rotate(360deg); }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🔍 Teste Upload OFX - Debug</h1>
        
        <div class="info">
            <strong>📋 Instruções:</strong>
            <ol style="margin: 10px 0 0 0;">
                <li>Selecione um arquivo OFX</li>
                <li>Clique em "Testar Upload"</li>
                <li>Aguarde o resultado (pode levar alguns segundos)</li>
                <li>O JSON abaixo mostrará o tempo de cada etapa</li>
            </ol>
        </div>
        
        <form id="uploadForm" enctype="multipart/form-data">
            <input type="hidden" name="csrf_token" value="{csrf_token}">
            
            <label for="file" style="font-weight: 600; color: #1d3469;">
                Selecione o arquivo OFX:
            </label>
            <input type="file" id="file" name="file" accept=".ofx" required>
            
            <button type="submit" id="btnSubmit">🚀 Testar Upload</button>
        </form>
        
        <div class="loading" id="loading">
            <span class="spinner"></span>
            Processando... aguarde (pode levar até 30 segundos)
        </div>
        
        <div id="resultado"></div>
    </div>
    
    <script>
        document.getElementById('uploadForm').addEventListener('submit', async function(e) {{
            e.preventDefault();
            
            const form = e.target;
            const formData = new FormData(form);
            const btn = document.getElementById('btnSubmit');
            const loading = document.getElementById('loading');
            const resultado = document.getElementById('resultado');
            
            // Desabilitar botão e mostrar loading
            btn.disabled = true;
            btn.textContent = '⏳ Processando...';
            loading.style.display = 'block';
            resultado.style.display = 'none';
            
            try {{
                const response = await fetch('/debug/test-ofx-real', {{
                    method: 'POST',
                    body: formData,
                    headers: {{
                        'X-CSRF-Token': '{csrf_token}'
                    }}
                }});
                
                const data = await response.json();
                
                // Mostrar resultado
                resultado.style.display = 'block';
                
                if (data.erro_geral || data.erro) {{
                    resultado.className = 'erro';
                    resultado.innerHTML = '<strong>❌ Erro:</strong><pre>' + 
                        JSON.stringify(data, null, 2) + '</pre>';
                }} else {{
                    resultado.className = 'sucesso';
                    
                    let html = '<strong>✅ Teste concluído em ' + data.total_tempo + '</strong><br><br>';
                    
                    if (data.etapas) {{
                        html += '<strong>📊 Etapas:</strong><table style="width:100%; border-collapse: collapse; margin-top: 10px;">';
                        html += '<tr style="background:#e8edf5;"><th style="padding:8px; text-align:left;">Etapa</th><th style="padding:8px; text-align:right;">Tempo</th><th style="padding:8px; text-align:left;">Detalhes</th></tr>';
                        
                        data.etapas.forEach(etapa => {{
                            const cor = etapa.ok === false ? '#f8d7da' : (parseFloat(etapa.tempo) > 5 ? '#fff3cd' : '#d4edda');
                            html += '<tr style="background:' + cor + ';">';
                            html += '<td style="padding:8px;">' + etapa.nome + '</td>';
                            html += '<td style="padding:8px; text-align:right; font-weight:600;">' + etapa.tempo + '</td>';
                            html += '<td style="padding:8px; font-size:12px;">' + 
                                (typeof etapa.detalhes === 'object' ? JSON.stringify(etapa.detalhes) : etapa.detalhes) + 
                                '</td>';
                            html += '</tr>';
                        }});
                        
                        html += '</table>';
                    }}
                    
                    if (data.amostra) {{
                        html += '<br><strong>📋 Amostra dos primeiros registros:</strong><pre>' + 
                            JSON.stringify(data.amostra, null, 2) + '</pre>';
                    }}
                    
                    html += '<br><strong>📄 JSON completo:</strong><pre>' + 
                        JSON.stringify(data, null, 2) + '</pre>';
                    
                    resultado.innerHTML = html;
                }}
                
            }} catch (error) {{
                resultado.style.display = 'block';
                resultado.className = 'erro';
                resultado.innerHTML = '<strong>❌ Erro de conexão:</strong><pre>' + error.message + '</pre>';
            }} finally {{
                btn.disabled = false;
                btn.textContent = '🚀 Testar Upload';
                loading.style.display = 'none';
            }}
        }});
    </script>
</body>
</html>"""
    
    return html, 200, {'Content-Type': 'text/html; charset=utf-8'}
