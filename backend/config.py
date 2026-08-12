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
    # Vite dev server origins; production serves the built SPA same-origin.
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # LLM
    openai_api_key: str = ""
    model_name: str = "gpt-4o-mini"
    openai_embedding_model: str = "text-embedding-3-small"
    # Explicit opt-in: enabling this sends Knowledge Hub text to the
    # configured embedding provider for semantic indexing.
    knowledge_embedding_enabled: bool = False
    knowledge_embedding_min_score: float = Field(default=0.38, ge=0.0, le=1.0)
    knowledge_embedding_batch_size: int = Field(default=64, ge=1, le=128)
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

    # Community Operations Copilot connectors
    discord_bot_token: str = ""
    discord_default_channel_id: str = ""
    discord_listener_enabled: bool = False
    discord_reply_max_chars: int = Field(default=1800, ge=500, le=2000)
    discord_rag_llm_enabled: bool = True
    discord_rag_model: str = "gpt-4o-mini"
    discord_rag_temperature: float = Field(default=0.2, ge=0.0, le=1.0)
    telegram_bot_token: str = ""
    telegram_default_chat_id: str = ""
    telegram_listener_enabled: bool = False
    telegram_polling_timeout_seconds: int = Field(default=25, ge=1, le=50)
    telegram_reply_max_chars: int = Field(default=3500, ge=500, le=4096)
    telegram_alerts_enabled: bool = False
    telegram_alert_risk_threshold: float = Field(default=0.55, ge=0.0, le=1.0)
    zalo_access_token: str = ""
    messenger_page_access_token: str = ""
    operations_demo_mode: bool = True
    operations_use_llm: bool = False
    operations_incident_window_minutes: int = Field(default=60, ge=5, le=1440)

    # Semantic document ingestion
    knowledge_extraction_enabled: bool = True
    knowledge_extraction_model: str = "gpt-4o-mini"
    knowledge_extraction_temperature: float = Field(default=0.0, ge=0.0, le=1.0)
    knowledge_archive_dir: str = "./data/knowledge_uploads"


@lru_cache
def get_settings() -> Settings:
    return Settings()
