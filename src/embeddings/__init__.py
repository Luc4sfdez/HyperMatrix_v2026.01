"""
HyperMatrix v2026 - Embeddings Module
Semantic search using sentence-transformers and ChromaDB.
"""

from .engine import EmbeddingEngine, get_embedding_engine

__all__ = ["EmbeddingEngine", "get_embedding_engine"]
