from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

PlatformName = Literal["discord", "telegram", "zalo", "messenger", "web", "demo"]
GateName = Literal["gate1_fast_filter", "gate2_context_review", "gate3_approved_case_retrieval"]
Decision = Literal["allow", "warn", "hide", "hold_for_review"]
IncidentStatus = Literal["open", "monitoring", "resolved", "snoozed"]
Severity = Literal["low", "medium", "high", "critical"]


class CommonMessage(BaseModel):
    message_id: str = Field(..., min_length=1, max_length=200)
    platform: PlatformName
    community_id: str = Field(default="community-001", min_length=1, max_length=200)
    channel_id: str = Field(default="general", min_length=1, max_length=200)
    thread_key: str | None = Field(default=None, max_length=200)
    parent_message_id: str | None = Field(default=None, max_length=200)
    author_id: str = Field(default="anonymous", min_length=1, max_length=200)
    author_name: str | None = Field(default=None, max_length=200)
    text: str = Field(..., min_length=1, max_length=10000)
    timestamp: datetime
    source_url: str | None = None
    raw: dict[str, object] = Field(default_factory=dict)


class MessageIngestRequest(BaseModel):
    messages: list[CommonMessage] = Field(..., min_length=1, max_length=500)
    analyze: bool = True


class AnalyzeMessageRequest(BaseModel):
    message: CommonMessage
    context: list[CommonMessage] = Field(default_factory=list, max_length=30)


class GateResult(BaseModel):
    gate: GateName
    passed: bool
    label: str
    category: str = "safe"
    risk_score: float = Field(default=0.0, ge=0.0, le=1.0)
    evidence: list[str] = Field(default_factory=list, max_length=6)
    explanation: str = Field(default="", max_length=500)
    model_used: str = "local-rules"
    duration_ms: int = 0


class ContextReviewOutput(BaseModel):
    category: str = "safe"
    risk_score: float = Field(default=0.0, ge=0.0, le=1.0)
    evidence: list[str] = Field(default_factory=list, max_length=6)
    explanation: str = Field(default="", max_length=500)


class MessageDecision(BaseModel):
    decision: Decision
    category: str
    severity: Severity
    risk_score: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: list[str] = Field(default_factory=list, max_length=8)
    explanation: str = Field(..., max_length=1000)
    model_used: str
    gates: list[GateResult] = Field(default_factory=list)
    incident_id: str | None = None
    # Backwards-compatible notification metadata. Existing API consumers can
    # ignore these fields, while realtime connectors can suppress duplicates.
    send_to_admin: bool = True
    send_to_member: bool = True
    already_marked: bool = False
    can_expand: bool = False
    matched_mark_id: str | None = None
    similarity: float | None = Field(default=None, ge=0.0, le=1.0)
    banner: str | None = None


class AnalyzeMessageResponse(BaseModel):
    message: CommonMessage
    result: MessageDecision


class Incident(BaseModel):
    incident_id: str
    platform: PlatformName
    community_id: str
    channel_id: str
    thread_key: str | None = None
    status: IncidentStatus
    severity: Severity
    risk_score: float
    title: str
    summary: str
    categories: list[str] = Field(default_factory=list)
    message_ids: list[str] = Field(default_factory=list)
    message_count: int = 0
    first_seen: datetime
    last_seen: datetime
    assigned_to: str | None = None
    created_at: datetime
    updated_at: datetime
    source_url: str | None = None


class IncidentUpdateRequest(BaseModel):
    status: IncidentStatus | None = None
    assigned_to: str | None = Field(default=None, max_length=100)
    note: str = Field(default="", max_length=2000)


class AdminPlatformActionRequest(BaseModel):
    """A deliberately explicit, human-approved action against one case."""

    action: Literal["dm", "delete_message", "timeout", "kick", "ban"]
    message_id: str | None = Field(default=None, max_length=200)
    message: str = Field(default="", max_length=1900)
    duration_minutes: int | None = Field(default=None, ge=1, le=40_320)
    actor: str = Field(default="Admin", min_length=1, max_length=100)
    confirmed: bool = False


class AdminPlatformActionResponse(BaseModel):
    action: str
    platform: Literal["discord", "telegram"]
    target_user_id: str
    target_message_id: str | None = None
    completed: bool
    detail: str


