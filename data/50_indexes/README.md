# 50 Indexes

Thư mục này mô tả manifest/index contract có thể tìm kiếm. Runtime dùng pgvector trên Supabase, không dùng thư mục persistence của Chroma. Giữ namespace truy xuất riêng cho `faq`, `knowledge`, `policies` và `moderation_memory`.

Index là output sinh tự động, không phải nguồn dữ liệu gốc. Index phải có thể build lại từ normalized/chunks và embedding metadata trong Supabase. Lưu model đang dùng, dimensions, version chia chunk và thời gian build trong manifest hoặc metadata runtime.

## Format manifest bắt buộc

```json
{"index_name":"knowledge","collection":"p232_knowledge","model":"text-embedding-3-small","dimensions":1536,"source_chunks":"data/30_chunks/knowledge/","embedding_version":1,"built_at":"2026-08-12T10:34:00Z"}
```
