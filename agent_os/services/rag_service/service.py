"""
Agent OS V6.0 - RAG Service
Retrieval-Augmented Generation service wrapping the RAG pipeline.
"""
import uuid
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field

from agent_os.core_platform.base import BaseService, ServiceContext
from agent_os.core_platform.exceptions import NotFoundException, ValidationException
from agent_os.ai_layer.rag.retrieval import (
    RetrievalEngine, RetrievalResult, RetrievedChunk, get_retrieval_engine,
)
from agent_os.ai_layer.rag.vector_store import Document, SearchResult
from agent_os.ai_layer.rag.embedding import get_embedding_provider
from agent_os.config import get_config


@dataclass
class RAGQueryResult:
    query_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    query: str = ""
    answer: str = ""
    chunks: List[Dict[str, Any]] = field(default_factory=list)
    total_found: int = 0
    latency_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "query_id": self.query_id,
            "query": self.query,
            "answer": self.answer,
            "chunks": self.chunks[:5],
            "total_found": self.total_found,
            "latency_ms": round(self.latency_ms, 2),
            "metadata": self.metadata,
        }


class RAGService(BaseService):
    """
    RAG Service: document ingestion, semantic search, context retrieval.

    API:
    - ingest_document / ingest_documents: Add documents to the knowledge base
    - search: Semantic + keyword hybrid search
    - ask: Search + answer generation (RAG query)
    - get_document / delete_document / list_documents: Document management
    - get_stats: Knowledge base statistics
    """

    def __init__(self):
        super().__init__()
        self._engine = get_retrieval_engine()
        self._embedder = get_embedding_provider()
        self._store = self._engine._store
        self._config = get_config().rag

    # ── Document Ingestion ────────────────────────────

    async def ingest_document(
        self, content: str, metadata: Optional[Dict[str, Any]] = None,
        ctx: Optional[ServiceContext] = None,
    ) -> Dict[str, Any]:
        """Ingest a single document into the knowledge base."""
        if not content or not content.strip():
            raise ValidationException("Document content cannot be empty")

        doc_ids = await self._engine.ingest_document(content, metadata)

        await self.emit_event("rag.document.ingested", {
            "doc_ids": doc_ids,
            "chunk_count": len(doc_ids),
            "metadata": metadata,
        }, ctx)

        self.log("info", f"Ingested document: {len(doc_ids)} chunks", ctx)

        return {
            "doc_ids": doc_ids,
            "chunk_count": len(doc_ids),
            "metadata": metadata,
        }

    async def ingest_documents(
        self, documents: List[Dict[str, Any]],
        ctx: Optional[ServiceContext] = None,
    ) -> Dict[str, Any]:
        """Batch ingest multiple documents."""
        if not documents:
            raise ValidationException("Documents list cannot be empty")

        all_ids = []
        for doc in documents:
            content = doc.get("content", "")
            metadata = doc.get("metadata", {})
            if content:
                ids = await self._engine.ingest_document(content, metadata)
                all_ids.extend(ids)

        await self.emit_event("rag.documents.ingested", {
            "doc_count": len(documents),
            "total_chunks": len(all_ids),
        }, ctx)

        self.log("info", f"Batch ingested {len(documents)} documents: {len(all_ids)} chunks", ctx)

        return {
            "doc_count": len(documents),
            "total_chunks": len(all_ids),
            "doc_ids": all_ids,
        }

    # ── Search & Retrieval ────────────────────────────

    async def search(
        self, query: str, top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None,
        threshold: Optional[float] = None,
        ctx: Optional[ServiceContext] = None,
    ) -> Dict[str, Any]:
        """Semantic + keyword hybrid search."""
        if not query or not query.strip():
            raise ValidationException("Query cannot be empty")

        result = await self._engine.search(
            query=query, top_k=top_k, filters=filters, threshold=threshold,
        )

        self.log("info", f"Search '{query[:50]}': {result.total_found} results", ctx)

        return result.to_dict()

    async def ask(
        self, query: str, top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None,
        include_answer: bool = True,
        ctx: Optional[ServiceContext] = None,
    ) -> Dict[str, Any]:
        """
        RAG query: search + answer generation.

        Retrieves relevant context and optionally generates
        an answer using the LLM gateway.
        """
        if not query or not query.strip():
            raise ValidationException("Query cannot be empty")

        result = await self._engine.search(
            query=query, top_k=top_k, filters=filters,
        )

        answer = ""
        if include_answer and result.chunks:
            answer = await self._generate_answer(query, result.context)

        query_result = RAGQueryResult(
            query=query,
            answer=answer,
            chunks=[c.to_dict() for c in result.chunks],
            total_found=result.total_found,
            latency_ms=result.latency_ms,
        )

        await self.emit_event("rag.query.executed", {
            "query": query[:100],
            "chunks_found": result.total_found,
            "has_answer": bool(answer),
        }, ctx)

        return query_result.to_dict()

    async def _generate_answer(self, query: str, context: str) -> str:
        """Generate answer using retrieved context via LLM gateway."""
        try:
            from agent_os.ai_layer.llm_gateway import get_llm_gateway
            llm = get_llm_gateway()
            prompt = (
                f"Based on the following context, answer the question.\n\n"
                f"Context:\n{context}\n\n"
                f"Question: {query}\n\n"
                f"Answer:"
            )
            response = await llm.generate(prompt)
            return response.strip()
        except Exception:
            # Fallback: return context-based summary
            return f"Found {len(context.split(chr(10)))} lines of relevant context."

    # ── Document Management ───────────────────────────

    async def get_document(self, doc_id: str) -> Dict[str, Any]:
        """Get a document by ID."""
        doc = await self._engine.get_document(doc_id)
        if not doc:
            raise NotFoundException("Document", doc_id)
        return doc.to_dict()

    async def delete_document(self, doc_id: str, ctx: Optional[ServiceContext] = None) -> Dict[str, Any]:
        """Delete a document by ID."""
        count = await self._engine.delete_document(doc_id)
        if count == 0:
            raise NotFoundException("Document", doc_id)

        self.log("info", f"Deleted document: {doc_id}", ctx)
        return {"deleted": True, "doc_id": doc_id}

    async def delete_by_filter(
        self, filters: Dict[str, Any],
        ctx: Optional[ServiceContext] = None,
    ) -> Dict[str, Any]:
        """Delete documents matching metadata filters."""
        count = await self._engine.delete_by_filter(filters)
        self.log("info", f"Deleted {count} documents by filter", ctx)
        return {"deleted": count, "filter": filters}

    async def list_documents(
        self, limit: int = 50, offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """List all documents in the knowledge base."""
        docs = list(self._store._documents.values())
        return [d.to_dict() for d in docs[offset:offset + limit]]

    async def clear_knowledge_base(self, ctx: Optional[ServiceContext] = None) -> Dict[str, Any]:
        """Clear all documents from the knowledge base."""
        count = await self._engine.count()
        await self._engine.clear()
        self.log("info", f"Cleared knowledge base: {count} documents", ctx)
        return {"cleared": True, "document_count": count}

    # ── Statistics ────────────────────────────────────

    async def get_stats(self) -> Dict[str, Any]:
        """Get knowledge base statistics."""
        count = await self._engine.count()

        sources = {}
        for doc in self._store._documents.values():
            source = doc.metadata.get("source", "unknown")
            sources[source] = sources.get(source, 0) + 1

        return {
            "total_documents": count,
            "embedding_dimension": self._embedder.dimension,
            "embedding_provider": self._config.embedding_provider,
            "vector_store_backend": self._config.vector_store_backend,
            "sources": sources,
            "config": {
                "chunk_size": self._config.chunk_size,
                "chunk_overlap": self._config.chunk_overlap,
                "top_k": self._config.top_k,
                "hybrid_search_weight": self._config.hybrid_search_weight,
            },
        }

    async def health_check(self) -> Dict[str, Any]:
        stats = await self.get_stats()
        return {
            "status": "healthy",
            "service": "RAGService",
            **stats,
        }


_rag_service: Optional[RAGService] = None


def get_rag_service() -> RAGService:
    global _rag_service
    if _rag_service is None:
        _rag_service = RAGService()
    return _rag_service