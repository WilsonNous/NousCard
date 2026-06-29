# services/regras_financeiras.py
# Carrega regras do JSON e fornece acesso otimizado

import json
import os
import logging
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

_CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "config",
    "categorias.json"
)


class RegrasFinanceiras:
    """
    Carrega e gerencia regras de classificação financeira.
    Fonte única de verdade para todas as categorias.
    """

    def __init__(self, config_path: str = None):
        self.config_path = config_path or _CONFIG_PATH
        self._dados = None
        self._indice_palavras = None  # Cache para busca rápida
        self._carregar()

    def _carregar(self) -> None:
        """Carrega o arquivo JSON de configuração."""
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                self._dados = json.load(f)
            self._construir_indice()
            logger.info(f"✅ Regras carregadas: {len(self.categorias)} categorias")
        except FileNotFoundError:
            logger.warning(f"⚠️ Arquivo de regras não encontrado: {self.config_path}")
            self._dados = {"categorias": {}, "tipos_pagamento": {}, "aliases": {}}
        except json.JSONDecodeError as e:
            logger.error(f"❌ Erro ao parsear JSON: {e}")
            self._dados = {"categorias": {}, "tipos_pagamento": {}, "aliases": {}}

    def _construir_indice(self) -> None:
        """Constrói índice invertido palavra → categoria para busca O(1)."""
        self._indice_palavras = {}
        for categoria, dados in self.categorias.items():
            for palavra in dados.get("palavras", []):
                palavra_upper = palavra.upper()
                if palavra_upper not in self._indice_palavras:
                    self._indice_palavras[palavra_upper] = []
                self._indice_palavras[palavra_upper].append({
                    "categoria": categoria,
                    "prioridade": dados.get("prioridade", 0)
                })

    @property
    def categorias(self) -> Dict:
        """Retorna todas as categorias."""
        return self._dados.get("categorias", {})

    @property
    def tipos_pagamento(self) -> Dict:
        """Retorna regras de tipo de pagamento."""
        return self._dados.get("tipos_pagamento", {})

    @property
    def aliases(self) -> Dict:
        """Retorna aliases para normalização."""
        return self._dados.get("aliases", {})

    def buscar_por_palavra(self, palavra: str) -> List[Dict]:
        """
        Busca categorias por palavra-chave usando índice.
        Retorna lista ordenada por prioridade (maior primeiro).
        """
        return sorted(
            self._indice_palavras.get(palavra.upper(), []),
            key=lambda x: x["prioridade"],
            reverse=True
        )

    def get_categoria_info(self, categoria: str) -> Dict:
        """Retorna informações completas de uma categoria."""
        return self.categorias.get(categoria, {})

    def get_grupo_subgrupo(self, categoria: str) -> Tuple[str, str]:
        """Retorna (grupo, subgrupo) para uma categoria."""
        info = self.get_categoria_info(categoria)
        return info.get("grupo", "Outros"), info.get("subgrupo", "Não Classificado")

    def get_centro_custo(self, categoria: str) -> str:
        """Retorna centro de custo da categoria."""
        return self.get_categoria_info(categoria).get("centro_custo", "Outros")

    def get_icone_cor(self, categoria: str) -> Tuple[str, str]:
        """Retorna (icone, cor) para Dashboard."""
        info = self.get_categoria_info(categoria)
        return info.get("icone", "fa-tag"), info.get("cor", "secondary")

    def get_natureza(self, categoria: str) -> str:
        """Retorna natureza (receita/despesa) da categoria."""
        return self.get_categoria_info(categoria).get("natureza", "despesa")

    def recarregar(self) -> None:
        """Recarrega regras do disco (útil para hot-reload)."""
        self._carregar()
        logger.info("🔄 Regras recarregadas")


# Instância global
regras = RegrasFinanceiras()