# 50 Indexes

Thư mục này chứa vector index có thể tìm kiếm, ví dụ thư mục persistence của Chroma. Giữ index riêng cho `faq`, `knowledge`, `policies` và `moderation_memory`.

Index là output sinh tự động, không phải nguồn dữ liệu gốc. Index phải có thể build lại từ `30_chunks/` và `40_embeddings/`. Lưu model đang dùng, dimensions, version chia chunk và thời gian build trong `manifests/`.

## Format manifest bắt buộc

```json
{"index_name":"knowledge","collection":"p232_knowledge","model":"text-embedding-3-small","dimensions":1536,"source_chunks":"data/30_chunks/knowledge/","embedding_version":1,"built_at":"2026-08-12T10:34:00Z"}
```
