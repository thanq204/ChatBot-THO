# 20 Normalized

## Mục đích

Bản ghi chuẩn đã validation để code tính năng sử dụng. Tầng này loại bỏ khác biệt giữa các format nguồn nhưng vẫn giữ liên kết đến dữ liệu gốc.

## Thư mục con

- `knowledge/`: tài liệu dùng cho RAG.
- `faq/`: câu hỏi member, suggestion và FAQ đã publish.
- `policies/`: rule và action moderation.
- `messages/`: message nền tảng đã chuẩn hóa.
- `moderation_memory/`: quyết định đã được Admin/Mod xác nhận để chống tạo review trùng.

Mỗi bản ghi nên giữ `source_id`, `source_type`, `dataset`, `version` và timestamp.
