"""Application configuration using Pydantic Settings v2."""
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # App
    ENVIRONMENT: Literal["development", "staging", "production"] = "development"
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    API_SECRET_KEY: str = Field(..., min_length=32)
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    BCRYPT_ROUNDS: int = 12
    ALLOWED_HOSTS: str = "localhost,127.0.0.1"
    ALLOWED_ORIGINS: str = "http://localhost:5173"
    FRONTEND_URL: str = "http://localhost:3000"
    SUPABASE_AUTH_REDIRECT_URL: str = "http://localhost:3000/auth/callback"

    # Supabase
    SUPABASE_URL: str
    SUPABASE_ANON_KEY: str
    SUPABASE_SERVICE_ROLE_KEY: str = ""
    DATABASE_URL: str

    # Amzur LiteLLM proxy  (replaces direct OpenAI / Anthropic keys)
    AMZUR_API_KEY: str
    AMZUR_BASE_URL: str = "https://litellm.amzur.com"
    LLM_MODEL: str = "amzur-lite"

    # LangGraph checkpointing (defaults to DATABASE_URL if not set)
    LANGGRAPH_CHECKPOINT_DB_URL: str = ""

    @property
    def effective_checkpoint_url(self) -> str:
        return self.LANGGRAPH_CHECKPOINT_DB_URL or self.DATABASE_URL

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    @property
    def allowed_hosts_list(self) -> list[str]:
        return [host.strip() for host in self.ALLOWED_HOSTS.split(",") if host.strip()]

    @property
    def allowed_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",") if origin.strip()]


settings = Settings()  # type: ignore[call-arg]
