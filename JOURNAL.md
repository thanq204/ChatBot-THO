# Weekly Journal - Team P-232 (THO)

> Nhật ký phản ánh tiến trình phát triển thực tế từ cuối tháng 7 đến đầu tháng 9/2026. Chi tiết đầu việc và commit được đối chiếu tại [WORKLOG.md](WORKLOG.md).

---

## Week 1: 27/07/2026 - 02/08/2026

### Mục tiêu tuần này

- [x] Chọn bài toán có thể demo end-to-end trong thời gian chương trình.
- [x] Xây prototype moderation đầu tiên.
- [x] Thiết lập AI logging để có bằng chứng quá trình sử dụng model.

### Đã hoàn thành

- Nhóm chọn bài toán hỗ trợ Admin/Mod phát hiện nội dung rủi ro và review trước khi hành động.
- Hoàn thành moderation demo đầu tiên, có category, risk, confidence và explanation.
- Kết nối Phoenix AI logging để lưu prompt/output phục vụ deliverable.
- Phác thảo dashboard review queue, dữ liệu incident/audit và hướng platform bot.

### Đóng góp trong tuần

| Thành viên | Đóng góp |
|---|---|
| Nguyễn Chiến Thắng | Chốt phạm vi QA, dựng moderation demo và AI logging |
| Bùi Hữu Nghĩa | Khảo sát model moderation và schema output |
| Nguyễn Thái Tú | Phác thảo luồng dashboard Admin/Mod |
| Hà Nhật Khánh Duy | Xác định entity dữ liệu và risk taxonomy ban đầu |

### Khó khăn & Giải pháp

| Khó khăn | Giải pháp | Kết quả |
|---|---|---|
| Phạm vi ban đầu còn rộng và thiên về demo model | Chọn một vòng lặp rõ: message -> AI analysis -> Admin review -> audit | Có MVP nhỏ nhưng đo và trình bày được |
| Chưa có dữ liệu thật đủ lớn | Tạo case mẫu an toàn/rủi ro và lưu log mọi lần chạy | Có tập test khởi đầu và trace để so sánh |

### Quyết định kỹ thuật

- AI chỉ đưa phân tích và đề xuất; quyết định ảnh hưởng người dùng phải do Admin/Mod xác nhận.
- Mọi model call quan trọng cần có log để phục vụ evaluation và debug.

### Bài học

- Chọn workflow end-to-end nhỏ hữu ích hơn việc làm nhiều màn hình nhưng không kết nối.
- Moderation phải lưu cả lý do và ngữ cảnh, không chỉ một nhãn toxic/safe.

### Kế hoạch tuần sau

- [x] Kiểm tra hướng triển khai trên Discord/Telegram.
- [x] Tách backend/frontend và dựng review dashboard.
- [x] Chuẩn hóa message/risk data contract.

---

## Week 2: 03/08/2026 - 09/08/2026

### Mục tiêu tuần này

- [x] Đánh giá lại hướng community radar cũ.
- [x] Chuyển trọng tâm sang Discord chatbot và moderation dashboard.
- [x] Tái cấu trúc repo để các thành viên làm song song.

### Đã hoàn thành

- Xây Admin Review Queue, Audit Log và risk ranking simulator.
- Có frontend demo moderation đa kênh Discord/Telegram.
- Chuyển chatbot sang Discord và thử luồng mention/reply.
- Tách `backend/` và `frontend/`, thống nhất data contract chung cho platform message.

### Đóng góp trong tuần

| Thành viên | Đóng góp |
|---|---|
| Nguyễn Chiến Thắng | Thử community radar, chuyển chatbot sang Discord và kiểm tra luồng chính |
| Bùi Hữu Nghĩa | Thử model/platform flow và thiết kế CommonMessage |
| Nguyễn Thái Tú | Xây ModGuard frontend, tái cấu trúc backend/frontend |
| Hà Nhật Khánh Duy | Xây review queue, audit log, risk simulator và cập nhật data mapping |

### Khó khăn & Giải pháp

| Khó khăn | Giải pháp | Kết quả |
|---|---|---|
| Hướng YouTube/community radar khó demo phản hồi realtime và hành động quản trị | Chuyển sang Discord/Telegram, nơi có message, member và action rõ ràng | Sản phẩm sát bài toán cộng đồng hơn |
| Frontend và backend thay đổi lẫn nhau gây khó merge | Tách thư mục, thống nhất model dữ liệu và phạm vi module | Có thể phát triển song song theo vai trò |

### Quyết định kỹ thuật

