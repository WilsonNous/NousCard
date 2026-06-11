# services/contrato_service.py
# Serviço para geração automática de contratos

import logging
from datetime import datetime, date, timedelta
from decimal import Decimal
from io import BytesIO

logger = logging.getLogger(__name__)

# ============================================================
# CONFIGURAÇÕES DE PREÇOS
# ============================================================
PLANOS = {
    'inicial': {
        'nome': 'Plano Inicial',
        'valor_setup': Decimal('297.00'),
        'valor_mensal': Decimal('97.00'),
        'limite_transacoes': 500,
        'descricao': 'Ideal para microempresas com até 500 transações/mês'
    },
    'profissional': {
        'nome': 'Plano Profissional',
        'valor_setup': Decimal('297.00'),
        'valor_mensal': Decimal('197.00'),
        'limite_transacoes': 2000,
        'descricao': 'Para pequenas empresas com até 2.000 transações/mês'
    },
    'business': {
        'nome': 'Plano Business',
        'valor_setup': Decimal('297.00'),
        'valor_mensal': Decimal('397.00'),
        'limite_transacoes': None,  # ilimitado
        'descricao': 'Transações ilimitadas para empresas em crescimento'
    },
    'parceiro': {
        'nome': 'Plano Parceiro',
        'valor_setup': Decimal('0.00'),
        'valor_mensal': Decimal('0.00'),
        'limite_transacoes': None,
        'descricao': 'Exclusivo para empresas parceiras (gratuito)'
    }
}


def gerar_contrato_para_empresa(empresa_id, plano='inicial', observacoes=None):
    """
    Gera contrato automaticamente para uma empresa.
    
    Args:
        empresa_id: ID da empresa
        plano: 'inicial', 'profissional', 'business' ou 'parceiro'
        observacoes: Texto adicional (opcional)
    
    Returns:
        dict: {ok: bool, contrato: Contrato, mensagem: str}
    """
    try:
        from models import db, Empresa, Contrato
        
        empresa = Empresa.query.get(empresa_id)
        if not empresa:
            return {"ok": False, "mensagem": "Empresa não encontrada"}
        
        # Verificar se já existe contrato ativo
        contrato_existente = Contrato.query.filter_by(
            empresa_id=empresa_id,
            ativo=True
        ).filter(Contrato.status.in_(['gerado', 'enviado', 'assinado', 'ativo'])).first()
        
        if contrato_existente:
            return {
                "ok": False, 
                "mensagem": f"Já existe contrato {contrato_existente.numero} para esta empresa",
                "contrato": contrato_existente
            }
        
        # Buscar dados do plano
        dados_plano = PLANOS.get(plano, PLANOS['inicial'])
        
        # Gerar número do contrato
        numero = Contrato.gerar_numero_contrato()
        
        # Datas
        hoje = date.today()
        data_inicio = hoje
        data_fim = hoje + timedelta(days=365)  # 1 ano de vigência
        
        # Criar contrato
        contrato = Contrato(
            numero=numero,
            empresa_id=empresa_id,
            data_emissao=hoje,
            data_inicio_vigencia=data_inicio,
            data_fim_vigencia=data_fim,
            valor_setup=dados_plano['valor_setup'],
            valor_mensal=dados_plano['valor_mensal'],
            plano=plano,
            status='gerado',
            observacoes=observacoes
        )
        
        db.session.add(contrato)
        db.session.commit()
        
        # Gerar PDF do contrato
        try:
            pdf_base64 = gerar_pdf_contrato(contrato, empresa, dados_plano)
            contrato.pdf_base64 = pdf_base64
            db.session.commit()
        except Exception as e:
            logger.warning(f"⚠️ Erro ao gerar PDF do contrato: {str(e)}")
        
        logger.info(f"✅ Contrato {numero} gerado para empresa {empresa.nome} (plano: {plano})")
        
        return {
            "ok": True,
            "contrato": contrato,
            "mensagem": f"Contrato {numero} gerado com sucesso!"
        }
        
    except Exception as e:
        logger.error(f"❌ Erro ao gerar contrato: {str(e)}", exc_info=True)
        db.session.rollback()
        return {"ok": False, "mensagem": f"Erro ao gerar contrato: {str(e)}"}


