import io
import zipfile
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from backend.config import Settings
from backend.models.operations import KnowledgeDocumentRequest
from backend.services import knowledge_importer as knowledge_importer_module
from backend.services.knowledge_importer import KnowledgeImporter, KnowledgeImportError
from backend.services.operations_store import OperationsStore


class FakeImportStore:
    def __init__(self, *, fail_upsert: bool = False) -> None:
        self.is_postgres = True
        self.fail_upsert = fail_upsert
        self.import_statuses: list[str] = []
        self.documents: list[tuple[str, KnowledgeDocumentRequest]] = []
        self.policies: list[tuple[str, object]] = []
        self.normalized: list[dict[str, object]] = []

    def record_import(self, response, source_hash=None, status="completed"):
        self.import_statuses.append(status)
        return response

    def archive_import(self, import_id, filename, content, content_type=None):
        return None

    def record_normalized_item(self, import_id, record_index, record_type, item, **identifiers):
        self.normalized.append(item)

    def upsert_knowledge(self, document_id, request, **metadata):
        if self.fail_upsert:
            raise RuntimeError("database unavailable")
        self.documents.append((document_id, request))
        return request

    def upsert_policy(self, policy_id, request):
        self.policies.append((policy_id, request))
        return request


def importer(store: FakeImportStore | None = None) -> tuple[KnowledgeImporter, FakeImportStore]:
    result_store = store or FakeImportStore()
    settings = Settings(
        openai_api_key="",
        knowledge_extraction_enabled=False,
        knowledge_embedding_enabled=False,
    )
    return KnowledgeImporter(result_store, settings), result_store


def test_semicolon_csv_and_vietnamese_aliases_are_normalized() -> None:
    service, store = importer()
    content = "Tiêu đề;Nội dung;Từ khóa\nNội quy;Tôn trọng thành viên;văn minh|hỗ trợ".encode("utf-16")

    response = service.import_file("noi-quy.csv", content)

    assert response.normalized_count == 1
    assert response.skipped_count == 0
    assert store.documents[0][1].title == "Nội quy"
    assert store.documents[0][1].body == "Tôn trọng thành viên"
    assert store.import_statuses == ["processing", "completed"]


def test_jsonl_skips_only_invalid_lines_and_accepts_scalars() -> None:
    service, store = importer()
    payload = b'{"title":"A","body":"Alpha"}\nnot-json\n"Beta"\n'

    response = service.import_file("mixed.jsonl", payload)

    assert response.normalized_count == 2
    assert any("JSONL bỏ qua 1 dòng" in warning for warning in response.warnings)
    assert [request.body for _, request in store.documents] == ["Alpha", "Beta"]


def test_question_and_answer_columns_become_one_canonical_document() -> None:
    service, store = importer()
    payload = "Câu hỏi,Trả lời\nLịch học ở đâu?,Xem trong kênh lịch học".encode()

    service.import_file("faq.csv", payload)

    document = store.documents[0][1]
    assert document.title == "Lịch học ở đâu?"
    assert document.body == "Câu hỏi: Lịch học ở đâu?\nCâu trả lời: Xem trong kênh lịch học"


def test_long_document_is_split_without_losing_text() -> None:
    service, store = importer()
    original = ("Một đoạn kiến thức đủ dài. " * 900).strip()

    response = service.import_file("long.txt", original.encode())

    assert response.normalized_count > 1
    assert all(len(request.body) <= 9000 for _, request in store.documents)
    rebuilt = " ".join(request.body for _, request in store.documents)
    assert rebuilt.replace("\n", " ") == original
    assert any("Đã tách tài liệu dài" in warning for warning in response.warnings)


def test_html_removes_script_and_keeps_visible_text() -> None:
    service, store = importer()
    html = b"<html><body><h1>Huong dan</h1><p>Noi dung chinh</p><script>secret()</script></body></html>"

    service.import_file("guide.html", html)

    body = store.documents[0][1].body
    assert "Huong dan" in body
    assert "Noi dung chinh" in body
    assert "secret" not in body


def _xlsx_bytes(first_column: str = "A") -> bytes:
    workbook = """<?xml version="1.0" encoding="UTF-8"?>
    <workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
      xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
      <sheets><sheet name="Knowledge" sheetId="1" r:id="rId1"/></sheets>
    </workbook>"""
    relationships = """<?xml version="1.0" encoding="UTF-8"?>
    <Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
      <Relationship Id="rId1" Target="worksheets/sheet1.xml"
        Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet"/>
    </Relationships>"""
    sheet = f"""<?xml version="1.0" encoding="UTF-8"?>
    <worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>
      <row r="1"><c r="{first_column}1" t="inlineStr"><is><t>title</t></is></c><c r="B1" t="inlineStr"><is><t>body</t></is></c></row>
      <row r="2"><c r="A2" t="inlineStr"><is><t>FAQ</t></is></c><c r="B2" t="inlineStr"><is><t>Câu trả lời</t></is></c></row>
    </sheetData></worksheet>"""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("xl/workbook.xml", workbook)
        archive.writestr("xl/_rels/workbook.xml.rels", relationships)
        archive.writestr("xl/worksheets/sheet1.xml", sheet)
    return buffer.getvalue()