- Discord là kênh thử nghiệm chính; Telegram được thiết kế theo cùng contract để mở rộng.
- Review queue và audit trail là lõi sản phẩm, không phải phần phụ của model demo.

### Bài học

- Pivot sớm giúp tránh đầu tư tiếp vào luồng khó chứng minh giá trị.
- Contract message chung giảm đáng kể code trùng giữa các nền tảng.

### Kế hoạch tuần sau

- [x] Nối dashboard với backend API.
- [x] Thêm Rule, FAQ/RAG và manual moderation action.
- [x] Chuyển dữ liệu runtime sang PostgreSQL Cloud.

---

## Week 3: 10/08/2026 - 16/08/2026

### Mục tiêu tuần này

- [x] Hoàn thiện MVP đa nền tảng có Rule, RAG và moderation action.
- [x] Kết nối các trang Admin với API thật.
- [x] Đạt các deliverable Gate 2: demo, architecture/data docs và evaluation evidence.

### Đã hoàn thành

- Thêm chatbot workflows đa nền tảng, command routing, gated RAG và warning DM.
- Thêm manual delete/timeout/kick/ban với xác nhận của Admin/Mod.
- Hoàn thành landing/login, notification, community tools, bot command management, moderation log và Mod management.
- Thêm AI routing có gate, cảnh báo có ngưỡng và chặn gửi warning sai.
- Chuyển runtime database từ SQLite sang PostgreSQL Cloud/Supabase.
- Hoàn thiện knowledge fallback, Discord all-channel scan, link về message nguồn và video Gate 2.

### Đóng góp trong tuần

| Thành viên | Đóng góp |
|---|---|
| Nguyễn Chiến Thắng | CI, data contracts, gated AI routing, alert QA, Supabase fallback và demo evidence |
| Bùi Hữu Nghĩa | Multi-platform workflow, Rule/RAG, manual action và warning DM |
| Nguyễn Thái Tú | API integration, landing/login, notification và toàn bộ nhóm trang Admin tools |
| Hà Nhật Khánh Duy | Data plan, PostgreSQL Cloud migration và kiểm tra integrity dữ liệu |

### Khó khăn & Giải pháp

| Khó khăn | Giải pháp | Kết quả |
|---|---|---|
| Bot cảnh báo theo từ khóa dễ sai khi thiếu ngữ cảnh | Tách fast filter, context review và confidence gate | Giảm warning sai, giữ case để Admin xem |
| SQLite local khác dữ liệu cloud và làm demo không nhất quán | Chuyển Supabase PostgreSQL thành source of truth | Dashboard và bot dùng cùng dữ liệu |
| Nhiều trang UI vẫn dùng mock data | Nối từng trang vào API và bổ sung audit/source link | Demo phản ánh dữ liệu thật end-to-end |

### Quyết định kỹ thuật

- Chatbot đi theo thứ tự `Rule -> Moderation -> FAQ -> RAG/LLM`.
- Runtime dùng Supabase PostgreSQL; SQLite chỉ dành cho unit test cô lập.
- Bot không tự thực hiện moderation action từ kết quả model.

### Bài học

- Một threshold không đủ cho moderation; cần kết hợp rule nhanh, context và review memory.
- Source link và audit log giúp Admin kiểm chứng AI thay vì tin vào một con số confidence.

### Kế hoạch tuần sau

- [x] Hoàn thiện authentication và role management.
- [x] Tối ưu database/frontend performance.
- [x] Bổ sung scope guardrail và Supabase semantics.

---

## Week 4: 17/08/2026 - 23/08/2026

### Mục tiêu tuần này

- [x] Bảo vệ dashboard bằng auth và phân quyền Admin/Mod.
- [x] Giảm độ trễ dashboard và lỗi connection database.
- [x] Ngăn chatbot trả lời nội dung ngoài phạm vi.
- [x] Đồng bộ tài liệu và dữ liệu với runtime Supabase.

### Đã hoàn thành

- Thêm Google sign-in, role management và invite restriction cho Mod.
- Đồng bộ runtime flow, Supabase data docs và knowledge semantics.
- Thêm PostgreSQL connection pool, tránh blocking I/O, React Query cache và route splitting.
- Sửa case author, flagged message retention và private alert.
- Thêm deterministic scope filter, chatbot guardrail và member upsert idempotent.
- Cải thiện Knowledge Hub, platform scan cursor và giao diện Sakura.

### Đóng góp trong tuần

| Thành viên | Đóng góp |
|---|---|
| Nguyễn Chiến Thắng | Supabase/data flow docs, harden AI routing, spam classification và integration QA |
| Bùi Hữu Nghĩa | Google auth/roles, invite restriction, alert retention và chatbot guardrail |
| Nguyễn Thái Tú | Knowledge UI, DB pooling, frontend cache, lazy routes và sync cursor |
| Hà Nhật Khánh Duy | Data validation, cập nhật dataset và deterministic scope filter |

