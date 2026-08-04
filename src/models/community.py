from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


ConversationStage = Literal[
    "healthy", "disagreement", "tense", "escalating", "critical", "resolving", "resolved"
]
Urgency = Literal["low", "medium", "high", "critical"]
ToneTrend = Literal["stable", "improving", "declining", "rapidly_declining"]
OutcomeStatus = Literal["improved", "unchanged", "worsened", "resolved", "unknown"]
InterventionAction = Literal[
    "observe",
    "private_nudge",
    "suggest_rewrite",
    "ask_for_clarification",
    "public_deescalation_reply",
    "slow_mode",
    "open_mediation",
    "temporary_cooldown",
    "warn",
    "hide",
    "lock_thread",
    "publish",
    "hold_for_review",
    "reject",
    "generate_reply_draft",
]
ActionMode = Literal["simulated", "authorized"]
YouTubeDataMode = Literal["public_api", "imported_dataset", "authorized"]
YouTubeFilterMode = Literal["all", "positive", "needs_review", "negative"]


class ConversationMessage(BaseModel):
    message_id: str = Field(..., min_length=1, max_length=200)
    parent_message_id: str | None = None
    author_id: str = Field(default="anonymous", min_length=1, max_length=200)
    text: str = Field(..., min_length=1, max_length=10000)
    timestamp: datetime
    platform_status: str = "published"
    like_count: int = Field(default=0, ge=0)
    source_url: str | None = None
    is_trigger: bool = False
    moderation_category: str | None = None
    moderation_risk_level: str | None = None
    moderation_action: str | None = None


class ConversationInput(BaseModel):
    platform: str = Field(default="local_demo", min_length=1, max_length=50)
    community_id: str = Field(default="COMMUNITY-001", min_length=1, max_length=200)
    channel_id: str = Field(default="general", min_length=1, max_length=200)
    thread_id: str | None = Field(default=None, max_length=200)
    content_url: str | None = None
    video_id: str | None = None
    video_title: str | None = None
    messages: list[ConversationMessage] = Field(..., min_length=1, max_length=200)
    source_mode: YouTubeDataMode | str = "local_demo"
    action_mode: ActionMode = "simulated"


class TriggerMessage(BaseModel):
    message_id: str
    text: str
    reason: str
    matched_terms: list[str] = Field(default_factory=list, max_length=8)
    context_note: str = Field(default="", max_length=500)


class ConversationAnalysis(BaseModel):
    conversation_stage: ConversationStage
    escalation_score: float = Field(..., ge=0.0, le=1.0)
    urgency: Urgency
    category: str = Field(default="other", max_length=100)
    risk_level: Literal["low", "medium", "high", "critical"] = "low"
    main_topic: str = Field(..., min_length=1, max_length=500)
    conflict_summary: str = Field(..., min_length=1, max_length=1000)
    root_causes: list[str] = Field(default_factory=list, max_length=8)
    triggers: list[TriggerMessage] = Field(default_factory=list, max_length=5)
    participants_in_conflict: list[str] = Field(default_factory=list, max_length=30)
    tone_trend: ToneTrend
    needs_intervention: bool
    recommended_intervention: InterventionAction
    confidence: float = Field(..., ge=0.0, le=1.0)
    model_used: str = Field(default="mock", max_length=200)
    reviewed_example_ids: list[str] = Field(default_factory=list, max_length=5)


class ConversationThread(BaseModel):
    thread_id: str
    platform: str
    community_id: str
    channel_id: str
    video_id: str | None = None
    video_title: str | None = None
    content_url: str | None = None
    messages: list[ConversationMessage]
    analysis: ConversationAnalysis | None = None
    source_mode: str
    action_mode: ActionMode
    imported_at: datetime
    expires_at: datetime | None = None
    last_analyzed_at: datetime | None = None


class InterventionRecommendation(BaseModel):
    recommended_action: InterventionAction
    reason: str = Field(..., min_length=1, max_length=1000)
    target_users: list[str] = Field(default_factory=list, max_length=30)
    draft_message: str = Field(default="", max_length=5000)
    expected_outcome: str = Field(..., min_length=1, max_length=500)
    urgency: Urgency
    requires_admin_approval: bool = True
    internal_action: InterventionAction | None = None
    youtube_action: str | None = None
    supported: bool = True
    support_reason: str | None = None
    model_used: str = "mock"


class MediationSummary(BaseModel):
    side_a_position: str
    side_b_position: str
    common_ground: list[str] = Field(default_factory=list, max_length=8)
    core_disagreement: list[str] = Field(default_factory=list, max_length=8)
    harmful_patterns: list[str] = Field(default_factory=list, max_length=8)
    recommended_next_steps: list[str] = Field(default_factory=list, max_length=8)
    admin_editable_draft: str = Field(..., max_length=5000)
    model_used: str = "mock"


class AdminInterventionRequest(BaseModel):
    selected_action: InterventionAction
    admin_edited_message: str = Field(default="", max_length=5000)
    reviewer: str = Field(default="Admin", min_length=1, max_length=100)
    admin_note: str = Field(default="", max_length=2000)
    classification_decision: Literal["accept_ai", "correct_ai", "uncertain"] = "accept_ai"
    admin_category: str | None = Field(default=None, max_length=100)
    admin_risk_level: Literal["low", "medium", "high", "critical"] | None = None
    admin_conversation_stage: ConversationStage | None = None
    confirm: bool = False


class OutcomeRequest(BaseModel):
    outcome: OutcomeStatus
    after_intervention_score: float | None = Field(default=None, ge=0.0, le=1.0)
    admin_note: str = Field(default="", max_length=2000)


class YouTubeVideoRequest(BaseModel):
    video_url_or_id: str = Field(..., min_length=1, max_length=500)
    max_results: int | None = Field(default=None, ge=1, le=100)
    filter_mode: YouTubeFilterMode = "all"
    auto_analyze: bool = True


class YouTubeSyncResponse(BaseModel):
    video_id: str
    video_title: str
    threads: list[ConversationThread]
    new_comments: int
    new_replies: int
    total_threads: int
    scanned_threads: int = 0
    analyzed_threads: int
    filter_mode: YouTubeFilterMode = "all"
    errors: list[str] = Field(default_factory=list)
    duration_ms: int
    source_mode: str
    action_mode: ActionMode


class YouTubeConnectionStatus(BaseModel):
    configured: bool
    connected: bool
    channel_id: str | None = None
    channel_title: str | None = None
    connected_at: datetime | None = None
    last_sync_at: datetime | None = None
    token_status: str = "not_configured"
    missing_credentials: list[str] = Field(default_factory=list)
    data_mode: str
    action_mode: ActionMode


class SimilarCase(BaseModel):
    feedback_id: str
    thread_id: str
    stage: str
    escalation_score: float
    admin_selected_action: str
    admin_note: str
    similarity_reason: str
    reviewed_at: datetime


class CommunityHealth(BaseModel):
    total_conversations: int
    stage_counts: dict[str, int]
    intervention_count: int
    admin_agreement_rate: float
    admin_edit_rate: float
    admin_rejection_rate: float
    improved_or_resolved: int
    average_escalation_score: float
    override_rate: float
    top_categories: list[dict[str, int | str]]
    top_channels: list[dict[str, int | str]]
