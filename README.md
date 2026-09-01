# THO - Triage, Help, Oversight

![THO logo](frontend/public/tho-logo.jpg)

THO là trợ lý AI hỗ trợ Admin/Moderator quản lý cộng đồng học tập trên Discord và Telegram. Hệ thống theo dõi tin nhắn người thật, phát hiện rủi ro theo ngữ cảnh, trả lời FAQ/RAG có kiểm soát và giữ quyền quyết định cuối cùng cho con người.

## Bài toán

- Admin/Mod phải theo dõi nhiều tin nhắn và dễ bỏ sót xung đột, spam hoặc lừa đảo.
- Bộ lọc từ khóa đơn giản khó phân biệt nói đùa, tranh luận, công kích và đe dọa thật.
- Câu hỏi lặp lại làm tốn thời gian; gửi mọi câu hỏi tới LLM vừa tốn chi phí vừa có nguy cơ trả lời không có nguồn.
- Đánh giá người bán liên quan tiền bạc nên không thể dựa vào điểm hoạt động hoặc phán quyết tự động của AI.

## Giải pháp

- Phân luồng chatbot theo `Rule -> Moderation -> FAQ -> RAG/LLM`.
- Moderation realtime qua ba gate: fast filter, context review và human-reviewed case retrieval.
- Loại tin nhắn bot, webhook, application và system khỏi moderation, analytics và EXP.
- Gom message rủi ro thành incident, gửi dashboard/Telegram và chờ Admin/Mod xử lý.
- FAQ chỉ trả nội dung đã được Admin duyệt.
- RAG dùng retrieval, reranking và relevance gate; nguồn yếu thì không trả bừa.
- LLM hỗ trợ input đa ngôn ngữ, còn phần giải thích hiển thị được chuẩn hóa về tiếng Việt.
- EXP chỉ phản ánh đóng góp tích cực của thành viên thật.
- Giao dịch cần buyer và seller cùng xác nhận; review và AI summary chỉ là bằng chứng hỗ trợ Admin/Mod.

THO không tự kết tội thành viên, chứng nhận người bán an toàn hoặc đưa tư vấn pháp lý/tài chính. Xóa tin nhắn, timeout, kick và ban chỉ được thực hiện sau khi người quản trị xác nhận.

## Tính năng hiện có

| Nhóm | Tính năng |
|---|---|
| Chatbot | Lệnh deterministic, FAQ đã duyệt, LLM hội thoại, RAG có citation và ghi nhận câu chưa có đáp án |
| Moderation | Lọc bot/webhook, ba gate realtime, phân tích đa ngôn ngữ, incident, review queue, manual action và audit trail |
| Dashboard | Tổng quan, cộng đồng, AI Sandbox, nhật ký, FAQ/knowledge, Mod, thông báo, lệnh bot, EXP và hồ sơ người bán |
| EXP | Reaction từ người thật, chống tự reaction/event trùng, chỉ cộng đóng góp dương |
| Giao dịch | `/trade_open`, `/trade_confirm`, `/trade_review`, `/seller_check` trên Discord và Telegram |
| Import knowledge | JSON, JSONL, CSV, TSV, XLSX, YAML, HTML, Markdown, TXT, DOCX và PDF |
| Xác thực | Password, Google OAuth, JWT, role Admin/Mod, invite Mod và token revocation |
| Tích hợp | Discord listener, Telegram listener/alert, SMTP invite, OpenAI, Gemini tùy cấu hình và Supabase |

## Kiến trúc

```mermaid
flowchart LR
    Member["Thành viên"] --> Discord["Discord"]
    Member --> Telegram["Telegram"]
    Staff["Admin / Mod"] --> Web["React 18 + Vite"]
    Discord --> Runtime["FastAPI + platform listeners"]
    Telegram --> Runtime
    Web --> Runtime
    Runtime --> Chat["Rule -> Moderation -> FAQ -> RAG/LLM"]
    Runtime --> Ops["Incident / Review / Audit"]
    Chat --> AI["OpenAI / Gemini + src/ai_models"]
    Ops --> DB[("Supabase PostgreSQL + pgvector")]
    Chat --> DB
```

Production dùng một Docker image chứa React SPA và FastAPI. Uvicorn nhận `PORT` từ Railway; toàn bộ dữ liệu runtime nằm trên Supabase, không nằm trong filesystem của container.

Tài liệu chi tiết:

- [Kiến trúc chính thức](ARCHITECTURE.md)
- [Sơ đồ và từng luồng runtime](docs/architecture_diagram.md)
- [Luồng dữ liệu Supabase](docs/SUPABASE_DATA_FLOW.md)
- [Moderation và chatbot pipeline](docs/community_pipeline.md)

## Tech stack

| Layer | Công nghệ |
|---|---|
| AI | OpenAI `gpt-4o-mini`, `text-embedding-3-small`; Gemini tùy cấu hình |
| Agent/model pipeline | LangGraph, LangChain, structured outputs, reranking và relevance gate |
| Backend | Python 3.11, FastAPI, Uvicorn, Pydantic |
| Frontend | React 18, Vite 6, React Router 7, TanStack Query 5, Motion |
| Database | Supabase PostgreSQL, pgvector, psycopg2 connection pool |
| Platform | discord.py, Telegram Bot API, SMTP |
| Delivery | GitHub Actions, Docker multi-stage, Railway |
| Quality | Ruff, pytest, frontend production build |

## Cài đặt local

### 1. Backend

