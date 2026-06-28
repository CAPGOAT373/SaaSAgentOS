"""
Agent OS V6.0 - Retrieval Engine
Semantic + keyword hybrid search, reranking, context assembly
"""
import re
import math
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field

from agent_os.config import get_config
from agent_os.ai_layer.rag.embedding import get_embedding_provider
from agent_os.ai_layer.rag.vector_store import (
    VectorStore, Document, SearchResult, get_vector_store,
)


@dataclass
class RetrievedChunk:
    doc_id: str = ""
    content: str = ""
    score: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    source: str = ""  # "semantic" | "keyword" | "hybrid"

    def to_dict(self) -> dict:
        return {
            "doc_id": self.doc_id,
            "content": self.content,
            "score": round(self.score, 4),
            "metadata": self.metadata,
            "source": self.source,
        }


@dataclass
class RetrievalResult:
    query: str = ""
    chunks: List[RetrievedChunk] = field(default_factory=list)
    total_found: int = 0
    latency_ms: float = 0.0
    context: str = ""

    def to_dict(self) -> dict:
        return {
            "query": self.query,
            "chunks": [c.to_dict() for c in self.chunks],
            "total_found": self.total_found,
            "latency_ms": round(self.latency_ms, 2),
            "context": self.context[:500],
        }


