from __future__ import annotations

import base64
import binascii
import json
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Query, status

from backend.models.operations import (
    AnalyzeMessageRequest,
    AnalyzeMessageResponse,
    AdminPlatformActionRequest,
    AdminPlatformActionResponse,
    AnnouncementRequest,
    AnnouncementResponse,
    CommonMessage,
    CommunityHealth,
    CommandContent,
    CommandContentRequest,
    FAQ,
    FAQSuggestion,
    FAQSuggestionApproveRequest,
    FAQUpsertRequest,
    FAQWriteResponse,
    MemberReport,
    Incident,
    IncidentUpdateRequest,
    KnowledgeDocument,
    KnowledgeDocumentRequest,
    KnowledgeImportRecord,
    KnowledgeImportRequest,
    KnowledgeImportResponse,
    MessageIngestRequest,
    OperationsSummary,
    PlatformStatus,
    Policy,
    PolicyUpsertRequest,
    RagRequest,
    RagResponse,
)
from backend.services.knowledge_importer import KnowledgeImporter, KnowledgeImportError
from backend.services.admin_announcements import AdminAnnouncementSender
from backend.services.operations_demo import seed_operations_demo
from backend.services.operations_pipeline import OperationsPipeline
from backend.services.operations_store import OperationsStore
from backend.services.platform_connectors import ConnectorError, PlatformConnectors
from backend.services.platform_moderation import PlatformModerationError, PlatformModerationService

router = APIRouter(tags=["community-operations"])
_store: OperationsStore | None = None
_pipeline: OperationsPipeline | None = None
_connectors: PlatformConnectors | None = None
_importer: KnowledgeImporter | None = None


def get_operations_store() -> OperationsStore:
    global _store
    if _store is None:
        _store = OperationsStore()
    return _store


def get_operations_pipeline() -> OperationsPipeline:
    global _pipeline
    if _pipeline is None:
        _pipeline = OperationsPipeline(get_operations_store())
    return _pipeline


def get_connectors() -> PlatformConnectors:
    global _connectors
    if _connectors is None:
        _connectors = PlatformConnectors()
    return _connectors


def get_importer() -> KnowledgeImporter:
    global _importer
    if _importer is None:
        _importer = KnowledgeImporter(get_operations_store())
    return _importer


@router.get("/platforms", response_model=list[PlatformStatus])
async def platform_statuses() -> list[PlatformStatus]:
    return get_connectors().statuses()


@router.post("/platforms/{platform}/pull")
async def pull_platform(platform: str, limit: int = Query(default=100, ge=1, le=500), channel_id: str | None = None) -> dict[str, object]:
    try:
        messages = get_connectors().pull(platform, limit, channel_id)
    except ConnectorError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return await ingest_messages(MessageIngestRequest(messages=messages, analyze=True))


@router.post("/messages/analyze", response_model=AnalyzeMessageResponse)
async def analyze_message(payload: AnalyzeMessageRequest) -> AnalyzeMessageResponse:
    result = get_operations_pipeline().analyze(payload.message, payload.context)
    return AnalyzeMessageResponse(message=payload.message, result=result)


@router.post("/messages/ingest")
async def ingest_messages(payload: MessageIngestRequest) -> dict[str, object]:
    pipeline = get_operations_pipeline()
    analyzed = []
    context_by_thread: dict[str, list[CommonMessage]] = {}
    for message in payload.messages:
        context = context_by_thread.get(message.thread_key or message.channel_id, [])[-30:]
        result = pipeline.analyze(message, context) if payload.analyze else None
        analyzed.append({"message": message, "result": result})
        context_by_thread.setdefault(message.thread_key or message.channel_id, []).append(message)
    return {"received": len(payload.messages), "analyzed": len(analyzed), "items": analyzed}


@router.get("/incidents", response_model=list[Incident])
async def incidents(status_filter: str | None = Query(default=None, alias="status"), platform: str | None = None) -> list[Incident]:
    return get_operations_store().list_incidents(status_filter, platform)


