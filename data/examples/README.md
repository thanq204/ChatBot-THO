# Ví dụ định dạng dữ liệu

Thư mục này chứa ví dụ hoàn chỉnh cho luồng `raw -> normalized -> chunks -> embeddings -> index`.

## Quy tắc đọc ví dụ

- File raw chỉ minh họa dữ liệu nhận từ web, có thể có cột hoặc field không thống nhất.
- File normalized là output bắt buộc sau bước chuẩn hóa; các module phía sau đọc format này.
- File JSONL có một JSON object trên mỗi dòng, không bọc toàn bộ dữ liệu trong một array.
- Các file mẫu chỉ dùng để hiểu schema, không phải dữ liệu production.

## Luồng ví dụ

```text
01_web_upload_raw.csv
  -> 02_raw_metadata.json
  -> 03_normalized_knowledge.jsonl
  -> 04_knowledge_chunks.jsonl
  -> 05_embedding_record.jsonl
  -> 06_index_manifest.json
```

Luồng FAQ riêng:

```text
07_member_questions.jsonl
  -> 08_faq_suggestions.jsonl
  -> 09_published_faq.jsonl
  -> 10_faq_chunks.jsonl
```

## Quy tắc cho Chat AI

```text
Đọc data/examples/README.md trước khi tạo data mới.
Nếu nhận file raw từ web, giữ nguyên file raw và tạo file normalized mới.
Không để module FAQ/RAG đọc trực tiếp CSV, TXT hoặc JSON raw.
File normalized phải dùng đúng schema trong các file mẫu tương ứng.
Nếu thêm field mới, cập nhật README mini và file mẫu trước khi code.
Luôn giữ source_import_id/source_id để truy ngược về dữ liệu gốc.
```

