# Worklog - Team P-232 (THO)

> Nhật ký được tổng hợp từ lịch sử commit/PR và các đầu việc phối hợp nội bộ trong giai đoạn 26/07/2026 - 01/09/2026. Thời gian là ước lượng công sức theo buổi làm việc, không phải số giờ được suy ra tự động từ Git.

## Thành viên và vai trò

| Thành viên | Vai trò chính | Phạm vi phụ trách |
|---|---|---|
| Nguyễn Chiến Thắng | QA / Integration | Kiểm thử, AI routing, moderation, CI/CD, deployment và tài liệu |
| Bùi Hữu Nghĩa | Model / Platform Bot | Chatbot, RAG, Discord/Telegram, moderation action và notification |
| Nguyễn Thái Tú | Web Developer | React dashboard, auth UX, API integration, accessibility và performance |
| Hà Nhật Khánh Duy | Data Analyst | Supabase schema, dữ liệu moderation, scope taxonomy và đánh giá dữ liệu |

---

## Tuần 1 - Khởi động và xác định bài toán

### 2026-07-26

| Member | Task | Status | Output | Time |
|---|---|---|---|---|
| Nguyễn Chiến Thắng | Chốt bài toán kiểm duyệt cộng đồng, tiêu chí demo và cách nghiệm thu | ✅ Done | Phạm vi MVP moderation + Admin review | 2h |
| Bùi Hữu Nghĩa | Khảo sát hướng dùng LLM cho phân loại nội dung và bot đa nền tảng | ✅ Done | Đề xuất pipeline model và platform adapter | 2h |
| Nguyễn Thái Tú | Phác thảo dashboard cho Admin/Mod và luồng xem incident | ✅ Done | Wireframe chức năng ban đầu | 2h |
| Hà Nhật Khánh Duy | Xác định nhóm dữ liệu cần lưu: message, risk, review và audit | ✅ Done | Danh sách entity và risk taxonomy ban đầu | 2h |

**Tổng kết ngày:** Nhóm thống nhất xây hệ thống hỗ trợ kiểm duyệt có human-in-the-loop thay vì để AI tự xử lý thành viên.

### 2026-08-01

| Member | Task | Status | Output | Time |
|---|---|---|---|---|
| Nguyễn Chiến Thắng | Xây moderation demo đầu tiên và tích hợp Phoenix AI logging | ✅ Done | Commit `3909bc2`, có demo end-to-end và log AI | 5h |
| Bùi Hữu Nghĩa | Review output model và đề xuất schema kết quả moderation | ✅ Done | Bộ trường category, risk, confidence, explanation | 2h |
| Nguyễn Thái Tú | Kiểm tra luồng dữ liệu cần hiển thị trên review queue | ✅ Done | Danh sách trạng thái UI và action cần có | 2h |
| Hà Nhật Khánh Duy | Chuẩn hóa ví dụ nội dung an toàn/rủi ro để thử pipeline | ✅ Done | Tập case ban đầu cho smoke test | 2h |

**Tổng kết ngày:** MVP đầu tiên chạy được và nhóm có cơ chế lưu bằng chứng AI để phục vụ đánh giá sau này.

---

## Tuần 2 - Chuyển trọng tâm sang Discord và tách kiến trúc

### 2026-08-03 - 2026-08-04

| Member | Task | Status | Output | Time |
|---|---|---|---|---|
| Nguyễn Chiến Thắng | Thử community radar và tinh chỉnh moderation flow | ✅ Done | Commit `7ebf8ba`, xác định giới hạn của hướng cũ | 4h |
| Bùi Hữu Nghĩa | Thử nghiệm model và luồng xử lý message cho chatbot | ✅ Done | Prototype model/platform ban đầu | 3h |
| Nguyễn Thái Tú | Tạo demo dashboard moderation đa kênh | ✅ Done | Commit `d955406`, giao diện ModGuard ban đầu | 5h |
| Hà Nhật Khánh Duy | Xây Admin Review Queue, Audit Log và risk ranking simulator | ✅ Done | Commits `2c60b9f`, `d702c4b` | 6h |

**Tổng kết giai đoạn:** Nhóm nhận thấy bài toán Discord/Telegram thực tế và review queue có giá trị hơn hướng community radar cũ, từ đó chuyển trọng tâm sản phẩm.

### 2026-08-06 - 2026-08-08

