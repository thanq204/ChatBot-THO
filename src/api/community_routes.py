"""Conversation radar, YouTube read sync and Admin feedback API."""

from __future__ import annotations

import secrets
from datetime import UTC, datetime
from urllib.parse import urlencode
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query, status

from src.config import get_settings
from src.models.community import (
    AdminInterventionRequest,
    ConversationInput,
    ConversationThread,
    OutcomeRequest,
    YouTubeSyncResponse,
    YouTubeVideoRequest,
)
from src.services.community_store import CommunityStore
from src.services.conversation_analysis import ConversationAnalysisService
from src.services.embedding_memory import EmbeddingMemory
from src.services.youtube_connector import YouTubeConfigurationError, YouTubeConnector

router = APIRouter(tags=["community-health"])
_store: CommunityStore | None = None
_analysis: ConversationAnalysisService | None = None
_youtube: YouTubeConnector | None = None
_embedding_memory: EmbeddingMemory | None = None


def get_community_store() -> CommunityStore:
    global _store
    if _store is None:
        _store = CommunityStore()
    return _store


def get_analysis_service() -> ConversationAnalysisService:
    global _analysis
    if _analysis is None:
        _analysis = ConversationAnalysisService()
    return _analysis


def get_youtube_connector() -> YouTubeConnector:
    global _youtube
    if _youtube is None:
        _youtube = YouTubeConnector(store=get_community_store())
    return _youtube


def get_embedding_memory() -> EmbeddingMemory:
    global _embedding_memory
    if _embedding_memory is None:
        _embedding_memory = EmbeddingMemory()
    return _embedding_memory


def analyze_and_save(thread: ConversationThread) -> tuple[ConversationThread, dict]:
    store = get_community_store()
    service = get_analysis_service()
    embedding_matches = get_embedding_memory().search(thread)
    initial = service.analyze(thread)
    with_analysis = thread.model_copy(update={"analysis": initial, "last_analyzed_at": datetime.now(UTC)})
    similar = store.similar_cases(with_analysis, get_settings().similar_case_limit)
    analysis = service.analyze(with_analysis, similar)
    strong_match = next((match for match in embedding_matches if match["score"] >= 0.90 and match["admin_action"] in {"hide", "warn", "hold_for_review"}), None)
    if strong_match:
        analysis = analysis.model_copy(update={
            "recommended_intervention": strong_match["admin_action"],
            "reviewed_example_ids": list(dict.fromkeys([*analysis.reviewed_example_ids, strong_match["intervention_id"]]))[:5],
        })
    with_analysis = with_analysis.model_copy(update={"analysis": analysis})
    saved = store.upsert_thread(with_analysis)
    recommendation = store.save_intervention(saved.thread_id, service.recommend(saved, analysis))
    if strong_match:
        recommendation["reason"] = f"Embedding match {strong_match['score']:.0%} với case Admin đã chọn {strong_match['admin_action']}. " + recommendation["reason"]
    return saved, recommendation


def matches_youtube_filter(analysis, filter_mode: str) -> bool:
    if filter_mode == "all":
        return True
    if filter_mode == "positive":
        return analysis.category == "safe" and analysis.risk_level == "low" and analysis.conversation_stage in {"healthy", "resolving", "resolved"} and not analysis.triggers
    if filter_mode == "negative":
        return analysis.category in {"harassment", "violence", "spam"} or analysis.risk_level in {"high", "critical"} or analysis.conversation_stage in {"tense", "escalating", "critical"}
    if filter_mode == "needs_review":
        return analysis.needs_intervention or analysis.escalation_score >= 0.18 or analysis.conversation_stage == "disagreement"
    return True


@router.get("/conversations", response_model=list[ConversationThread])
async def list_conversations(stage: str | None = None, source_mode: str | None = None, video_id: str | None = None) -> list[ConversationThread]:
    return get_community_store().list_threads(stage=stage, source_mode=source_mode, video_id=video_id)


