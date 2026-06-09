# utils/cnpj_helper.py
import requests
import logging

logger = logging.getLogger(__name__)

def consultar_cnpj(cnpj: str) -> dict | None:
    """
    Consulta dados da empresa via BrasilAPI (gratuito, sem autenticação)
    Retorna dict com dados formatados ou None se falhar.
    """
    # Limpar CNPJ (só números)
    cnpj_limpo = ''.join(filter(str.isdigit, cnpj))
    
    if len(cnpj_limpo) != 14:
        return None
    
    try:
        url = f"https://brasilapi.com.br/api/cnpj/v1/{cnpj_limpo}"
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            dados = response.json()
            return {
                'razao_social': dados.get('razao_social', ''),
                'nome_fantasia': dados.get('nome_fantasia', ''),
                'logradouro': dados.get('logradouro', ''),
                'numero': dados.get('numero', ''),
                'complemento': dados.get('complemento', ''),
                'bairro': dados.get('bairro', ''),
                'cep': dados.get('cep', ''),
                'municipio': dados.get('municipio', ''),
                'uf': dados.get('uf', ''),
                'telefone': dados.get('ddd_telefone_1', ''),
                'email': dados.get('email', ''),
                'situacao': dados.get('descricao_situacao_cadastral', '')
            }
        else:
            logger.warning(f"BrasilAPI retornou {response.status_code} para CNPJ {cnpj_limpo}")
            return None
            
    except requests.RequestException as e:
        logger.error(f"Erro ao consultar BrasilAPI: {str(e)}")
        return None
