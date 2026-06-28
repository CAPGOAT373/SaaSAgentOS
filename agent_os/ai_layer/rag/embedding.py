"""
Agent OS V6.0 - Embedding Pipeline
Text → Vector conversion with pluggable providers
"""
import hashlib
import re
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from collections import Counter

from agent_os.config import get_config


class EmbeddingProvider(ABC):
    """Abstract embedding provider interface."""

    @abstractmethod
    async def embed(self, texts: List[str]) -> List[List[float]]:
        """Convert a list of texts to embedding vectors."""
        pass

    @abstractmethod
    async def embed_single(self, text: str) -> List[float]:
        """Convert a single text to an embedding vector."""
        pass

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Return the embedding dimension."""
        pass


class HashEmbeddingProvider(EmbeddingProvider):
    """
    Deterministic hash-based embedding for testing and development.

    Uses character n-grams + word-level hashing to produce a simple
    but semantically meaningful vector representation. Same text
    always produces the same vector. Similar texts produce similar vectors.

    For production, swap with OpenAIEmbeddingProvider or SentenceTransformerProvider.
    """

    def __init__(self, dim: int = 256, ngram_range: tuple = (2, 4)):
        self._dim = dim
        self._ngram_range = ngram_range

    @property
    def dimension(self) -> int:
        return self._dim

    async def embed_single(self, text: str) -> List[float]:
        results = await self.embed([text])
        return results[0]

    async def embed(self, texts: List[str]) -> List[List[float]]:
        vectors = []
        for text in texts:
            vec = self._text_to_vector(text)
            vectors.append(vec)
        return vectors

    def _text_to_vector(self, text: str) -> List[float]:
        """Convert text to a sparse-like dense vector using n-gram hashing."""
        text = text.lower().strip()
        if not text:
            return [0.0] * self._dim

        vec = [0.0] * self._dim

        # Word-level hashing
        words = re.findall(r'\w+', text)
        for word in words:
            idx = self._hash_to_index(word)
            vec[idx] += 1.0

        # Character n-gram hashing for subword features
        for n in range(self._ngram_range[0], self._ngram_range[1] + 1):
            for i in range(len(text) - n + 1):
                ngram = text[i:i + n]
                idx = self._hash_to_index(ngram)
                vec[idx] += 0.3  # Lower weight for n-grams

        # Normalize to unit length
        norm = sum(v * v for v in vec) ** 0.5
        if norm > 0:
            vec = [v / norm for v in vec]

        return vec

    def _hash_to_index(self, s: str) -> int:
        """Hash a string to an index in [0, dim)."""
        h = hashlib.md5(s.encode('utf-8')).hexdigest()
        return int(h, 16) % self._dim


class OpenAIEmbeddingProvider(EmbeddingProvider):
    """
    OpenAI embedding provider stub.

    Requires: pip install openai
    Usage: Set RAGConfig.embedding_provider = "openai"
    """

    def __init__(self, model: str = "text-embedding-3-small", dim: int = 1536):
        self._model = model
        self._dim = dim
        self._client = None

    @property
    def dimension(self) -> int:
        return self._dim

    async def _ensure_client(self):
        if self._client is None:
            try:
                from openai import AsyncOpenAI
                cfg = get_config()
                self._client = AsyncOpenAI(api_key=cfg.llm.api_key)
            except ImportError:
                raise ImportError("openai package required. Install: pip install openai")

    async def embed_single(self, text: str) -> List[float]:
        results = await self.embed([text])
        return results[0]

    async def embed(self, texts: List[str]) -> List[List[float]]:
        await self._ensure_client()
        response = await self._client.embeddings.create(
            model=self._model,
            input=texts,
        )
        return [d.embedding for d in response.data]


_embedding_provider: Optional[EmbeddingProvider] = None


def get_embedding_provider() -> EmbeddingProvider:
    """Get the configured embedding provider singleton."""
    global _embedding_provider
    if _embedding_provider is None:
        cfg = get_config().rag
        if cfg.embedding_provider == "openai":
            _embedding_provider = OpenAIEmbeddingProvider(dim=cfg.embedding_dim)
        else:
            _embedding_provider = HashEmbeddingProvider(dim=cfg.embedding_dim)
    return _embedding_provider