"""
ResuMax Backend — Configuration
Loads environment variables with validation via pydantic-settings.
"""

from pydantic_settings import BaseSettings
from pydantic import Field
from functools import lru_cache
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from .env file."""

    # ── Supabase ──────────────────────────────────────────────
    supabase_url: str = Field(..., description="Supabase project URL")
    supabase_service_role_key: str = Field(..., description="Supabase service role key (bypasses RLS)")

    # ── Groq ──────────────────────────────────────────────────
    groq_api_key: str = Field(default="", description="Groq API key for LLM inference")

    # ── Ollama Cloud (Behavioral AI) ────────────────────────────
    ollama_cloud_api_key: str = Field(default="", description="Ollama Cloud API key for behavioral profiling")
    ollama_cloud_base_url: str = Field(default="https://ollama.com", description="Ollama Cloud API base URL")
    ollama_cloud_model: str = Field(default="qwen3.5:397b-cloud", description="Ollama Cloud model for behavior analysis")

    # ── AWS Bedrock (optional) ────────────────────────────────
    aws_access_key_id: Optional[str] = Field(default=None, description="AWS access key")
    aws_secret_access_key: Optional[str] = Field(default=None, description="AWS secret key")
    aws_region: str = Field(default="us-east-1", description="AWS region for Bedrock")

    # ── LinkedIn OAuth ────────────────────────────────────────
    linkedin_client_id: str = Field(default="", description="LinkedIn OAuth Client ID")
    linkedin_client_secret: str = Field(default="", description="LinkedIn OAuth Client Secret")
    linkedin_redirect_uri: str = Field(
        default="http://localhost:8000/api/auth/linkedin/callback",
        description="LinkedIn OAuth redirect URI",
    )
    frontend_url: str = Field(default="http://localhost:3000", description="Frontend URL for redirects")

    # ── Server ────────────────────────────────────────────────
    host: str = Field(default="0.0.0.0", description="Server host")
    port: int = Field(default=8000, description="Server port")
    cors_origins: str = Field(
        default="http://localhost:3000",
        description="Comma-separated list of allowed CORS origins"
    )

    # ── Logging ───────────────────────────────────────────────
    log_level: str = Field(default="INFO", description="Log level")

    # ── App ───────────────────────────────────────────────────
    app_name: str = "ResuMax API"
    app_version: str = "1.0.0"
    debug: bool = Field(default=False, description="Debug mode")

    @property
    def cors_origins_list(self) -> list[str]:
        """Parse comma-separated CORS origins into a list."""
        return [origin.strip() for origin in self.cors_origins.split(",")]

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
    }


@lru_cache()
def get_settings() -> Settings:
    """Cached settings instance — loaded once, reused everywhere."""
    return Settings()
