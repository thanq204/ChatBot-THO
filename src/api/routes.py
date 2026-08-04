from fastapi import APIRouter, HTTPException, status

from src.agents.graph import agent
from src.models.moderation import (
    AdminDecisionRequest,
    AuditLogEntry,
    MemberSubmission,
    ModerationSubmissionResponse,
    ReviewCase,
)
from src.models.schemas import ChatRequest, ChatResponse
from src.services.demo_cases import DEMO_CASES
from src.services.moderation import ModerationConfigurationError, ModerationEngine
from src.services.review_store import ReviewStore

router = APIRouter()
_moderation_engine: ModerationEngine | None = None
_review_store: ReviewStore | None = None


def get_moderation_engine() -> ModerationEngine:
    global _moderation_engine
    if _moderation_engine is None:
        _moderation_engine = ModerationEngine()
    return _moderation_engine


def get_review_store() -> ReviewStore:
    global _review_store
    if _review_store is None:
        _review_store = ReviewStore()
    return _review_store


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    try:
        result = await agent.ainvoke({"query": request.message})
        return ChatResponse(response=result.get("response", ""), analysis=result.get("analysis", ""))
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Agent request failed.") from exc


@router.get("/status")
async def agent_status():
    return {"status": "ready", "agent": "LangGraph Agent v1.0"}


@router.post("/moderation/submit", response_model=ModerationSubmissionResponse)
async def submit_for_moderation(submission: MemberSubmission) -> ModerationSubmissionResponse:
    try:
        result = await get_moderation_engine().moderate(submission)
    except ModerationConfigurationError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=exc.user_message) from exc
    review = get_review_store().create_review(submission, result) if result.needs_admin_review else None
    message = "Nội dung đang chờ Admin xem xét." if review else "Phân tích moderation đã hoàn tất."
    return ModerationSubmissionResponse(
        moderation=result,
        review=review,
        queue_item_created=review is not None,
        review_id=review.review_id if review else None,
        mode=result.mode,
        fallback_used=result.fallback_used,
        message=message,
    )


@router.get("/moderation/review-queue", response_model=list[ReviewCase])
async def review_queue() -> list[ReviewCase]:
    return get_review_store().list_pending()


@router.post("/moderation/review-queue/{review_id}/decision", response_model=ReviewCase)
async def decide_review(review_id: str, decision: AdminDecisionRequest) -> ReviewCase:
    try:
        return get_review_store().decide(review_id, decision)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Review case not found.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.get("/moderation/audit-logs", response_model=list[AuditLogEntry])
async def audit_logs() -> list[AuditLogEntry]:
    return get_review_store().list_audit_logs()


@router.get("/moderation/demo-cases", response_model=list[MemberSubmission])
async def demo_cases() -> list[MemberSubmission]:
    return DEMO_CASES


@router.get("/moderation/status")
async def moderation_status() -> dict[str, object]:
    engine = get_moderation_engine()
    settings = engine.settings
    provider = engine.provider
    return {
        "mode": "mock" if settings.moderation_mode == "mock" else provider,
        "moderation_mode": settings.moderation_mode,
        "provider": provider,
        "configured": bool(settings.openai_api_key if provider == "openai" else settings.gemini_api_key),
        "triage_model": settings.openai_moderation_model if provider == "openai" else settings.gemini_triage_model,
        "review_model": settings.openai_moderation_model if provider == "openai" else settings.gemini_review_model,
        "allow_mock_fallback": settings.allow_mock_fallback,
    }