### Khó khăn & Giải pháp

| Khó khăn | Giải pháp | Kết quả |
|---|---|---|
| Mỗi request mở kết nối PostgreSQL mới và có thể chạm giới hạn Supabase | Dùng connection pool và chuyển blocking call khỏi event loop | Dashboard ổn định và phản hồi nhanh hơn |
| Chatbot có thể trả lời game, crypto hoặc nội dung ngoài cộng đồng | Thêm scope taxonomy deterministic trước LLM/RAG | Từ chối nhất quán, giảm tốn token |
| Member sync lặp tạo dữ liệu trùng | Upsert idempotent và lưu sync cursor | Có thể pull lại mà không nhân bản member/message |

### Quyết định kỹ thuật

- Scope filter deterministic chạy trước nhánh LLM để guardrail không phụ thuộc model.
- Auth user của dashboard và member Discord/Telegram là hai loại identity khác nhau.
- Cache frontend chỉ tối ưu đọc; Supabase vẫn là nguồn dữ liệu chuẩn.

### Bài học

- Lỗi hiệu năng thường nằm ở connection lifecycle và blocking I/O, không chỉ ở model.
- Guardrail quan trọng nên có lớp deterministic bên cạnh prompt của LLM.

### Kế hoạch tuần sau

- [x] Deploy ổn định lên Railway.
- [x] Thay uy tín tin nhắn bằng EXP và verified trade flow.
- [x] Hoàn thiện UX, accessibility và moderation đa ngôn ngữ.

---

## Week 5: 24/08/2026 - 30/08/2026

### Mục tiêu tuần này

- [x] Đưa hệ thống chạy ổn định trên Railway.
- [x] Tách bảng EXP khỏi đánh giá độ tin cậy người bán.
- [x] Hoàn thiện parity Discord/Telegram và luồng trade.
- [x] Nâng chất lượng UI, accessibility và AI Sandbox đa ngôn ngữ.

### Đã hoàn thành

- Sửa Docker để dùng đúng `PORT`, chạy non-root và copy Supabase migrations vào image.
- Thêm EXP từ đóng góp tích cực và verified trade flow: open, confirm, review, seller check.
- Thêm Telegram moderation/notification, workspace setup và member join/leave updates.
- Hoàn thiện signup/invite, self profile, guild scoping, duplicate message handling và pool cleanup.
- Loại bot/webhook message khỏi community analytics và EXP.
- Thêm multilingual moderation explanation, chuẩn hóa output về tiếng Việt và persona THO.
- Nâng dashboard với pagination, toast, WCAG AA, focus trap, mascot, landing interactive và AI Command Center.

### Đóng góp trong tuần

| Thành viên | Đóng góp |
|---|---|
| Nguyễn Chiến Thắng | Railway/Docker, EXP/trade, bot-message filter, AI hardening, đa ngôn ngữ và persona THO |
| Bùi Hữu Nghĩa | Telegram moderation, platform parity, workspace setup và member update events |
| Nguyễn Thái Tú | Auth UX, pool/guild fixes, pagination, accessibility, landing page và Command Center |
| Hà Nhật Khánh Duy | Review schema EXP/trade, test data đa ngôn ngữ và kiểm tra scope v1 |

### Khó khăn & Giải pháp

| Khó khăn | Giải pháp | Kết quả |
|---|---|---|
| Railway báo permission denied và thiếu migration/runtime port | Đặt virtualenv ngoài `/root`, chạy `appuser`, copy migrations và dùng `${PORT}` | Container khởi động và health check thành công |
| Điểm uy tín theo tin nhắn không đủ giá trị cho giao dịch tiền bạc | Đổi thành EXP; tạo trade có xác nhận hai phía và review gắn `trade_id` | Tách rõ hoạt động cộng đồng và lịch sử người bán |
| Bot tự tạo tin nhắn rồi bị tính vào moderation/analytics | Lọc bot, webhook, application và system ở adapter/pipeline/store | Chỉ dữ liệu người thật ảnh hưởng thống kê |
| LLM hiểu tiếng Nhật nhưng explanation trả tiếng Anh hoặc lặp lại câu gốc | Dùng structured multilingual review và lớp chuẩn hóa tiếng Việt | AI Sandbox giải thích nguyên nhân xung đột rõ hơn |
| Danh sách dài, dialog và màu phụ gây khó sử dụng | Pagination dùng chung, focus trap, toast và WCAG contrast | Dashboard dễ demo và dễ thao tác hơn |

