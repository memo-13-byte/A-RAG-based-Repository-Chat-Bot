"""
Pydantic Models for AutoFix API
"""
from pydantic import BaseModel, Field, HttpUrl
from typing import Optional, Literal
from datetime import datetime


class AutoFixSubmitRequest(BaseModel):
    """Request model for submitting an autofix"""
    repo_url: HttpUrl = Field(
        ...,
        description="GitHub repository URL",
        examples=["https://github.com/user/repo.git"]
    )
    issue_description: str = Field(
        ...,
        min_length=10,
        max_length=2000,
        description="Detailed description of the issue to fix",
        examples=["Add type hints to the main() function"]
    )
    model: str = Field(
        default="gpt-4o-mini-2024-07-18",
        description="LLM model to use for code generation"
    )
    temperature: float = Field(
        default=0.2,
        ge=0.0,
        le=1.0,
        description="Model temperature for generation"
    )


class AutoFixSubmitResponse(BaseModel):
    """Response model for submit autofix"""
    task_id: str = Field(..., description="Unique task identifier")
    status: Literal["processing", "running"] = Field(..., description="Initial task status")
    message: str = Field(..., description="Status message")


class AutoFixStatusResponse(BaseModel):
    """Response model for autofix status"""
    task_id: str = Field(..., description="Task identifier")
    status: Literal["processing", "running", "completed", "failed"] = Field(
        ..., 
        description="Current task status"
    )
    patch_path: Optional[str] = Field(
        None, 
        description="Path to generated patch (if completed)"
    )
    error: Optional[str] = Field(
        None, 
        description="Error message (if failed)"
    )


class AutoFixHealthResponse(BaseModel):
    """Response model for health check"""
    healthy: bool = Field(..., description="Service health status")
    service: str = Field(default="autocoderover", description="Service name")
    version: str = Field(default="1.0", description="Service version")


class AutoFixTask(BaseModel):
    """Internal model for tracking autofix tasks"""
    task_id: str
    repo_url: str
    issue_description: str
    model: str
    temperature: float
    status: Literal["processing", "running", "completed", "failed"]
    patch_path: Optional[str] = None
    error: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None