@router.get("/conversations/{thread_id}")
async def conversation_detail(thread_id: str) -> dict:
    thread = get_community_store().get_thread(thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail="Conversation thread not found.")
    if thread.analysis:
        # Enrich older rows on read so the UI can show exact matched terms
        # without requiring the user to sync the same video again.
        thread = thread.model_copy(update={"analysis": get_analysis_service()._annotate_trigger_evidence(thread, thread.analysis)})
    return {
        "thread": thread,
        "intervention": get_community_store().latest_intervention(thread_id),
        "embedding_matches": get_embedding_memory().search(thread),
        "mediation": None,
    }


@router.post("/conversations/analyze")
async def analyze_conversation(payload: ConversationInput) -> dict:
    thread = ConversationThread(
        thread_id=payload.thread_id or f"local-{uuid4().hex[:12]}", platform=payload.platform,
        community_id=payload.community_id, channel_id=payload.channel_id, video_id=payload.video_id,
        video_title=payload.video_title, content_url=payload.content_url, messages=payload.messages,
        source_mode=payload.source_mode, action_mode=payload.action_mode, imported_at=datetime.now(UTC),
    )
    saved, intervention = analyze_and_save(thread)
    return {"thread": saved, "intervention": intervention, "similar_cases": saved.analysis.reviewed_example_ids if saved.analysis else []}


@router.post("/conversations/{thread_id}/interventions/recommend")
async def recommend_intervention(thread_id: str) -> dict:
    thread = get_community_store().get_thread(thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail="Conversation thread not found.")
    if not thread.analysis:
        thread, _ = analyze_and_save(thread)
    recommendation = get_community_store().save_intervention(thread_id, get_analysis_service().recommend(thread, thread.analysis))
    return {"thread": thread, "intervention": recommendation, "action_mode": thread.action_mode}


@router.post("/conversations/{thread_id}/mediation")
async def create_mediation(thread_id: str) -> dict:
    thread = get_community_store().get_thread(thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail="Conversation thread not found.")
    if not thread.analysis:
        thread, _ = analyze_and_save(thread)
    mediation = get_community_store().save_mediation(thread_id, get_analysis_service().mediation(thread, thread.analysis))
    return mediation


@router.post("/conversations/{thread_id}/admin-decision")
async def admin_decision(thread_id: str, request: AdminInterventionRequest) -> dict:
    try:
        result = get_community_store().decide_intervention(thread_id, request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="No intervention recommendation found for this thread.") from exc
    result["execution"] = {
        "status": "simulated",
        "youtube_write_performed": False,
        "message": "SIMULATED ACTION: đã lưu quyết định Admin local; chưa gọi YouTube write API.",
    }
    if request.confirm:
        thread = get_community_store().get_thread(thread_id)
        if thread:
            get_embedding_memory().remember_review(thread, result["intervention_id"], request.selected_action, request.reviewer)
    return result


@router.post("/conversations/{thread_id}/outcome")
async def record_outcome(thread_id: str, request: OutcomeRequest) -> dict:
    try:
        return get_community_store().save_outcome(thread_id, request.outcome, request.after_intervention_score, request.admin_note)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="No reviewed intervention found for this thread.") from exc


@router.get("/feedback/history")
async def feedback_history() -> list[dict]:
    return get_community_store().list_feedback()


@router.get("/analytics/community-health")
async def community_health():
    return get_community_store().health(source_mode="public_api")


@router.get("/audit/community")
async def community_audit() -> dict:
    return {"feedback": get_community_store().list_feedback(source_mode="public_api"), "notice": "Audit trail lưu chi tiết AI recommendation và Admin decision của YouTube public trong SQLite local."}