| Member | Task | Status | Output | Time |
|---|---|---|---|---|
| Nguyễn Chiến Thắng | Chuyển chatbot sang Discord và kiểm tra luồng mention/reply | ✅ Done | Commit `9f13680`, Discord chatbot hoạt động | 5h |
| Bùi Hữu Nghĩa | Rà soát contract message chung để chuẩn bị đa nền tảng | ✅ Done | Định dạng message dùng chung cho Discord/Telegram | 3h |
| Nguyễn Thái Tú | Tái cấu trúc repo thành backend/frontend và thống nhất cách làm việc | ✅ Done | Commits `d7e58e4`, `8d688da` | 6h |
| Hà Nhật Khánh Duy | Điều chỉnh data plan theo message, channel, member và incident | ✅ Done | Data mapping phù hợp Discord | 3h |

**Tổng kết giai đoạn:** Repo được tách lớp rõ hơn; Discord trở thành kênh thử nghiệm chính và dữ liệu bắt đầu theo một contract dùng chung.

---

## Tuần 3 - Hoàn thiện MVP đa nền tảng và Gate 2

### 2026-08-10 - 2026-08-11

| Member | Task | Status | Output | Time |
|---|---|---|---|---|
| Nguyễn Chiến Thắng | Cấu hình CI và kiểm tra luồng tích hợp các branch | ✅ Done | Commits `7f11993`, `13155b2` | 4h |
| Bùi Hữu Nghĩa | Xây workflow chatbot đa nền tảng và sửa AI log hook | ✅ Done | Commits `6eeac7c`, `f9f7729` | 7h |
| Nguyễn Thái Tú | Nối các trang quản trị còn lại với backend API | ✅ Done | Commit `352ce31` | 6h |
| Hà Nhật Khánh Duy | Hoàn thiện kế hoạch dữ liệu và phân chia đầu việc | ✅ Done | Commit `933b974` | 3h |

**Tổng kết giai đoạn:** Backend, frontend, model và data đã có đầu mối rõ; nhóm bắt đầu tích hợp thành một sản phẩm thay vì các demo rời rạc.

### 2026-08-12

| Member | Task | Status | Output | Time |
|---|---|---|---|---|
| Nguyễn Chiến Thắng | Bổ sung data schemas và examples để các luồng dùng cùng format | ✅ Done | Commit `470bde2`, thư mục data contracts | 4h |
| Bùi Hữu Nghĩa | Thêm rule commands, gated RAG, manual action và warning DM | ✅ Done | Commits `9aff25e`, `b02c4d9`, `e077731` | 8h |
| Nguyễn Thái Tú | Xây landing/login, trang thông báo và API broadcast đa nền tảng | ✅ Done | Commits `726ee5c`, `76307d0`, `825e6fa` | 8h |
| Hà Nhật Khánh Duy | Review schema và bổ sung sample cho message, incident, knowledge | ✅ Done | Checklist chất lượng dữ liệu đầu vào | 3h |

**Tổng kết ngày:** Các luồng Rule, RAG, moderation action, notification và giao diện đăng nhập đã kết nối được với nhau.

### 2026-08-13 - 2026-08-14

| Member | Task | Status | Output | Time |
|---|---|---|---|---|
| Nguyễn Chiến Thắng | Thêm AI routing có gate, cải thiện alert và chặn warning sai | ✅ Done | Commits `07a7c71`, `4dc2552`, `9ee6ea5` | 8h |
| Bùi Hữu Nghĩa | Kiểm thử tích hợp chatbot và moderation action với schema mới | ✅ Done | Danh sách lỗi integration và bản sửa phối hợp | 4h |
| Nguyễn Thái Tú | Sửa UI và thêm biểu đồ tổng quan | ✅ Done | Commits `6b31b8e`, `c675b31` | 7h |
| Hà Nhật Khánh Duy | Chuyển database sang PostgreSQL Cloud và loại phụ thuộc SQLite runtime | ✅ Done | Commits `5dac408`, `d452e86` | 8h |

**Tổng kết giai đoạn:** Hệ thống có Gate 2 rõ ràng và bắt đầu sử dụng PostgreSQL Cloud làm nguồn dữ liệu runtime.

### 2026-08-15 - 2026-08-16

| Member | Task | Status | Output | Time |
|---|---|---|---|---|
| Nguyễn Chiến Thắng | Hoàn thiện Supabase knowledge fallback, test command và tài liệu demo | ✅ Done | Commits `6dda7a2`, `d3a1f11`, `1ed883e` | 7h |
| Bùi Hữu Nghĩa | Test chéo command, RAG và platform action sau khi nối dashboard | ✅ Done | Kết quả smoke test Discord/Telegram | 3h |
| Nguyễn Thái Tú | Xây community tools, bot commands, audit log, Mod page, link nguồn và bộ lọc case | ✅ Done | Commits `8532907` đến `f3a0090` | 12h |
| Hà Nhật Khánh Duy | Đối chiếu dữ liệu incident/audit với PostgreSQL và kiểm tra sample | ✅ Done | Data validation cho review queue | 4h |