class Policy(BaseModel):
    policy_id: str
    name: str
    description: str
    category: str
    action: Decision
    trigger_terms: list[str] = Field(default_factory=list)
    active: bool = True
    version: int = 1
    updated_at: datetime


class PolicyUpsertRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: str = Field(..., min_length=1, max_length=1000)
    category: str = Field(default="other", min_length=1, max_length=50)
    action: Decision = "hold_for_review"
    trigger_terms: list[str] = Field(default_factory=list, max_length=30)
    active: bool = True


class KnowledgeDocument(BaseModel):
    document_id: str
    title: str
    body: str
    tags: list[str] = Field(default_factory=list)
    dataset: str = "general"
    active: bool = True
    updated_at: datetime


class KnowledgeDocumentRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    body: str = Field(..., min_length=1, max_length=10000)
    tags: list[str] = Field(default_factory=list, max_length=20)
    dataset: str = Field(default="general", min_length=1, max_length=80)
    active: bool = True


class KnowledgeImportResponse(BaseModel):
    import_id: str
    filename: str
    format: str
    target: Literal["knowledge", "policy", "auto"]
    normalized_count: int
    skipped_count: int = 0
    warnings: list[str] = Field(default_factory=list)
    normalized_by: str = "canonical-normalizer"
    knowledge_ids: list[str] = Field(default_factory=list)
    policy_ids: list[str] = Field(default_factory=list)
    created_at: datetime


class KnowledgeImportRequest(BaseModel):
    filename: str = Field(..., min_length=1, max_length=255)
    content_base64: str = Field(..., min_length=1, max_length=10_000_000)
    target: Literal["knowledge", "policy", "auto"] = "auto"


class KnowledgeImportRecord(BaseModel):
    import_id: str
    filename: str
    format: str
    target: str
    normalized_count: int
    skipped_count: int
    warnings: list[str] = Field(default_factory=list)
    normalized_by: str
    created_at: datetime


class RagRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    platform: PlatformName | None = None
    dataset: str | None = Field(default=None, max_length=80)


class RagResponse(BaseModel):
    answer: str
    sources: list[KnowledgeDocument]
    model_used: str


class FAQ(BaseModel):
    faq_id: str
    question: str
    answer: str
    tags: list[str] = Field(default_factory=list)
    active: bool = True
    updated_at: datetime


class FAQUpsertRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=500)
    answer: str = Field(..., min_length=1, max_length=5000)
    tags: list[str] = Field(default_factory=list, max_length=20)
    active: bool = True


class FAQWriteResponse(BaseModel):
    faq: FAQ
    duplicate_warning: str | None = None
    similar_faqs: list[FAQ] = Field(default_factory=list)


class FAQSuggestion(BaseModel):
    suggestion_id: str
    representative_question: str
    question_count: int
    status: Literal["open", "approved", "dismissed"] = "open"
    sample_questions: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class FAQTopic(BaseModel):
    cluster_id: str
    topic_label: str
    representative_question: str
    question_count: int
    sample_questions: list[str] = Field(default_factory=list)
    status: Literal["open", "approved", "dismissed"] = "open"
    approved_faq_id: str | None = None
    updated_at: datetime


class FAQSuggestionApproveRequest(BaseModel):
    faq_id: str | None = Field(default=None, max_length=200)
    question: str | None = Field(default=None, min_length=3, max_length=500)
    answer: str = Field(..., min_length=1, max_length=5000)
    tags: list[str] = Field(default_factory=list, max_length=20)


class ChatOutcome(BaseModel):
    answer: str
    stage: Literal["rule", "faq", "moderation", "rag", "llm", "scope-filter"]
    model_used: str
    moderation: MessageDecision | None = None
    faq_id: str | None = None
    sources: list[KnowledgeDocument] = Field(default_factory=list)
    retrieval_score: float | None = Field(default=None, ge=0.0, le=1.0)
    relevance_passed: bool | None = None


# The two live bot integrations a command's reply can be scoped to.
CommandPlatform = Literal["telegram", "discord"]


class CommandContent(BaseModel):
    command: str
    body: str
    description: str = ""
    platforms: list[CommandPlatform] = Field(default_factory=lambda: ["telegram", "discord"])
    updated_at: datetime


