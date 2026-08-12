# 00 Inbox

## Mục đích

Khu vực tạm cho dữ liệu vừa nhận vào hệ thống nhưng chưa được validation.

## Thư mục con

- `web_uploads/`: file upload từ giao diện Admin.
- `member_questions/`: câu hỏi nhận từ Discord, Telegram, YouTube hoặc form web.

## Luồng

```text
nguồn bên ngoài -> inbox -> validation -> 10_raw hoặc quarantine
```

Không dùng trực tiếp dữ liệu trong inbox để trả lời FAQ hoặc truy xuất RAG. Mỗi item phải có source và thời gian nhận.
