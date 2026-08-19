"""Safe file-to-canonical-schema importer for Admin knowledge and policies."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import uuid
import zipfile
from datetime import UTC, datetime
from html import unescape
from pathlib import Path, PurePath
from xml.etree import ElementTree

import PyPDF2

from backend.config import Settings, get_settings
from backend.models.operations import (
    KnowledgeDocumentRequest,
    KnowledgeImportResponse,
    PolicyUpsertRequest,
)
from backend.services.operations_store import OperationsStore
from backend.services.semantic_extractor import SemanticDocumentExtractor, SemanticExtractionError

ALLOWED_FORMATS = {"json", "jsonl", "csv", "md", "markdown", "txt", "docx", "pdf"}
VALID_ACTIONS = {"allow", "warn", "hide", "hold_for_review"}


class KnowledgeImportError(ValueError):
    pass


class KnowledgeImporter:
    def __init__(self, store: OperationsStore, settings: Settings | None = None) -> None:
        self.store = store
        self.settings = settings or get_settings()
        self.semantic_extractor = SemanticDocumentExtractor(self.settings)

    def import_file(self, filename: str, content: bytes, target: str = "auto") -> KnowledgeImportResponse:
        extension = PurePath(filename).suffix.lower().lstrip(".") or "txt"
        if extension == "markdown":
            extension = "md"
        if extension not in ALLOWED_FORMATS:
            raise KnowledgeImportError("Định dạng chưa được phép. Chỉ nhận JSON, JSONL, CSV, MD, TXT, DOCX hoặc PDF.")
        if len(content) > 5 * 1024 * 1024:
            raise KnowledgeImportError("File vượt quá giới hạn 5MB.")
        try:
            rows = self._parse(extension, content, filename)
        except (UnicodeError, json.JSONDecodeError, csv.Error) as exc:
            raise KnowledgeImportError("Không đọc được file. Hãy kiểm tra encoding hoặc cấu trúc JSON/CSV.") from exc
        if not rows:
            raise KnowledgeImportError("Không tìm thấy bản ghi hoặc nội dung có thể chuẩn hóa.")
        import_id = f"IMP-{uuid.uuid4().hex[:10].upper()}"
        created_at = datetime.now(UTC)
        source_hash = hashlib.sha256(content).hexdigest()
        warnings: list[str] = []
        started = KnowledgeImportResponse(
            import_id=import_id,
            filename=filename,
            format=extension,
            target=target if target in {"knowledge", "policy"} else "auto",
            normalized_count=0,
            created_at=created_at,
        )
        self.store.record_import(started, source_hash=source_hash, status="processing")
        if self.store.is_postgres:
            self.store.archive_import(import_id, filename, content)
        else:
            archive_error = self._archive_upload(filename, content)
            if archive_error:
                warnings.append(archive_error)
        normalized_by = "canonical-normalizer"
        if self.semantic_extractor.available and len(rows) <= 50:
            try:
                rows = self.semantic_extractor.extract(rows)
                normalized_by = f"semantic-extractor:{self.settings.knowledge_extraction_model}"
            except SemanticExtractionError as exc:
                warnings.append(f"LLM extraction failed; deterministic normalization used: {str(exc)[:180]}")
        elif self.semantic_extractor.available and len(rows) > 50:
            warnings.append("File có hơn 50 bản ghi; semantic extraction được bỏ qua để kiểm soát chi phí. Deterministic normalization được sử dụng.")
        else:
            warnings.append("LLM extraction skipped; deterministic normalization used because no OpenAI key is configured.")
        normalized = 0
        skipped = 0
        knowledge_ids: list[str] = []
        policy_ids: list[str] = []
        for index, row in enumerate(rows, 1):
            item = self._canonical(row, filename, index)
            if not item["body"]:
                skipped += 1
                warnings.append(f"Dòng {index} thiếu body/content/text nên bị bỏ qua.")
                continue
            kind = target if target in {"knowledge", "policy"} else ("policy" if item["kind"] == "policy" else "knowledge")
            if kind == "policy":
                policy_id = self._scoped_policy_id(str(item["policy_id"] or ""), filename, index)
                self.store.record_normalized_item(import_id, index, kind, item, policy_id=policy_id)
                self.store.upsert_policy(policy_id, PolicyUpsertRequest(name=item["title"], description=item["body"][:1000], category=item["category"], action=item["action"], trigger_terms=item["trigger_terms"], active=item["active"]))
                policy_ids.append(policy_id)
            else:
                document_id = self._scoped_document_id(str(item["document_id"] or ""), filename, index)
                self.store.record_normalized_item(import_id, index, kind, item, document_id=document_id)
                self.store.upsert_knowledge(document_id, KnowledgeDocumentRequest(title=item["title"], body=item["body"], tags=item["tags"], dataset=item["dataset"], active=item["active"]), import_id=import_id, source_file=filename)
                knowledge_ids.append(document_id)
            normalized += 1
        response = KnowledgeImportResponse(import_id=import_id, filename=filename, format=extension, target=target if target in {"knowledge", "policy"} else "auto", normalized_count=normalized, skipped_count=skipped, warnings=warnings[:20], normalized_by=normalized_by, knowledge_ids=knowledge_ids, policy_ids=policy_ids, created_at=created_at)
        return self.store.record_import(response, source_hash=source_hash, status="completed")

    @staticmethod
    def _scoped_document_id(raw_id: str, filename: str, index: int) -> str:
        """Keep document IDs stable within one file but isolated across files.

        Many CSV exports number every row from 1 again. Using that number as a
        global primary key caused a later upload to overwrite an older file.
        The filename fingerprint makes re-uploading the same file an update,
        while a different file gets its own persistent document namespace.
        """
        fingerprint = hashlib.sha1(filename.strip().lower().encode("utf-8")).hexdigest()[:10].upper()
        row_key = re.sub(r"[^A-Za-z0-9_-]+", "-", raw_id.strip()) or f"row-{index}"
        return f"KN-{fingerprint}-{row_key}"[:200]

    @staticmethod
    def _scoped_policy_id(raw_id: str, filename: str, index: int) -> str:
        fingerprint = hashlib.sha1(filename.strip().lower().encode("utf-8")).hexdigest()[:10].upper()
        row_key = re.sub(r"[^A-Za-z0-9_-]+", "-", raw_id.strip()) or f"row-{index}"
        return f"POL-{fingerprint}-{row_key}"[:200]

    def _archive_upload(self, filename: str, content: bytes) -> str | None:
        """Keep the original upload locally for audit and re-processing."""
        try:
            archive_dir = Path(self.settings.knowledge_archive_dir)
            archive_dir.mkdir(parents=True, exist_ok=True)
            safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", PurePath(filename).name).strip("._") or "upload.bin"
            digest = hashlib.sha256(content).hexdigest()[:12].upper()
            (archive_dir / f"{digest}_{safe_name}").write_bytes(content)
            return None
        except OSError as exc:
            return f"Original file archive skipped: {type(exc).__name__}. Normalized records were still saved."

    def _parse(self, extension: str, content: bytes, filename: str) -> list[dict[str, object]]:
        if extension == "pdf":
            return [{"title": PurePath(filename).stem, "body": self._pdf_text(content), "tags": ["document"]}]
        if extension == "docx":
            return [{"title": PurePath(filename).stem, "body": self._docx_text(content), "tags": ["document"]}]
        text = content.decode("utf-8-sig", errors="replace")
        if extension == "json":
            payload = json.loads(text)
            if isinstance(payload, list):
                return [item if isinstance(item, dict) else {"body": str(item)} for item in payload]
            if isinstance(payload, dict):
                for key in ("documents", "knowledge", "policies", "items", "data"):
                    if isinstance(payload.get(key), list):
                        return [item if isinstance(item, dict) else {"body": str(item)} for item in payload[key]]
                return [payload]
        if extension == "jsonl":
            return [json.loads(line) for line in text.splitlines() if line.strip()]
        if extension == "csv":
            return [dict(row) for row in csv.DictReader(io.StringIO(text))]
        if extension == "md":
            sections = re.split(r"(?m)^#{1,3}\s+", text)
            headings = re.findall(r"(?m)^#{1,3}\s+(.+)$", text)
            if len(sections) > 1:
                return [{"title": headings[index - 1].strip() if index - 1 < len(headings) else PurePath(filename).stem, "body": section.strip(), "tags": ["markdown"]} for index, section in enumerate(sections[1:], 1) if section.strip()]
        return [{"title": PurePath(filename).stem, "body": text.strip(), "tags": [extension]}]

    @staticmethod
    def _canonical(row: dict[str, object], filename: str, index: int) -> dict[str, object]:
        def value(*keys: str, default: str = "") -> str:
            for key in keys:
                candidate = row.get(key)
                if candidate is not None and str(candidate).strip():
                    return str(candidate).strip()
            return default

        raw_tags = row.get("tags") or row.get("tag") or ""
        tags = raw_tags if isinstance(raw_tags, list) else [item.strip() for item in re.split(r"[,;|]", str(raw_tags)) if item.strip()]
        action = value("action", "decision", "recommended_action", default="hold_for_review")
        if action not in VALID_ACTIONS:
            action = "hold_for_review"
        kind = value("type", "kind", "target", default="knowledge").lower()
        return {
            "document_id": value("document_id", "id"), "policy_id": value("policy_id", "policyId"),
            "title": value("title", "name", "tieu_de", default=f"Imported item {index}"),
            "body": value("body", "content", "text", "description", "noi_dung"), "tags": tags,
            "dataset": value("dataset", "collection", "namespace", default="general"),
            "category": value("category", "label", default="other"), "action": action,
            "trigger_terms": [item.strip() for item in re.split(r"[,;|]", value("trigger_terms", "terms", "keywords")) if item.strip()],
            "kind": "policy" if kind in {"policy", "policies", "rule", "rules"} or action != "hold_for_review" and value("action", "decision") else "knowledge",
            "active": str(row.get("active", "true")).lower() not in {"false", "0", "no"},
        }

    @staticmethod
    def _docx_text(content: bytes) -> str:
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                xml = archive.read("word/document.xml")
            root = ElementTree.fromstring(xml)
            paragraphs = []
            for paragraph in root.iter("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p"):
                text = "".join(node.text or "" for node in paragraph.iter("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t"))
                if text.strip():
                    paragraphs.append(unescape(text.strip()))
            return "\n\n".join(paragraphs)
        except (KeyError, zipfile.BadZipFile, ElementTree.ParseError) as exc:
            raise KnowledgeImportError("DOCX không đọc được hoặc bị hỏng.") from exc

    @staticmethod
    def _pdf_text(content: bytes) -> str:
        try:
            reader = PyPDF2.PdfReader(io.BytesIO(content))
            pages = []
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    pages.append(text.strip())
            return "\n\n".join(pages)
        except Exception as exc:
            raise KnowledgeImportError("PDF không đọc được hoặc bị hỏng.") from exc
