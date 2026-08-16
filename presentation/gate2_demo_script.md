# Kịch bản video Gate 2 - tối đa 3 phút

Kịch bản này giúp quay video đúng tiêu chí. Chỉ đánh dấu deliverable hoàn thành sau khi có bản ghi thực tế và link xem được.

**Video đã hoàn thành:** [Xem bản demo Gate 2 trên YouTube](https://youtu.be/1EdQj81X47M)

## 0:00-0:20 - Vấn đề và user flow

Lời nói gợi ý:

> CHAT-10 giúp cộng đồng học tập giảm tải moderation và trả lời câu hỏi lặp lại trên Discord. User flow chính là thành viên tag bot, hệ thống phân luồng và trả câu trả lời bằng LLM hoặc RAG có nguồn.

Hiển thị Discord và trang Admin dashboard.

## 0:20-0:50 - Rule và FAQ

1. Gửi `@CHAT-10 /help`.
2. Gửi `@CHAT-10 làm sao để báo cáo spam?`.
3. Chỉ ra rằng FAQ trả câu Admin đã duyệt, không gọi LLM.

## 0:50-1:30 - LLM thật

1. Gửi `@CHAT-10 bạn tên là gì`.
2. Gửi `@CHAT-10 hôm nay ngày bao nhiêu`.
3. Chỉ vào nhãn `[LLM]` và nói model đang dùng là `gpt-4o-mini`, không phải mock.

## 1:30-2:10 - RAG, reranking và relevance

1. Gửi `@CHAT-10 tôi đang tham gia một dự án, muốn học bằng dự án thì phương pháp này như nào?`.
2. Chỉ vào nhãn `[RAG]`.
3. Chỉ vào dòng `Trích từ tài liệu: Project-Based Learning (...)`.
4. Giải thích: retrieval lấy candidate, reranker sắp xếp, relevance gate chặn nguồn yếu; runtime trả nội dung canonical để không viết lan man.

## 2:10-2:40 - Moderation và Admin

1. Gửi một demo message có tín hiệu spam hoặc công kích.
2. Mở incident/review trên Admin dashboard.
3. Hiển thị evidence, risk score và audit trail.
4. Không bấm ban/kick thật nếu chưa có môi trường test riêng.

## 2:40-3:00 - Bằng chứng

1. Hiển thị `eval/results/report.md` sau khi đã thêm đủ 5 ảnh test Discord thực tế.
2. Hiển thị architecture diagram.
3. Kết luận: user flow chạy end-to-end với OpenAI thật, FAQ/RAG tiết kiệm chi phí và relevance gate giảm trả lời sai nguồn.

## Checklist trước khi nộp

- [x] Video dài không quá 3 phút.
- [x] Có ít nhất một lời gọi LLM thật và nhìn thấy output.
- [x] Có một user flow end-to-end từ input tới output có ý nghĩa.
- [x] Không lộ `.env`, API key, bot token hoặc dữ liệu cá nhân.
- [x] Link YouTube mở được với chế độ không công khai.
- [x] Đã gắn link video vào `README.md` và `GATE2_SUBMISSION.md`.