def test_xlsx_rows_are_imported_without_external_excel_runtime() -> None:
    service, store = importer()

    response = service.import_file("knowledge.xlsx", _xlsx_bytes())

    assert response.normalized_count == 1
    assert store.documents[0][1].title == "FAQ"
    assert store.documents[0][1].body == "Câu trả lời"


def test_office_archive_rejects_excessive_uncompressed_size(monkeypatch) -> None:
    monkeypatch.setattr(knowledge_importer_module, "MAX_ARCHIVE_UNCOMPRESSED_BYTES", 100)
    service, _store = importer()

    with pytest.raises(KnowledgeImportError, match="giải nén vượt quá"):
        service.import_file("knowledge.xlsx", _xlsx_bytes())


def test_xlsx_rejects_column_index_memory_bomb() -> None:
    service, _store = importer()

    with pytest.raises(KnowledgeImportError, match="512 cột"):
        service.import_file("knowledge.xlsx", _xlsx_bytes("ZZZZ"))


def test_docx_keeps_paragraphs_and_table_cells() -> None:
    document = """<?xml version="1.0" encoding="UTF-8"?>
    <w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>
      <w:p><w:r><w:t>Giới thiệu</w:t></w:r></w:p>
      <w:tbl><w:tr>
        <w:tc><w:p><w:r><w:t>Câu hỏi</w:t></w:r></w:p></w:tc>
        <w:tc><w:p><w:r><w:t>Câu trả lời</w:t></w:r></w:p></w:tc>
      </w:tr></w:tbl>
    </w:body></w:document>"""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("word/document.xml", document)
    service, store = importer()

    service.import_file("guide.docx", buffer.getvalue())

    body = store.documents[0][1].body
    assert "Giới thiệu" in body
    assert "Câu hỏi | Câu trả lời" in body


def test_pdf_keeps_page_number_and_warns_for_blank_page(monkeypatch) -> None:
    class Page:
        def __init__(self, text: str) -> None:
            self._text = text

        def extract_text(self, **kwargs):
            return self._text

    reader = SimpleNamespace(is_encrypted=False, pages=[Page("Nội dung trang một"), Page("")])
    monkeypatch.setattr(knowledge_importer_module.pypdf, "PdfReader", lambda stream: reader)
    service, store = importer()

    response = service.import_file("guide.pdf", b"fake-pdf")

    assert response.normalized_count == 1
    assert store.documents[0][1].title == "guide - trang 1"
    assert "page:1" in store.documents[0][1].tags
    assert any("1 trang không lấy được chữ" in warning for warning in response.warnings)


def test_pdf_rejects_excessive_page_count(monkeypatch) -> None:
    reader = SimpleNamespace(is_encrypted=False, pages=[Mock(), Mock()])
    monkeypatch.setattr(knowledge_importer_module, "MAX_PDF_PAGES", 1)
    monkeypatch.setattr(knowledge_importer_module.pypdf, "PdfReader", lambda stream: reader)
    service, _store = importer()

    with pytest.raises(KnowledgeImportError, match="quá nhiều trang"):
        service.import_file("guide.pdf", b"fake-pdf")


def test_failed_persistence_marks_import_failed() -> None:
    service, store = importer(FakeImportStore(fail_upsert=True))

    with pytest.raises(KnowledgeImportError, match="lưu dữ liệu"):
        service.import_file("knowledge.txt", b"valid content")

    assert store.import_statuses == ["processing", "failed"]


class FakeCursor:
    def __init__(self) -> None:
        self.calls = []

    def execute(self, sql, parameters=()):
        self.calls.append((sql, parameters))

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False


class FakeConnection:
    def __init__(self) -> None:
        self.cursor_instance = FakeCursor()

    def cursor(self):
        return self.cursor_instance

    def commit(self):
        return None

    def close(self):
        return None


def test_embedding_payload_does_not_overwrite_document_request() -> None:
    store = object.__new__(OperationsStore)
    store.settings = Settings(
        openai_api_key="test-key",
        knowledge_embedding_enabled=True,
        openai_embedding_model="text-embedding-3-small",
        openai_embedding_dimensions=256,
    )
    embedding_api = Mock()
    embedding_api.embeddings.create.return_value = SimpleNamespace(
        data=[SimpleNamespace(embedding=[0.1] * 256)]
    )
    connection = FakeConnection()
    store._openai = Mock(return_value=embedding_api)
    store._connect_pg = Mock(return_value=connection)
    result = store.upsert_knowledge(
        "KN-1",
        KnowledgeDocumentRequest(title="Title", body="Body", tags=["tag"]),
    )

    assert result.document_id == "KN-1"
    assert result.title == "Title"
    assert result.body == "Body"
    assert result.tags == ["tag"]
    document_insert = connection.cursor_instance.calls[0][1]
    assert document_insert[1:5] == ("Title", "Body", '["tag"]', "general")
