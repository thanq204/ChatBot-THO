from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

PlatformName = Literal["discord", "telegram", "zalo", "messenger", "web", "demo"]
GateName = Literal["gate1_fast_filter", "gate2_classifier", "gate3_context_review"]
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


class IncidentUpdateRequest(BaseModel):
    status: IncidentStatus | None = None
    assigned_to: str | None = Field(default=None, max_length=100)
    note: str = Field(default="", max_length=2000)


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


class PlatformStatus(BaseModel):
    platform: PlatformName
    configured: bool
    connected: bool
    mode: str
    missing_credentials: list[str] = Field(default_factory=list)
    note: str


class NotifyRequest(BaseModel):
    platforms: list[PlatformName] = Field(..., min_length=1, max_length=5)
    title: str = Field(default="", max_length=200)
    message: str = Field(..., min_length=1, max_length=2000)
    incident_id: str | None = None


class NotifyResult(BaseModel):
    platform: PlatformName
    sent: bool
    detail: str


class OperationsSummary(BaseModel):
    messages_analyzed: int
    open_incidents: int
    critical_incidents: int
    by_platform: dict[str, int]
    by_decision: dict[str, int]
    by_category: dict[str, int]
