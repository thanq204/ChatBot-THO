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
    app_name: str = "THO - Triage, Help, Oversight"
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
    openai_embedding_dimensions: int = Field(default=1536, ge=256, le=3072)
    semantic_embedding_cache_size: int = Field(default=128, ge=0, le=1024)
    # Explicit opt-in: enabling this sends Knowledge Hub text to the
    # configured embedding provider for semantic indexing.
    knowledge_embedding_enabled: bool = False
    knowledge_embedding_min_score: float = Field(default=0.38, ge=0.0, le=1.0)
    knowledge_embedding_batch_size: int = Field(default=64, ge=1, le=128)
    rag_candidate_limit: int = Field(default=6, ge=1, le=20)
    rag_relevance_threshold: float = Field(default=0.52, ge=0.0, le=1.0)
    rag_vector_min_score: float = Field(default=0.38, ge=0.0, le=1.0)
    rag_semantic_only_min_score: float = Field(default=0.62, ge=0.0, le=1.0)
    rag_query_coverage_min_score: float = Field(default=0.24, ge=0.0, le=1.0)
    rag_minimum_margin: float = Field(default=0.025, ge=0.0, le=1.0)
    rag_rerank_vector_weight: float = Field(default=0.58, ge=0.0, le=1.0)
    rag_rerank_lexical_weight: float = Field(default=0.30, ge=0.0, le=1.0)
    rag_rerank_phrase_weight: float = Field(default=0.12, ge=0.0, le=1.0)
    llm_temperature: float = Field(default=0.7, ge=0.0, le=2.0)

    # Moderation pipeline
    moderation_mode: Literal["openai", "gemini", "mock"] = "openai"
    moderation_provider: Literal["openai", "gemini"] = "openai"
    gemini_api_key: str = ""
    gemini_triage_model: str = "gemini-3.1-flash-lite"
    gemini_review_model: str = "gemini-3.6-flash"
    gemini_embedding_model: str = "gemini-embedding-001"
    enable_policy_retrieval: bool = False
    moderation_policy_semantic_threshold: float = Field(default=0.72, ge=0.0, le=1.0)
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
    moderation_context_window_minutes: int = Field(default=10, ge=1, le=120)
    moderation_context_message_limit: int = Field(default=12, ge=1, le=30)
    moderation_memory_embedding_enabled: bool = True
    moderation_memory_similarity_threshold: float = Field(default=0.90, ge=0.0, le=1.0)
    moderation_memory_llm_verify_enabled: bool = True
    moderation_memory_llm_candidate_threshold: float = Field(default=0.55, ge=0.0, le=1.0)
    moderation_memory_llm_model: str = "gpt-4o-mini"
    moderation_policy_cache_seconds: int = Field(default=15, ge=0, le=300)
    spam_repeat_window_seconds: int = Field(default=120, ge=30, le=3600)
    spam_repeat_message_threshold: int = Field(default=3, ge=2, le=20)
    reputation_helpful_reaction_threshold: int = Field(default=3, ge=1, le=50)
    reputation_block_link_reaction_threshold: int = Field(default=3, ge=1, le=50)
    seller_assessment_model: str = "gpt-4o-mini"
    seller_min_verified_transactions: int = Field(default=3, ge=1, le=100)
    seller_min_unique_buyers: int = Field(default=3, ge=1, le=100)
    seller_review_burst_threshold: int = Field(default=5, ge=3, le=100)
    seller_review_burst_window_hours: int = Field(default=24, ge=1, le=168)

    # FAQ analytics: every safe tagged question is embedded and clustered.
    faq_semantic_clustering_enabled: bool = True
    faq_cluster_candidate_threshold: float = Field(default=0.55, ge=0.0, le=1.0)
    faq_cluster_auto_merge_threshold: float = Field(default=0.95, ge=0.0, le=1.0)
    faq_semantic_match_threshold: float = Field(default=0.82, ge=0.0, le=1.0)
    faq_clustering_model: str = "gpt-4o-mini"
    faq_top_limit: int = Field(default=10, ge=1, le=50)

    # Database
    database_url: str = "sqlite:///./data/app.db"

    # Dashboard authentication / authorization
    auth_jwt_secret: str = ""  # Required outside development.
    auth_access_token_minutes: int = Field(default=60, ge=5, le=24 * 60)
    auth_root_admin_email: str = ""
    auth_root_admin_password: str = ""
    google_oauth_client_id: str = ""
    # Origin used to build links inside emails (invite links, etc). Set to the
    # deployed frontend URL in production; defaults to the Vite dev server.
    app_public_url: str = "http://localhost:5173"

    # Outbound email (Mod invite links). Empty smtp_host disables sending and
    # the invite flow falls back to the Admin copying the link manually.
    smtp_host: str = ""
    smtp_port: int = Field(default=587, ge=1, le=65535)
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from_email: str = ""
    smtp_from_name: str = "AI Community Manager"
    smtp_use_tls: bool = True

    # PostgreSQL Database for FAQ RAG
    faq_pg_dsn: str = ""  # If set, overrides individual parameters (useful for Supabase/Neon)
    faq_pg_host: str = "localhost"
    faq_pg_port: int = 5433
    faq_pg_db: str = "faq_rag"
    faq_pg_user: str = "faq_user"
    faq_pg_password: str = "faq_pass_dev"
    # Supabase session-mode poolers often cap connections per project. Keep
    # startup to one connection and grow only when concurrent requests need it;
    # restart the backend after changing any database or Discord .env setting.
    postgres_pool_min_size: int = Field(default=1, ge=1, le=10)
    postgres_pool_max_size: int = Field(default=5, ge=1, le=32)

    # Vector Store
    chroma_persist_dir: str = "./data/chroma"

    # Community Operations Copilot connectors
    discord_bot_token: str = ""
    discord_default_channel_id: str = ""
    # Seller feedback is accepted only for trades opened in this dedicated channel.
    discord_trade_channel_id: str = ""
    discord_listener_enabled: bool = False
    discord_reply_max_chars: int = Field(default=1800, ge=500, le=2000)
    discord_rag_llm_enabled: bool = True
    discord_rag_model: str = "gpt-4o-mini"
    discord_rag_temperature: float = Field(default=0.2, ge=0.0, le=1.0)
    telegram_bot_token: str = ""
    telegram_default_chat_id: str = ""
    # Seller feedback is accepted only for trades opened in this dedicated chat.
    telegram_trade_chat_id: str = ""
    # Private chat ID of the Admin/Mod who receives moderation alerts.  This
    # is deliberately separate from the community group chat ID above.
    telegram_admin_chat_id: str = ""
    telegram_listener_enabled: bool = False
    telegram_welcome_new_members_enabled: bool = True
    telegram_polling_timeout_seconds: int = Field(default=25, ge=1, le=50)
    telegram_reply_max_chars: int = Field(default=3500, ge=500, le=4096)
    telegram_alerts_enabled: bool = False
    telegram_alert_risk_threshold: float = Field(default=0.55, ge=0.0, le=1.0)
    # Opt-in: send one private warning for every non-allow moderation decision.
    moderation_auto_warn_dm_enabled: bool = False
    zalo_access_token: str = ""
    messenger_page_access_token: str = ""
    operations_demo_mode: bool = True
    operations_use_llm: bool = False
    operations_seed_defaults: bool = False
    operations_startup_maintenance_enabled: bool = False
    operations_incident_window_minutes: int = Field(default=60, ge=5, le=1440)

    # Semantic document ingestion
    knowledge_extraction_enabled: bool = True
    knowledge_extraction_model: str = "gpt-4o-mini"
    knowledge_extraction_temperature: float = Field(default=0.0, ge=0.0, le=1.0)
    knowledge_archive_dir: str = "./data/knowledge_uploads"


@lru_cache
def get_settings() -> Settings:
    return Settings()
