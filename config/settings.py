"""
Application configuration settings
"""

import os
from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    # Project paths
    BASE_DIR: Path = Path(__file__).parent.parent
    DATA_DIR: Path = BASE_DIR / "data"
    RAW_DATA_DIR: Path = DATA_DIR / "raw"
    PROCESSED_DATA_DIR: Path = DATA_DIR / "processed"
    VECTOR_STORE_DIR: Path = DATA_DIR / "vector_store"
    TEN_K_DOCS_DIR: Path = DATA_DIR / "10k_documents"
    MODELS_DIR: Path = BASE_DIR / "models"

    # API Keys
    OPENAI_API_KEY: Optional[str] = Field(None, env="OPENAI_API_KEY")
    ANTHROPIC_API_KEY: Optional[str] = Field(None, env="ANTHROPIC_API_KEY")

    # Supabase
    SUPABASE_URL: Optional[str] = Field(None, env="SUPABASE_URL")
    SUPABASE_KEY: Optional[str] = Field(None, env="SUPABASE_KEY")

    # SEC EDGAR API
    SEC_API_USER_AGENT: str = Field(
        "researcher@university.edu", env="SEC_API_USER_AGENT"
    )

    # Finnhub
    FINNHUB_API_KEY: Optional[str] = Field(None, env="FINNHUB_API_KEY")

    # Application Settings
    DEBUG: bool = Field(False, env="DEBUG")
    LOG_LEVEL: str = Field("INFO", env="LOG_LEVEL")
    MAX_WORKERS: int = Field(4, env="MAX_WORKERS")

    # Model Settings (matches .env)
    EMBEDDING_MODEL: str = Field("text-embedding-3-small", env="EMBEDDING_MODEL")
    CHAT_MODEL: str = Field("gpt-4.1-mini", env="CHAT_MODEL")
    REPORT_MODEL: str = Field("gpt-4.1-mini", env="REPORT_MODEL")
    TEMPERATURE: float = Field(0.1, env="TEMPERATURE")
    MAX_TOKENS: int = Field(4096, env="MAX_TOKENS")

    # RAG Settings
    CHUNK_SIZE: int = 1000
    CHUNK_OVERLAP: int = 200
    TOP_K_RESULTS: int = 5
    SIMILARITY_THRESHOLD: float = 0.7

    # Relationship Settings (for SEC 10-K analysis)
    RELATIONSHIP_TYPES: list = [
        "supplier",
        "customer",
        "competitor",
        "subsidiary",
        "partner",
        "mentioned",
    ]
    MAX_GRAPH_DEPTH: int = 3
    MIN_RELATIONSHIP_STRENGTH: float = 0.5

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        extra = (
            "ignore"  # Ignore extra fields from .env that aren't defined in Settings
        )

    def ensure_directories(self):
        """Create necessary directories (call on demand, not at module load)"""
        self.RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.VECTOR_STORE_DIR.mkdir(parents=True, exist_ok=True)
        self.TEN_K_DOCS_DIR.mkdir(parents=True, exist_ok=True)
        self.MODELS_DIR.mkdir(parents=True, exist_ok=True)


# Global settings instance
settings = Settings()

# NOTE: Directory creation moved to settings.ensure_directories()
# for faster app startup. Call settings.ensure_directories() when needed.
