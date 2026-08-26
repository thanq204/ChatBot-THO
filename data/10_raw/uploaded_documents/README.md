# Tài liệu upload raw

Lưu file gốc đã qua validation từ luồng upload web, nhóm theo `import_id`.

```text
{import_id}/
├── source.ext
└── metadata.json
```

Các format hiện được hỗ trợ gồm JSON, JSONL, CSV/TSV, XLSX, YAML, HTML, Markdown, TXT, DOCX và PDF (tối đa 5 MB). Parsing và normalization thuộc bước sau.

Importer tự nhận encoding và dấu phân cách CSV, đọc từng sheet XLSX, giữ nội dung bảng DOCX và số trang PDF. PDF scan không có lớp chữ cần được OCR trước khi upload. Bản ghi lỗi riêng lẻ được bỏ qua kèm cảnh báo; tài liệu dài được tách thành nhiều document canonical để không mất nội dung.

## Output bắt buộc sau chuẩn hóa

File raw chỉ giữ bản gốc. Normalizer phải tạo file mới dạng JSONL tại `20_normalized/knowledge/`, mỗi dòng một document theo format:

```json
{"document_id":"KN-IMP-ABC123-001","title":"Nội quy nhóm","body":"Tôn trọng mọi người trong quá trình trao đổi","tags":["rules"],"dataset":"community_rules","source_import_id":"IMP-ABC123","source_file":"rules.csv","version":1,"active":true,"created_at":"2026-08-12T10:31:00Z","updated_at":"2026-08-12T10:31:00Z"}
```
