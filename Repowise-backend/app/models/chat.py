from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

class ChatMessage(BaseModel):
    """Chat message model"""
    role: str = Field(..., description="Mesaj sahibi: user veya assistant")
    content: str = Field(..., description="Mesaj içeriği")
    timestamp: Optional[datetime] = None

class ChatRequest(BaseModel):
    """Chat request model"""
    message: str = Field(..., min_length=1, max_length=1000, description="Kullanıcı mesajı")
    repository_url: Optional[str] = Field(None, description="GitHub repository URL")
    conversation_id: Optional[str] = Field(None, description="Sohbet ID'si")

class ChatResponse(BaseModel):
    """Chat response model"""
    message: str = Field(..., description="Chatbot yanıtı")
    conversation_id: str = Field(..., description="Sohbet ID'si")
    sources: Optional[List[str]] = Field(default=[], description="Kaynak belgeler")
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0, description="Güven skoru")

class RepositoryInfo(BaseModel):
    """Repository information model"""
    name: str
    url: str
    description: Optional[str] = None
    language: Optional[str] = None
    stars: Optional[int] = 0
