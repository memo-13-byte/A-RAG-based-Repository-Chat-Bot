import os
from pathlib import Path
from pydantic_settings import BaseSettings
from typing import Optional
from dotenv import load_dotenv

# Get the directory where this config.py file is located
# This file is at: Repowise-backend/app/core/config.py
# We need to go up 3 levels to reach Repowise-backend/
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Construct path to .env file
dotenv_path = BASE_DIR / '.env'

# Load environment variables from .env file
if dotenv_path.exists():
    load_dotenv(dotenv_path=dotenv_path)
    print(f"Configuration: .env file loaded from {dotenv_path}")
else:
    print(f"Warning: .env file not found at {dotenv_path}")
    print(f"Current working directory: {os.getcwd()}")
    # Try loading from current directory as fallback
    load_dotenv()


class Settings(BaseSettings):
    """Application settings - loaded from .env file"""

    # API Keys
    OPENAI_API_KEY: Optional[str] = None
    ANTHROPIC_API_KEY: Optional[str] = None
    GITHUB_TOKEN: Optional[str] = None

    # Neo4j Database
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "password"

    # Vector Database (Chroma)
    CHROMA_PERSIST_DIRECTORY: str = "./chroma_db"

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # Application
    APP_NAME: str = "RepoWise Dev"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True

    class Config:
        env_file = ".env"
        case_sensitive = True


# Global settings instance
settings = Settings()


# Validation function
def validate_settings():
    """Validate that required API keys are configured"""
    errors = []

    if not settings.GITHUB_TOKEN:
        errors.append("GITHUB_TOKEN is not set")

    if not settings.OPENAI_API_KEY:
        errors.append("OPENAI_API_KEY is not set")

    if errors:
        error_msg = "\n  - ".join(errors)
        raise ValueError(
            f"Missing required configuration:\n  - {error_msg}\n\nPlease add these to your .env file at: {dotenv_path}")

    return True