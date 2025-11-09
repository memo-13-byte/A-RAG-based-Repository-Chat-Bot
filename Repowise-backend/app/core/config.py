from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings - .env dosyasından okunur"""

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
    APP_NAME: str = "RepoWise API"
    DEBUG: bool = True

    class Config:
        env_file = ".env"
        case_sensitive = True


# Global settings instance
settings = Settings()