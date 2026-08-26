"""Safe file-to-canonical-schema importer for Admin knowledge and policies."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import posixpath
import re
import unicodedata
import uuid
import zipfile
from datetime import UTC, datetime
from html import unescape
from html.parser import HTMLParser
from pathlib import Path, PurePath
from xml.etree import ElementTree

import pypdf
import yaml
from charset_normalizer import from_bytes
from pydantic import ValidationError

from backend.config import Settings, get_settings
from backend.models.operations import (
    KnowledgeDocumentRequest,
    KnowledgeImportResponse,
    PolicyUpsertRequest,
)
from backend.services.operations_store import OperationsStore
from backend.services.semantic_extractor import SemanticDocumentExtractor, SemanticExtractionError

ALLOWED_FORMATS = {
    "json", "jsonl", "csv", "tsv", "xlsx", "yaml", "yml",
    "html", "htm", "md", "markdown", "txt", "docx", "pdf",
}
VALID_ACTIONS = {"allow", "warn", "hide", "hold_for_review"}
MAX_UPLOAD_BYTES = 5 * 1024 * 1024
MAX_CANONICAL_BODY_CHARS = 9000
MAX_IMPORT_ROWS = 10_000
MAX_SPREADSHEET_COLUMNS = 512
MAX_ARCHIVE_MEMBERS = 2_000
MAX_ARCHIVE_UNCOMPRESSED_BYTES = 50 * 1024 * 1024
MAX_PDF_PAGES = 500
MAX_EXTRACTED_TEXT_CHARS = 5_000_000


class _VisibleHTMLParser(HTMLParser):
    BLOCK_TAGS = {
        "address", "article", "aside", "blockquote", "br", "div", "dl", "dt", "dd",
        "figcaption", "footer", "h1", "h2", "h3", "h4", "h5", "h6", "header",
        "hr", "li", "main", "nav", "ol", "p", "pre", "section", "table", "tr", "ul",
    }
    SKIP_TAGS = {"script", "style", "svg", "noscript"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in self.SKIP_TAGS:
            self._skip_depth += 1
        elif not self._skip_depth and tag in self.BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in self.SKIP_TAGS and self._skip_depth:
            self._skip_depth -= 1
        elif not self._skip_depth and tag in self.BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._skip_depth and data.strip():
            self.parts.append(data)

    def text(self) -> str:
        return "".join(self.parts)


class KnowledgeImportError(ValueError):
    pass


class KnowledgeImporter:
    def __init__(self, store: OperationsStore, settings: Settings | None = None) -> None:
        self.store = store
        self.settings = settings or get_settings()
        self.semantic_extractor = SemanticDocumentExtractor(self.settings)

    def import_file(self, filename: str, content: bytes, target: str = "auto") -> KnowledgeImportResponse:
        extension = PurePath(filename).suffix.lower().lstrip(".") or "txt"
        extension = {"markdown": "md", "yml": "yaml", "htm": "html"}.get(extension, extension)
        if extension not in ALLOWED_FORMATS:
            raise KnowledgeImportError(
                "Định dạng chưa được phép. Chỉ nhận JSON, JSONL, CSV/TSV, XLSX, YAML, HTML, MD, TXT, DOCX hoặc PDF."
            )
        if len(content) > MAX_UPLOAD_BYTES:
            raise KnowledgeImportError("File vượt quá giới hạn 5MB.")
        if not content:
            raise KnowledgeImportError("File rỗng, không có dữ liệu để import.")

        import_id = f"IMP-{uuid.uuid4().hex[:10].upper()}"
        created_at = datetime.now(UTC)
        source_hash = hashlib.sha256(content).hexdigest()
        normalized_target = target if target in {"knowledge", "policy"} else "auto"
        warnings: list[str] = []
        normalized = 0
        skipped = 0
        knowledge_ids: list[str] = []
        policy_ids: list[str] = []
        normalized_by = "canonical-normalizer:v2"
        started = KnowledgeImportResponse(
            import_id=import_id,
            filename=filename,
            format=extension,
            target=normalized_target,
            normalized_count=0,
            created_at=created_at,
        )
        self.store.record_import(started, source_hash=source_hash, status="processing")

        try:
            if self.store.is_postgres:
                self.store.archive_import(import_id, filename, content)
            else:
                archive_error = self._archive_upload(filename, content)
                if archive_error:
                    warnings.append(archive_error)

            try:
                rows, parse_warnings = self._parse(extension, content, filename)
            except (UnicodeError, json.JSONDecodeError, csv.Error, yaml.YAMLError) as exc:
                raise KnowledgeImportError(
                    "Không đọc được file. Hãy kiểm tra encoding hoặc cấu trúc dữ liệu."
                ) from exc
            warnings.extend(parse_warnings)
            rows, preparation_warnings = self._prepare_rows(rows, filename)
            warnings.extend(preparation_warnings)
            if not rows:
                raise KnowledgeImportError("Không tìm thấy bản ghi hoặc nội dung có thể chuẩn hóa.")
            if len(rows) > MAX_IMPORT_ROWS:
                raise KnowledgeImportError(f"File có quá nhiều bản ghi; giới hạn hiện tại là {MAX_IMPORT_ROWS:,}.")

            if self.semantic_extractor.available and len(rows) <= 50:
                try:
                    rows = self.semantic_extractor.extract(rows)
                    normalized_by = f"semantic-extractor:{self.settings.knowledge_extraction_model}+canonical-v2"
                except SemanticExtractionError as exc:
                    warnings.append(f"LLM extraction failed; canonical v2 được dùng thay thế: {str(exc)[:180]}")
            elif self.semantic_extractor.available and len(rows) > 50:
                warnings.append(
                    "File có hơn 50 bản ghi; bỏ qua LLM extraction để kiểm soát chi phí, vẫn chuẩn hóa bằng canonical v2."
                )
            else:
                warnings.append("LLM extraction không khả dụng; canonical v2 đã chuẩn hóa dữ liệu.")

            for index, row in enumerate(rows, 1):
                item = self._canonical(row, filename, index)
                if not item["body"]:
                    skipped += 1
                    warnings.append(f"Bản ghi {index} không có nội dung sử dụng được nên bị bỏ qua.")
                    continue
                kind = normalized_target if normalized_target != "auto" else str(item["kind"])
                try:
                    if kind == "policy":
                        policy_id = self._scoped_policy_id(str(item["policy_id"] or ""), filename, index)
                        policy_request = PolicyUpsertRequest(
                            name=str(item["title"]),
                            description=str(item["body"])[:1000],
                            category=str(item["category"]),
                            action=str(item["action"]),
                            trigger_terms=list(item["trigger_terms"]),
                            active=bool(item["active"]),
                        )
                        self.store.upsert_policy(policy_id, policy_request)
                        self.store.record_normalized_item(import_id, index, kind, item, policy_id=policy_id)
                        policy_ids.append(policy_id)
                    else:
                        document_id = self._scoped_document_id(str(item["document_id"] or ""), filename, index)
                        knowledge_request = KnowledgeDocumentRequest(
                            title=str(item["title"]),
                            body=str(item["body"]),
                            tags=list(item["tags"]),
                            dataset=str(item["dataset"]),
                            active=bool(item["active"]),
                        )
                        self.store.upsert_knowledge(
                            document_id,
                            knowledge_request,
                            import_id=import_id,
                            source_file=filename,
                        )
                        self.store.record_normalized_item(import_id, index, kind, item, document_id=document_id)
                        knowledge_ids.append(document_id)
                except ValidationError as exc:
                    skipped += 1
                    warnings.append(f"Bản ghi {index} sai schema canonical và bị bỏ qua: {self._validation_summary(exc)}")
                    continue
                normalized += 1

            if not normalized:
                raise KnowledgeImportError("Không có bản ghi nào vượt qua bước chuẩn hóa schema.")
            response = KnowledgeImportResponse(
                import_id=import_id,
                filename=filename,
                format=extension,
                target=normalized_target,
                normalized_count=normalized,
                skipped_count=skipped,
                warnings=warnings[:50],
                normalized_by=normalized_by,
                knowledge_ids=knowledge_ids,
                policy_ids=policy_ids,
                created_at=created_at,
            )
            return self.store.record_import(response, source_hash=source_hash, status="completed")
        except KnowledgeImportError as exc:
            self._record_failed_import(
                started, source_hash, normalized, skipped, warnings, normalized_by, str(exc)
            )
            raise
        except Exception as exc:
            message = f"Import thất bại ở bước lưu dữ liệu ({type(exc).__name__})."
            self._record_failed_import(
                started, source_hash, normalized, skipped, warnings, normalized_by, message
            )
            raise KnowledgeImportError(message) from exc

    def _record_failed_import(
        self,
        started: KnowledgeImportResponse,
        source_hash: str,
        normalized: int,
        skipped: int,
        warnings: list[str],
        normalized_by: str,
        message: str,
    ) -> None:
        failed = started.model_copy(
            update={
                "normalized_count": normalized,
                "skipped_count": skipped,
                "warnings": [*warnings, message][:50],
                "normalized_by": normalized_by,
            }
        )
        try:
            self.store.record_import(failed, source_hash=source_hash, status="failed")
        except Exception:
            # Preserve the original import error if even status persistence is unavailable.
            pass

    @staticmethod
    def _validation_summary(exc: ValidationError) -> str:
        first = exc.errors(include_url=False)[0]
        field = ".".join(str(part) for part in first.get("loc", ())) or "record"
        return f"{field}: {first.get('msg', 'invalid value')}"

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

    def _parse(
        self,
        extension: str,
        content: bytes,
        filename: str,
    ) -> tuple[list[dict[str, object]], list[str]]:
        if extension == "pdf":
            return self._pdf_rows(content, filename)
        if extension == "docx":
            return ([{"title": PurePath(filename).stem, "body": self._docx_text(content), "tags": ["document", "docx"]}], [])
        if extension == "xlsx":
            return self._xlsx_rows(content, filename)

        text, encoding_warning = self._decode_text(content)
        warnings = [encoding_warning] if encoding_warning else []
        if extension == "json":
            return self._payload_rows(json.loads(text)), warnings
        if extension == "yaml":
            return self._payload_rows(yaml.safe_load(text)), warnings
        if extension == "jsonl":
            rows: list[dict[str, object]] = []
            invalid_lines: list[int] = []
            for line_number, line in enumerate(text.splitlines(), 1):
                if not line.strip():
                    continue
                try:
                    value = json.loads(line)
                except json.JSONDecodeError:
                    invalid_lines.append(line_number)
                    continue
                rows.extend(self._payload_rows(value))
            if invalid_lines:
                preview = ", ".join(str(number) for number in invalid_lines[:8])
                suffix = "..." if len(invalid_lines) > 8 else ""
                warnings.append(f"JSONL bỏ qua {len(invalid_lines)} dòng JSON lỗi: {preview}{suffix}.")
            return rows, warnings
        if extension in {"csv", "tsv"}:
            rows, csv_warnings = self._csv_rows(text, extension)
            return rows, [*warnings, *csv_warnings]
        if extension == "md":
            return self._markdown_rows(text, filename), warnings
        if extension == "html":
            parser = _VisibleHTMLParser()
            parser.feed(text)
            return ([{"title": PurePath(filename).stem, "body": parser.text(), "tags": ["html"]}], warnings)
        return ([{"title": PurePath(filename).stem, "body": text, "tags": [extension]}], warnings)

    @staticmethod
    def _decode_text(content: bytes) -> tuple[str, str | None]:
        if content.startswith((b"\xff\xfe", b"\xfe\xff")):
            return content.decode("utf-16"), "File dùng UTF-16; hệ thống đã chuyển sang Unicode chuẩn."
        try:
            return content.decode("utf-8-sig"), None
        except UnicodeDecodeError:
            match = from_bytes(content).best()
            if match is None:
                raise KnowledgeImportError("Không xác định được encoding của file văn bản.")
            encoding = match.encoding or "unknown"
            return str(match), f"File dùng encoding {encoding}; hệ thống đã tự chuyển sang Unicode."

    @classmethod
    def _payload_rows(cls, payload: object) -> list[dict[str, object]]:
        if payload is None:
            return []
        if isinstance(payload, list):
            return [item if isinstance(item, dict) else {"body": cls._coerce_scalar(item)} for item in payload]
        if isinstance(payload, dict):
            normalized_keys = {cls._normalize_key(str(key)): key for key in payload}
            for wrapper in ("documents", "knowledge", "policies", "items", "data", "records", "rows", "results"):
                original_key = normalized_keys.get(wrapper)
                if original_key is not None and isinstance(payload[original_key], list):
                    return cls._payload_rows(payload[original_key])
            return [payload]
        return [{"body": cls._coerce_scalar(payload)}]

    @classmethod
    def _csv_rows(cls, text: str, extension: str) -> tuple[list[dict[str, object]], list[str]]:
        sample = text[:16_384]
        warnings: list[str] = []
        delimiter = "\t" if extension == "tsv" else ","
        try:
            delimiter = csv.Sniffer().sniff(sample, delimiters=",;\t|").delimiter
        except csv.Error:
            warnings.append(f"Không tự nhận diện được dấu phân cách; dùng {repr(delimiter)}.")

        reader = csv.reader(io.StringIO(text), delimiter=delimiter)
        raw_rows = [row for row in reader if any(str(cell).strip() for cell in row)]
        if not raw_rows:
            return [], warnings
        header = cls._unique_headers(raw_rows[0])
        if not any(str(cell).strip() for cell in raw_rows[0]):
            header = [f"column_{index}" for index in range(1, len(raw_rows[0]) + 1)]
        rows = []
        for raw in raw_rows[1:]:
            padded = [*raw, *([""] * max(0, len(header) - len(raw)))]
            rows.append({header[index]: padded[index] for index in range(len(header))})
        if len(raw_rows) == 1:
            rows.append({"body": " | ".join(raw_rows[0])})
            warnings.append("File chỉ có một hàng; hàng này được xử lý như nội dung thay vì header.")
        return rows, warnings

    @classmethod
    def _unique_headers(cls, values: list[object]) -> list[str]:
        headers: list[str] = []
        counts: dict[str, int] = {}
        for index, value in enumerate(values, 1):
            base = cls._normalize_key(cls._coerce_scalar(value)) or f"column_{index}"
            counts[base] = counts.get(base, 0) + 1
            headers.append(base if counts[base] == 1 else f"{base}_{counts[base]}")
        return headers

    @staticmethod
    def _markdown_rows(text: str, filename: str) -> list[dict[str, object]]:
        matches = list(re.finditer(r"(?m)^(#{1,4})\s+(.+?)\s*$", text))
        if not matches:
            return [{"title": PurePath(filename).stem, "body": text, "tags": ["markdown"]}]
        rows: list[dict[str, object]] = []
        preamble = text[:matches[0].start()].strip()
        if preamble:
            rows.append({"title": PurePath(filename).stem, "body": preamble, "tags": ["markdown", "preamble"]})
        for index, match in enumerate(matches):
            start = match.end()
            end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
            body = text[start:end].strip()
            if body:
                rows.append({"title": match.group(2).strip(), "body": body, "tags": ["markdown"]})
        return rows

    @classmethod
    def _xlsx_rows(cls, content: bytes, filename: str) -> tuple[list[dict[str, object]], list[str]]:
        main_ns = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
        rel_ns = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
        package_rel_ns = "http://schemas.openxmlformats.org/package/2006/relationships"
        rows: list[dict[str, object]] = []
        warnings: list[str] = []
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                cls._validate_office_archive(archive)
                shared: list[str] = []
                if "xl/sharedStrings.xml" in archive.namelist():
                    shared_root = ElementTree.fromstring(archive.read("xl/sharedStrings.xml"))
                    for item in shared_root.findall(f"{{{main_ns}}}si"):
                        shared.append("".join(node.text or "" for node in item.iter(f"{{{main_ns}}}t")))

                workbook = ElementTree.fromstring(archive.read("xl/workbook.xml"))
                relationships = ElementTree.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
                targets = {
                    relation.attrib["Id"]: relation.attrib["Target"]
                    for relation in relationships.findall(f"{{{package_rel_ns}}}Relationship")
                }
                for sheet in workbook.findall(f".//{{{main_ns}}}sheet"):
                    sheet_name = sheet.attrib.get("name", "Sheet")
                    relationship_id = sheet.attrib.get(f"{{{rel_ns}}}id", "")
                    target = targets.get(relationship_id, "")
                    path = target.lstrip("/") if target.startswith("/xl/") else posixpath.normpath(f"xl/{target}")
                    if path not in archive.namelist():
                        warnings.append(f"Không đọc được sheet {sheet_name}.")
                        continue
                    root = ElementTree.fromstring(archive.read(path))
                    matrix: list[list[str]] = []
                    for row_node in root.findall(f".//{{{main_ns}}}sheetData/{{{main_ns}}}row"):
                        if len(matrix) >= MAX_IMPORT_ROWS:
                            raise KnowledgeImportError(
                                f"Bảng tính vượt quá giới hạn {MAX_IMPORT_ROWS:,} dòng dữ liệu."
                            )
                        values: dict[int, str] = {}
                        for cell in row_node.findall(f"{{{main_ns}}}c"):
                            reference = cell.attrib.get("r", "A1")
                            letters = re.match(r"[A-Z]+", reference.upper())
                            column = cls._xlsx_column_index(letters.group(0) if letters else "A")
                            if column >= MAX_SPREADSHEET_COLUMNS:
                                raise KnowledgeImportError(
                                    f"Bảng tính vượt quá giới hạn {MAX_SPREADSHEET_COLUMNS} cột."
                                )
                            values[column] = cls._xlsx_cell_value(cell, shared, main_ns)
                        if values:
                            matrix.append([values.get(index, "") for index in range(max(values) + 1)])
                    matrix = [row for row in matrix if any(cell.strip() for cell in row)]
                    if not matrix:
                        warnings.append(f"Sheet {sheet_name} không có dữ liệu và đã bị bỏ qua.")
                        continue
                    if len(matrix) == 1:
                        rows.append({"title": f"{PurePath(filename).stem} - {sheet_name}", "body": " | ".join(matrix[0]), "sheet": sheet_name})
                        continue
                    headers = cls._unique_headers(matrix[0])
                    for raw in matrix[1:]:
                        padded = [*raw, *([""] * max(0, len(headers) - len(raw)))]
                        item = {headers[index]: padded[index] for index in range(len(headers))}
                        item["sheet"] = sheet_name
                        rows.append(item)
            return rows, warnings
        except (KeyError, zipfile.BadZipFile, ElementTree.ParseError) as exc:
            raise KnowledgeImportError("XLSX không đọc được, bị hỏng hoặc không đúng định dạng Office Open XML.") from exc

    @staticmethod
    def _validate_office_archive(archive: zipfile.ZipFile) -> None:
        """Reject ZIP bombs before any DOCX/XLSX member is decompressed."""
        members = archive.infolist()
        if len(members) > MAX_ARCHIVE_MEMBERS:
            raise KnowledgeImportError(
                f"File Office có quá nhiều thành phần; giới hạn là {MAX_ARCHIVE_MEMBERS:,}."
            )
        total_size = sum(max(0, item.file_size) for item in members)
        if total_size > MAX_ARCHIVE_UNCOMPRESSED_BYTES:
            raise KnowledgeImportError("File Office giải nén vượt quá giới hạn an toàn 50 MB.")
        if any(item.flag_bits & 0x1 for item in members):
            raise KnowledgeImportError("File Office được mã hóa nên không thể xử lý an toàn.")

    @staticmethod
    def _xlsx_column_index(letters: str) -> int:
        value = 0
        for char in letters:
            value = value * 26 + ord(char) - ord("A") + 1
        return value - 1

    @staticmethod
    def _xlsx_cell_value(cell: ElementTree.Element, shared: list[str], namespace: str) -> str:
        cell_type = cell.attrib.get("t")
        if cell_type == "inlineStr":
            return "".join(node.text or "" for node in cell.iter(f"{{{namespace}}}t"))
        value_node = cell.find(f"{{{namespace}}}v")
        value = value_node.text if value_node is not None and value_node.text is not None else ""
        if cell_type == "s" and value.isdigit() and int(value) < len(shared):
            return shared[int(value)]
        if cell_type == "b":
            return "true" if value == "1" else "false"
        return value

    @classmethod
    def _prepare_rows(
        cls,
        rows: list[dict[str, object]],
        filename: str,
    ) -> tuple[list[dict[str, object]], list[str]]:
        prepared: list[dict[str, object]] = []
        warnings: list[str] = []
        split_count = 0
        for row_index, row in enumerate(rows, 1):
            if not isinstance(row, dict):
                row = {"body": cls._coerce_scalar(row)}
            normalized: dict[str, object] = {}
            for key, value in row.items():
                normalized_key = cls._normalize_key(str(key))
                if not normalized_key:
                    continue
                normalized[normalized_key] = value

            body = cls._extract_body(normalized)
            if not body:
                metadata_keys = {
                    "id", "document_id", "policy_id", "title", "name", "tags", "tag",
                    "dataset", "collection", "namespace", "type", "kind", "target", "active",
                    "category", "label", "action", "decision", "trigger_terms", "terms", "keywords",
                }
                body_parts = []
                for key, value in normalized.items():
                    text = cls._clean_text(cls._coerce_scalar(value))
                    if key not in metadata_keys and text:
                        body_parts.append(f"{key.replace('_', ' ').title()}: {text}")
                body = "\n".join(body_parts)
            body = cls._clean_text(body)
            if not body:
                prepared.append(normalized)
                continue

            title = cls._first_value(
                normalized,
                "title", "name", "tieu_de", "heading", "subject", "chu_de", "topic", "question", "cau_hoi",
            )
            if not title:
                first_line = next((line.strip() for line in body.splitlines() if line.strip()), PurePath(filename).stem)
                title = first_line[:120]
            normalized["title"] = cls._clean_text(title)[:200]
            normalized["body"] = body
            normalized.setdefault("dataset", cls._filename_dataset(filename))

            parts = cls._split_text(body, MAX_CANONICAL_BODY_CHARS)
            if len(parts) > 1:
                split_count += len(parts) - 1
            for part_index, part in enumerate(parts, 1):
                item = dict(normalized)
                item["body"] = part
                if len(parts) > 1:
                    item["title"] = f"{normalized['title']} (phần {part_index}/{len(parts)})"[:200]
                    for identifier in ("document_id", "policy_id", "id"):
                        if item.get(identifier):
                            item[identifier] = f"{item[identifier]}-part-{part_index}"
                prepared.append(item)
        if split_count:
            warnings.append(f"Đã tách tài liệu dài thành {split_count} phần bổ sung để không mất nội dung.")
        return prepared, warnings

    @classmethod
    def _extract_body(cls, row: dict[str, object]) -> str:
        body = cls._first_value(
            row,
            "body", "content", "text", "description", "noi_dung", "noi_dung_chinh",
            "document", "article", "answer", "tra_loi", "response", "details", "chi_tiet",
        )
        question = cls._first_value(row, "question", "cau_hoi", "query", "prompt")
        answer = cls._first_value(row, "answer", "tra_loi", "response", "dap_an")
        if question and answer:
            return f"Câu hỏi: {question}\nCâu trả lời: {answer}"
        return body or question

    @classmethod
    def _first_value(cls, row: dict[str, object], *keys: str) -> str:
        for key in keys:
            candidate = row.get(key)
            if candidate is not None:
                text = cls._clean_text(cls._coerce_scalar(candidate))
                if text:
                    return text
        return ""

    @staticmethod
    def _split_text(text: str, limit: int) -> list[str]:
        if len(text) <= limit:
            return [text]
        parts: list[str] = []
        current = ""
        paragraphs = re.split(r"\n\s*\n", text)
        for paragraph in paragraphs:
            paragraph = paragraph.strip()
            while len(paragraph) > limit:
                split_at = paragraph.rfind(". ", 0, limit)
                if split_at >= limit // 2:
                    split_at += 1
                else:
                    split_at = paragraph.rfind(" ", 0, limit)
                if split_at < limit // 2:
                    split_at = limit
                piece, paragraph = paragraph[:split_at].strip(), paragraph[split_at:].strip()
                if current:
                    parts.append(current.strip())
                    current = ""
                if piece:
                    parts.append(piece)
            candidate = f"{current}\n\n{paragraph}".strip() if current else paragraph
            if len(candidate) > limit:
                parts.append(current.strip())
                current = paragraph
            else:
                current = candidate
        if current.strip():
            parts.append(current.strip())
        return parts

    @staticmethod
    def _filename_dataset(filename: str) -> str:
        stem = unicodedata.normalize("NFKD", PurePath(filename).stem)
        ascii_stem = "".join(char for char in stem if not unicodedata.combining(char))
        slug = re.sub(r"[^a-z0-9]+", "_", ascii_stem.lower()).strip("_")
        return (slug or "general")[:80]

    @staticmethod
    def _normalize_key(value: str) -> str:
        value = value.replace("đ", "d").replace("Đ", "D")
        normalized = unicodedata.normalize("NFKD", value.replace("\ufeff", ""))
        ascii_value = "".join(char for char in normalized if not unicodedata.combining(char))
        return re.sub(r"[^a-z0-9]+", "_", ascii_value.lower()).strip("_")

    @staticmethod
    def _clean_text(value: str) -> str:
        value = unicodedata.normalize("NFKC", unescape(value)).replace("\x00", "")
        value = value.replace("\r\n", "\n").replace("\r", "\n")
        value = re.sub(r"[\t\f\v]+", " ", value)
        value = re.sub(r"[ ]{2,}", " ", value)
        value = re.sub(r"\n[ ]+", "\n", value)
        value = re.sub(r"\n{3,}", "\n\n", value)
        return value.strip()

    @staticmethod
    def _coerce_scalar(value: object) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return value
        if isinstance(value, (dict, list, tuple)):
            return json.dumps(value, ensure_ascii=False, default=str)
        return str(value)

    @staticmethod
    def _canonical(row: dict[str, object], filename: str, index: int) -> dict[str, object]:
        def value(*keys: str, default: str = "") -> str:
            for key in keys:
                candidate = row.get(key)
                if candidate is not None and str(candidate).strip():
                    return str(candidate).strip()
            return default

        raw_tags = row.get("tags") or row.get("tag") or row.get("tu_khoa") or ""
        raw_tag_list = raw_tags if isinstance(raw_tags, list) else re.split(r"[,;|]", str(raw_tags))
        tags: list[str] = []
        for raw_tag in raw_tag_list:
            tag = KnowledgeImporter._clean_text(str(raw_tag))[:60]
            if tag and tag.casefold() not in {item.casefold() for item in tags}:
                tags.append(tag)
            if len(tags) == 20:
                break
        action_aliases = {
            "canh_bao": "warn", "warning": "warn", "an": "hide", "remove": "hide",
            "cho_duyet": "hold_for_review", "review": "hold_for_review", "giu_lai": "allow",
        }
        raw_action = value("action", "decision", "recommended_action", default="hold_for_review")
        action = action_aliases.get(KnowledgeImporter._normalize_key(raw_action), raw_action.lower())
        if action not in VALID_ACTIONS:
            action = "hold_for_review"
        kind = value("type", "kind", "target", default="knowledge").lower()
        title = KnowledgeImporter._clean_text(value("title", "name", "tieu_de", default=f"Imported item {index}"))[:200]
        body = KnowledgeImporter._clean_text(value("body", "content", "text", "description", "noi_dung"))[:MAX_CANONICAL_BODY_CHARS]
        dataset = KnowledgeImporter._clean_text(value("dataset", "collection", "namespace", default=KnowledgeImporter._filename_dataset(filename)))[:80]
        category = KnowledgeImporter._clean_text(value("category", "label", default="other"))[:50]
        trigger_terms = []
        for item in re.split(r"[,;|]", value("trigger_terms", "terms", "keywords", "tu_khoa")):
            term = KnowledgeImporter._clean_text(item)[:100]
            if term and term.casefold() not in {existing.casefold() for existing in trigger_terms}:
                trigger_terms.append(term)
            if len(trigger_terms) == 30:
                break
        explicit_action = bool(value("action", "decision", "recommended_action"))
        return {
            "document_id": value("document_id", "documentid", "id"),
            "policy_id": value("policy_id", "policyid"),
            "title": title or f"Imported item {index}", "body": body, "tags": tags,
            "dataset": dataset or "general", "category": category or "other", "action": action,
            "trigger_terms": trigger_terms,
            "kind": "policy" if kind in {"policy", "policies", "rule", "rules", "quy_dinh"} or explicit_action and action != "hold_for_review" else "knowledge",
            "active": KnowledgeImporter._normalize_key(str(row.get("active", "true"))) not in {"false", "0", "no", "khong", "inactive"},
        }

    @staticmethod
    def _docx_text(content: bytes) -> str:
        namespace = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"

        def paragraph_text(node: ElementTree.Element) -> str:
            return "".join(item.text or "" for item in node.iter(f"{{{namespace}}}t")).strip()

        def document_part_text(xml: bytes) -> list[str]:
            root = ElementTree.fromstring(xml)
            body = root.find(f".//{{{namespace}}}body")
            container = body if body is not None else root
            parts: list[str] = []
            for child in container:
                if child.tag == f"{{{namespace}}}p":
                    text = paragraph_text(child)
                    if text:
                        parts.append(text)
                elif child.tag == f"{{{namespace}}}tbl":
                    table_rows: list[str] = []
                    for table_row in child.findall(f"{{{namespace}}}tr"):
                        cells = [paragraph_text(cell) for cell in table_row.findall(f"{{{namespace}}}tc")]
                        if any(cells):
                            table_rows.append(" | ".join(cells))
                    if table_rows:
                        parts.append("\n".join(table_rows))
            return parts

        try:
            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                KnowledgeImporter._validate_office_archive(archive)
                parts = document_part_text(archive.read("word/document.xml"))
                for name in archive.namelist():
                    if re.fullmatch(r"word/(header|footer)\d+\.xml", name):
                        parts.extend(document_part_text(archive.read(name)))
            text = "\n\n".join(unescape(part) for part in parts if part.strip())
            if not text.strip():
                raise KnowledgeImportError("DOCX không chứa đoạn văn hoặc bảng có thể đọc được.")
            return text
        except (KeyError, zipfile.BadZipFile, ElementTree.ParseError) as exc:
            raise KnowledgeImportError("DOCX không đọc được hoặc bị hỏng.") from exc

    @staticmethod
    def _pdf_rows(content: bytes, filename: str) -> tuple[list[dict[str, object]], list[str]]:
        try:
            reader = pypdf.PdfReader(io.BytesIO(content))
            if reader.is_encrypted:
                try:
                    reader.decrypt("")
                except Exception as exc:
                    raise KnowledgeImportError("PDF đang được bảo vệ bằng mật khẩu.") from exc
            if len(reader.pages) > MAX_PDF_PAGES:
                raise KnowledgeImportError(f"PDF có quá nhiều trang; giới hạn là {MAX_PDF_PAGES} trang.")
            rows: list[dict[str, object]] = []
            blank_pages: list[int] = []
            extracted_chars = 0
            stem = PurePath(filename).stem
            for page_number, page in enumerate(reader.pages, 1):
                try:
                    text = page.extract_text(extraction_mode="layout")
                except (TypeError, ValueError):
                    text = page.extract_text()
                text = KnowledgeImporter._clean_text(text or "")
                if not text:
                    blank_pages.append(page_number)
                    continue
                extracted_chars += len(text)
                if extracted_chars > MAX_EXTRACTED_TEXT_CHARS:
                    raise KnowledgeImportError("Nội dung trích xuất từ PDF vượt quá giới hạn an toàn 5 triệu ký tự.")
                rows.append({
                    "title": f"{stem} - trang {page_number}",
                    "body": text,
                    "tags": ["document", "pdf", f"page:{page_number}"],
                    "source_page": page_number,
                })
            if not rows:
                raise KnowledgeImportError(
                    "PDF không có lớp chữ để đọc. Đây có thể là bản scan; hãy chạy OCR hoặc xuất lại PDF có thể chọn văn bản."
                )
            warnings = []
            if blank_pages:
                preview = ", ".join(str(page) for page in blank_pages[:10])
                suffix = "..." if len(blank_pages) > 10 else ""
                warnings.append(f"PDF có {len(blank_pages)} trang không lấy được chữ: {preview}{suffix}.")
            return rows, warnings
        except KnowledgeImportError:
            raise
        except Exception as exc:
            raise KnowledgeImportError("PDF không đọc được hoặc bị hỏng.") from exc
