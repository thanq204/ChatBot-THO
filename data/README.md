# Khu vực dữ liệu

Đây là quy ước dữ liệu dùng chung của P-232. Hãy đọc [RULES.md](RULES.md) trước khi thêm hoặc đọc dữ liệu.

## Vai trò của thư mục data

Thư mục này chỉ chứa data contract, ví dụ, README mini và một số artifact local phục vụ phát triển. Runtime production không đọc `data/app.db`, file CSV raw hoặc file embedding trong thư mục này khi `FAQ_PG_DSN` trỏ tới Supabase.

## Luồng xử lý

```text
Input/web upload -> Supabase import raw -> Supabase normalized -> Supabase chunks -> Supabase pgvector -> runtime retrieval
                         ^
                         |
       data/00_inbox -> data/10_raw -> data/20_normalized -> data/30_chunks -> data/40_embeddings -> data/50_indexes
       (contract/example dùng để kiểm tra schema, không phải production store)
```

- `00_inbox/` đến `50_indexes/`: contract/example cho từng bước; dữ liệu chạy thật tương ứng nằm trong Supabase.
- `90_exports/`: báo cáo và dataset được xuất có chủ đích.
- `quarantine/`: dữ liệu lỗi hoặc thất bại, không được đưa vào truy xuất chính thức.

Runtime production hiện tại:

- Runtime production nằm trong Supabase PostgreSQL + pgvector: message, incident, gate runs, policy, FAQ, knowledge, chunks, embeddings và audit.
- File upload gốc nằm trong `knowledge_import_raw`; bản chuẩn hóa nằm trong `knowledge_normalized_records` của Supabase.
- `*.db`, `*.lock` và file backup trong workspace là artifact local/test, không phải source of truth production.

## Ví dụ định dạng cụ thể

Xem [`examples/README.md`](examples/README.md) để thấy đầy đủ contract raw, normalized, chunk, embedding và manifest index. Khi chạy thật, importer ghi các lớp tương ứng vào Supabase và giữ `import_id` để truy vết; các bước sau chỉ đọc bản đã chuẩn hóa, không đọc raw trực tiếp để trả lời.
