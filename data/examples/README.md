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

Luồng moderation memory riêng:

```text
11_moderation_mark.jsonl
  -> 12_moderation_memory_chunk.jsonl
  -> 13_moderation_memory_embedding.jsonl
  -> 14_moderation_match_result.json
```

## Dữ liệu cần thu thập thủ công

Mỗi file từ `15` đến `21` chỉ chứa đúng một record để minh họa trên Git. Thành viên Data tạo thêm record theo cùng schema tại nơi tiếp nhận/chuẩn hóa tương ứng, không sửa file mẫu thành dữ liệu production.

| Loại dữ liệu | File mẫu | Nơi tiếp nhận | Nơi chuẩn hóa | Bảng runtime |
|---|---|---|---|---|
| Tài liệu RAG | `15_manual_knowledge_example.jsonl` | `data/00_inbox/web_uploads/` | `data/20_normalized/knowledge/knowledge.jsonl` | `operations_knowledge` |
| FAQ đã duyệt | `16_manual_faq_example.jsonl` | `data/00_inbox/member_questions/` hoặc trang Admin | `data/20_normalized/faq/published_faq.jsonl` | `operations_faqs` |
| Policy moderation | `17_manual_policy_example.jsonl` | Trang Quy tắc AI | `data/20_normalized/policies/policies.jsonl` | `operations_policies` |
| Case Admin/Mod đã duyệt | `18_manual_moderation_mark_example.jsonl` | Incident đã review | `data/20_normalized/moderation_memory/moderation_marks.jsonl` | `operations_moderation_marks` |
| Context moderation có nhãn | `19_manual_context_case_example.jsonl` | Phiên review thủ công | `data/20_normalized/messages/moderation_context_cases.jsonl` | Chưa có bảng riêng |
| Case eval thủ công | `20_manual_eval_example.jsonl` | Tổng hợp từ QA | `data/90_exports/eval/moderation_eval.jsonl` | Không dùng runtime |
| Nội dung command | `21_manual_command_content_example.jsonl` | Trang Admin/API | `data/90_exports/command_content.jsonl` | `operations_command_content` |

`moderation mark` chỉ được đưa vào runtime sau khi Admin/Mod xác nhận. Case mẫu không phải dữ liệu production và không được dùng để tự động ban, kick hoặc xóa message.

## Quy tắc cho Chat AI

```text
Đọc data/examples/README.md trước khi tạo data mới.
Nếu nhận file raw từ web, giữ nguyên file raw và tạo file normalized mới.
Không để module FAQ/RAG đọc trực tiếp CSV, TXT hoặc JSON raw.
File normalized phải dùng đúng schema trong các file mẫu tương ứng.
Nếu thêm field mới, cập nhật README mini và file mẫu trước khi code.
Luôn giữ source_import_id/source_id để truy ngược về dữ liệu gốc.
```
