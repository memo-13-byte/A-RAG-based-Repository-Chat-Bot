"""
FastAPI Main Application - Phase 3
Updated with Knowledge Graph endpoints
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

# Import routers
from app.api import repository, chat, graph

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="RepoWise API",
    description="AI-powered repository analysis with RAG and Knowledge Graph",
    version="3.0.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(repository.router, prefix="/api")
app.include_router(chat.router, prefix="/api")
app.include_router(graph.router, prefix="/api")  # NEW: Phase 3 Graph API

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "RepoWise API - Phase 3",
        "version": "3.0.0",
        "features": {
            "repository_analysis": "Phase 1 ✅",
            "rag_pipeline": "Phase 2 ✅",
            "knowledge_graph": "Phase 3 ✅"
        },
        "endpoints": {
            "repository": "/api/repository",
            "chat": "/api/chat",
            "graph": "/api/graph",
            "docs": "/docs"
        }
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "phase": "Phase 3: Knowledge Graph",
        "services": {
            "api": "running",
            "chromadb": "connected",
            "neo4j": "connected"
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)