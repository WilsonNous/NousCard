# services/cache_classificador.py
# Cache LRU para classificação financeira

import logging
from collections import OrderedDict
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class CacheClassificador:
    """
    Cache LRU (Least Recently Used) para resultados de classificação.
    Evita reclassificar descrições idênticas.
    """

    def __init__(self, max_size: int = 10000):
        self.max_size = max_size
        self._cache: OrderedDict = OrderedDict()
        self._hits = 0
        self._misses = 0

    def get(self, chave: str) -> Optional[Dict]:
        """
        Busca no cache.
        Se encontrado, move para o final (LRU).
        """
        if chave in self._cache:
            self._cache.move_to_end(chave)
            self._hits += 1
            return self._cache[chave]
        self._misses += 1
        return None

    def set(self, chave: str, valor: Dict) -> None:
        """Armazena no cache. Remove o mais antigo se cheio."""
        if chave in self._cache:
            self._cache.move_to_end(chave)
        else:
            if len(self._cache) >= self.max_size:
                self._cache.popitem(last=False)  # Remove o mais antigo
        self._cache[chave] = valor

    def clear(self) -> None:
        """Limpa o cache."""
        self._cache.clear()
        self._hits = 0
        self._misses = 0
        logger.info("🧹 Cache limpo")

    @property
    def stats(self) -> Dict:
        """Estatísticas do cache."""
        total = self._hits + self._misses
        hit_rate = (self._hits / total * 100) if total > 0 else 0
        return {
            "size": len(self._cache),
            "max_size": self.max_size,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": f"{hit_rate:.1f}%"
        }

    def __len__(self) -> int:
        return len(self._cache)

    def __contains__(self, chave: str) -> bool:
        return chave in self._cache


# Instância global
cache = CacheClassificador()