```powershell
git clone https://github.com/AI20K-Build-Phase-Cohort-3/P-232.git
Set-Location P-232
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Các biến tối thiểu:

```dotenv
APP_ENV=development
OPENAI_API_KEY=your-openai-key
FAQ_PG_DSN=postgresql://postgres:[PASSWORD]@db.[PROJECT-REF].supabase.co:5432/postgres
AUTH_JWT_SECRET=replace-with-a-long-random-secret
MODERATION_MODE=openai
MODERATION_PROVIDER=openai
DISCORD_RAG_LLM_ENABLED=true
DISCORD_RAG_MODEL=gpt-4o-mini
```

Khi `FAQ_PG_DSN` được cấu hình, Supabase là source of truth. Ứng dụng không tự chuyển sang SQLite khi Supabase lỗi; `DATABASE_URL=sqlite://...` chỉ dành cho test cô lập.

Chạy backend:

```powershell
python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

Development mở Swagger tại `http://127.0.0.1:8000/docs`; production tắt Swagger/OpenAPI public.

### 2. Frontend

```powershell
Set-Location frontend
npm ci
npm run dev
```

Vite chạy riêng trong development và gọi API qua `/api`. Production build được FastAPI phục vụ trực tiếp.

### 3. Discord và Telegram

```dotenv
DISCORD_BOT_TOKEN=your-discord-token
DISCORD_LISTENER_ENABLED=true
DISCORD_TRADE_CHANNEL_ID=your-dedicated-trade-channel-id

TELEGRAM_BOT_TOKEN=your-telegram-token
TELEGRAM_LISTENER_ENABLED=true
TELEGRAM_DEFAULT_CHAT_ID=your-community-chat-id
TELEGRAM_TRADE_CHAT_ID=your-dedicated-trade-chat-id
TELEGRAM_ADMIN_CHAT_ID=your-private-admin-chat-id
TELEGRAM_ALERTS_ENABLED=true
```

Trade command chỉ mở trong channel/chat được cấu hình. Không đưa bot token, API key, database password hoặc SMTP App Password vào Git.

Danh sách đầy đủ nằm trong [.env.example](.env.example).

## Chạy bằng Docker

```powershell
docker build -t tho .
docker run --env-file .env -p 8000:8000 tho
```

Health check:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

## Ví dụ demo

```text
@THO /help
@THO hôm nay ngày bao nhiêu?
@THO học bằng dự án là gì?
@THO làm sao để báo cáo spam?

/trade_open @seller Bàn phím cơ cũ
/trade_confirm TRD-XXXXXXXXXXXX
/trade_review TRD-XXXXXXXXXXXX
/seller_check @seller
```

Kết quả kỳ vọng:

- Lệnh trả từ nhánh `Rule`.
- Câu đã có FAQ trả từ `admin-faq` và không gọi LLM.
- Hội thoại chung trả nhãn `[LLM]` hoặc `[Hệ thống]` khi provider lỗi.
- Câu kiến thức đủ liên quan trả `[RAG]` và citation; nguồn yếu trả `Không đủ nguồn`.
- Message rủi ro tạo incident chờ người quản trị, không tự động tác động thành viên.

## Kiểm thử

```powershell
python -m ruff check backend src tests eval
python -m pytest tests -q
npm ci --prefix frontend
npm run build --prefix frontend
docker build -t tho-ci .
```

GitHub Actions chạy các bước backend, frontend và Docker trên push hoặc pull request vào `main`, `Develop` và `QA`.

## Cấu trúc repo

```text
backend/                 FastAPI, auth, services, moderation và platform bots
frontend/                React/Vite dashboard
src/ai_models/           Reranking, relevance, citation và moderation memory
supabase/migrations/     Runtime PostgreSQL/pgvector schema
data/                    Contract và ví dụ chuẩn hóa, không phải production DB
tests/                   Unit và integration tests
eval/                    Evaluation cases và báo cáo
docs/                    Architecture, pipeline và data flow
presentation/            Kịch bản demo/pitch
scripts/                 AI logging hooks và Phoenix submission
```

## Giới hạn hiện tại

- Hệ thống đang triển khai cho một community. Schema có `community_id`, nhưng connector, cấu hình và quyền dữ liệu chưa cô lập multi-tenant end-to-end.
- Đăng ký dashboard chỉ tạo một Admin trong community hiện tại, chưa tự tạo tenant, community hoặc bot configuration mới.
- Rate limiter nằm trong bộ nhớ và phù hợp một replica; cần distributed store trước khi scale ngang.
- Kết quả người bán là dữ kiện hỗ trợ, không phải chứng nhận an toàn hay thay thế kiểm tra của Admin/Mod.

BTC vui lòng dùng tài khoản test được gợi ý trực tiếp trên trang đăng nhập/landing page; tính năng đăng ký và provision cộng đồng mới chưa hoàn thiện.

## Thành viên

| Thành viên | Vai trò | Mã sinh viên |
|---|---|---|
| Nguyễn Chiến Thắng | QA | 2A202601734 |
| Bùi Hữu Nghĩa | Model | 2A202601880 |
| Nguyễn Thái Tú | Web Developer | 2A202601504 |
| Hà Nhật Khánh Duy | Data Analyst | 2A202602031 |

## Tài liệu nộp bài

- [Bản đồ deliverables](GATE2_SUBMISSION.md)
- [Model pipeline](src/ai_models/README.md)
- [Data rules](data/RULES.md)
- [Evaluation report](eval/results/report.md)
- [Video MVP](https://youtu.be/1EdQj81X47M)

## License

MIT
