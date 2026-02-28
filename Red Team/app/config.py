"""
Configuration settings for Sentinel AI Red Team Agent.
"""
import os
from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Environment
    environment: str = os.getenv("ENVIRONMENT", "development")
    
    # Database
    postgres_user: str = os.getenv("POSTGRES_USER", "sentinel_db_admin")
    postgres_password: str = os.getenv("POSTGRES_PASSWORD", "sentinel_db_password")
    postgres_db: str = os.getenv("POSTGRES_DB", "sentinel_db")
    postgres_host: str = os.getenv("POSTGRES_HOST", "db")
    postgres_port: int = int(os.getenv("POSTGRES_PORT", "5432"))
    
    # Redis
    redis_url: str = os.getenv("REDIS_URL", "redis://redis:6379/0")
    
    # API Security
    api_key: str = os.getenv("REDTEAM_API_KEY", "sentinel-redteam-dev-key")
    api_key_header: str = "X-API-Key"
    
    # Analysis Backend (main Sentinel backend for proxied API calls)
    analysis_backend_url: str = os.getenv("ANALYSIS_BACKEND_URL", "http://backend:8003")
    
    # AI Model URLs (for health checks and per-model pipeline)
    mistral_api_url: str = os.getenv("MISTRAL_API_BASE_URL", "http://lm-proxy:8080")
    qwen_api_url: str = os.getenv("QWEN_API_BASE_URL", "http://qwen-proxy:8080")
    
    @property
    def database_url(self) -> str:
        """Construct async PostgreSQL connection URL."""
        return f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
    
    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
