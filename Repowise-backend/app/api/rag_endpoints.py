"""
RAG API Endpoints - Phase 2
Endpoints for repository indexing and RAG-powered queries
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from ..services.rag_service import rag_service  #  Import singleton directly!
from ..core.config import settings
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/rag", tags=["RAG Pipeline"])

# No need to initialize - using singleton from rag_service.py


# Request/Response Models
class IndexRepositoryRequest(BaseModel):
    """Request model for repository indexing"""
    repository_url: str = Field(..., description="GitHub repository URL")
    collection_name: Optional[str] = Field(None, description="Custom collection name")
    chunk_size: int = Field(1000, description="Size of text chunks", ge=100, le=5000)
    max_files: int = Field(500, description="Maximum files to process", ge=1, le=2000)
    force_reindex: bool = Field(False, description="Force re-indexing if collection exists")


class SearchRequest(BaseModel):
    """Request model for semantic search"""
    query: str = Field(..., description="Search query")
    collection_name: str = Field(..., description="Collection to search")
    n_results: int = Field(5, description="Number of results", ge=1, le=20)
    language_filter: Optional[str] = Field(None, description="Filter by language (e.g., 'python')")


class GenerateAnswerRequest(BaseModel):
    """Request model for RAG answer generation"""
    query: str = Field(..., description="User question")
    collection_name: str = Field(..., description="Collection to query")
    n_context: int = Field(3, description="Number of context documents", ge=1, le=10)
    use_llm: bool = Field(True, description="Use LLM for generation")


class IndexResponse(BaseModel):
    """Response model for indexing"""
    status: str
    collection_name: Optional[str] = None
    document_count: Optional[int] = None
    message: Optional[str] = None


# Endpoints

@router.post("/index", response_model=IndexResponse)
async def index_repository(
        request: IndexRepositoryRequest,
        background_tasks: BackgroundTasks
):
    """
    Index a repository for RAG queries

    This endpoint:
    1. Processes repository files
    2. Generates code embeddings
    3. Stores in vector database

    **Note**: This can take several minutes for large repositories.
    Consider using background_tasks for async processing.
    """
    try:
        logger.info(f"Indexing repository: {request.repository_url}")

        # For large repos, consider background processing
        result = rag_service.index_repository(
            repo_url=request.repository_url,
            chunk_size=request.chunk_size,
            max_files=request.max_files,
            force_reindex=request.force_reindex
        )

        if result["status"] == "error":
            raise HTTPException(status_code=500, detail=result.get("message", "Indexing failed"))

        return IndexResponse(**result)

    except Exception as e:
        logger.error(f"Error in index_repository: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/search")
async def search_code(request: SearchRequest):
    """
    Perform semantic search in indexed repository

    Returns relevant code snippets based on semantic similarity
    to the query.
    """
    try:
        logger.info(f"Searching: '{request.query}' in '{request.collection_name}'")

        result = rag_service.search(
            query=request.query,
            repo_name=request.collection_name,
            n_results=request.n_results,
            language_filter=request.language_filter
        )

        if result["status"] == "error":
            raise HTTPException(status_code=404, detail=result.get("message", "Search failed"))

        return result

    except Exception as e:
        logger.error(f"Error in search_code: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/answer")
async def generate_answer(request: GenerateAnswerRequest):
    """
    Generate context-aware answer using RAG

    This endpoint:
    1. Retrieves relevant code context
    2. Generates answer using LLM (if enabled)
    3. Returns answer with source attribution
    """
    try:
        logger.info(f"Generating answer for: '{request.query}'")

        result = rag_service.query(
            repo_name=request.collection_name,
            question=request.query,
            n_results=request.n_context,
            use_llm=request.use_llm
        )

        return result

    except Exception as e:
        logger.error(f"Error in generate_answer: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/collections")
async def list_collections():
    """
    List all indexed repositories (collections)

    Returns list of available collections that can be queried.
    """
    try:
        collections = rag_service.list_indexed_repositories()

        # Get stats for each collection
        collection_info = []
        for collection_name in collections:
            info = rag_service.get_collection_info(collection_name)
            collection_info.append(info)

        return {
            "status": "success",
            "count": len(collections),
            "collections": collection_info
        }

    except Exception as e:
        logger.error(f"Error listing collections: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/collections/{collection_name}")
async def get_collection_info(collection_name: str):
    """
    Get information about a specific collection

    Returns document count and metadata for the collection.
    """
    try:
        info = rag_service.get_collection_info(collection_name)

        if info.get("count", 0) == 0:
            raise HTTPException(status_code=404, detail="Collection not found")

        return {
            "status": "success",
            "collection": info
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting collection info: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/collections/{collection_name}")
async def delete_collection(collection_name: str):
    """
    Delete a collection

    **Warning**: This permanently deletes all indexed data for the collection.
    """
    try:
        success = rag_service.delete_index(collection_name)

        if not success:
            raise HTTPException(status_code=404, detail="Collection not found or deletion failed")

        return {
            "status": "success",
            "message": f"Collection '{collection_name}' deleted successfully"
        }

    except Exception as e:
        logger.error(f"Error deleting collection: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Health check endpoint
@router.get("/health")
async def rag_health():
    """
    Check RAG service health

    Returns status of all RAG components.
    """
    try:
        # Check ChromaDB
        collections = rag_service.list_indexed_repositories()

        # Check embedding service
        embedding_info = {
            "model_name": "sentence-transformers/all-MiniLM-L6-v2",
            "embedding_dimension": 384
        }

        # Check LLM service
        llm_available = rag_service.llm is not None

        return {
            "status": "healthy",
            "chromadb": {
                "available": True,
                "collections_count": len(collections)
            },
            "embedding_service": {
                "available": True,
                "model": embedding_info["model_name"],
                "dimension": embedding_info["embedding_dimension"]
            },
            "llm_service": {
                "available": llm_available
            }
        }

    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e)
        }