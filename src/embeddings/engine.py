"""
HyperMatrix v2026 - Embedding Engine
Semantic search using sentence-transformers and ChromaDB.
"""

import os
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Global embedding engine instance
_embedding_engine: Optional["EmbeddingEngine"] = None

# Configuration
DATA_DIR = os.getenv("DATA_DIR", "/app/data")
VECTORS_DIR = os.path.join(DATA_DIR, "vectors")
MODEL_NAME = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")


@dataclass
class SearchResult:
    """Result from semantic search."""
    filepath: str
    content: str
    score: float
    metadata: Dict[str, Any]


class EmbeddingEngine:
    """
    Embedding engine for semantic code search.
    Uses sentence-transformers for embeddings and ChromaDB for vector storage.
    """

    def __init__(self, persist_directory: str = None):
        self.persist_directory = persist_directory or VECTORS_DIR
        self.model = None
        self.chroma_client = None
        self.collection = None
        self._initialized = False
        self._available = False

        # Try to initialize
        self._init_engine()

    def _init_engine(self):
        """Initialize the embedding model and vector store."""
        try:
            # Import heavy dependencies only when needed
            from sentence_transformers import SentenceTransformer
            import chromadb
            from chromadb.config import Settings

            # Initialize model
            logger.info(f"Loading embedding model: {MODEL_NAME}")
            self.model = SentenceTransformer(MODEL_NAME)

            # Initialize ChromaDB with persistence
            os.makedirs(self.persist_directory, exist_ok=True)
            self.chroma_client = chromadb.PersistentClient(
                path=self.persist_directory,
                settings=Settings(anonymized_telemetry=False)
            )

            # Get or create collection
            self.collection = self.chroma_client.get_or_create_collection(
                name="code_embeddings",
                metadata={"description": "HyperMatrix code embeddings"}
            )

            self._initialized = True
            self._available = True
            logger.info(f"Embedding engine initialized. Collection has {self.collection.count()} documents.")

        except ImportError as e:
            logger.warning(f"Embedding dependencies not available: {e}")
            self._available = False
        except Exception as e:
            logger.error(f"Failed to initialize embedding engine: {e}")
            self._available = False

    @property
    def is_available(self) -> bool:
        """Check if embedding engine is available."""
        return self._available and self._initialized

    def index_file(
        self,
        file_path: str,
        content: str,
        metadata: Dict[str, Any] = None
    ) -> bool:
        """
        Index a file with its content.

        Args:
            file_path: Unique identifier for the file
            content: Text content to embed
            metadata: Additional metadata (file_type, functions, classes, etc.)

        Returns:
            True if indexing was successful
        """
        if not self.is_available:
            return False

        try:
            # Truncate content if too long (model has max sequence length)
            max_length = 8000  # Characters, not tokens
            if len(content) > max_length:
                content = content[:max_length]

            # Generate embedding
            embedding = self.model.encode(content).tolist()

            # Prepare metadata
            meta = metadata or {}
            meta["filepath"] = file_path
            meta["content_length"] = len(content)

            # Upsert to collection (update if exists, insert if not)
            self.collection.upsert(
                ids=[file_path],
                embeddings=[embedding],
                documents=[content],
                metadatas=[meta]
            )

            logger.debug(f"Indexed: {file_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to index {file_path}: {e}")
            return False

    def index_code_element(
        self,
        element_id: str,
        element_type: str,
        name: str,
        content: str,
        file_path: str,
        lineno: int = 0,
        metadata: Dict[str, Any] = None
    ) -> bool:
        """
        Index a specific code element (function, class, etc.).

        Args:
            element_id: Unique identifier (e.g., "filepath:function:name")
            element_type: Type of element (function, class, method, etc.)
            name: Name of the element
            content: Code content
            file_path: Source file path
            lineno: Line number
            metadata: Additional metadata

        Returns:
            True if indexing was successful
        """
        if not self.is_available:
            return False

        meta = metadata or {}
        meta.update({
            "element_type": element_type,
            "name": name,
            "filepath": file_path,
            "lineno": lineno,
        })

        return self.index_file(element_id, content, meta)

    def search(
        self,
        query: str,
        n_results: int = 10,
        filter_type: str = None,
        filter_path: str = None
    ) -> List[SearchResult]:
        """
        Semantic search for code.

        Args:
            query: Search query in natural language
            n_results: Number of results to return
            filter_type: Filter by element type (function, class, file)
            filter_path: Filter by file path prefix

        Returns:
            List of SearchResult objects
        """
        if not self.is_available:
            return []

        try:
            # Generate query embedding
            query_embedding = self.model.encode(query).tolist()

            # Build where filter
            where_filter = None
            if filter_type or filter_path:
                conditions = []
                if filter_type:
                    conditions.append({"element_type": filter_type})
                if filter_path:
                    conditions.append({"filepath": {"$contains": filter_path}})

                if len(conditions) == 1:
                    where_filter = conditions[0]
                else:
                    where_filter = {"$and": conditions}

            # Query collection
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results,
                where=where_filter,
                include=["documents", "metadatas", "distances"]
            )

            # Convert to SearchResult objects
            search_results = []
            if results and results["ids"] and results["ids"][0]:
                for i, doc_id in enumerate(results["ids"][0]):
                    # ChromaDB returns distances, convert to similarity score
                    distance = results["distances"][0][i] if results["distances"] else 0
                    score = 1.0 / (1.0 + distance)  # Convert distance to similarity

                    search_results.append(SearchResult(
                        filepath=doc_id,
                        content=results["documents"][0][i] if results["documents"] else "",
                        score=score,
                        metadata=results["metadatas"][0][i] if results["metadatas"] else {}
                    ))

            return search_results

        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []

    def hybrid_search(
        self,
        query: str,
        keyword: str = None,
        n_results: int = 10
    ) -> List[SearchResult]:
        """
        Hybrid search combining semantic and keyword search.

        Args:
            query: Semantic query
            keyword: Optional keyword to filter results
            n_results: Number of results

        Returns:
            List of SearchResult objects
        """
        # First do semantic search
        results = self.search(query, n_results=n_results * 2)

        # If keyword provided, boost results containing it
        if keyword:
            keyword_lower = keyword.lower()
            for result in results:
                if keyword_lower in result.content.lower():
                    result.score *= 1.5  # Boost score
                if keyword_lower in result.filepath.lower():
                    result.score *= 1.3  # Boost score

            # Re-sort by score
            results.sort(key=lambda x: x.score, reverse=True)

        return results[:n_results]

    def delete_file(self, file_path: str) -> bool:
        """Delete a file from the index."""
        if not self.is_available:
            return False

        try:
            self.collection.delete(ids=[file_path])
            return True
        except Exception as e:
            logger.error(f"Failed to delete {file_path}: {e}")
            return False

    def clear_collection(self) -> bool:
        """Clear all documents from the collection."""
        if not self.is_available:
            return False

        try:
            # Delete and recreate collection
            self.chroma_client.delete_collection("code_embeddings")
            self.collection = self.chroma_client.get_or_create_collection(
                name="code_embeddings",
                metadata={"description": "HyperMatrix code embeddings"}
            )
            logger.info("Collection cleared")
            return True
        except Exception as e:
            logger.error(f"Failed to clear collection: {e}")
            return False

    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about the embedding index."""
        if not self.is_available:
            return {
                "available": False,
                "message": "Embedding engine not available"
            }

        try:
            count = self.collection.count()
            return {
                "available": True,
                "model": MODEL_NAME,
                "persist_directory": self.persist_directory,
                "document_count": count,
            }
        except Exception as e:
            return {
                "available": True,
                "error": str(e)
            }


def get_embedding_engine() -> EmbeddingEngine:
    """Get the global embedding engine instance."""
    global _embedding_engine
    if _embedding_engine is None:
        _embedding_engine = EmbeddingEngine()
    return _embedding_engine
