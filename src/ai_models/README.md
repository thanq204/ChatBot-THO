# Model pipeline Rule - Moderation - FAQ - LLM/RAG

Package này chỉ chứa logic model, không chứa API route, bot transport, database migration hoặc UI.

## Luồng input

```text
Lệnh /help, /rule, ... -> Rule -> dừng
Tin nhắn nhóm bình thường -> Moderation realtime -> dừng
Tin nhắn tag @chatbot -> Moderation -> Supabase FAQ match -> RAG -> rerank -> relevance -> LLM/extractive
Tin nhắn riêng với bot -> Moderation -> Supabase FAQ match -> RAG -> rerank -> relevance -> LLM/extractive
```

FAQ và RAG chỉ tham gia luồng hỏi đáp. Tin nhắn nhóm không tag bot không được gọi FAQ, retrieval hoặc LLM.

## Khi nào gọi LLM

- FAQ semantic match đủ mạnh: trả câu trả lời Admin đã duyệt, không gọi LLM.
- Rerank/relevance không đạt: không gọi LLM, ghi nhận câu hỏi chưa có đáp án.
- Nguồn rất mạnh và có độ phủ từ khóa cao: trả đoạn trích trực tiếp, không gọi LLM.
- Nguồn đạt relevance nhưng cần tổng hợp: gọi grounded LLM với đúng nguồn đã qua gate.
- LLM bị tắt hoặc lỗi: trả đoạn trích nguồn, không tự suy đoán.

## Phân biệt loại câu trả lời và trích nguồn

Gọi `compose_answer()` sau khi có nội dung trả lời. Output luôn có `answer_mode`, `model_used`, `citations` và `display_text`.

```text
[FAQ đã duyệt]      -> câu trả lời do Admin/Mod duyệt
[RAG]               -> lấy trực tiếp từ nguồn, không gọi LLM
[RAG + LLM]         -> LLM tổng hợp từ context đã qua relevance gate
[Không đủ nguồn]    -> từ chối trả lời, không gọi LLM
```

Mọi output RAG thành công bắt buộc có `source_id`, title và đoạn trích. Không gắn citation vào nguồn chưa qua relevance gate.

Runtime chatbot hiện dùng `[RAG]` cho knowledge đã chuẩn hóa và không gọi LLM ở nhánh này. `RAG + LLM` chỉ còn là capability dự phòng trong package model, chưa được bật trong Discord/Telegram.

## Moderation memory

Sau khi Admin/Mod quyết định một review, adapter backend tạo `ModerationMark`, embedding nội dung và lưu runtime vào `operations_moderation_marks` và `operations_moderation_embeddings` trên Supabase. Contract mẫu nằm tại `data/20_normalized/moderation_memory/README.md`.

Với message mới đã bị model moderation đánh dấu, gọi `check_moderation_memory()` trước khi tạo review mới:

- match đủ ngưỡng: `send_to_admin=false`, hiện banner đã đánh dấu và cho mở chi tiết;
- không match: `send_to_admin=true`, tạo review theo luồng hiện tại;
- chỉ so sánh cùng category mặc định để tránh dùng nhầm quyết định giữa spam, harassment và violence.

## Điểm tích hợp

Backend cần làm adapter từ model hiện tại sang `FAQEntry`, `RetrievalCandidate` và `ModerationMark`. Vector phải được tạo bởi cùng embedding model và cùng version với index tương ứng.