**Tổng kết giai đoạn:** MVP Gate 2 có dashboard quản trị, dữ liệu cloud, chatbot/RAG và bằng chứng demo end-to-end.

---

## Tuần 4 - Auth, hiệu năng, scope và Supabase semantics

### 2026-08-17 - 2026-08-19

| Member | Task | Status | Output | Time |
|---|---|---|---|---|
| Nguyễn Chiến Thắng | Đồng bộ runtime flow và tài liệu Supabase, review các PR tích hợp | ✅ Done | Commit `6f4db7d` và các merge PR | 5h |
| Bùi Hữu Nghĩa | Thêm Google sign-in, role management và giới hạn signup theo invite | ✅ Done | Commits `2cee9a9`, `bc0e9fc` | 8h |
| Nguyễn Thái Tú | Sắp xếp lại Knowledge Hub và đồng bộ màu giao diện Sakura | ✅ Done | Commits `dce5e44`, `6d3c8b7` | 6h |
| Hà Nhật Khánh Duy | Rà soát quan hệ app user với member nền tảng và dữ liệu knowledge | ✅ Done | Ghi chú phân tách identity/runtime member | 3h |

**Tổng kết giai đoạn:** Dashboard có auth/role rõ hơn và tài liệu data flow bắt đầu phản ánh đúng Supabase runtime.

### 2026-08-20 - 2026-08-21

| Member | Task | Status | Output | Time |
|---|---|---|---|---|
| Nguyễn Chiến Thắng | Harden AI routing, Supabase semantics, spam classification và bảng xếp hạng | ✅ Done | Commits `89c4615`, `3470bb1` | 8h |
| Bùi Hữu Nghĩa | Giữ flagged message, gửi private alert và hiển thị đúng tác giả case | ✅ Done | Commits `c85a686`, `70cbd8c` | 6h |
| Nguyễn Thái Tú | Thêm DB pool, tránh block event loop, cache dashboard và route splitting | ✅ Done | Commits `6cab919`, `2e85a00`, `6a1f393` | 10h |
| Hà Nhật Khánh Duy | Kiểm tra dữ liệu spam/reputation và cập nhật tập dữ liệu | ✅ Done | Commit `9df64b5` | 4h |

**Tổng kết giai đoạn:** Hệ thống ổn định và nhanh hơn, đồng thời giảm sai lệch giữa dữ liệu hiển thị với dữ liệu nền tảng.

### 2026-08-23

| Member | Task | Status | Output | Time |
|---|---|---|---|---|
| Nguyễn Chiến Thắng | Regression test AI routing và hợp nhất các sửa lỗi scope/sync | ✅ Done | QA checklist cho chatbot và dashboard | 4h |
| Bùi Hữu Nghĩa | Thêm chatbot scope guardrail và member upsert idempotent | ✅ Done | Commits `c2f4108`, `76e78b7` | 6h |
| Nguyễn Thái Tú | Sửa Discord scan cursor và tổ chức lại Knowledge Base UI | ✅ Done | Commits `66bbf0c`, `b4ecc9a` | 6h |
| Hà Nhật Khánh Duy | Xây deterministic scope filter cho câu hỏi ngoài phạm vi | ✅ Done | Commit `e6cc984` | 5h |

**Tổng kết ngày:** Chatbot từ chối ổn định các chủ đề ngoài phạm vi và đồng bộ nền tảng không còn tạo member/message trùng.

---

## Tuần 5 - Railway, EXP/trade, đa ngôn ngữ và hoàn thiện UX

### 2026-08-24

| Member | Task | Status | Output | Time |
|---|---|---|---|---|
| Nguyễn Chiến Thắng | Sửa Docker/Railway, thêm migration runtime, EXP và verified trade flow | ✅ Done | Commits `3135049`, `1e76565`, `d640c7a`, `4ae6c6e` | 10h |
| Bùi Hữu Nghĩa | Tăng cường Telegram moderation, notification và yêu cầu nguồn cho topic chưa biết | ✅ Done | Commits `4c641f4`, `95e71ca` | 8h |
| Nguyễn Thái Tú | Hoàn thiện signup/invite, self profile, sidebar và sửa pool leak/guild scope | ✅ Done | Commits `7844070`, `39a9e8a`, `982699d`, `c9f0c1f`, `153a32f` | 11h |
| Hà Nhật Khánh Duy | Kiểm tra schema EXP/trade, ràng buộc buyer/seller và dữ liệu review | ✅ Done | Checklist integrity cho giao dịch xác thực | 4h |

