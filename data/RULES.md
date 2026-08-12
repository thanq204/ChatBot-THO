# Quy tắc dữ liệu và hướng dẫn cho AI

File này là quy ước bắt buộc cho mọi thành viên và mọi Chat AI làm việc với `data/`.

## Quy tắc bắt buộc

1. Chỉ đọc hoặc ghi dữ liệu trong thư mục được phân công cho tính năng.
2. Không tạo thư mục cấp cao mới nếu chưa cập nhật file này.
3. Không tự ý di chuyển, đổi tên, xóa hoặc ghi đè dữ liệu hiện có.
4. Dữ liệu raw phải bất biến. Xử lý lại phải tạo output hoặc version mới.
5. File text dùng UTF-8.
6. Dữ liệu dạng collection append-only dùng JSONL, mỗi dòng là một JSON object hợp lệ.
7. Timestamp dùng ISO-8601 UTC, ví dụ `2026-08-12T10:30:00Z`.
8. Dùng ID ổn định. Không dùng số dòng làm ID duy nhất.
9. Liên kết bản ghi bằng ID, không liên kết bằng tên file hoặc tên thư mục.
10. Không lưu API key, password, token hoặc secret trong thư mục này.
11. Không commit database, raw upload, embedding, index, lock hoặc log sinh tự động nếu team chưa thống nhất.
12. Không tạo database riêng cho FAQ, RAG hoặc embedding. `data/app.db` vẫn là database chính hiện tại.
13. File lỗi phải giữ trong `quarantine/`, không được âm thầm xóa.
14. Trước khi đổi schema, phải cập nhật README mini tương ứng và nêu rõ ảnh hưởng migration.

## Luồng dữ liệu

```text
File upload hoặc sự kiện từ nền tảng
  -> 00_inbox
  -> 10_raw
  -> 20_normalized
  -> 30_chunks
  -> 40_embeddings
  -> 50_indexes
  -> Tìm kiếm FAQ hoặc truy xuất RAG
```

## Các loại ID ổn định

| ID | Ý nghĩa |
|---|---|
| `IMP-*` | Một lần upload/import |
| `MSG-*` | Một message từ nền tảng |
| `Q-*` | Một câu hỏi của member |
| `FAQS-*` | Một nhóm/suggestion FAQ |
| `FAQ-*` | Một FAQ đã publish |
| `POL-*` | Một policy moderation |
| `KN-*` | Một tài liệu knowledge đã chuẩn hóa |
| `CHUNK-*` | Một chunk dùng cho truy xuất |

## Quy tắc raw và normalized

- File nhận trực tiếp từ web có thể là CSV, JSON, JSONL, TXT, Markdown hoặc DOCX và **không bắt buộc** theo schema chung.
- Phải giữ nguyên file raw sau khi nhận; không sửa nội dung, không đổi field và không ghi đè file gốc.
- Sau bước đọc/parse/chuẩn hóa, phải tạo **một file normalized riêng** trong thư mục tương ứng dưới `20_normalized/`.
- File normalized phải dùng đúng schema được ghi trong README mini của thư mục đó và JSONL phải có một object hợp lệ trên mỗi dòng.
- Các bước chunking, embedding và index chỉ được đọc file normalized hoặc output của bước ngay trước; không đọc trực tiếp file raw.
- Mọi bản ghi normalized phải giữ liên kết về nguồn bằng `source_import_id`, `source_file`, `source_id` hoặc trường tương đương.
- Ví dụ đầy đủ từ raw đến index nằm trong [`examples/README.md`](examples/README.md).

## Metadata chung bắt buộc

Mỗi bản ghi JSON/JSONL cần có các trường sau nếu phù hợp:

```json
{
  "id": "stable-id",
  "source_type": "web_upload",
  "source_id": "IMP-ABC123",
  "dataset": "knowledge",
  "version": 1,
  "created_at": "2026-08-12T10:30:00Z",
  "updated_at": "2026-08-12T10:30:00Z",
  "active": true
}
```

## Hướng dẫn cho AI theo từng role

### Role ingestion hoặc upload web

```text
Bạn chỉ phụ trách `data/00_inbox` và `data/10_raw`.
Giữ nguyên file upload và tạo import manifest.
Dùng `import_id=IMP-...`, gồm filename, format, source, checksum và status.
Role này không được ghi embedding hoặc bảng nghiệp vụ của ứng dụng.
Nếu parse thất bại, đưa file vào `data/quarantine/failed_parses`.
Trước khi kết thúc, báo rõ path input và output.
```

### Role normalization

```text
Bạn chỉ phụ trách `data/20_normalized`.
Đọc từ `data/10_raw` và chuyển dữ liệu sang schema chuẩn.
Giữ `source_id/import_id` và tạo ID ổn định cho document, question, FAQ hoặc policy.
Không ghi đè file raw. Bản ghi không hợp lệ đưa vào `data/quarantine`.
Dùng JSONL UTF-8, mỗi dòng một JSON object.
Báo rõ schema, field, ID và mapping source-to-output.
```

### Role FAQ

```text
Bạn phụ trách `data/20_normalized/faq` và `data/30_chunks/faq`.
Tách câu hỏi member khỏi FAQ suggestion và FAQ đã publish.
Không coi suggestion chưa được duyệt là câu trả lời chính thức.
Liên kết `question_id -> suggestion_id -> faq_id -> chunk_id`.
Chỉ tạo embedding FAQ sau khi FAQ được approved/published.
```

### Role RAG hoặc chunking

```text
Bạn phụ trách `data/30_chunks`.
Đọc knowledge, policy hoặc FAQ đã publish từ `data/20_normalized`.
Tạo `chunk_id` ổn định và giữ `document_id/faq_id` làm liên kết nguồn.
Không sửa bản ghi normalized.
Lưu `chunk_index`, `text`, `dataset`, `source_type` và `source_id`.
```

### Role embedding hoặc vector index

```text
Bạn phụ trách `data/40_embeddings` và `data/50_indexes`.
Chỉ đọc chunks; không embedding trực tiếp raw upload.
Mỗi vector artifact phải có model, dimensions, text_hash, version và chunk_id.
Tách index FAQ, knowledge và policy.
Không trộn model hoặc số chiều khác nhau trong một index.
Nếu embedding thất bại, ghi lỗi vào `data/quarantine/failed_embeddings`.
```

### Role tích hợp tính năng hoặc consumer

```text
Bạn được đọc data contract nhưng không được tự tạo format mới.
Dùng ID ổn định để query `data/app.db` hoặc index đã được duyệt.
Không ghi trực tiếp vào thư mục của feature khác.
Nếu cần field mới, cập nhật README mini của owner và giải thích migration.
```

### Role QA hoặc audit

```text
Bạn chỉ phụ trách `data/90_exports` và `data/quarantine`.
Kiểm tra schema, ID trùng, liên kết hỏng, thiếu source và embedding metadata.
Không âm thầm sửa dữ liệu production.
Ghi validation report gồm timestamp, phạm vi, số lượng và lỗi.
```

## Tiêu chí hoàn thành thay đổi dữ liệu

- Đã chọn đúng thư mục.
- Đã đọc hoặc cập nhật README mini tương ứng.
- Không ghi đè dữ liệu raw.
- Có ID và liên kết đến source.
- Output parse được thành JSON/JSONL UTF-8 nếu phù hợp.
- Bản ghi lỗi xuất hiện trong `quarantine/`.
- AI đã báo file đọc, file ghi, schema và cách validation.