@router.get("/incidents/{incident_id}")
async def incident_detail(incident_id: str) -> dict[str, object]:
    incident = get_operations_store().get_incident(incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found.")
    return {"incident": incident, "messages": get_operations_store().list_incident_messages(incident_id), "audit": get_operations_store().audit(incident_id)}


@router.patch("/incidents/{incident_id}", response_model=Incident)
async def update_incident(incident_id: str, payload: IncidentUpdateRequest) -> Incident:
    result = get_operations_store().update_incident(incident_id, payload.status, payload.assigned_to, payload.note)
    if not result:
        raise HTTPException(status_code=404, detail="Incident not found.")
    return result


@router.get("/audit")
async def operations_audit(incident_id: str | None = None) -> list[dict[str, object]]:
    return get_operations_store().audit(incident_id)


@router.get("/policies", response_model=list[Policy])
async def policies() -> list[Policy]:
    return get_operations_store().list_policies()


@router.put("/policies/{policy_id}", response_model=Policy)
async def upsert_policy(policy_id: str, payload: PolicyUpsertRequest) -> Policy:
    return get_operations_store().upsert_policy(policy_id, payload)


@router.delete("/policies/{policy_id}")
async def delete_policy(policy_id: str) -> dict[str, object]:
    if not get_operations_store().delete_policy(policy_id):
        raise HTTPException(status_code=404, detail="Không tìm thấy quy định để xóa.")
    return {"deleted": True, "policy_id": policy_id}


@router.get("/knowledge", response_model=list[KnowledgeDocument])
async def knowledge(dataset: str | None = Query(default=None, max_length=80)) -> list[KnowledgeDocument]:
    return get_operations_store().list_knowledge(dataset)


@router.post("/knowledge/import", response_model=KnowledgeImportResponse)
async def import_knowledge(payload: KnowledgeImportRequest) -> KnowledgeImportResponse:
    try:
        content = base64.b64decode(payload.content_base64, validate=True)
        return get_importer().import_file(payload.filename, content, payload.target)
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(status_code=400, detail="File upload không hợp lệ.") from exc
    except KnowledgeImportError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/knowledge/imports", response_model=list[KnowledgeImportRecord])
async def knowledge_imports() -> list[KnowledgeImportRecord]:
    return get_operations_store().list_imports()


@router.put("/knowledge/{document_id}", response_model=KnowledgeDocument)
async def upsert_knowledge(document_id: str, payload: KnowledgeDocumentRequest) -> KnowledgeDocument:
    return get_operations_store().upsert_knowledge(document_id, payload)


@router.delete("/knowledge/{document_id}")
async def delete_knowledge(document_id: str) -> dict[str, object]:
    if not get_operations_store().delete_knowledge(document_id):
        raise HTTPException(status_code=404, detail="Không tìm thấy tài liệu để xóa.")
    return {"deleted": True, "document_id": document_id}


@router.get("/faqs", response_model=list[FAQ])
async def faqs(active_only: bool = False) -> list[FAQ]:
    return get_operations_store().list_faqs(active_only)


@router.put("/faqs/{faq_id}", response_model=FAQWriteResponse)
async def upsert_faq(faq_id: str, payload: FAQUpsertRequest) -> FAQWriteResponse:
    faq, similar = get_operations_store().upsert_faq(faq_id, payload)
    warning = "Câu hỏi này có độ tương tự cao với FAQ hiện có; hãy kiểm tra trước khi xuất bản." if similar else None
    return FAQWriteResponse(faq=faq, duplicate_warning=warning, similar_faqs=similar)


@router.delete("/faqs/{faq_id}")
async def delete_faq(faq_id: str) -> dict[str, object]:
    if not get_operations_store().delete_faq(faq_id):
        raise HTTPException(status_code=404, detail="FAQ not found.")
    return {"deleted": True, "faq_id": faq_id}


@router.get("/faq-suggestions", response_model=list[FAQSuggestion])
async def faq_suggestions(status_filter: str = Query(default="open", alias="status")) -> list[FAQSuggestion]:
    return get_operations_store().list_faq_suggestions(status_filter)


@router.post("/faq-suggestions/{suggestion_id}/approve", response_model=FAQWriteResponse)
async def approve_faq_suggestion(suggestion_id: str, payload: FAQSuggestionApproveRequest) -> FAQWriteResponse:
    suggestion = next((item for item in get_operations_store().list_faq_suggestions("") if item.suggestion_id == suggestion_id), None)
    if not suggestion:
        raise HTTPException(status_code=404, detail="FAQ suggestion not found.")
    faq_id = payload.faq_id or f"FAQ-{suggestion_id.removeprefix('FAQS-')}"
    faq, similar = get_operations_store().upsert_faq(faq_id, FAQUpsertRequest(question=suggestion.representative_question, answer=payload.answer, tags=payload.tags))
    get_operations_store().set_faq_suggestion_status(suggestion_id, "approved")
    warning = "FAQ được tạo nhưng có nội dung tương tự FAQ khác; hãy rà soát." if similar else None
    return FAQWriteResponse(faq=faq, duplicate_warning=warning, similar_faqs=similar)


@router.post("/faq-suggestions/{suggestion_id}/dismiss", response_model=FAQSuggestion)
async def dismiss_faq_suggestion(suggestion_id: str) -> FAQSuggestion:
    result = get_operations_store().set_faq_suggestion_status(suggestion_id, "dismissed")
    if not result:
        raise HTTPException(status_code=404, detail="FAQ suggestion not found.")
    return result


@router.post("/incidents/{incident_id}/actions", response_model=AdminPlatformActionResponse)
async def execute_incident_action(incident_id: str, payload: AdminPlatformActionRequest) -> AdminPlatformActionResponse:
    """Run one Admin-confirmed platform action; never called automatically."""
    if not payload.confirmed:
        raise HTTPException(status_code=400, detail="Set confirmed=true after reviewing the case.")
    store = get_operations_store()
    incident = store.get_incident(incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found.")
    message = store.get_incident_message(incident_id, payload.message_id)
    if not message:
        raise HTTPException(status_code=404, detail="Message not found in this incident.")
    raw = json.loads(message.get("raw_json") or "{}")
    target_message_id = message["message_id"]
    if incident.platform == "telegram":
        target_message_id = str((raw.get("message") or {}).get("message_id") or target_message_id.rsplit("-", 1)[-1])
    try:
        result = PlatformModerationService().execute(
            platform=incident.platform,
            community_id=incident.community_id,
            channel_id=incident.channel_id,
            user_id=message["author_id"],
            message_id=target_message_id if payload.action == "delete_message" else None,
            action=payload.action,
            text=payload.message,
            duration_minutes=payload.duration_minutes,
        )
    except PlatformModerationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    store.add_audit(
        incident_id,
        message["message_id"],
        "admin_platform_action",
        payload.actor,
        {"action": payload.action, "completed": result.completed, "detail": result.detail, "target_user_id": message["author_id"], "duration_minutes": payload.duration_minutes},
    )
    return result


@router.get("/community-health", response_model=CommunityHealth)
async def community_health(window_hours: int = Query(default=24, ge=1, le=24 * 90)) -> CommunityHealth:
    return get_operations_store().community_health(window_hours)


@router.get("/admin/command-content/{command}", response_model=CommandContent)
async def command_content(command: str) -> CommandContent:
    result = get_operations_store().get_command_content(command.strip().lower().lstrip("/"))
    if not result:
        raise HTTPException(status_code=404, detail="Command content not found.")
    return result


@router.put("/admin/command-content/{command}", response_model=CommandContent)
async def upsert_command_content(command: str, payload: CommandContentRequest) -> CommandContent:
    if command.strip().lower().lstrip("/") not in {"event", "daily", "weekly", "resources", "admin"}:
        raise HTTPException(status_code=400, detail="Only event, daily, weekly, resources and admin content can be managed.")
    return get_operations_store().upsert_command_content(command, payload)


@router.get("/admin/member-reports", response_model=list[MemberReport])
async def member_reports() -> list[MemberReport]:
    return get_operations_store().list_member_reports()


@router.post("/admin/announcements", response_model=AnnouncementResponse)
async def send_admin_announcement(payload: AnnouncementRequest) -> AnnouncementResponse:
    sender = AdminAnnouncementSender()
    targets = list(dict.fromkeys(payload.targets))
    deliveries = [sender.send(payload.message, target) for target in targets]
    announcement_id = f"ANN-{uuid.uuid4().hex[:10].upper()}"
    created_at = datetime.now(UTC)
    get_operations_store().add_audit(
        None,
        None,
        "admin_announcement",
        payload.actor,
        {"announcement_id": announcement_id, "targets": targets, "delivered": [item.model_dump() for item in deliveries]},
    )
    return AnnouncementResponse(announcement_id=announcement_id, deliveries=deliveries, created_at=created_at)


@router.post("/rag/ask", response_model=RagResponse)
async def rag_ask(payload: RagRequest) -> RagResponse:
    sources = get_operations_store().search_knowledge(payload.question, dataset=payload.dataset)
    if sources:
        answer = "Mình tìm thấy các hướng dẫn liên quan:\n" + "\n".join(f"- {source.title}: {source.body}" for source in sources)
    else:
        answer = "Chưa tìm thấy tài liệu phù hợp. Hãy chuyển câu hỏi cho Admin hoặc bổ sung knowledge document."
    return RagResponse(answer=answer, sources=sources, model_used="local-knowledge-retrieval")


@router.get("/analytics", response_model=OperationsSummary)
async def operations_analytics() -> OperationsSummary:
    return get_operations_store().summary()


@router.post("/demo/seed")
async def seed_demo() -> dict[str, int]:
    return {"seeded": seed_operations_demo(get_operations_pipeline())}
