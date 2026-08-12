# Khu vực dữ liệu

Đây là quy ước dữ liệu dùng chung của P-232. Hãy đọc [RULES.md](RULES.md) trước khi thêm hoặc đọc dữ liệu.

## Luồng xử lý

```text
00_inbox -> 10_raw -> 20_normalized -> 30_chunks -> 40_embeddings -> 50_indexes
```

- `00_inbox/`: file mới nhận và câu hỏi mới từ các nền tảng.
- `10_raw/`: bản sao bất biến của dữ liệu gốc.
- `20_normalized/`: bản ghi chuẩn để các tính năng sử dụng.
- `30_chunks/`: các đoạn văn bản đã chuẩn bị cho truy xuất.
- `40_embeddings/`: metadata embedding và các artifact vector.
- `50_indexes/`: vector index dùng để tìm kiếm.
- `90_exports/`: báo cáo và dataset được xuất có chủ đích.
- `quarantine/`: dữ liệu lỗi hoặc thất bại, không được đưa vào truy xuất chính thức.

Dữ liệu runtime hiện tại được giữ nguyên:

- `app.db`: database chính và nguồn dữ liệu nghiệp vụ hiện tại.
- `knowledge_uploads/`: kho upload đang được code ứng dụng sử dụng.
- `*.db`, `*.lock` và file backup: artifact runtime; không tự ý di chuyển hoặc đổi tên.

## Ví dụ định dạng cụ thể

Xem [`examples/README.md`](examples/README.md) để thấy đầy đủ file raw, file normalized, chunk, embedding và manifest index. Quy tắc bắt buộc là: file raw giữ nguyên, bước normalization tạo file mới theo schema chung, các bước sau chỉ đọc file normalized.
