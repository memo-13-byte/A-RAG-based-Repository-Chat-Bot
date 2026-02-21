"""
FastAPI Main Application - Phase 3 + AutoFix
Updated with Knowledge Graph endpoints and AutoCodeRover integration
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

# Import routers
from .api import repository, chat, graph
from .api.v1 import autofix

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="RepoWise API",
    description="AI-powered repository analysis with RAG, Knowledge Graph, and AutoFix",
    version="3.1.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",      # Vite dev server
        "http://127.0.0.1:5173",      # Alternative localhost
        "http://localhost:3000",      # React dev server (alternative)
        "http://127.0.0.1:3000",      # Alternative
        # Add production URLs when deploying
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(repository.router, prefix="/api")
app.include_router(chat.router, prefix="/api")
app.include_router(graph.router, prefix="/api")      # Phase 3: Graph API
app.include_router(autofix.router)                    # AutoFix API

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "RepoWise API - Phase 3 + AutoFix",
        "version": "3.1.0",
        "features": {
            "repository_analysis": "Phase 1 ✅",
            "rag_pipeline": "Phase 2 ✅",
            "knowledge_graph": "Phase 3 ✅",
            "autofix": "AutoCodeRover ✅"
        },
        "endpoints": {
            "repository": "/api/repository",
            "chat": "/api/chat",
            "graph": "/api/graph",
            "autofix": "/api/v1/autofix",
            "docs": "/docs"
        }
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    from .services.autocoderover_service import get_autocoderover_service

    # Check AutoFix service health
    autofix_healthy = False
    try:
        acr_service = get_autocoderover_service()
        autofix_healthy = await acr_service.health_check()
    except Exception as e:
        logger.warning(f"AutoFix health check failed: {e}")

    return {
        "status": "healthy",
        "phase": "Phase 3: Knowledge Graph + AutoFix",
        "services": {
            "api": "running",
            "chromadb": "connected",
            "neo4j": "connected",
            "autofix": "connected" if autofix_healthy else "unavailable"
        }
    }

@app.on_event("startup")
async def startup_event():
    """Startup event handler"""
    logger.info("Starting RepoWise API v3.1.0")
    logger.info("Features: Repository Analysis, RAG, Knowledge Graph, AutoFix")

    # Check AutoFix availability
    try:
        from .services.autocoderover_service import get_autocoderover_service
        acr_service = get_autocoderover_service()
        is_healthy = await acr_service.health_check()

        if is_healthy:
            logger.info("✅ AutoFix service is available")
        else:
            logger.warning("⚠️ AutoFix service is not responding")
    except Exception as e:
        logger.warning(f"⚠️ AutoFix service check failed: {e}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)