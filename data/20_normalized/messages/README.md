# Message đã chuẩn hóa

Lưu message độc lập nền tảng tại đây khi feature cần bản file bên cạnh `app.db`.

Giữ `message_id`, platform, community/channel ID, author ID, text, source URL, timestamp và `raw_source_id`. Không tạo nhiều ID cho cùng một message.

## Phân luồng

- Command như `/help`, `/rule`, `/faq`: đi `Rule`, không gọi model.
- Message nhóm không tag chatbot: chỉ đi `Moderation` realtime.
- Message tag chatbot hoặc chat riêng: đi `Moderation -> FAQ -> LLM/RAG`.
- FAQ match đủ ngưỡng: trả câu trả lời đã duyệt và dừng; không gọi RAG/LLM.
- FAQ chưa có: retrieval, rerank và relevance phải đạt trước khi gọi LLM.
