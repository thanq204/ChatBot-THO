# Audit ba dataset RAG học tập

## Phạm vi

- `hoc_tap_rag_mon_hoc_20.csv`: 20/20 dòng parse được.
- `hoc_tap_rag_phuong_phap_20.csv`: 20/20 dòng parse được.
- `hoc_tap_rag_lich_hoc_20.csv`: 20/20 dòng parse được.
- Không có field rỗng hoặc dòng hỏng CSV trong ba file.

## Lỗi tái hiện từ Discord

Câu hỏi:

```text
tôi đang tham gia 1 dự án, muốn học bằng dự án thì phương pháp này như nào
```

Retrieval hiện tại trong backend xếp:

1. `Feynman Technique`: score chuẩn hóa `1.0` - sai ý định.
2. `Project-Based Learning`: score chuẩn hóa `0.8` - nguồn đúng.

Nguyên nhân là bộ chấm điểm cũ cộng các từ chung `phương pháp`, `học`, `bằng`, `đang` riêng lẻ và không ưu tiên đủ mạnh cụm đặc hiệu `học bằng dự án`. Reranker mới loại từ hội thoại chung và tăng trọng số cho chuỗi nội dung liên tiếp, nên test cùng câu hỏi chọn `Project-Based Learning`.

## Vấn đề dữ liệu

1. `id` từ `1` đến `20` lặp lại trong cả ba file. Importer hiện sinh ID theo import nên chưa ghi đè, nhưng raw ID không thể dùng độc lập để truy nguồn. Nên đổi thành `MON-001`, `PP-001`, `LICH-001` hoặc giữ cặp khóa `source_import_id + raw_id`.
2. Import semantic đã đổi title tiếng Việt sang tiếng Anh, ví dụ `Học bằng dự án` thành `Project-Based Learning`, làm giảm exact-title match tiếng Việt. Nên giữ `source_title="Học bằng dự án"`, dùng title chuẩn hóa riêng và thêm aliases song ngữ.
3. Cả 60 row đang vào dataset `general`. Nên map `mon_hoc`, `phuong_phap`, `lich_hoc/thoi_gian_hoc` thành dataset hoặc tags riêng để retrieval lọc đúng miền.
4. File lịch học trộn `loai_du_lieu=thoi_gian_hoc` và `lich_hoc`. Đây có thể là chủ ý, nhưng cần field cha thống nhất như `dataset=hoc_tap_lich_hoc` và dùng `loai_du_lieu` làm subtype.
5. Nhiều row chỉ có một câu mô tả. Ví dụ `Học bằng dự án` nói lợi ích nhưng chưa có quy trình. Với câu hỏi “làm như nào”, model chỉ được trả phần đã có hoặc từ chối; muốn trả chi tiết cần bổ sung `cac_buoc`, `vi_du`, `khi_nao_dung`, `han_che` và nguồn tham khảo.
6. CSV thiếu provenance hiển thị cho citation. Normalized record nên có `source_file`, `raw_id`, `source_title`, `version`, `updated_at` và `source_url` nếu có.

## Tiêu chí sửa

- Retrieval phải chọn đúng `Học bằng dự án` cho câu hỏi test trên.
- Rerank và relevance phải chạy trước LLM.
- Câu trả lời RAG phải có nhãn `RAG · Trích xuất` hoặc `RAG + LLM`.
- RAG thành công phải kèm title, `source_id` và đoạn trích nguyên văn.
- Không đủ nội dung cho câu hỏi “cách làm” thì không được bịa thêm bước.

## Regression test RAG thuần

Chạy trên `data/app.db` với `DISCORD_RAG_LLM_ENABLED=true`, nhưng nhánh knowledge bắt buộc không gọi LLM:

| # | Câu hỏi | Nguồn kỳ vọng | Nguồn thực tế | Score | Kết quả |
|---|---|---|---|---:|---|
| 1 | Muốn học bằng dự án thì làm như nào? | Project-Based Learning | Project-Based Learning | 0.871 | Pass |
| 2 | Áp dụng Pomodoro như thế nào? | Pomodoro Technique | Pomodoro Technique | 0.905 | Pass |
| 3 | Nên học Toán như thế nào? | Learning Mathematics | Learning Mathematics | 0.885 | Pass |
| 4 | Quy trình học RAG gồm bước nào? | Learning RAG | Learning RAG | 0.913 | Pass |
| 5 | Trước kỳ thi nên học thế nào? | Pre-Exam Study Focus | Pre-Exam Study Focus | 0.900 | Pass |

Kết quả: `5/5` đúng source, `model_used=rag-retrieval`, số lần gọi LLM bằng `0`.

Hai case Pomodoro và Learning RAG từng chọn sai do từ chung lấn át tên riêng. Reranker hiện thêm distinctive-title signal cho thuật ngữ xuất hiện trong query và title; relevance gate vẫn chạy sau rerank.
