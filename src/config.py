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
    llm_temperature: float = Field(default=0.7, ge=0.0, le=2.0)

    # Moderation pipeline
    moderation_mode: Literal["gemini", "mock"] = "gemini"
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

    # Database
    database_url: str = "sqlite:///./data/app.db"

    # Vector Store
    chroma_persist_dir: str = "./data/chroma"


@lru_cache
def get_settings() -> Settings:
    return Settings()
