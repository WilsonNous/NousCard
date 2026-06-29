# services/aliases_financeiros.py
# Normalização de descrições antes da classificação

import re
import logging
from typing import Dict

logger = logging.getLogger(__name__)


class AliasesFinanceiros:
    """
    Normaliza descrições financeiras antes da classificação.
    Remove variações desnecessárias e padroniza nomes.
    """

    # Aliases hardcoded (fallback rápido)
    ALIASES_PADRAO = {
        "POSTOMARILU": "POSTO MARILU",
        "POSTO-MARILU": "POSTO MARILU",
        "NETFLIX.COM": "NETFLIX",
        "NETFLIX ENTRETENIMENTO": "NETFLIX",
        "PAGSEGURO INTERNET IP S.A.": "PAGSEGURO",
        "MERCADOPAGO": "MERCADO PAGO",
        "NU PAGAMENTOS": "NUBANK",
    }

    # Padrões regex para limpeza
    PADROES_LIMPEZA = [
        (r"\s+", " "),                    # Múltiplos espaços → um espaço
        (r"[^\w\sÀ-ÿ&().,-]", ""),        # Remove caracteres especiais
        (r"\s*-\s*", " "),                # Hífens → espaço
        (r"\.COM(\.BR)?", ""),            # Remove .com/.com.br
        (r"\s+LTDA(\s+ME)?", ""),         # Remove LTDA/ME
        (r"\s+EIRELI(\s+ME)?", ""),       # Remove EIRELI
        (r"\s+S\.A\.?", ""),              # Remove S.A.
        (r"\s{2,}", " "),                 # Espaços duplos → único
    ]

    def __init__(self, aliases_adicionais: Dict[str, str] = None):
        self.aliases = self.ALIASES_PADRAO.copy()
        if aliases_adicionais:
            self.aliases.update(aliases_adicionais)

    def normalizar(self, descricao: str) -> str:
        """
        Normaliza uma descrição financeira.

        Etapas:
        1. Converte para maiúsculas
        2. Remove espaços extras
        3. Remove caracteres especiais
        4. Remove sufixos jurídicos (LTDA, S.A., etc.)
        5. Aplica aliases
        6. Remove domínios (.com, .com.br)
        """
        if not descricao:
            return ""

        descricao = descricao.upper().strip()

        # Aplicar padrões de limpeza
        for pattern, replacement in self.PADROES_LIMPEZA:
            descricao = re.sub(pattern, replacement, descricao)

        descricao = descricao.strip()

        # Aplicar aliases (substituição direta)
        for alias, valor in self.aliases.items():
            if alias in descricao:
                descricao = descricao.replace(alias, valor)
                break

        return descricao

    def adicionar_alias(self, original: str, substituto: str) -> None:
        """Adiciona um novo alias em runtime."""
        self.aliases[original.upper()] = substituto.upper()
        logger.info(f"✅ Alias adicionado: {original} → {substituto}")


# Instância global
aliases = AliasesFinanceiros()