class CommandContentRequest(BaseModel):
    body: str = Field(..., min_length=1, max_length=5000)
    description: str = Field(default="", max_length=300)
    platforms: list[CommandPlatform] = Field(default_factory=lambda: ["telegram", "discord"], min_length=1, max_length=2)


# Commands the bot already seeds Admin-editable content for out of the box.
# These can never be deleted, only rewritten.
CORE_BOT_COMMANDS: frozenset[str] = frozenset({"event", "daily", "weekly", "resources", "admin"})

# Names the chat orchestrator handles with dedicated logic (not plain stored
# text), so Admin cannot claim them when creating a new command.
RESERVED_BOT_COMMANDS: frozenset[str] = CORE_BOT_COMMANDS | frozenset(
    {"start", "help", "rule", "rules", "faq", "report", "settings"}
)


class MemberReport(BaseModel):
    report_id: str
    platform: PlatformName
    reporter_id: str
    channel_id: str
    details: str
    status: Literal["open", "reviewed"] = "open"
    created_at: datetime


class MemberReportUpdateRequest(BaseModel):
    status: Literal["open", "reviewed"]
    actor: str = Field(default="Admin", min_length=1, max_length=100)


class MemberReputation(BaseModel):
    member_id: str
    platform: PlatformName
    community_id: str
    platform_user_id: str
    display_name: str | None = None
    reputation_score: int = 0
    positive_points: int = 0
    penalty_points: int = 0
    event_count: int = 0
    last_event_at: datetime | None = None
    last_seen_at: datetime
    status: Literal["trusted", "neutral", "watch", "risk"] = "neutral"


class ReputationRule(BaseModel):
    rule_id: str
    name: str
    description: str
    points: int
    trigger_mode: Literal["automatic", "community_signal", "admin_review", "event_confirmation"]
    daily_limit: int | None = None
    weekly_limit: int | None = None
    requirements: list[str] = Field(default_factory=list)
    approval_status: Literal["draft", "approved", "rejected"] = "draft"
    active: bool = False
    updated_at: datetime


class IncidentReputationDecisionRequest(BaseModel):
    outcome: Literal["confirmed", "dismissed"]
    note: str = Field(default="", max_length=1000)


class IncidentReputationDecisionResponse(BaseModel):
    incident_id: str
    outcome: Literal["confirmed", "dismissed"]
    affected_members: int = 0
    points_applied: int = 0


class FlaggedLink(BaseModel):
    link_id: str
    canonical_url: str
    domain: str
    status: Literal["blocked", "released"] = "blocked"
    flag_count: int = 1
    first_message_id: str | None = None
    last_message_id: str | None = None
    reported_by: str | None = None
    first_flagged_at: datetime
    last_seen_at: datetime


class CommunityHealth(BaseModel):
    window_hours: int
    messages_total: int
    spam_count: int
    toxic_count: int
    risky_count: int
    unique_members: int
    new_members: int
    top_topics: list[tuple[str, int]] = Field(default_factory=list)
    open_faq_suggestions: int
    generated_at: datetime


class TimelineBucket(BaseModel):
    """One slot of the activity grid. Emitted even when empty."""

    start: datetime
    scanned: int
    violations: int


class ActivityTimeline(BaseModel):
    window_hours: int
    bucket_hours: int
    scanned_total: int
    violations_total: int
    buckets: list[TimelineBucket] = Field(default_factory=list)
    generated_at: datetime


class AnnouncementRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=1900)
    targets: list[Literal["discord", "telegram"]] = Field(..., min_length=1, max_length=2)
    actor: str = Field(default="Admin", min_length=1, max_length=100)


class AnnouncementDelivery(BaseModel):
    platform: Literal["discord", "telegram"]
    delivered: bool
    detail: str


class AnnouncementResponse(BaseModel):
    announcement_id: str
    deliveries: list[AnnouncementDelivery]
    created_at: datetime


class PlatformStatus(BaseModel):
    platform: PlatformName
    configured: bool
    connected: bool
    mode: str
    missing_credentials: list[str] = Field(default_factory=list)
    note: str


class DiscordChannelOption(BaseModel):
    guild_id: str
    guild_name: str
    channel_id: str
    channel_name: str


class OperationsSummary(BaseModel):
    messages_analyzed: int
    open_incidents: int
    critical_incidents: int
    by_platform: dict[str, int]
    by_decision: dict[str, int]
    by_category: dict[str, int]