def gerar_pdf_contrato(contrato, empresa, dados_plano):
    """
    Gera PDF do contrato em base64.
    Usa a biblioteca reportlab ou similar.
    """
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        from reportlab.lib import colors
        from reportlab.lib.units import cm
        import base64
        
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, 
                               leftMargin=2*cm, rightMargin=2*cm,
                               topMargin=2*cm, bottomMargin=2*cm)
        
        styles = getSampleStyleSheet()
        styles.add(ParagraphStyle(name='Titulo', fontSize=16, alignment=1, spaceAfter=20))
        styles.add(ParagraphStyle(name='Subtitulo', fontSize=12, spaceAfter=10))
        styles.add(ParagraphStyle(name='Texto', fontSize=10, spaceAfter=8, leading=14))
        
        elementos = []
        
        # Título
        elementos.append(Paragraph("CONTRATO DE PRESTAÇÃO DE SERVIÇOS", styles['Titulo']))
        elementos.append(Paragraph(f"NousCard - Conciliação Inteligente de Cartões", styles['Subtitulo']))
        elementos.append(Spacer(1, 0.5*cm))
        
        # Número do contrato
        elementos.append(Paragraph(f"<b>Contrato nº:</b> {contrato.numero}", styles['Texto']))
        elementos.append(Paragraph(f"<b>Data de Emissão:</b> {contrato.data_emissao.strftime('%d/%m/%Y')}", styles['Texto']))
        elementos.append(Spacer(1, 0.5*cm))
        
        # Dados da CONTRATANTE
        elementos.append(Paragraph("<b>CONTRATANTE:</b>", styles['Subtitulo']))
        elementos.append(Paragraph(f"<b>Razão Social:</b> {empresa.nome}", styles['Texto']))
        elementos.append(Paragraph(f"<b>CNPJ:</b> {empresa.cnpj or 'Não informado'}", styles['Texto']))
        elementos.append(Paragraph(f"<b>Endereço:</b> {empresa.endereco or 'Não informado'}", styles['Texto']))
        elementos.append(Spacer(1, 0.5*cm))
        
        # Dados da CONTRATADA
        elementos.append(Paragraph("<b>CONTRATADA:</b>", styles['Subtitulo']))
        elementos.append(Paragraph("<b>Nous Tecnologia LTDA</b>", styles['Texto']))
        elementos.append(Paragraph("CNPJ: [CNPJ da Nous Tecnologia]", styles['Texto']))
        elementos.append(Paragraph("Endereço: Florianópolis - SC", styles['Texto']))
        elementos.append(Spacer(1, 0.5*cm))
        
        # Cláusulas
        elementos.append(Paragraph("<b>CLÁUSULA 1ª - DO OBJETO</b>", styles['Subtitulo']))
        elementos.append(Paragraph(
            "O presente contrato tem por objeto a prestação de serviços da plataforma NousCard, "
            "que oferece conciliação automática de cartões, dashboard financeiro inteligente, "
            "importação de extratos bancários (OFX, CSV, Excel) e relatórios gerenciais.",
            styles['Texto']
        ))
        elementos.append(Spacer(1, 0.3*cm))
        
        elementos.append(Paragraph("<b>CLÁUSULA 2ª - DO PLANO CONTRATADO</b>", styles['Subtitulo']))
        elementos.append(Paragraph(f"<b>Plano:</b> {dados_plano['nome']}", styles['Texto']))
        elementos.append(Paragraph(f"<b>Descrição:</b> {dados_plano['descricao']}", styles['Texto']))
        if dados_plano['limite_transacoes']:
            elementos.append(Paragraph(f"<b>Limite:</b> Até {dados_plano['limite_transacoes']} transações/mês", styles['Texto']))
        else:
            elementos.append(Paragraph("<b>Limite:</b> Transações ilimitadas", styles['Texto']))
        elementos.append(Spacer(1, 0.3*cm))
        
        elementos.append(Paragraph("<b>CLÁUSULA 3ª - DOS VALORES</b>", styles['Subtitulo']))
        elementos.append(Paragraph(
            f"<b>Taxa de Setup (pagamento único):</b> R$ {float(contrato.valor_setup):.2f}",
            styles['Texto']
        ))
        elementos.append(Paragraph(
            f"<b>Mensalidade:</b> R$ {float(contrato.valor_mensal):.2f}",
            styles['Texto']
        ))
        elementos.append(Paragraph(
            "O pagamento da mensalidade deverá ser efetuado até o dia 10 de cada mês, "
            "via boleto bancário ou PIX.",
            styles['Texto']
        ))
        elementos.append(Spacer(1, 0.3*cm))
        
        elementos.append(Paragraph("<b>CLÁUSULA 4ª - DA VIGÊNCIA</b>", styles['Subtitulo']))
        elementos.append(Paragraph(
            f"O presente contrato tem vigência de <b>{contrato.data_inicio_vigencia.strftime('%d/%m/%Y')}</b> "
            f"a <b>{contrato.data_fim_vigencia.strftime('%d/%m/%Y')}</b>, podendo ser renovado automaticamente.",
            styles['Texto']
        ))
        elementos.append(Spacer(1, 0.3*cm))
        
        elementos.append(Paragraph("<b>CLÁUSULA 5ª - DA CONFIDENCIALIDADE E LGPD</b>", styles['Subtitulo']))
        elementos.append(Paragraph(
            "A CONTRATADA compromete-se a manter sigilo sobre todas as informações financeiras "
            "da CONTRATANTE, em conformidade com a Lei Geral de Proteção de Dados (LGPD - Lei 13.709/2018).",
            styles['Texto']
        ))
        elementos.append(Spacer(1, 0.3*cm))
        
        elementos.append(Paragraph("<b>CLÁUSULA 6ª - DO CANCELAMENTO</b>", styles['Subtitulo']))
        elementos.append(Paragraph(
            "O contrato poderá ser cancelado por qualquer das partes mediante aviso prévio de 30 dias.",
            styles['Texto']
        ))
        elementos.append(Spacer(1, 1*cm))
        
        # Assinaturas
        elementos.append(Paragraph("Florianópolis, " + contrato.data_emissao.strftime("%d de %B de %Y"), styles['Texto']))
        elementos.append(Spacer(1, 2*cm))
        
        elementos.append(Paragraph("_________________________________", styles['Texto']))
        elementos.append(Paragraph("<b>CONTRATANTE</b>", styles['Texto']))
        elementos.append(Spacer(1, 1*cm))
        
        elementos.append(Paragraph("_________________________________", styles['Texto']))
        elementos.append(Paragraph("<b>CONTRATADA - Nous Tecnologia LTDA</b>", styles['Texto']))
        elementos.append(Spacer(1, 1*cm))
        
        elementos.append(Paragraph("_________________________________", styles['Texto']))
        elementos.append(Paragraph("<b>TESTEMUNHA 1</b>", styles['Texto']))
        elementos.append(Spacer(1, 1*cm))
        
        elementos.append(Paragraph("_________________________________", styles['Texto']))
        elementos.append(Paragraph("<b>TESTEMUNHA 2</b>", styles['Texto']))
        
        # Gerar PDF
        doc.build(elementos)
        
        # Converter para base64
        pdf_bytes = buffer.getvalue()
        buffer.close()
        
        return base64.b64encode(pdf_bytes).decode('utf-8')
        
    except Exception as e:
        logger.error(f"❌ Erro ao gerar PDF: {str(e)}", exc_info=True)
        raise
