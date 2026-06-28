"""
Agent OS V6.0 - Vector Store
In-memory vector database with pluggable backends
"""
import uuid
import math
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timezone

from agent_os.config import get_config


@dataclass
class Document:
    doc_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    content: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    embedding: Optional[List[float]] = None
    chunk_index: int = 0
    parent_doc_id: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict:
        return {
            "doc_id": self.doc_id,
            "content": self.content[:200],
            "metadata": self.metadata,
            "chunk_index": self.chunk_index,
            "parent_doc_id": self.parent_doc_id,
            "created_at": self.created_at,
        }


@dataclass
class SearchResult:
    doc: Document
    score: float
    rank: int = 0

    def to_dict(self) -> dict:
        return {
            "doc": self.doc.to_dict(),
            "score": round(self.score, 4),
            "rank": self.rank,
        }


class VectorStore(ABC):
    """Abstract vector store interface."""

    @abstractmethod
    async def add(self, documents: List[Document]) -> List[str]:
        """Add documents to the store, returns doc_ids."""
        pass

    @abstractmethod
    async def search(
        self, query_embedding: List[float], top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None,
        threshold: float = 0.0,
    ) -> List[SearchResult]:
        """Search for similar documents by embedding."""
        pass

    @abstractmethod
    async def delete(self, doc_ids: List[str]) -> int:
        """Delete documents by IDs, returns count deleted."""
        pass

    @abstractmethod
    async def get(self, doc_id: str) -> Optional[Document]:
        """Get a document by ID."""
        pass

    @abstractmethod
    async def count(self) -> int:
        """Return total document count."""
        pass

    @abstractmethod
    async def clear(self):
        """Remove all documents."""
        pass


class InMemoryVectorStore(VectorStore):
    """
    In-memory vector store with cosine similarity search.

    Suitable for development and testing. For production,
    swap with ChromaDB, Qdrant, Pinecone, or Milvus backends.
    """

    def __init__(self):
        self._documents: Dict[str, Document] = {}
        self._embeddings: Dict[str, List[float]] = {}

    async def add(self, documents: List[Document]) -> List[str]:
        ids = []
        for doc in documents:
            self._documents[doc.doc_id] = doc
            if doc.embedding:
                self._embeddings[doc.doc_id] = doc.embedding
            ids.append(doc.doc_id)
        return ids

    async def search(
        self, query_embedding: List[float], top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None,
        threshold: float = 0.0,
    ) -> List[SearchResult]:
        scores = []
        for doc_id, emb in self._embeddings.items():
            doc = self._documents[doc_id]

            # Apply filters
            if filters:
                if not self._match_filters(doc, filters):
                    continue

            score = self._cosine_similarity(query_embedding, emb)
            if score >= threshold:
                scores.append((doc, score))

        scores.sort(key=lambda x: x[1], reverse=True)
        results = []
        for rank, (doc, score) in enumerate(scores[:top_k]):
            results.append(SearchResult(doc=doc, score=score, rank=rank + 1))

        return results

    async def delete(self, doc_ids: List[str]) -> int:
        count = 0
        for doc_id in doc_ids:
            if doc_id in self._documents:
                del self._documents[doc_id]
                self._embeddings.pop(doc_id, None)
                count += 1
        return count

    async def get(self, doc_id: str) -> Optional[Document]:
        return self._documents.get(doc_id)

    async def count(self) -> int:
        return len(self._documents)

    async def clear(self):
        self._documents.clear()
        self._embeddings.clear()

    @staticmethod
    def _cosine_similarity(a: List[float], b: List[float]) -> float:
        if not a or not b:
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(x * x for x in b))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    @staticmethod
    def _match_filters(doc: Document, filters: Dict[str, Any]) -> bool:
        for key, value in filters.items():
            doc_val = doc.metadata.get(key)
            if doc_val != value:
                return False
        return True


_vector_store: Optional[VectorStore] = None


def get_vector_store() -> VectorStore:
    """Get the configured vector store singleton."""
    global _vector_store
    if _vector_store is None:
        cfg = get_config().rag
        if cfg.vector_store_backend == "memory":
            _vector_store = InMemoryVectorStore()
        else:
            # Fallback to in-memory for unsupported backends
            _vector_store = InMemoryVectorStore()
    return _vector_store