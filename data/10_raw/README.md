# 10 Raw

## Mục đích

Bản sao nguồn bất biến được giữ để audit, chạy lại và xử lý lại.

Không normalize trực tiếp trong file raw. Parser hoặc importer đọc từ đây và ghi kết quả mới vào `20_normalized/`.

## Metadata bắt buộc

Lưu `import_id`, source, tên file gốc, format, checksum, thời gian nhận và trạng thái xử lý. Giữ nguyên bytes gốc nếu có thể.