### Quyết định kỹ thuật

- EXP không được dùng để suy luận người bán đáng tin.
- Seller summary chỉ tóm tắt giao dịch đã xác nhận; AI không được chứng nhận “an toàn” hoặc kết luận “lừa đảo”.
- Production đóng gói React SPA và FastAPI trong một Docker image.
- Persona cute chỉ áp dụng hội thoại thường; moderation, từ chối và cảnh báo phải rõ ràng, tôn trọng.

### Bài học

- Với tính năng liên quan tiền bạc, cần provenance, cỡ mẫu và human review thay vì một điểm số tổng quát.
- Platform bot phải lọc automated message ở nhiều lớp để tránh dữ liệu bẩn quay lại từ API sync.
- Accessibility và trạng thái phản hồi là một phần của độ tin cậy sản phẩm, không chỉ là trang trí UI.

### Kế hoạch tuần sau

- [x] Audit tất cả route và flow theo code hiện tại.
- [x] Đồng bộ architecture, README, CI và metadata THO.
- [x] Chạy full regression test trước khi nộp.

---

## Week 6: 31/08/2026 - 01/09/2026

### Mục tiêu tuần này

- [x] Đối chiếu tài liệu kiến trúc với runtime mới nhất.
- [x] Harden auth/database và hoàn thiện CI cho backend, frontend, Docker.
- [x] Chạy regression test toàn hệ thống và chốt giới hạn hiện tại.

### Đã hoàn thành

- Viết lại `ARCHITECTURE.md`, `README.md` và các sơ đồ Rule/Moderation/FAQ/RAG, auth, data, trade, EXP và deployment.
- Đồng bộ branding runtime thành THO, xóa mô tả starter Next.js/ChromaDB cũ.
- Cập nhật CI chạy Ruff, pytest, frontend build và Docker build trên `main`, `Develop`, `QA`.
- Harden auth/database lifecycle và kiểm tra không có secret thật trong diff.
- Kết quả cuối: Ruff pass, `208` tests pass, Vite production build pass.
- Ghi rõ giới hạn: đăng ký hiện chỉ tạo Admin trong community đang cấu hình, chưa provision tenant/community mới.

### Đóng góp trong tuần

| Thành viên | Đóng góp |
|---|---|
| Nguyễn Chiến Thắng | Audit code, hardening, CI, architecture, test và release QA |
| Bùi Hữu Nghĩa | Smoke test Discord/Telegram listener, command và alert |
| Nguyễn Thái Tú | Review route/role gate, frontend production build và UI consistency |
| Hà Nhật Khánh Duy | Đối chiếu Supabase tables, import pipeline và data flow documentation |

### Khó khăn & Giải pháp

| Khó khăn | Giải pháp | Kết quả |
|---|---|---|
| Tài liệu còn template Next.js/ChromaDB và mô tả luồng cũ | Đọc trực tiếp entrypoint, routes, services, migrations và Dockerfile rồi viết lại | Architecture khớp code nhánh QA |
| CI trước đó chỉ kiểm tra một phần hoặc phụ thuộc runner riêng | Tách backend/frontend/docker jobs trên GitHub-hosted runner | Có pipeline tái lập cho cả ba lớp |
| Multi-community chưa thật sự hoàn thiện dù schema có `community_id` | Ghi rõ giới hạn và hướng cần làm: tenant provisioning, connector config, data isolation | Không tạo kỳ vọng sai khi demo/đăng ký |

### Quyết định kỹ thuật

- Giữ deployment một replica trong giai đoạn MVP; rate limiter in-memory và listener cùng process phù hợp phạm vi hiện tại.
- Chưa tuyên bố multi-tenant cho đến khi auth, connector và query đều scope theo community end-to-end.
- Tài liệu kiến trúc chính thức phải được cập nhật cùng code ở mỗi release quan trọng.

### Bài học

- “Có cột `community_id`” chưa đồng nghĩa hệ thống đã multi-tenant.
- Full regression cần kiểm tra backend, frontend build và container, không chỉ unit test.
- Tài liệu tốt phải nêu cả giới hạn và trade-off, không chỉ luồng thành công.

### Kế hoạch tiếp theo

- [ ] Thiết kế tenant/community provisioning và data isolation end-to-end.
- [ ] Tách listener thành worker/queue khi cần scale nhiều replica.
- [ ] Bổ sung Redis/distributed rate limit và monitoring production.
- [ ] Mở rộng evaluation bằng dữ liệu tiếng Việt đa dạng và phản hồi người dùng thật.
