from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="RepoWise API",
    description="RAG-Based Repository Chatbot API",
    version="1.0.0"
)

# CORS middleware - Frontend için gerekli
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Production'da belirli origin'lere izin ver
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    """API'nin çalışıp çalışmadığını kontrol et"""
    return {
        "message": "RepoWise API is running!",
        "status": "healthy",
        "version": "1.0.0"
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "ok"}

# API routes
from app.api import chat, repository

app.include_router(chat.router, prefix="/api/chat", tags=["chat"])
app.include_router(repository.router, prefix="/api/repository", tags=["repository"])
