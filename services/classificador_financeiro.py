# services/classificador_financeiro.py
# Motor Oficial de Classificação Financeira do NOUSCARD
# Versão 2.0 - Evoluído com cache, score, aliases e JSON

import logging
from typing import Dict, Optional

from services.regras_financeiras import regras
from services.aliases_financeiros import aliases
from services.cache_classificador import cache
from services.score_classificacao import scorer

logger = logging.getLogger(__name__)


class ClassificadorFinanceiro:
    """
    Motor oficial de classificação financeira do NOUSCARD.

    Utilizado por:
    - Importador
    - Normalização
    - Dashboard
    - DRE
    - Fluxo de Caixa
    - Extrato Bancário
    - Relatórios Financeiros

    Características:
    - Cache LRU para performance
    - Score de confiança
    - Aliases para normalização
    - Regras em JSON (hot-reload)
    - Separação receita/despesa
    - Centro de custo
    - Ícones e cores para Dashboard
    """

    def __init__(self):
        self.regras = regras
        self.aliases = aliases
        self.cache = cache
        self.scorer = scorer

    # ============================================================
    # MÉTODO PRINCIPAL
    # ============================================================

    def classificar(
        self,
        descricao: str,
        valor: float,
        trntype: Optional[str] = None
    ) -> Dict:
        """
        Classifica uma transação financeira.

        Args:
            descricao: Descrição da transação
            valor: Valor (positivo = receita, negativo = despesa)
            trntype: Tipo de transação (opcional)

        Returns:
            dict com categoria, tipo_pagamento, natureza, grupo,
                 subgrupo, centro_custo, score, icone, cor
        """
        valor = float(valor) if valor else 0.0

        # 1. Normalizar descrição (aliases)
        descricao_normalizada = self.aliases.normalizar(descricao)

        # 2. Verificar cache
        chave_cache = f"{descricao_normalizada}|{valor}|{trntype}"
        cached = self.cache.get(chave_cache)
        if cached:
            return cached

        # 3. Classificar
        resultado = self._classificar_interno(descricao_normalizada, valor, trntype)

        # 4. Armazenar no cache
        self.cache.set(chave_cache, resultado)

        return resultado

    def classificar_movimento(self, normalizacao) -> Dict:
        """
        Classifica diretamente um objeto de Normalização.

        Args:
            normalizacao: Objeto Normalizacao do SQLAlchemy

        Returns:
            dict com classificação completa
        """
        return self.classificar(
            descricao=normalizacao.descricao or normalizacao.historico or "",
            valor=float(normalizacao.valor_bruto or 0),
            trntype=getattr(normalizacao, 'trntype', None)
        )

    # ============================================================
    # MÉTODOS PRIVADOS
    # ============================================================

    def _classificar_interno(
        self,
        descricao: str,
        valor: float,
        trntype: Optional[str] = None
    ) -> Dict:
        """Classificação interna (sem cache)."""
        descricao_upper = descricao.upper()

        # 1. Coletar todos os matches possíveis
        matches = self._coletar_matches(descricao_upper, valor)

        # 2. Escolher melhor categoria por score
        categoria, score = self.scorer.classificar_com_score(
            matches, descricao_upper, valor
        )

        # 3. Fallback se nenhum match
        if not categoria:
            categoria = self._fallback(descricao_upper, valor, trntype)
            score = 10

        # 4. Tipo de pagamento
        tipo_pagamento = self._classificar_tipo_pagamento(descricao_upper)

        # 5. Natureza
        natureza = self.regras.get_natureza(categoria)
        if not natureza:
            natureza = "receita" if valor > 0 else "despesa"

        # 6. Grupo e subgrupo
        grupo, subgrupo = self.regras.get_grupo_subgrupo(categoria)

        # 7. Centro de custo
        centro_custo = self.regras.get_centro_custo(categoria)

        # 8. Ícone e cor
        icone, cor = self.regras.get_icone_cor(categoria)

        return {
            "categoria": categoria,
            "tipo_pagamento": tipo_pagamento,
            "natureza": natureza,
            "grupo": grupo,
            "subgrupo": subgrupo,
            "centro_custo": centro_custo,
            "icone": icone,
            "cor": cor,
            "score": score
        }

    def _coletar_matches(self, descricao: str, valor: float) -> list:
        """
        Coleta todos os matches possíveis por palavra-chave.
        Separa receitas e despesas baseado no valor.
        """
        matches = []
        natureza_esperada = "receita" if valor > 0 else "despesa"

        for categoria, dados in self.regras.categorias.items():
            # Filtrar por natureza (receita/despesa)
            natureza_categoria = dados.get("natureza", "despesa")
            if natureza_categoria != natureza_esperada:
                continue

            # Buscar palavras que deram match
            for palavra in dados.get("palavras", []):
                if palavra.upper() in descricao:
                    matches.append({
                        "categoria": categoria,
                        "palavra": palavra,
                        "prioridade": dados.get("prioridade", 50),
                        "natureza": natureza_categoria
                    })
                    break  # Uma palavra já basta por categoria

        return matches

    def _classificar_tipo_pagamento(self, descricao: str) -> str:
        """Classifica o tipo de pagamento."""
        for tipo, palavras in self.regras.tipos_pagamento.items():
            for palavra in palavras:
                if palavra.upper() in descricao:
                    return tipo
        return "outros"

    def _fallback(self, descricao: str, valor: float, trntype: Optional[str] = None) -> str:
        """Fallback quando nenhuma regra específica é encontrada."""
        if valor > 0:
            if "PIX" in descricao:
                return "receitas_pix"
            return "receitas_nao_classificadas"
        else:
            if trntype and "CREDIT" in trntype.upper():
                return "receitas_nao_classificadas"
            return "outras_despesas"

    # ============================================================
    # MÉTODOS PÚBLICOS
    # ============================================================

    def get_stats(self) -> Dict:
        """Retorna estatísticas do classificador."""
        return {
            "cache": self.cache.stats,
            "categorias": len(self.regras.categorias),
            "tipos_pagamento": len(self.regras.tipos_pagamento),
            "aliases": len(self.aliases.aliases)
        }

    def recarregar_regras(self) -> None:
        """Recarrega regras do JSON (hot-reload)."""
        self.regras.recarregar()
        self.cache.clear()
        logger.info("🔄 Regras recarregadas e cache limpo")


# ============================================================
# INSTÂNCIA GLOBAL (SINGLETON)
# ============================================================

classificador = ClassificadorFinanceiro()