**Tổng kết ngày:** Bản mới deploy được lên Railway và sản phẩm tách EXP hoạt động khỏi đánh giá người bán có xác nhận hai phía.

### 2026-08-25 - 2026-08-26

| Member | Task | Status | Output | Time |
|---|---|---|---|---|
| Nguyễn Chiến Thắng | Bỏ message tự động khỏi analytics, localize AI flow và nâng moderation đa ngôn ngữ | ✅ Done | Commits `9ba3f81`, `b0eb8a7`, `d8acf97` | 9h |
| Bùi Hữu Nghĩa | Bổ sung workspace setup và kiểm tra parity Discord/Telegram | ✅ Done | Commit `92125a7` và integration review | 6h |
| Nguyễn Thái Tú | Thêm demo quick-fill, pagination, toast, accessibility, mascot và focus handling | ✅ Done | Chuỗi commits UI `71bbc28` đến `87ee104` | 14h |
| Hà Nhật Khánh Duy | Chuẩn bị câu đa ngôn ngữ và câu nhiễu để test giải thích moderation | ✅ Done | Bộ input kiểm thử Nhật/Anh/Việt và slang | 4h |

**Tổng kết giai đoạn:** Dashboard dễ demo hơn, đạt accessibility tốt hơn và moderation giải thích tiếng Việt cho input đa ngôn ngữ.

### 2026-08-27 - 2026-08-29

| Member | Task | Status | Output | Time |
|---|---|---|---|---|
| Nguyễn Chiến Thắng | Thêm persona THO, regression test và hợp nhất các nhánh QA/Develop | ✅ Done | Commits `3f818e0`, `acaf21f`, PR #78-#90 | 8h |
| Bùi Hữu Nghĩa | Hoàn thiện Discord/Telegram integration và member join/leave updates | ✅ Done | Commits `adeb590`, `d3b61d9` | 9h |
| Nguyễn Thái Tú | Nâng landing page, AI Sandbox, dashboard và Command Center | ✅ Done | Commits `4d29484`, `8752bf8`, `5531346`, `8159408` | 14h |
| Hà Nhật Khánh Duy | Kiểm tra scope v1 trên dữ liệu và phản hồi các trường hợp lọt/chặn nhầm | ✅ Done | Commit `6ee74d7`, scope validation report | 5h |

**Tổng kết giai đoạn:** Sản phẩm được thống nhất thương hiệu THO, UI sẵn sàng demo và hai bot có chức năng gần tương đương hơn.

---

## Tuần 6 - Audit cuối, kiến trúc và chất lượng release

### 2026-09-01

| Member | Task | Status | Output | Time |
|---|---|---|---|---|
| Nguyễn Chiến Thắng | Audit toàn hệ thống, harden auth/database/CI và viết lại kiến trúc mới nhất | ✅ Done | Commit `6dea099`; Ruff pass, 208 tests pass, Vite build pass | 10h |
| Bùi Hữu Nghĩa | Smoke test lại Discord/Telegram listener, command và alert theo kiến trúc mới | ✅ Done | Checklist platform regression | 3h |
| Nguyễn Thái Tú | Kiểm tra route/role gate, production build và tính nhất quán UI THO | ✅ Done | Frontend release review | 3h |
| Hà Nhật Khánh Duy | Đối chiếu bảng Supabase, knowledge import và mô tả data flow | ✅ Done | Data/architecture consistency review | 3h |

**Tổng kết ngày:** Tài liệu, metadata runtime, CI và code cùng phản ánh kiến trúc THO hiện tại; nhánh QA ở trạng thái có thể trình bày và tiếp tục triển khai.

---

## Tổng hợp đóng góp

| Thành viên | Đóng góp nổi bật | Bằng chứng tiêu biểu |
|---|---|---|
| Nguyễn Chiến Thắng | QA, AI gate, moderation, Supabase semantics, EXP/trade, Railway, CI và architecture | `3909bc2`, `07a7c71`, `89c4615`, `4ae6c6e`, `d8acf97`, `6dea099` |
| Bùi Hữu Nghĩa | Multi-platform chatbot, gated RAG, manual action, auth và Telegram/Discord integration | `6eeac7c`, `9aff25e`, `b02c4d9`, `2cee9a9`, `4c641f4`, `d3b61d9` |
| Nguyễn Thái Tú | Dashboard/API integration, admin tools, auth UX, performance, accessibility và Command Center | `352ce31`, `8532907`, `6cab919`, `7844070`, `8088303`, `8159408` |
| Hà Nhật Khánh Duy | Review queue, risk simulator, PostgreSQL Cloud, data updates và scope filter | `2c60b9f`, `d702c4b`, `5dac408`, `d452e86`, `9df64b5`, `e6cc984` |
