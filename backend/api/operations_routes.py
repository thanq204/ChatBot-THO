from __future__ import annotations

import base64
import binascii

from fastapi import APIRouter, HTTPException, Query, status

from backend.models.operations import (
    AnalyzeMessageRequest,
    AnalyzeMessageResponse,
    CommonMessage,
    Incident,
    IncidentUpdateRequest,
    KnowledgeDocument,
    KnowledgeDocumentRequest,
    KnowledgeImportRecord,
    KnowledgeImportRequest,
    KnowledgeImportResponse,
    MessageIngestRequest,
    NotifyRequest,
    NotifyResult,
    OperationsSummary,
    PlatformStatus,
    Policy,
    PolicyUpsertRequest,
    RagRequest,
    RagResponse,
)
from backend.services.knowledge_importer import KnowledgeImporter, KnowledgeImportError
from backend.services.notification_dispatch import NotificationDispatcher
from backend.services.operations_demo import seed_operations_demo
from backend.services.operations_pipeline import OperationsPipeline
from backend.services.operations_store import OperationsStore
from backend.services.platform_connectors import ConnectorError, PlatformConnectors

router = APIRouter(tags=["community-operations"])
_store: OperationsStore | None = None
_pipeline: OperationsPipeline | None = None
_connectors: PlatformConnectors | None = None
_importer: KnowledgeImporter | None = None
_dispatcher: NotificationDispatcher | None = None


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


def get_dispatcher() -> NotificationDispatcher:
    global _dispatcher
    if _dispatcher is None:
        _dispatcher = NotificationDispatcher()
    return _dispatcher


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


@router.post("/notify", response_model=list[NotifyResult])
async def notify(payload: NotifyRequest) -> list[NotifyResult]:
    results = get_dispatcher().send(payload.platforms, payload.title, payload.message)
    get_operations_store().add_audit(
        payload.incident_id,
        None,
        "notification_sent",
        "Admin",
        {
            "platforms": payload.platforms,
            "title": payload.title,
            "message": payload.message,
            "results": [result.model_dump() for result in results],
        },
    )
    return results


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
