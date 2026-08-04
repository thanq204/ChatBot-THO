from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # App
    app_name: str = "AI20K Agent"
    app_env: Literal["development", "production", "test"] = "development"
    app_port: int = Field(default=8000, ge=1, le=65535)
    app_host: str = "0.0.0.0"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    cors_origins: str = "http://localhost:3000"

    # LLM
    openai_api_key: str = ""
    model_name: str = "gpt-4o-mini"
    openai_embedding_model: str = "text-embedding-3-small"
    llm_temperature: float = Field(default=0.7, ge=0.0, le=2.0)

    # Moderation pipeline
    moderation_mode: Literal["openai", "gemini", "mock"] = "openai"
    moderation_provider: Literal["openai", "gemini"] = "openai"
    gemini_api_key: str = ""
    gemini_triage_model: str = "gemini-3.1-flash-lite"
    gemini_review_model: str = "gemini-3.6-flash"
    gemini_embedding_model: str = "gemini-embedding-001"
    enable_policy_retrieval: bool = False
    moderation_review_threshold: float = Field(default=0.80, ge=0.0, le=1.0)
    moderation_auto_action_threshold: float = Field(default=0.90, ge=0.0, le=1.0)
    gemini_temperature: float = Field(default=0.1, ge=0.0, le=2.0)
    gemini_max_output_tokens: int = Field(default=1024, ge=128, le=8192)
    gemini_timeout_seconds: int = Field(default=30, ge=1, le=120)
    gemini_max_retries: int = Field(default=2, ge=0, le=5)
    allow_mock_fallback: bool = False
    openai_moderation_model: str = "gpt-4o-mini"

    # Conversation analysis and case-based feedback
    escalation_review_threshold: float = Field(default=0.65, ge=0.0, le=1.0)
    escalation_critical_threshold: float = Field(default=0.85, ge=0.0, le=1.0)
    similar_case_limit: int = Field(default=5, ge=1, le=20)
    enable_case_based_learning: bool = True

    # Database
    database_url: str = "sqlite:///./data/app.db"

    # Vector Store
    chroma_persist_dir: str = "./data/chroma"

    # YouTube integration
    youtube_data_mode: Literal["public_api", "imported_dataset", "authorized"] = "public_api"
    youtube_api_key: str = ""
    youtube_default_video_id: str = ""
    youtube_max_results_per_sync: int = Field(default=50, ge=1, le=100)
    youtube_max_threads_per_analysis: int = Field(default=50, ge=1, le=100)
    youtube_dataset_path: str = "./data/youtube_demo"
    youtube_data_retention_days: int = Field(default=30, ge=1, le=3650)
    youtube_allow_public_read: bool = True
    youtube_authorized_mode: bool = False
    youtube_action_mode: Literal["simulated", "authorized"] = "simulated"
    youtube_sync_mode: Literal["manual", "polling"] = "manual"
    youtube_poll_interval_seconds: int = Field(default=120, ge=30, le=86400)
    google_client_id: str = ""
    google_client_secret: str = ""
    youtube_redirect_uri: str = "http://localhost:8000/api/v1/integrations/youtube/callback"
    youtube_oauth_scope: str = "https://www.googleapis.com/auth/youtube.force-ssl"
    youtube_channel_id: str = ""
    token_encryption_key: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