@router.post("/youtube/sync", response_model=YouTubeSyncResponse)
async def youtube_sync(payload: YouTubeVideoRequest) -> YouTubeSyncResponse:
    try:
        requested = payload.max_results or get_settings().youtube_max_results_per_sync
        scan_limit = min(100, max(requested, 100 if payload.filter_mode != "all" else requested))
        result = get_youtube_connector().sync_video(payload.video_url_or_id, requested, fetch_limit=scan_limit, persist_threads=False)
        raw_threads = list(result["threads"])
        result["scanned_threads"] = len(raw_threads)
        result["filter_mode"] = payload.filter_mode
        if payload.auto_analyze:
            analyzed = []
            candidates = []
            for thread in raw_threads:
                quick_analysis = get_analysis_service().analyze(thread, allow_remote=False)
                if matches_youtube_filter(quick_analysis, payload.filter_mode):
                    candidates.append(thread)
                if payload.filter_mode != "all" and len(candidates) >= requested:
                    break
            selected = raw_threads[:requested] if payload.filter_mode == "all" else candidates[:requested]
            for thread in selected:
                saved, _ = analyze_and_save(thread)
                analyzed.append(saved)
            result["threads"] = analyzed
            result["analyzed_threads"] = len(analyzed)
            result["total_threads"] = len(analyzed)
            result["new_comments"] = sum(1 for thread in analyzed for message in thread.messages if not message.parent_message_id)
            result["new_replies"] = sum(1 for thread in analyzed for message in thread.messages if message.parent_message_id)
            if payload.filter_mode != "all" and len(analyzed) < requested:
                result["errors"] = [f"Đã quét {len(raw_threads)} thread nhưng chỉ tìm thấy {len(analyzed)} kết quả phù hợp với bộ lọc."]
        return YouTubeSyncResponse(**result)
    except YouTubeConfigurationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/youtube/parse")
async def parse_youtube(value: YouTubeVideoRequest) -> dict:
    try:
        return {"video_id": get_youtube_connector().parse_video_id(value.video_url_or_id)}
    except YouTubeConfigurationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/integrations/youtube/status")
async def youtube_status() -> dict:
    settings = get_settings()
    connection = get_community_store().get_youtube_connection()
    missing = [key for key, configured in (("YOUTUBE_API_KEY", bool(settings.youtube_api_key)), ("GOOGLE_CLIENT_ID", bool(settings.google_client_id)), ("GOOGLE_CLIENT_SECRET", bool(settings.google_client_secret))) if not configured]
    return {
        "configured": bool(settings.youtube_api_key), "connected": bool(connection),
        "channel_id": connection.get("channel_id") if connection else None,
        "channel_title": connection.get("channel_title") if connection else None,
        "token_status": "connected" if connection else "not_connected",
        "missing_credentials": missing, "data_mode": settings.youtube_data_mode,
        "action_mode": settings.youtube_action_mode, "public_read_only": settings.youtube_data_mode == "public_api",
    }


@router.get("/youtube/status")
async def youtube_status_alias() -> dict:
    return await youtube_status()


@router.get("/integrations/youtube/connect")
async def youtube_connect() -> dict:
    settings = get_settings()
    if not settings.google_client_id:
        return {"ready": False, "message": "OAuth scaffold sẵn sàng nhưng thiếu GOOGLE_CLIENT_ID/SECRET; public read không cần OAuth."}
    state = secrets.token_urlsafe(16)
    query = urlencode({"client_id": settings.google_client_id, "redirect_uri": settings.youtube_redirect_uri, "response_type": "code", "scope": settings.youtube_oauth_scope, "access_type": "offline", "prompt": "consent", "state": state})
    return {"ready": True, "authorization_url": f"https://accounts.google.com/o/oauth2/v2/auth?{query}", "state": state, "message": "Chỉ tiếp tục nếu bạn muốn cấp quyền cho action trên channel."}


@router.get("/integrations/youtube/callback")
async def youtube_callback(code: str | None = Query(default=None), error: str | None = Query(default=None)) -> dict:
    if error:
        return {"connected": False, "error": error}
    if not code:
        raise HTTPException(status_code=400, detail="Thiếu OAuth code.")
    return {"connected": False, "message": "OAuth callback scaffold đã nhận code. Cần cấu hình Google client và token encryption để bật channel actions."}
