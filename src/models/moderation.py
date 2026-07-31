from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

ModerationAction = Literal["allow", "warn", "hide", "review"]
AdminAction = Literal["allow", "warn", "hide"]
ModerationCategory = Literal[
    "safe", "spam", "harassment", "hate", "violence", "sexual", "self_harm", "ambiguous", "other"
]
RiskLevel = Literal["low", "medium", "high", "critical"]


class MemberSubmission(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=100)
    role: Literal["member"] = "member"
    text: str = Field(..., min_length=1, max_length=5000)
    channel: str = Field(default="general", min_length=1, max_length=100)
    recent_context: list[str] = Field(default_factory=list, max_length=10)


class ModerationResult(BaseModel):
    action: ModerationAction
    category: ModerationCategory
    risk_level: RiskLevel
    policy_id: str | None = Field(default=None, max_length=100)
    reason: str = Field(..., min_length=1, max_length=500)
    confidence: float = Field(..., ge=0.0, le=1.0)
    needs_admin_review: bool
    evidence: list[str] = Field(default_factory=list, max_length=5)
    model_used: str
    mode: Literal["gemini", "mock", "mock-fallback"]
    fallback_used: bool = False
    fallback_reason: str | None = None


class GeminiModerationOutput(BaseModel):
    """The exact structured output requested from both Gemini stages."""

    action: ModerationAction
    category: ModerationCategory
    risk_level: RiskLevel
    policy_id: str | None = None
    reason: str = Field(..., min_length=1, max_length=500)
    confidence: float = Field(..., ge=0.0, le=1.0)
    needs_admin_review: bool
    evidence: list[str] = Field(default_factory=list, max_length=5)


class ReviewCase(BaseModel):
    review_id: str
    user_id: str
    content: str
    channel: str
    recent_context: list[str] = Field(default_factory=list)
    model_action: ModerationAction
    model_category: ModerationCategory
    model_risk_level: RiskLevel
    model_reason: str
    model_confidence: float
    evidence: list[str] = Field(default_factory=list)
    model_used: str
    fallback_used: bool = False
    status: Literal["pending", "reviewed"]
    created_at: datetime
    reviewed_at: datetime | None = None
    admin_action: AdminAction | None = None
    admin_note: str | None = None
    reviewer: str | None = None


class ModerationSubmissionResponse(BaseModel):
    moderation: ModerationResult
    review: ReviewCase | None = None
    queue_item_created: bool
    review_id: str | None = None
    mode: Literal["gemini", "mock", "mock-fallback"]
    fallback_used: bool
    message: str


class AdminDecisionRequest(BaseModel):
    action: AdminAction
    admin_note: str = Field(default="", max_length=1000)
    reviewer: str = Field(default="Admin", min_length=1, max_length=100)


class AuditLogEntry(BaseModel):
    audit_id: str
    review_id: str
    user_id: str
    content: str
    channel: str
    model_action: ModerationAction
    model_category: ModerationCategory
    model_risk_level: RiskLevel
    model_reason: str
    model_confidence: float
    evidence: list[str] = Field(default_factory=list)
    model_used: str
    fallback_used: bool = False
    admin_action: AdminAction
    admin_note: str
    reviewer: str
    created_at: datetime
    reviewed_at: datetime
