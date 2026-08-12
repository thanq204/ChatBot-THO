# Upload từ web

Lưu file mới upload tại đây trước khi validation.

Dùng một thư mục cho mỗi import:

```text
{import_id}/
├── original/
└── manifest.json
```

Manifest phải có `import_id`, tên file gốc, format, source, checksum, thời gian nhận và status. File hợp lệ được chuyển hoặc copy sang `10_raw/uploaded_documents/`; không sửa file gốc.

## Ví dụ raw và normalized

File nhận từ web chưa cần theo schema chung. Ví dụ raw `rules.csv`:

```csv
name,description,tag
Nội quy nhóm,Tôn trọng mọi người trong quá trình trao đổi,rules
```

Sau khi nhận, phải tạo file normalized mới tại `20_normalized/knowledge/knowledge.jsonl`, không sửa CSV:

```json
{"document_id":"KN-IMP-ABC123-001","title":"Nội quy nhóm","body":"Tôn trọng mọi người trong quá trình trao đổi","tags":["rules"],"dataset":"community_rules","source_import_id":"IMP-ABC123","source_file":"rules.csv","version":1,"active":true,"created_at":"2026-08-12T10:31:00Z","updated_at":"2026-08-12T10:31:00Z"}
```

File mẫu đầy đủ: `data/examples/01_web_upload_raw.csv` và `data/examples/03_normalized_knowledge.jsonl`.
