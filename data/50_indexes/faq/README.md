# Index FAQ

Mô tả namespace/vector index cho question và answer FAQ đã duyệt trong pgvector Supabase. Không thêm suggestion đang mở hoặc câu hỏi raw của member vào index trả lời chính thức.

Nếu cần gom topic, dùng `faq_question_embeddings` và `faq_topic_clusters` riêng; bảng trả lời chính thức `operations_faqs` chỉ chứa FAQ có `active=true` và đã được Admin/Mod duyệt.
