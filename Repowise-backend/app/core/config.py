"""
Application Configuration
Loads settings from .env file with support for multiple LLM providers
"""

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

    # ========== API Keys ==========

    # GitHub (REQUIRED for base functionality)
    GITHUB_TOKEN: Optional[str] = None
    
    # GitLab (OPTIONAL - but required for GitLab features)
    GITLAB_TOKEN: Optional[str] = None  # <--- YENİ EKLENDİ

    # LLM Providers (OPTIONAL - at least one recommended)
    GROQ_API_KEY: Optional[str] = None  # FREE - Recommended!
    OPENAI_API_KEY: Optional[str] = None  # PAID - Optional
    ANTHROPIC_API_KEY: Optional[str] = None  # PAID - Optional

    # ========== Databases ==========

    # Neo4j Database (Phase 3)
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "password"

    # Vector Database - Chroma (Phase 2)
    CHROMA_PERSIST_DIRECTORY: str = "./chroma_db"

    # ========== Server ==========

    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # ========== Application ==========

    APP_NAME: str = "RepoWise"
    APP_VERSION: str = "0.2.1"  # Version bumped for GitLab Support
    DEBUG: bool = True

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"


# Global settings instance
settings = Settings()


def validate_settings():
    """
    Validate that required configuration is present

    Raises:
        ValueError: If required settings are missing

    Returns:
        bool: True if validation passes
    """
    errors = []

    # GitHub token is REQUIRED (Core dependency)
    if not settings.GITHUB_TOKEN:
        errors.append("GITHUB_TOKEN is not set (REQUIRED for GitHub API access)")

    # At least one LLM provider is recommended (but not required)
    has_llm = any([
        settings.GROQ_API_KEY,
        settings.OPENAI_API_KEY,
        settings.ANTHROPIC_API_KEY
    ])

    if not has_llm:
        print("\nWARNING: No LLM API keys configured")
        print("   System will use rule-based fallback responses")
        print("   For better quality, add one of:")
        print("   - GROQ_API_KEY (FREE & FAST - recommended)")
        print("   - OPENAI_API_KEY (PAID)")
        print("   - ANTHROPIC_API_KEY (PAID)")
        print()

    if errors:
        error_msg = "\n  - ".join(errors)
        raise ValueError(
            f"\nMissing required configuration:\n  - {error_msg}\n\n"
            f"Please add these to your .env file at: {dotenv_path}"
        )

    return True


def print_settings_status():
    """
    Print current configuration status with visual indicators
    """
    print("=" * 80)
    print(f"{settings.APP_NAME} v{settings.APP_VERSION} - Configuration Status")
    print("=" * 80)

    # GitHub
    print("\nGitHub API:")
    if settings.GITHUB_TOKEN:
        token_preview = settings.GITHUB_TOKEN[:15] + "..." if len(settings.GITHUB_TOKEN) > 15 else settings.GITHUB_TOKEN
        print(f"Token: {token_preview}")
    else:
        print(f"Token: NOT SET (REQUIRED!)")
        
    # GitLab 
    print("\nGitLab API:")
    if settings.GITLAB_TOKEN:
        token_preview = settings.GITLAB_TOKEN[:10] + "..." if len(settings.GITLAB_TOKEN) > 10 else "******"
        print(f"Token: {token_preview} (Ready)")
    else:
        print(f"Token: NOT SET (GitLab features unavailable)")

    # LLM Providers
    print("\nLLM Providers:")

    llm_count = 0

    # Groq
    if settings.GROQ_API_KEY:
        key_preview = settings.GROQ_API_KEY[:15] + "..." if len(settings.GROQ_API_KEY) > 15 else settings.GROQ_API_KEY
        print(f"Groq: {key_preview} (FREE & FAST)")
        llm_count += 1
    else:
        print(f"Groq: NOT SET (recommended for free LLM)")

    # OpenAI
    if settings.OPENAI_API_KEY:
        key_preview = settings.OPENAI_API_KEY[:15] + "..." if len(
            settings.OPENAI_API_KEY) > 15 else settings.OPENAI_API_KEY
        print(f"OpenAI: {key_preview} (PAID)")
        llm_count += 1
    else:
        print(f"OpenAI: NOT SET")

    # Anthropic
    if settings.ANTHROPIC_API_KEY:
        key_preview = settings.ANTHROPIC_API_KEY[:15] + "..." if len(
            settings.ANTHROPIC_API_KEY) > 15 else settings.ANTHROPIC_API_KEY
        print(f"Anthropic: {key_preview} (PAID)")
        llm_count += 1
    else:
        print(f"Anthropic: NOT SET")

    # Summary
    print("\nSummary:")
    if llm_count == 0:
        print("LLM Mode: Rule-based fallback (no API keys)")
        print("Tip: Add GROQ_API_KEY for free LLM responses")
    elif settings.GROQ_API_KEY:
        print(f"LLM Mode: Groq (FREE & FAST)")
        if llm_count > 1:
            print(f"{llm_count} providers configured (Groq prioritized)")
    elif settings.OPENAI_API_KEY:
        print(f"LLM Mode: OpenAI (PAID)")
    elif settings.ANTHROPIC_API_KEY:
        print(f"LLM Mode: Anthropic (PAID)")

    # Databases
    print("\nDatabases:")
    print(f"ChromaDB: {settings.CHROMA_PERSIST_DIRECTORY}")
    print(f"Neo4j: {settings.NEO4J_URI}")

    # Server
    print("\nServer:")
    print(f"  Host: {settings.HOST}:{settings.PORT}")
    print(f"  Debug: {settings.DEBUG}")

    print("=" * 80)
    print()


def get_active_llm_provider() -> str:
    """
    Get the currently active LLM provider

    Returns:
        str: Name of active provider or 'fallback'
    """
    if settings.GROQ_API_KEY:
        return "groq"
    elif settings.OPENAI_API_KEY:
        return "openai"
    elif settings.ANTHROPIC_API_KEY:
        return "anthropic"
    else:
        return "fallback"


# Validate on import (but don't fail on missing LLM keys)
try:
    validate_settings()
except ValueError as e:
    print(str(e))
    print("\nCannot start without GITHUB_TOKEN")
    raise

# Print status on import (optional - comment out if too verbose)
if __name__ != "__main__":
    # Only print if running as main app, not during imports
    pass

# For testing
if __name__ == "__main__":
    print_settings_status()

    print("\nActive LLM Provider:", get_active_llm_provider())

    print("\nConfiguration loaded successfully!")