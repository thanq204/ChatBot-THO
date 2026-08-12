# 30 Chunks

Chunk là đơn vị truy xuất được tạo chỉ từ knowledge đã chuẩn hóa, FAQ đã publish hoặc policy đang active.

Mỗi chunk phải có `chunk_id`, source ID, chunk index, text, dataset, version và thời gian tạo. Với cùng input và cấu hình, việc chia chunk phải cho kết quả có thể tái lập. Không sửa bản ghi normalized tại đây.

## Format chuẩn file chunk

Lưu dạng JSONL, mỗi dòng một chunk:

```json
{"chunk_id":"CHUNK-KN-IMP-ABC123-001-0001","document_id":"KN-IMP-ABC123-001","chunk_index":0,"text":"Tôn trọng mọi người trong quá trình trao đổi","dataset":"community_rules","source_type":"knowledge","source_id":"KN-IMP-ABC123-001","version":1,"created_at":"2026-08-12T10:32:00Z"}
```

`text` là nội dung thực sự được embedding. Không đưa cả object normalized vào embedding model.
