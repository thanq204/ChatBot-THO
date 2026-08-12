# Knowledge đã chuẩn hóa

Mỗi knowledge document là một item nguồn sạch trước khi chia chunk.

## File chuẩn bắt buộc

Khuyến nghị lưu các bản ghi trong `knowledge.jsonl`, mỗi dòng một document. Các field bắt buộc là `document_id`, `title`, `body`, `tags`, `dataset`, `source_import_id`, `source_file`, `version`, `active`, `created_at` và `updated_at`.

Ví dụ output sau chuẩn hóa:

```json
{
  "document_id": "KN-ABC123-row-1",
  "title": "Tiêu đề tài liệu",
  "body": "Nội dung tài liệu",
  "tags": ["rules"],
  "dataset": "community_rules",
  "source_import_id": "IMP-ABC123",
  "source_file": "rules.csv",
  "version": 1,
  "active": true,
  "created_at": "2026-08-12T10:30:00Z",
  "updated_at": "2026-08-12T10:30:00Z"
}
```
