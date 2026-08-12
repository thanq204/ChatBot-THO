# 40 Embeddings

Lưu embedding artifact theo dataset và model:

```text
{dataset}/{embedding_model}/
├── vectors.jsonl
└── manifest.json
```

Mỗi item phải có `chunk_id`, model, dimensions, text hash, version và thời gian tạo. Không trộn model hoặc số chiều vector khác nhau trong một index. Nếu vector nằm trong Chroma hoặc service khác, chỉ giữ manifest và bản export có thể tái tạo tại đây.

## Format chuẩn file embedding

Nếu lưu vector dạng JSONL, mỗi dòng có dạng:

```json
{"chunk_id":"CHUNK-KN-IMP-ABC123-001-0001","model":"text-embedding-3-small","dimensions":1536,"text_hash":"sha256:...","vector":[0.012,-0.034,0.087],"version":1,"created_at":"2026-08-12T10:33:00Z"}
```

Vector trong ví dụ chỉ là vector rút gọn, không dùng cho production. Nếu dùng Chroma, phải có manifest ghi collection, model, dimensions, source chunks và thời gian build.

Giữ collection riêng cho `faq_questions`, `knowledge`, `policies` và `moderation_memory`. Query và record trong cùng collection phải dùng cùng model, dimensions và version chuẩn hóa.
