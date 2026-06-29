# services/score_classificacao.py
# Sistema de score e prioridade para classificação

import logging
from typing import Dict, List, Tuple, Optional

logger = logging.getLogger(__name__)


class ScoreClassificacao:
    """
    Calcula score de confiança para cada classificação.
    Score vai de 0 a 100.
    """

    # Pesos para cada fator
    PESOS = {
        "match_exato": 40,       # Palavra exata
        "match_parcial": 25,     # Substring
        "prioridade_regra": 20,  # Prioridade da regra (0-20)
        "contexto_valor": 15,    # Valor bate com natureza esperada
    }

    def calcular(
        self,
        descricao: str,
        palavra_encontrada: str,
        prioridade_regra: int,
        natureza_esperada: str,
        valor: float
    ) -> int:
        """
        Calcula score de confiança (0-100).

        Args:
            descricao: Descrição original
            palavra_encontrada: Palavra que deu match
            prioridade_regra: Prioridade da regra (0-100)
            natureza_esperada: Natureza esperada da categoria
            valor: Valor da transação
        """
        score = 0

        # 1. Match exato vs parcial
        if palavra_encontrada.upper() == descricao.upper():
            score += self.PESOS["match_exato"]
        else:
            score += self.PESOS["match_parcial"]

        # 2. Prioridade da regra (proporcional)
        score += min(prioridade_regra, 100) * self.PESOS["prioridade_regra"] / 100

        # 3. Contexto do valor
        natureza_real = "receita" if valor > 0 else "despesa"
        if natureza_real == natureza_esperada:
            score += self.PESOS["contexto_valor"]

        return min(score, 100)

    def classificar_com_score(
        self,
        matches: List[Dict],
        descricao: str,
        valor: float
    ) -> Tuple[Optional[str], int]:
        """
        Escolhe a melhor categoria baseado em score.

        Args:
            matches: Lista de matches (categoria, prioridade, palavra)
            descricao: Descrição original
            valor: Valor da transação

        Returns:
            (categoria, score) - categoria pode ser None se nenhum match
        """
        if not matches:
            return None, 0

        melhor_categoria = None
        melhor_score = 0

        for match in matches:
            score = self.calcular(
                descricao=descricao,
                palavra_encontrada=match.get("palavra", ""),
                prioridade_regra=match.get("prioridade", 0),
                natureza_esperada=match.get("natureza", "despesa"),
                valor=valor
            )

            if score > melhor_score:
                melhor_score = score
                melhor_categoria = match["categoria"]

        return melhor_categoria, melhor_score


# Instância global
scorer = ScoreClassificacao()