class RetrievalEngine:
    """
    Hybrid retrieval engine: semantic search + keyword search + reranking.

    Features:
    - Semantic search via embedding similarity
    - Keyword search via BM25-like scoring
    - Hybrid fusion with configurable weights
    - Result deduplication
    - Context window assembly
    """

    def __init__(
        self,
        vector_store: Optional[VectorStore] = None,
    ):
        self._store = vector_store or get_vector_store()
        self._embedder = get_embedding_provider()
        self._config = get_config().rag

    async def search(
        self, query: str, top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None,
        threshold: Optional[float] = None,
    ) -> RetrievalResult:
        """
        Hybrid search: semantic + keyword.

        Args:
            query: Search query text
            top_k: Number of results to return
            filters: Metadata filters (e.g., {"source": "docs"})
            threshold: Minimum similarity threshold

        Returns:
            RetrievalResult with ranked chunks
        """
        import time
        start = time.time()

        threshold = threshold if threshold is not None else self._config.similarity_threshold
        top_k = top_k or self._config.top_k

        # 1. Semantic search
        query_embedding = await self._embedder.embed_single(query)
        semantic_results = await self._store.search(
            query_embedding=query_embedding,
            top_k=top_k * 2,  # Fetch more for fusion
            filters=filters,
            threshold=threshold,
        )

        # 2. Keyword search (BM25-like)
        keyword_results = await self._keyword_search(
            query, top_k=top_k * 2, filters=filters,
        )

        # 3. Hybrid fusion
        merged = self._fusion_merge(
            semantic_results, keyword_results,
            weight=self._config.hybrid_search_weight,
        )

        # 4. Rerank if enabled
        if self._config.rerank_enabled:
            merged = self._rerank(query, merged)

        # 5. Select top_k and assemble context
        selected = merged[:top_k]
        chunks = []
        for sr in selected:
            chunks.append(RetrievedChunk(
                doc_id=sr.doc.doc_id,
                content=sr.doc.content,
                score=sr.score,
                metadata=sr.doc.metadata,
                source=sr.doc.metadata.get("_source", "hybrid"),
            ))

        # Assemble context
        context = self._assemble_context(chunks)

        latency = (time.time() - start) * 1000

        return RetrievalResult(
            query=query,
            chunks=chunks,
            total_found=len(merged),
            latency_ms=latency,
            context=context,
        )

    async def _keyword_search(
        self, query: str, top_k: int = 10,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[SearchResult]:
        """BM25-like keyword search over stored documents."""
        from agent_os.ai_layer.rag.vector_store import SearchResult

        query_terms = set(re.findall(r'\w+', query.lower()))

        if not query_terms:
            return []

        scored = []
        store = self._store
        if hasattr(store, '_documents') and hasattr(store, '_match_filters'):
            for doc_id, doc in store._documents.items():
                if filters and not store._match_filters(doc, filters):
                    continue

                score = self._bm25_score(query_terms, doc.content)
                if score > 0:
                    scored.append(SearchResult(doc=doc, score=score))

        scored.sort(key=lambda x: x.score, reverse=True)
        return scored[:top_k]

    def _bm25_score(self, query_terms: set, doc_text: str, k1: float = 1.5, b: float = 0.75) -> float:
        """Simple BM25-like scoring."""
        doc_terms = re.findall(r'\w+', doc_text.lower())
        if not doc_terms:
            return 0.0

        doc_len = len(doc_terms)
        avg_doc_len = 100  # Simplified; in production, compute from corpus

        score = 0.0
        term_freqs = {}
        for t in doc_terms:
            term_freqs[t] = term_freqs.get(t, 0) + 1

        for term in query_terms:
            tf = term_freqs.get(term, 0)
            if tf == 0:
                continue
            # BM25 term weight
            idf = 1.0  # Simplified; in production, compute from corpus
            numerator = tf * (k1 + 1)
            denominator = tf + k1 * (1 - b + b * doc_len / max(avg_doc_len, 1))
            score += idf * numerator / denominator

        return score

    def _fusion_merge(
        self, semantic: List[SearchResult], keyword: List[SearchResult],
        weight: float = 0.5,
    ) -> List[SearchResult]:
        """Merge semantic and keyword results using weighted fusion."""
        merged: Dict[str, SearchResult] = {}

        # Semantic results
        for sr in semantic:
            merged[sr.doc.doc_id] = SearchResult(
                doc=sr.doc, score=sr.score * weight, rank=0,
            )
            merged[sr.doc.doc_id].doc.metadata["_source"] = "semantic"

        # Keyword results (normalize scores to [0, 1])
        max_kw = max((r.score for r in keyword), default=1.0)
        for sr in keyword:
            norm_score = sr.score / max(max_kw, 1.0) * (1 - weight)
            if sr.doc.doc_id in merged:
                merged[sr.doc.doc_id].score += norm_score
                merged[sr.doc.doc_id].doc.metadata["_source"] = "hybrid"
            else:
                merged[sr.doc.doc_id] = SearchResult(
                    doc=sr.doc, score=norm_score, rank=0,
                )
                merged[sr.doc.doc_id].doc.metadata["_source"] = "keyword"

        results = list(merged.values())
        results.sort(key=lambda x: x.score, reverse=True)
        return results

    def _rerank(self, query: str, results: List[SearchResult]) -> List[SearchResult]:
        """Rerank results using cross-attention-like scoring."""
        query_terms = set(re.findall(r'\w+', query.lower()))

        for sr in results:
            doc_terms = set(re.findall(r'\w+', sr.doc.content.lower()))
            overlap = len(query_terms & doc_terms)
            # Boost by term overlap
            boost = 1.0 + (overlap / max(len(query_terms), 1)) * 0.2
            sr.score *= boost

        results.sort(key=lambda x: x.score, reverse=True)
        return results

    def _assemble_context(self, chunks: List[RetrievedChunk]) -> str:
        """Assemble retrieved chunks into a context string."""
        max_len = self._config.max_context_length
        context_parts = []
        total_len = 0

        for chunk in chunks:
            content = chunk.content
            if total_len + len(content) > max_len:
                remaining = max_len - total_len
                if remaining > 100:
                    context_parts.append(content[:remaining])
                break
            context_parts.append(content)
            total_len += len(content)

        return "\n\n---\n\n".join(context_parts)

    async def ingest_document(
        self, content: str, metadata: Optional[Dict[str, Any]] = None,
    ) -> List[str]:
        """Ingest a document: chunk, embed, store."""
        chunks = self._chunk_text(content)
        documents = []
        for i, chunk_text in enumerate(chunks):
            embedding = await self._embedder.embed_single(chunk_text)
            doc = Document(
                content=chunk_text,
                metadata=metadata or {},
                embedding=embedding,
                chunk_index=i,
            )
            documents.append(doc)

        return await self._store.add(documents)

    def _chunk_text(self, text: str) -> List[str]:
        """Split text into overlapping chunks."""
        chunk_size = self._config.chunk_size
        chunk_overlap = self._config.chunk_overlap

        if len(text) <= chunk_size:
            return [text]

        chunks = []
        start = 0
        while start < len(text):
            end = min(start + chunk_size, len(text))
            chunks.append(text[start:end])
            start += chunk_size - chunk_overlap

        return chunks

    async def delete_document(self, doc_id: str) -> int:
        return await self._store.delete([doc_id])

    async def delete_by_filter(self, filters: Dict[str, Any]) -> int:
        """Delete documents matching metadata filters."""
        store = self._store
        if hasattr(store, '_documents') and hasattr(store, '_match_filters'):
            to_delete = []
            for doc_id, doc in store._documents.items():
                if store._match_filters(doc, filters):
                    to_delete.append(doc_id)
            return await self._store.delete(to_delete)
        return 0

    async def get_document(self, doc_id: str) -> Optional[Document]:
        return await self._store.get(doc_id)

    async def count(self) -> int:
        return await self._store.count()

    async def clear(self):
        await self._store.clear()


_retrieval_engine: Optional[RetrievalEngine] = None


def get_retrieval_engine() -> RetrievalEngine:
    """Get the retrieval engine singleton."""
    global _retrieval_engine
    if _retrieval_engine is None:
        _retrieval_engine = RetrievalEngine()
    return _retrieval_engine