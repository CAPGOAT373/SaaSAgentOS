"""
Agent OS V6.0 - RAG Service Tests
Unit tests for Embedding, VectorStore, RetrievalEngine, and RAGService
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from agent_os.config import get_config, RAGConfig
from agent_os.core_platform.exceptions import NotFoundException, ValidationException
from agent_os.ai_layer.rag.embedding import (
    EmbeddingProvider, HashEmbeddingProvider, OpenAIEmbeddingProvider,
    get_embedding_provider,
)
from agent_os.ai_layer.rag.vector_store import (
    VectorStore, InMemoryVectorStore, Document, SearchResult, get_vector_store,
)
from agent_os.ai_layer.rag.retrieval import (
    RetrievalEngine, RetrievalResult, RetrievedChunk, get_retrieval_engine,
)
from agent_os.services.rag_service.service import (
    RAGService, RAGQueryResult, get_rag_service,
)


# ============================================================
# Embedding Tests
# ============================================================

class TestEmbeddingProvider:
    """Tests for HashEmbeddingProvider."""

    @pytest.fixture
    def embedder(self):
        return HashEmbeddingProvider(dim=128)

    @pytest.mark.asyncio
    async def test_embed_single(self, embedder):
        vec = await embedder.embed_single("hello world")
        assert len(vec) == 128
        assert isinstance(vec[0], float)

    @pytest.mark.asyncio
    async def test_embed_batch(self, embedder):
        texts = ["hello world", "goodbye world", "test"]
        vecs = await embedder.embed(texts)
        assert len(vecs) == 3
        assert all(len(v) == 128 for v in vecs)

    @pytest.mark.asyncio
    async def test_embed_deterministic(self, embedder):
        v1 = await embedder.embed_single("hello world")
        v2 = await embedder.embed_single("hello world")
        assert v1 == v2

    @pytest.mark.asyncio
    async def test_embed_different_texts(self, embedder):
        v1 = await embedder.embed_single("hello world")
        v2 = await embedder.embed_single("completely different text")
        assert v1 != v2

    @pytest.mark.asyncio
    async def test_embed_similar_texts(self, embedder):
        v1 = await embedder.embed_single("The quick brown fox jumps over the lazy dog")
        v2 = await embedder.embed_single("A quick brown fox jumped over a lazy dog")
        sim = InMemoryVectorStore._cosine_similarity(v1, v2)
        assert sim > 0.5

    @pytest.mark.asyncio
    async def test_embed_empty_text(self, embedder):
        vec = await embedder.embed_single("")
        assert len(vec) == 128
        assert all(v == 0.0 for v in vec)

    @pytest.mark.asyncio
    async def test_embed_unicode_text(self, embedder):
        vec = await embedder.embed_single("你好世界 こんにちは")
        assert len(vec) == 128

    def test_dimension_property(self, embedder):
        assert embedder.dimension == 128

    @pytest.mark.asyncio
    async def test_embed_vector_normalized(self, embedder):
        vec = await embedder.embed_single("test text")
        norm = sum(v * v for v in vec) ** 0.5
        assert 0.99 < norm < 1.01


# ============================================================
# Vector Store Tests
# ============================================================

class TestVectorStore:
    """Tests for InMemoryVectorStore."""

    @pytest.fixture
    def store(self):
        return InMemoryVectorStore()

    @pytest.fixture
    def embedder(self):
        return HashEmbeddingProvider(dim=64)

    @pytest.mark.asyncio
    async def test_add_document(self, store, embedder):
        emb = await embedder.embed_single("test content")
        doc = Document(content="test content", embedding=emb, metadata={"source": "test"})
        ids = await store.add([doc])
        assert len(ids) == 1
        assert ids[0] == doc.doc_id

    @pytest.mark.asyncio
    async def test_add_multiple_documents(self, store, embedder):
        docs = []
        for i in range(5):
            emb = await embedder.embed_single(f"document {i}")
            docs.append(Document(content=f"document {i}", embedding=emb))
        ids = await store.add(docs)
        assert len(ids) == 5

    @pytest.mark.asyncio
    async def test_search_semantic(self, store, embedder):
        for text in ["machine learning basics", "deep learning neural networks", "cooking recipes pasta"]:
            emb = await embedder.embed_single(text)
            await store.add([Document(content=text, embedding=emb)])

        query_emb = await embedder.embed_single("artificial intelligence and ML")
        results = await store.search(query_emb, top_k=2)

        assert len(results) == 2
        assert results[0].score > results[1].score
        assert "machine" in results[0].doc.content or "neural" in results[0].doc.content

    @pytest.mark.asyncio
    async def test_search_threshold(self, store, embedder):
        emb = await embedder.embed_single("python programming")
        await store.add([Document(content="python programming", embedding=emb)])

        query_emb = await embedder.embed_single("cooking recipes")
        results = await store.search(query_emb, top_k=5, threshold=0.5)

        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_search_with_filters(self, store, embedder):
        emb1 = await embedder.embed_single("python code")
        emb2 = await embedder.embed_single("python tutorial")
        await store.add([
            Document(content="python code", embedding=emb1, metadata={"source": "docs", "lang": "en"}),
            Document(content="python tutorial", embedding=emb2, metadata={"source": "blog", "lang": "en"}),
        ])

        query_emb = await embedder.embed_single("python")
        results = await store.search(query_emb, top_k=5, filters={"source": "docs"})

        assert len(results) == 1
        assert results[0].doc.metadata["source"] == "docs"

    @pytest.mark.asyncio
    async def test_get_document(self, store, embedder):
        emb = await embedder.embed_single("test")
        doc = Document(content="test", embedding=emb)
        await store.add([doc])

        fetched = await store.get(doc.doc_id)
        assert fetched is not None
        assert fetched.content == "test"

    @pytest.mark.asyncio
    async def test_get_nonexistent(self, store):
        doc = await store.get("nonexistent-id")
        assert doc is None

    @pytest.mark.asyncio
    async def test_delete(self, store, embedder):
        emb = await embedder.embed_single("test")
        doc = Document(content="test", embedding=emb)
        await store.add([doc])

        count = await store.delete([doc.doc_id])
        assert count == 1
        assert await store.get(doc.doc_id) is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent(self, store):
        count = await store.delete(["nonexistent"])
        assert count == 0

    @pytest.mark.asyncio
    async def test_count(self, store, embedder):
        assert await store.count() == 0
        emb = await embedder.embed_single("test")
        await store.add([Document(content="test", embedding=emb)])
        assert await store.count() == 1

    @pytest.mark.asyncio
    async def test_clear(self, store, embedder):
        emb = await embedder.embed_single("test")
        await store.add([Document(content="test", embedding=emb)])
        await store.clear()
        assert await store.count() == 0

    @pytest.mark.asyncio
    async def test_document_to_dict(self, store, embedder):
        emb = await embedder.embed_single("test")
        doc = Document(content="test content", embedding=emb, metadata={"key": "val"})
        d = doc.to_dict()
        assert d["doc_id"] == doc.doc_id
        assert d["content"] == "test content"
        assert d["metadata"]["key"] == "val"

    @pytest.mark.asyncio
    async def test_search_result_to_dict(self, store, embedder):
        emb = await embedder.embed_single("test")
        doc = Document(content="test", embedding=emb)
        sr = SearchResult(doc=doc, score=0.95, rank=1)
        d = sr.to_dict()
        assert d["score"] == 0.95
        assert d["rank"] == 1

    def test_cosine_similarity_identical(self):
        v = [0.5, 0.5, 0.5, 0.5]
        sim = InMemoryVectorStore._cosine_similarity(v, v)
        assert abs(sim - 1.0) < 0.0001

    def test_cosine_similarity_orthogonal(self):
        v1 = [1.0, 0.0, 0.0]
        v2 = [0.0, 1.0, 0.0]
        sim = InMemoryVectorStore._cosine_similarity(v1, v2)
        assert abs(sim - 0.0) < 0.0001


# ============================================================
# Retrieval Engine Tests
# ============================================================

class TestRetrievalEngine:
    """Tests for RetrievalEngine."""

    @pytest.fixture
    def engine(self):
        store = InMemoryVectorStore()
        embedder = HashEmbeddingProvider(dim=64)
        e = RetrievalEngine(vector_store=store)
        e._embedder = embedder
        return e

    @pytest.mark.asyncio
    async def test_ingest_document(self, engine):
        ids = await engine.ingest_document(
            "This is a test document about machine learning and artificial intelligence.",
            metadata={"source": "test", "topic": "AI"},
        )
        assert len(ids) > 0
        assert await engine.count() > 0

    @pytest.mark.asyncio
    async def test_ingest_long_document_chunks(self, engine):
        long_text = "chunk " * 300
        ids = await engine.ingest_document(long_text)
        assert len(ids) > 1

    @pytest.mark.asyncio
    async def test_search_returns_results(self, engine):
        await engine.ingest_document(
            "Python is a popular programming language for data science.",
            metadata={"source": "docs"},
        )
        await engine.ingest_document(
            "Machine learning uses algorithms to find patterns in data.",
            metadata={"source": "docs"},
        )
        await engine.ingest_document(
            "Cooking pasta requires boiling water and adding salt.",
            metadata={"source": "recipes"},
        )

        result = await engine.search("python programming", top_k=2)
        assert len(result.chunks) > 0
        assert result.total_found > 0
        assert result.query == "python programming"

    @pytest.mark.asyncio
    async def test_search_with_filters(self, engine):
        await engine.ingest_document(
            "Python data science tutorial", metadata={"source": "docs"},
        )
        await engine.ingest_document(
            "Python web development", metadata={"source": "blog"},
        )

        result = await engine.search("python", filters={"source": "docs"})
        assert len(result.chunks) == 1
        assert result.chunks[0].metadata["source"] == "docs"

    @pytest.mark.asyncio
    async def test_search_empty_store(self, engine):
        result = await engine.search("any query")
        assert len(result.chunks) == 0
        assert result.total_found == 0

    @pytest.mark.asyncio
    async def test_search_latency_recorded(self, engine):
        await engine.ingest_document("test document for search")
        result = await engine.search("test")
        assert result.latency_ms >= 0

    @pytest.mark.asyncio
    async def test_context_assembly(self, engine):
        await engine.ingest_document(
            "First chunk of information about the topic. " * 20,
            metadata={"topic": "A"},
        )
        await engine.ingest_document(
            "Second chunk with different information. " * 20,
            metadata={"topic": "B"},
        )

        result = await engine.search("information topic", top_k=2)
        assert len(result.context) > 0
        assert "---" in result.context

    @pytest.mark.asyncio
    async def test_delete_document(self, engine):
        ids = await engine.ingest_document("test document")
        count = await engine.delete_document(ids[0])
        assert count == 1

    @pytest.mark.asyncio
    async def test_delete_by_filter(self, engine):
        await engine.ingest_document("doc A", metadata={"source": "keep"})
        await engine.ingest_document("doc B", metadata={"source": "delete"})
        await engine.ingest_document("doc C", metadata={"source": "delete"})

        count = await engine.delete_by_filter({"source": "delete"})
        assert count == 2

    @pytest.mark.asyncio
    async def test_hybrid_search_fusion(self, engine):
        await engine.ingest_document("deep learning neural networks backpropagation")
        await engine.ingest_document("python python python programming")

        result = await engine.search("python programming")
        assert result.total_found >= 1

    @pytest.mark.asyncio
    async def test_get_document(self, engine):
        ids = await engine.ingest_document("specific document content")
        doc = await engine.get_document(ids[0])
        assert doc is not None
        assert "specific" in doc.content


# ============================================================
# RAG Service Tests
# ============================================================

class TestRAGService:
    """Tests for RAGService."""

    @pytest.fixture
    def rag_svc(self):
        svc = RAGService()
        store = InMemoryVectorStore()
        embedder = HashEmbeddingProvider(dim=64)
        engine = RetrievalEngine(vector_store=store)
        engine._embedder = embedder
        svc._engine = engine
        svc._embedder = embedder
        svc._store = store
        return svc

    @pytest.mark.asyncio
    async def test_ingest_document(self, rag_svc, service_context):
        result = await rag_svc.ingest_document(
            "Machine learning is a subset of artificial intelligence.",
            metadata={"source": "wiki"}, ctx=service_context,
        )
        assert result["chunk_count"] > 0
        assert len(result["doc_ids"]) > 0

    @pytest.mark.asyncio
    async def test_ingest_empty_document(self, rag_svc):
        with pytest.raises(ValidationException, match="cannot be empty"):
            await rag_svc.ingest_document("")

    @pytest.mark.asyncio
    async def test_ingest_whitespace_document(self, rag_svc):
        with pytest.raises(ValidationException, match="cannot be empty"):
            await rag_svc.ingest_document("   ")

    @pytest.mark.asyncio
    async def test_ingest_documents_batch(self, rag_svc, service_context):
        docs = [
            {"content": "Python programming guide", "metadata": {"source": "docs"}},
            {"content": "JavaScript tutorial", "metadata": {"source": "tutorials"}},
            {"content": "Database design patterns", "metadata": {"source": "docs"}},
        ]
        result = await rag_svc.ingest_documents(docs, ctx=service_context)
        assert result["doc_count"] == 3
        assert result["total_chunks"] >= 3

    @pytest.mark.asyncio
    async def test_ingest_documents_empty_list(self, rag_svc):
        with pytest.raises(ValidationException, match="cannot be empty"):
            await rag_svc.ingest_documents([])

    @pytest.mark.asyncio
    async def test_search(self, rag_svc, service_context):
        await rag_svc.ingest_document("Python is great for data science")
        await rag_svc.ingest_document("JavaScript is for web development")
        await rag_svc.ingest_document("Python pandas for data analysis")

        result = await rag_svc.search("python data", top_k=2, ctx=service_context)
        assert len(result["chunks"]) == 2
        assert result["total_found"] >= 2

    @pytest.mark.asyncio
    async def test_search_empty_query(self, rag_svc):
        with pytest.raises(ValidationException, match="cannot be empty"):
            await rag_svc.search("")

    @pytest.mark.asyncio
    async def test_ask(self, rag_svc, service_context):
        await rag_svc.ingest_document(
            "The capital of France is Paris. France is in Europe.",
            metadata={"source": "geography"},
        )
        await rag_svc.ingest_document(
            "Python was created by Guido van Rossum in 1991.",
            metadata={"source": "history"},
        )

        result = await rag_svc.ask("What is the capital of France?", top_k=2, ctx=service_context)

        assert result["query"] == "What is the capital of France?"
        assert len(result["chunks"]) > 0
        assert result["total_found"] > 0

    @pytest.mark.asyncio
    async def test_get_document(self, rag_svc):
        result = await rag_svc.ingest_document("test doc content")
        doc_id = result["doc_ids"][0]

        doc = await rag_svc.get_document(doc_id)
        assert doc["doc_id"] == doc_id

    @pytest.mark.asyncio
    async def test_get_document_not_found(self, rag_svc):
        with pytest.raises(NotFoundException, match="Document not found"):
            await rag_svc.get_document("nonexistent")

    @pytest.mark.asyncio
    async def test_delete_document(self, rag_svc, service_context):
        result = await rag_svc.ingest_document("to be deleted")
        doc_id = result["doc_ids"][0]

        del_result = await rag_svc.delete_document(doc_id, ctx=service_context)
        assert del_result["deleted"] is True

        with pytest.raises(NotFoundException):
            await rag_svc.get_document(doc_id)

    @pytest.mark.asyncio
    async def test_delete_document_not_found(self, rag_svc):
        with pytest.raises(NotFoundException, match="Document not found"):
            await rag_svc.delete_document("nonexistent")

    @pytest.mark.asyncio
    async def test_delete_by_filter(self, rag_svc, service_context):
        await rag_svc.ingest_document("keep me", metadata={"tag": "keep"})
        await rag_svc.ingest_document("delete me", metadata={"tag": "delete"})
        await rag_svc.ingest_document("delete me too", metadata={"tag": "delete"})

        result = await rag_svc.delete_by_filter({"tag": "delete"}, ctx=service_context)
        assert result["deleted"] == 2

    @pytest.mark.asyncio
    async def test_list_documents(self, rag_svc):
        await rag_svc.ingest_document("doc1")
        await rag_svc.ingest_document("doc2")

        docs = await rag_svc.list_documents()
        assert len(docs) >= 2

    @pytest.mark.asyncio
    async def test_clear_knowledge_base(self, rag_svc, service_context):
        await rag_svc.ingest_document("doc1")
        await rag_svc.ingest_document("doc2")

        result = await rag_svc.clear_knowledge_base(ctx=service_context)
        assert result["cleared"] is True
        assert result["document_count"] >= 2

        docs = await rag_svc.list_documents()
        assert len(docs) == 0

    @pytest.mark.asyncio
    async def test_get_stats(self, rag_svc):
        await rag_svc.ingest_document("doc1", metadata={"source": "wiki"})
        await rag_svc.ingest_document("doc2", metadata={"source": "docs"})

        stats = await rag_svc.get_stats()
        assert stats["total_documents"] >= 2
        assert stats["embedding_dimension"] == 64
        assert "sources" in stats
        assert "config" in stats

    @pytest.mark.asyncio
    async def test_health_check(self, rag_svc):
        result = await rag_svc.health_check()
        assert result["status"] == "healthy"
        assert result["service"] == "RAGService"

    def test_rag_query_result_to_dict(self):
        qr = RAGQueryResult(
            query="test query", answer="test answer",
            chunks=[{"content": "chunk1"}], total_found=5,
            latency_ms=12.5,
        )
        d = qr.to_dict()
        assert d["query"] == "test query"
        assert d["answer"] == "test answer"
        assert d["latency_ms"] == 12.5

    def test_singleton(self):
        svc1 = get_rag_service()
        svc2 = get_rag_service()
        assert svc1 is svc2


# ============================================================
# Integration Tests (Full Pipeline)
# ============================================================

class TestRAGPipelineIntegration:
    """End-to-end integration tests for the full RAG pipeline."""

    @pytest.fixture
    def rag_svc(self):
        svc = RAGService()
        store = InMemoryVectorStore()
        embedder = HashEmbeddingProvider(dim=32)
        engine = RetrievalEngine(vector_store=store)
        engine._embedder = embedder
        svc._engine = engine
        svc._embedder = embedder
        svc._store = store
        return svc

    @pytest.mark.asyncio
    async def test_full_rag_pipeline(self, rag_svc, service_context):
        """Ingest - Search - Retrieve - Verify."""
        await rag_svc.ingest_documents([
            {
                "content": "Cloud computing provides on-demand access to computing resources including servers, storage, databases, networking, software, and analytics over the internet.",
                "metadata": {"source": "cloud", "topic": "infrastructure"},
            },
            {
                "content": "Container orchestration tools like Kubernetes automate deployment, scaling, and management of containerized applications.",
                "metadata": {"source": "containers", "topic": "devops"},
            },
            {
                "content": "Serverless computing allows developers to build and run applications without managing servers. AWS Lambda is a popular serverless platform.",
                "metadata": {"source": "serverless", "topic": "cloud"},
            },
            {
                "content": "Machine learning models require training data, feature engineering, and hyperparameter tuning to achieve good performance.",
                "metadata": {"source": "ml", "topic": "AI"},
            },
            {
                "content": "Data preprocessing is a crucial step in machine learning pipelines. It involves cleaning, normalization, and feature extraction.",
                "metadata": {"source": "ml", "topic": "AI"},
            },
        ], ctx=service_context)

        # Verify stats
        stats = await rag_svc.get_stats()
        assert stats["total_documents"] >= 5
        assert stats["sources"]["cloud"] >= 1
        assert stats["sources"]["ml"] >= 2

        # Search for cloud
        result = await rag_svc.search("cloud computing services", top_k=3, ctx=service_context)
        assert len(result["chunks"]) == 3
        assert any("cloud" in c["content"].lower() or "serverless" in c["content"].lower()
                   for c in result["chunks"])

        # Search for ML
        ml_result = await rag_svc.search("machine learning data preprocessing", top_k=3)
        assert len(ml_result["chunks"]) >= 2
        assert any("machine learning" in c["content"].lower() or "preprocessing" in c["content"].lower()
                   for c in ml_result["chunks"])

        # Filter by metadata
        filtered = await rag_svc.search("computing", filters={"topic": "AI"}, top_k=5)
        for chunk in filtered["chunks"]:
            assert chunk["metadata"]["topic"] == "AI"

    @pytest.mark.asyncio
    async def test_semantic_similarity_ranking(self, rag_svc, service_context):
        """Verify that semantically similar content ranks higher."""
        await rag_svc.ingest_documents([
            {"content": "The Eiffel Tower is a wrought-iron lattice tower in Paris, France."},
            {"content": "Machine learning is a method of data analysis that automates analytical model building."},
            {"content": "Paris is the capital city of France, known for its art, culture, and cuisine."},
        ], ctx=service_context)

        result = await rag_svc.search("famous landmarks in Paris France", top_k=3)
        assert "machine learning" not in result["chunks"][0]["content"].lower()

    @pytest.mark.asyncio
    async def test_chunking_large_document(self, rag_svc, service_context):
        """Verify large documents are properly chunked."""
        large_text = "The quick brown fox jumps over the lazy dog. " * 100
        result = await rag_svc.ingest_document(large_text, ctx=service_context)
        assert result["chunk_count"] > 1

        search = await rag_svc.search("quick brown fox", top_k=3)
        assert len(search["chunks"]) > 0

    @pytest.mark.asyncio
    async def test_delete_and_cleanup(self, rag_svc, service_context):
        """Verify delete and cleanup operations."""
        await rag_svc.ingest_documents([
            {"content": "Doc A", "metadata": {"batch": "1"}},
            {"content": "Doc B", "metadata": {"batch": "1"}},
            {"content": "Doc C", "metadata": {"batch": "2"}},
        ], ctx=service_context)

        deleted = await rag_svc.delete_by_filter({"batch": "1"}, ctx=service_context)
        assert deleted["deleted"] == 2

        docs = await rag_svc.list_documents()
        assert len(docs) >= 1
        for d in docs:
            assert d["metadata"].get("batch") != "1"

        await rag_svc.clear_knowledge_base(ctx=service_context)
        docs = await rag_svc.list_documents()
        assert len(docs) == 0