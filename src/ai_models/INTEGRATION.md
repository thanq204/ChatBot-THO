# Handoff tích hợp model pipeline

Tài liệu này mô tả phần backend/frontend cần làm sau khi package model được merge. Package hiện tại không tự sửa API, bot, database hoặc UI.

## Backend

1. Khởi tạo một `CommunityAIPipeline` dùng chung; không tạo lại index cho từng message.
2. Discord/Telegram truyền chính xác `bot_mentioned`, `private_chat` và `bot_username` vào `route_input()`.
3. Với message nhóm không tag bot, chỉ chạy moderation realtime; không gọi FAQ/RAG/LLM.
4. Với câu hỏi tag bot hoặc chat riêng, chạy moderation trước. Nếu được phép tiếp tục, embedding câu hỏi đúng một lần rồi tái sử dụng vector cho FAQ và retrieval.
5. Map FAQ đã approved/active thành `FAQEntry`. Không đưa suggestion đang mở vào collection trả lời.
6. Map kết quả vector search thành `RetrievalCandidate`, gọi `decide_question()` với `llm_enabled=false` và trả nguyên văn `body` của source đã qua relevance gate.
7. Sau khi có answer, gọi `compose_answer()` và trả nguyên `answer_mode`, `model_used`, `citations`, `display_text`; không tự tạo citation trong UI.
8. Nếu `should_record_unanswered=true`, lưu câu hỏi member và gom suggestion cho Admin theo contract FAQ hiện tại.
9. Sau khi Admin/Mod quyết định một review, ghi moderation mark vào `data/app.db`, tạo chunk/embedding và cập nhật index `moderation_memory`.
10. Với message mới bị moderation đánh dấu, gọi `check_moderation_memory()` sau khi đã có category và trước khi tạo review mới.
11. Nếu memory match trả `send_to_admin=false`, không tạo review/ticket mới; trả metadata của mark cũ để UI mở chi tiết.

Không dùng moderation memory để tự động ban, kick, timeout hoặc delete. Quyết định cũ chỉ chống review trùng và cung cấp bằng chứng cho người kiểm duyệt.

## Response contract cần bổ sung

```json
{
  "flow": "moderation",
  "send_to_admin": false,
  "already_marked": true,
  "can_expand": true,
  "similarity": 0.94,
  "mark_id": "MM-20260812-0001",
  "banner": "(Đã được đánh dấu: công kích cá nhân bởi: mod-lan vào lúc: 2026-08-12T10:30:00Z)"
}
```

Response hỏi đáp:

```json
{
  "answer": "Học bằng dự án giúp kết hợp nhiều kiến thức vào một sản phẩm thực tế.",
  "display_text": "[RAG]\nHọc bằng dự án giúp kết hợp nhiều kiến thức vào một sản phẩm thực tế.\n\nNguồn: Project-Based Learning (KN-PROJECT)\nTrích: ...",
  "answer_mode": "extractive",
  "model_used": "rag-retrieval",
  "citations": [
    {
      "source_id": "KN-PROJECT",
      "title": "Project-Based Learning",
      "excerpt": "Học bằng dự án giúp kết hợp nhiều kiến thức vào một sản phẩm thực tế.",
      "source_type": "knowledge",
      "source_url": null
    }
  ]
}
```

## Frontend

1. Review queue không tạo card mới khi `send_to_admin=false`.
2. Hiện banner từ response ở trạng thái thu gọn.
3. Khi Admin/Mod bấm xem, gọi endpoint chi tiết theo `mark_id` và hiện message, category, decision, reason, người đánh dấu, thời gian và source URL.
4. Không hiển thị vector, embedding model hoặc nội dung raw nhạy cảm trong danh sách tổng quan.

## Cấu hình khuyến nghị

```text
FAQ_MATCH_THRESHOLD=0.86
FAQ_MATCH_MIN_MARGIN=0.035
RAG_RERANK_THRESHOLD=0.52
RAG_VECTOR_MIN_SCORE=0.38
RAG_QUERY_COVERAGE_MIN=0.24
RAG_RERANK_MIN_MARGIN=0.025
MODERATION_MEMORY_THRESHOLD=0.90
MODERATION_MEMORY_CATEGORY_FILTER=true
```

Các ngưỡng này là baseline an toàn, cần hiệu chỉnh bằng eval set tiếng Việt của dự án trước production.
