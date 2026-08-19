# FAQ đã chuẩn hóa

File JSONL bên dưới là contract để kiểm tra format. Runtime thật lưu và truy xuất trong Supabase: câu hỏi ở `operations_faq_questions`, nhóm chủ đề ở `faq_topic_clusters`/`faq_topic_members`, FAQ đã duyệt ở `operations_faqs`.

Giữ riêng ba nhóm dữ liệu:

```text
member_questions.jsonl -> suggestions.jsonl -> published_faq.jsonl
```

Suggestion đang mở chưa phải là câu trả lời. Chỉ FAQ đã approved/published mới được đưa vào index FAQ. Giữ chuỗi liên kết `question_id -> suggestion_id -> faq_id`.

## Format chuẩn từng file

`member_questions.jsonl`:

```json
{"question_id":"Q-20260812-0001","message_id":"MSG-discord-123","platform":"discord","author_id":"member-456","question":"Làm sao để đăng ký môn học?","normalized_question":"lam sao de dang ky mon hoc","status":"new","created_at":"2026-08-12T10:35:00Z"}
```

`suggestions.jsonl`:

```json
{"suggestion_id":"FAQS-20260812-0001","representative_question":"Làm sao để đăng ký môn học?","normalized_question":"dang ky mon hoc","question_count":2,"sample_question_ids":["Q-20260812-0001","Q-20260812-0002"],"status":"open","created_at":"2026-08-12T10:40:00Z","updated_at":"2026-08-12T10:40:00Z"}
```

`published_faq.jsonl`, chỉ ghi sau khi Admin duyệt; runtime tương ứng là `operations_faqs` và `operations_faq_embeddings`:

```json
{"faq_id":"FAQ-COURSE-REGISTRATION","question":"Làm sao để đăng ký môn học?","answer":"Bạn đăng ký môn học trên hệ thống đào tạo theo thời gian nhà trường thông báo.","tags":["course","registration"],"source_suggestion_id":"FAQS-20260812-0001","version":1,"active":true,"created_at":"2026-08-12T10:45:00Z","updated_at":"2026-08-12T10:45:00Z"}
```
