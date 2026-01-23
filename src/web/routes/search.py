"""
HyperMatrix v2026 - Semantic Search API
Endpoints for semantic code search using embeddings.
"""

import logging
from typing import Optional, List
from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel

from ...embeddings import get_embedding_engine

router = APIRouter(prefix="/api/search", tags=["search"])
logger = logging.getLogger(__name__)


class SearchRequest(BaseModel):
    """Request body for search."""
    query: str
    n_results: int = 10
    filter_type: Optional[str] = None
    filter_path: Optional[str] = None
    keyword: Optional[str] = None


class SearchResultItem(BaseModel):
    """A single search result."""
    filepath: str
    content: str
    score: float
    element_type: Optional[str] = None
    name: Optional[str] = None
    lineno: Optional[int] = None


class SearchResponse(BaseModel):
    """Response for search."""
    query: str
    results: List[SearchResultItem]
    total: int


@router.get("/status")
async def search_status():
    """Get status of the semantic search engine."""
    engine = get_embedding_engine()
    stats = engine.get_stats()
    return {
        "semantic_search": stats,
        "capabilities": {
            "semantic_search": engine.is_available,
            "hybrid_search": engine.is_available,
            "code_element_search": engine.is_available,
        }
    }


@router.get("")
async def search(
    q: str = Query(..., min_length=1, description="Search query"),
    n: int = Query(10, ge=1, le=50, description="Number of results"),
    type: Optional[str] = Query(None, description="Filter by type (function, class, file)"),
    path: Optional[str] = Query(None, description="Filter by path prefix"),
    keyword: Optional[str] = Query(None, description="Keyword for hybrid search"),
):
    """
    Semantic search for code.

    Performs semantic similarity search using embeddings.
    Optionally combines with keyword search for hybrid results.
    """
    engine = get_embedding_engine()

    if not engine.is_available:
        return {
            "query": q,
            "results": [],
            "total": 0,
            "message": "Semantic search not available. Install sentence-transformers and chromadb."
        }

    # Use hybrid search if keyword provided, otherwise pure semantic
    if keyword:
        results = engine.hybrid_search(q, keyword=keyword, n_results=n)
    else:
        results = engine.search(q, n_results=n, filter_type=type, filter_path=path)

    return {
        "query": q,
        "results": [
            {
                "filepath": r.filepath,
                "content": r.content[:500] + "..." if len(r.content) > 500 else r.content,
                "score": round(r.score, 4),
                "element_type": r.metadata.get("element_type"),
                "name": r.metadata.get("name"),
                "lineno": r.metadata.get("lineno"),
            }
            for r in results
        ],
        "total": len(results),
    }


@router.post("")
async def search_post(request: SearchRequest):
    """
    Semantic search for code (POST version).

    Same as GET but accepts JSON body for complex queries.
    """
    engine = get_embedding_engine()

    if not engine.is_available:
        return {
            "query": request.query,
            "results": [],
            "total": 0,
            "message": "Semantic search not available"
        }

    if request.keyword:
        results = engine.hybrid_search(
            request.query,
            keyword=request.keyword,
            n_results=request.n_results
        )
    else:
        results = engine.search(
            request.query,
            n_results=request.n_results,
            filter_type=request.filter_type,
            filter_path=request.filter_path
        )

    return {
        "query": request.query,
        "results": [
            {
                "filepath": r.filepath,
                "content": r.content[:500] + "..." if len(r.content) > 500 else r.content,
                "score": round(r.score, 4),
                "element_type": r.metadata.get("element_type"),
                "name": r.metadata.get("name"),
                "lineno": r.metadata.get("lineno"),
            }
            for r in results
        ],
        "total": len(results),
    }


@router.delete("/index")
async def clear_index():
    """Clear the entire search index."""
    engine = get_embedding_engine()

    if not engine.is_available:
        raise HTTPException(status_code=503, detail="Embedding engine not available")

    success = engine.clear_collection()
    if success:
        return {"status": "cleared", "message": "Search index cleared successfully"}
    else:
        raise HTTPException(status_code=500, detail="Failed to clear index")


@router.get("/similar/{filepath:path}")
async def find_similar(
    filepath: str,
    n: int = Query(10, ge=1, le=50, description="Number of similar files"),
):
    """
    Find files similar to the given file.

    Uses the embedding of the target file to find similar content.
    """
    engine = get_embedding_engine()

    if not engine.is_available:
        return {
            "filepath": filepath,
            "similar": [],
            "message": "Semantic search not available"
        }

    # Get the document from the collection
    try:
        result = engine.collection.get(
            ids=[filepath],
            include=["documents", "embeddings"]
        )

        if not result or not result["embeddings"] or not result["embeddings"][0]:
            return {
                "filepath": filepath,
                "similar": [],
                "message": "File not found in index"
            }

        # Use the file's embedding to search for similar
        file_embedding = result["embeddings"][0]

        similar_results = engine.collection.query(
            query_embeddings=[file_embedding],
            n_results=n + 1,  # +1 because it will include itself
            include=["documents", "metadatas", "distances"]
        )

        similar = []
        if similar_results and similar_results["ids"]:
            for i, doc_id in enumerate(similar_results["ids"][0]):
                if doc_id == filepath:
                    continue  # Skip the file itself

                distance = similar_results["distances"][0][i]
                score = 1.0 / (1.0 + distance)

                similar.append({
                    "filepath": doc_id,
                    "score": round(score, 4),
                    "metadata": similar_results["metadatas"][0][i] if similar_results["metadatas"] else {}
                })

        return {
            "filepath": filepath,
            "similar": similar[:n],
            "total": len(similar)
        }

    except Exception as e:
        logger.error(f"Error finding similar files: {e}")
        return {
            "filepath": filepath,
            "similar": [],
            "error": str(e)
        }
