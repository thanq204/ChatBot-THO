from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.concurrency import run_in_threadpool

from backend.agents.graph import agent
from backend.models.auth import UserPublic
from backend.models.moderation import (
    AdminDecisionRequest,
    AuditLogEntry,
    MemberSubmission,
    ModerationSubmissionResponse,
    ReviewCase,
)
from backend.models.schemas import ChatRequest, ChatResponse
from backend.services.auth_service import current_user, require_roles
from backend.services.demo_cases import DEMO_CASES
from backend.services.moderation import ModerationConfigurationError, ModerationEngine
from backend.services.rate_limit import rate_limit
from backend.services.review_store import ReviewStore

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
async def chat(
    request: ChatRequest,
    _: UserPublic = Depends(current_user),
    __: UserPublic = Depends(rate_limit("legacy-agent-chat", limit=15)),
) -> ChatResponse:
    try:
        result = await agent.ainvoke({"query": request.message})
        return ChatResponse(response=result.get("response", ""), analysis=result.get("analysis", ""))
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Không thể xử lý yêu cầu bằng Agent.") from exc


@router.get("/status")
def agent_status(_: UserPublic = Depends(current_user)):
    return {"status": "ready", "agent": "LangGraph Agent v1.0"}


@router.post("/moderation/submit", response_model=ModerationSubmissionResponse)
async def submit_for_moderation(
    submission: MemberSubmission,
    _: UserPublic = Depends(require_roles("admin", "mod")),
    __: UserPublic = Depends(rate_limit("moderation-sandbox", limit=20)),
) -> ModerationSubmissionResponse:
    try:
        result = await get_moderation_engine().moderate(submission)
    except ModerationConfigurationError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=exc.user_message) from exc
    # This handler has to stay a coroutine for `moderate`, so the blocking write
    # below must be pushed off the event loop by hand.
    review = (
        await run_in_threadpool(get_review_store().create_review, submission, result)
        if result.needs_admin_review
        else None
    )
    message = "Nội dung đang chờ Admin xem xét." if review else "Phân tích kiểm duyệt đã hoàn tất."
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
def review_queue(_: UserPublic = Depends(require_roles("admin", "mod"))) -> list[ReviewCase]:
    return get_review_store().list_pending()


@router.post("/moderation/review-queue/{review_id}/decision", response_model=ReviewCase)
def decide_review(
    review_id: str,
    decision: AdminDecisionRequest,
    _: UserPublic = Depends(require_roles("admin", "mod")),
) -> ReviewCase:
    try:
        return get_review_store().decide(review_id, decision)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy trường hợp cần duyệt.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.get("/moderation/audit-logs", response_model=list[AuditLogEntry])
def audit_logs(_: UserPublic = Depends(require_roles("admin"))) -> list[AuditLogEntry]:
    return get_review_store().list_audit_logs()


@router.get("/moderation/demo-cases", response_model=list[MemberSubmission])
def demo_cases(_: UserPublic = Depends(require_roles("admin", "mod"))) -> list[MemberSubmission]:
    return DEMO_CASES


@router.get("/moderation/status")
def moderation_status(_: UserPublic = Depends(require_roles("admin", "mod"))) -> dict[str, object]:
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
