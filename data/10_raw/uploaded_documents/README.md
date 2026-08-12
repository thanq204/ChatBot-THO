# Tài liệu upload raw

Lưu file gốc đã qua validation từ luồng upload web, nhóm theo `import_id`.

```text
{import_id}/
├── source.ext
└── metadata.json
```

Các format hiện được hỗ trợ gồm JSON, JSONL, CSV, Markdown, TXT và DOCX. Parsing và normalization thuộc bước sau.

## Output bắt buộc sau chuẩn hóa

File raw chỉ giữ bản gốc. Normalizer phải tạo file mới dạng JSONL tại `20_normalized/knowledge/`, mỗi dòng một document theo format:

```json
{"document_id":"KN-IMP-ABC123-001","title":"Nội quy nhóm","body":"Tôn trọng mọi người trong quá trình trao đổi","tags":["rules"],"dataset":"community_rules","source_import_id":"IMP-ABC123","source_file":"rules.csv","version":1,"active":true,"created_at":"2026-08-12T10:31:00Z","updated_at":"2026-08-12T10:31:00Z"}
```
