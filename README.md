# CHAT-10 - Community Health & Conflict Mediation Copilot

CHAT-10 hỗ trợ Admin/Moderator quản lý cộng đồng học tập trên Discord và Telegram. Hệ thống kết hợp moderation theo ngữ cảnh, FAQ do Admin duyệt, RAG có reranking/relevance gate và LLM thật cho hội thoại chung.

## Vấn đề

- Admin/Mod phải theo dõi nhiều tin nhắn, đọc lại ngữ cảnh xung đột và xử lý cảnh báo trùng lặp.
- Thành viên thường hỏi lại cùng một câu; gửi mọi câu hỏi tới LLM gây tốn chi phí và dễ trả lời không có nguồn.
- Bộ lọc từ khóa đơn giản không đủ phân biệt phản biện, nói đùa, công kích và đe dọa thật.

## Giải pháp

- Phân tích moderation theo ba tầng: lọc nhanh, phân loại policy và đánh giá ngữ cảnh.
- Gom tin nhắn rủi ro thành incident để Admin/Mod review, hành động và lưu audit trail.
- Phân luồng chatbot theo thứ tự `Rule -> Moderation -> FAQ -> LLM hoặc RAG`.
- FAQ trả câu trả lời đã được Admin duyệt mà không gọi LLM.
- Câu hội thoại chung như tên bot, khả năng, ngày/giờ dùng LLM thật và hiển thị nhãn `[LLM]`.
- Câu kiến thức dùng retrieval, reranking và relevance gate; chỉ trả nguồn đạt ngưỡng với nhãn `[RAG]` và citation.
- Câu chưa đủ nguồn được ghi nhận để Admin cân nhắc bổ sung FAQ hoặc tài liệu.
- EXP chỉ ghi nhận đóng góp tích cực; moderation và tranh chấp không làm EXP âm.
- Đánh giá người bán chỉ nhận từ giao dịch Discord được buyer và seller cùng xác nhận; AI tóm tắt dữ kiện, Admin/Mod quyết định case nhạy cảm.

## Người dùng

- Chính: Admin và Moderator của cộng đồng học tập.
- Phụ: thành viên hỏi đáp, xem nội quy, gửi báo cáo hoặc tra cứu tài liệu đã duyệt.

## Tính năng MVP

| Nhóm | Tính năng |
|---|---|
| Chatbot | Lệnh `/help`, `/rule`, `/event`, `/daily`, `/weekly`, `/faq`, `/report`, `/admin`, `/resources` |
| Hỏi đáp | FAQ match, LLM hội thoại chung, RAG có citation, ghi nhận câu chưa có đáp án |
| Moderation | Ba gate, incident grouping, review queue, audit log, manual action |
| Cộng đồng | Bảng EXP cho thành viên thật; giới hạn chống cày và không trộn với vi phạm |
| Giao dịch | `/trade_open`, `/trade_confirm`, `/trade_review`, `/seller_check`; hồ sơ người bán có cỡ mẫu và hàng đợi Admin/Mod |
| Nền tảng | Discord listener, Telegram listener/alert, FastAPI, React/Vite admin dashboard |
| Dữ liệu | Supabase PostgreSQL + pgvector; `data/` chỉ giữ contract/example, import knowledge CSV/JSON/TXT, embedding OpenAI tùy chọn |

## Kiến trúc

Sơ đồ và mô tả chi tiết nằm tại [docs/architecture_diagram.md](docs/architecture_diagram.md).

```text
Discord/Telegram/Web
        |
        v
FastAPI + platform listeners
        |
        +--> Moderation gates --> Incident/Review/Audit --> Admin dashboard
        |
        +--> Rule --> FAQ --> General LLM
                         \--> Retrieval --> Reranker --> Relevance --> RAG + citation
        |
        v
Supabase PostgreSQL + pgvector
  (messages, moderation, FAQ, knowledge, embeddings, EXP, trades, seller reviews, audit)
```

## Tech Stack

| Layer | Công nghệ |
|---|---|
| Model | OpenAI `gpt-4o-mini`, `text-embedding-3-small`; Gemini có thể cấu hình |
| Agent | LangGraph, LangChain |
| Backend | Python 3.11+, FastAPI, Uvicorn, Pydantic |
| Frontend | React 18, Vite |
| Database | Supabase PostgreSQL + pgvector |
| Platform | Discord.py, Telegram Bot API |
| DevOps | Docker, Docker Compose, GitHub Actions |
| Test | pytest, Ruff |

## Cài đặt

### 1. Clone và tạo môi trường

```powershell
git clone https://github.com/AI20K-Build-Phase-Cohort-3/P-232.git
cd P-232
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

### 2. Cấu hình biến môi trường

```powershell
Copy-Item .env.example .env
```

Biến tối thiểu để chạy backend và LLM:

```dotenv
OPENAI_API_KEY=your-openai-key
FAQ_PG_DSN=postgresql://postgres:[PASSWORD]@db.[PROJECT-REF].supabase.co:5432/postgres
MODERATION_MODE=openai
MODERATION_PROVIDER=openai
DISCORD_RAG_LLM_ENABLED=true
DISCORD_RAG_MODEL=gpt-4o-mini
# Chỉ dùng khi chạy test cô lập, không dùng làm runtime production.
DATABASE_URL=sqlite:///./data/community_channel.db
```

Khi `FAQ_PG_DSN` được cấu hình, Supabase là source of truth của runtime. `DATABASE_URL` chỉ còn phục vụ unit test SQLite được chỉ định rõ; ứng dụng không tự chuyển sang SQLite khi Supabase lỗi.

Để bật Discord:

```dotenv
DISCORD_BOT_TOKEN=your-discord-token
DISCORD_LISTENER_ENABLED=true
DISCORD_TRADE_CHANNEL_ID=your-dedicated-trade-channel-id
```

Luồng giao dịch chỉ mở trong `DISCORD_TRADE_CHANNEL_ID`. Hai bên xác nhận cùng một `trade_id`; sau đó chỉ buyer mới được gửi một review. Mặc định cần ít nhất `3` giao dịch xác thực và `3` buyer khác nhau để hồ sơ chuyển từ “Chưa đủ dữ liệu” sang “Có lịch sử giao dịch”. Đây không phải chứng nhận người bán an toàn.

Để bật Telegram:

```dotenv
TELEGRAM_BOT_TOKEN=your-telegram-token
TELEGRAM_LISTENER_ENABLED=true
```

Không commit `.env`. Danh sách đầy đủ và giá trị mặc định nằm trong [.env.example](.env.example).

### 3. Chạy ứng dụng

Backend và bot listener:

```powershell
python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

Swagger UI: `http://127.0.0.1:8000/docs`

Frontend development, trong terminal khác:

```powershell
Set-Location frontend
npm install
npm run dev
```

Chạy bằng Docker:

```powershell
docker compose up --build
```

## Sample Queries

### Discord/Telegram

```text
@CHAT-10 /help
@CHAT-10 bạn tên là gì
@CHAT-10 hôm nay ngày bao nhiêu
@CHAT-10 tôi đang tham gia một dự án, muốn học bằng dự án thì phương pháp này như nào?
@CHAT-10 làm sao để báo cáo spam?
/trade_open @seller Bàn phím cơ cũ
/trade_confirm TRD-XXXXXXXXXXXX
/trade_review TRD-XXXXXXXXXXXX
/seller_check @seller
```

Kỳ vọng:

- Lệnh trả từ nhánh `Rule`.
- Câu hỏi đã có FAQ trả từ `admin-faq`.
- Tên bot và ngày/giờ trả với nhãn `[LLM]`.
- Câu hỏi kiến thức đủ liên quan trả `[RAG]` và dòng `Trích từ tài liệu:`.

### API

Health check:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

Phân tích moderation:

```powershell
$body = @{
  message = @{
    message_id = "sample-001"
    platform = "web"
    author_id = "member-01"
    text = "Mình không đồng ý, bạn cho mình xin nguồn nhé"
    timestamp = (Get-Date).ToUniversalTime().ToString("o")
  }
  context = @()
} | ConvertTo-Json -Depth 5

Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/api/v1/messages/analyze `
  -ContentType "application/json" `
  -Body $body
```

RAG API:

```powershell
$body = @{ question = "Học bằng dự án là gì?" } | ConvertTo-Json
Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/api/v1/rag/ask `
  -ContentType "application/json" `
  -Body $body
```

## Kiểm thử

```powershell
python -m pytest -q
python -m ruff check backend src tests eval
```

Bằng chứng Discord manual sẽ được bổ sung tại [eval/results/report.md](eval/results/report.md) sau khi có đủ 5 ảnh test thực tế.

## Cấu trúc dự án

```text
backend/                 FastAPI, LangGraph, services và platform bots
frontend/                React/Vite admin dashboard
src/ai_models/           Routing, FAQ, reranking, relevance, citation và memory
data/                    Data contracts, examples và hướng dẫn chuẩn hóa (không phải runtime DB)
tests/                   Unit/integration tests
eval/                    Báo cáo và ảnh evaluation thực tế
docs/                    Architecture và technical guide
presentation/            Kịch bản/video/pitch artifacts
scripts/                 AI logging hooks và Phoenix submission
```

## Trạng thái Gate 2

> Người chấm có thể xem nhanh từng deliverable, vị trí code, test và chỗ gắn video tại [GATE2_SUBMISSION.md](GATE2_SUBMISSION.md).

| Deliverable | Trạng thái | Bằng chứng |
|---|---|---|
| MVP demo video 3 phút, end-to-end với LLM thật | Đạt | [Video MVP trên YouTube](https://youtu.be/1EdQj81X47M) |
| Architecture diagram | Đạt | `docs/architecture_diagram.md` |
| Repo có ít nhất 10 PR merged | Đạt | 12 PR merge riêng biệt trong lịch sử Git |
| README có setup, env vars, sample queries | Đạt | README này |
| Ít nhất 5 manual eval với output thật | Đạt | 5/5 case Discord trong `eval/results/report.md` |

**Tổng hiện tại: 5/5 deliverable Gate 2.**

## Thành viên

| Thành viên | Vai trò | Mã sinh viên |
|---|---|---|
| Nguyễn Chiến Thắng | QA | 2A202601734 |
| Bùi Hữu Nghĩa | Model | 2A202601880 |
| Nguyễn Thái Tú | Web Developer | 2A202601504 |
| Hà Nhật Khánh Duy | Data Analyst | 2A202602031 |

## Tài liệu liên quan

- [Bản đồ nộp bài Gate 2](GATE2_SUBMISSION.md)
- [Architecture](docs/architecture_diagram.md)
- [Model pipeline](src/ai_models/README.md)
- [Supabase data flow](docs/SUPABASE_DATA_FLOW.md)
- [Data rules](data/RULES.md)
- [Evaluation report](eval/results/report.md)
- [Video MVP Gate 2](https://youtu.be/1EdQj81X47M)

## License

MIT

<!-- Nội dung starter template cũ được giữ tạm bên dưới để không làm mất lịch sử khi file bị Windows khóa thao tác replace.

Template chính thức cho học viên **VinUni AI20K Build Phase** — cung cấp sẵn cấu trúc dự án, code mẫu, và hướng dẫn kỹ thuật chi tiết để xây dựng AI Agent đạt điểm cao (35+/50).

> 📖 **Technical Guidebook:** [phoenix.note.transformerlabs.ai/technical-book](https://phoenix.note.transformerlabs.ai/technical-book)

## 🎯 Template này dùng để làm gì?

Khi tham gia AI20K Build Phase, mỗi đội cần xây dựng một AI Agent hoàn chỉnh — từ kiến trúc, code, test, đến deploy. Thay vì bắt đầu từ con số không, template này cung cấp:

- **Cấu trúc thư mục chuẩn** — đã được thiết kế theo best practices (separation of concerns)
- **Code mẫu** cho các phần cốt lõi: LangGraph agent, FastAPI API, config, schemas
- **Docker + CI/CD sẵn** — Dockerfile multi-stage, GitHub Actions workflow
- **Hướng dẫn kỹ thuật 10 chương** — từ clone template đến nộp bài Demo Day
- **Checklist 10 deliverables** — đảm bảo không bỏ sót yêu cầu BTC
- **AI Usage Logging tự động** — Pre-configured hooks cho Claude Code, Cursor, Codex, Gemini CLI, Antigravity, và GitHub Copilot

## ⚡ Quick Start

### Bước 1: Fork hoặc Clone

```bash
# Clone template
git clone https://github.com/AI20K-Build-Cohort-2/starter-code-template.git team-YOUR_TEAM_NAME
cd team-YOUR_TEAM_NAME

# Xóa git history cũ và khởi tạo lại
rm -rf .git
git init
git add .
git commit -m "feat: khởi tạo dự án từ template"
```

### Bước 2: Setup môi trường

```bash
# Tạo virtual environment
python3.11 -m venv .venv
source .venv/bin/activate

# Cài dependencies
pip install -e ".[dev]"

# Cấu hình API keys
cp .env.example .env
# Mở .env và thêm OPENAI_API_KEY của bạn
# Đồng thời cập nhật AI_LOG_API_KEY bằng key riêng từ link mời của BTC
# (giá trị trong .env.example chỉ là placeholder)
```

### Bước 3: Cài AI Logging Hooks

```bash
# Linux / macOS / Git Bash
bash scripts/setup_hooks.sh

# Windows PowerShell
# powershell -ExecutionPolicy Bypass -File scripts\setup_hooks.ps1
```

Hooks tự động log mọi AI prompt khi dùng Claude Code, Cursor, Codex, Gemini CLI, Antigravity, hoặc GitHub Copilot. Không cần thao tác thủ công.

### Bước 4: Chạy server

```bash
# Chạy FastAPI backend
uvicorn src.main:app --reload --port 8000

# Mở Swagger UI
# http://localhost:8000/docs
```

### Bước 5: Đọc hướng dẫn

📖 Mở **[Technical Guidebook](https://phoenix.note.transformerlabs.ai/technical-book)** và làm theo từng chương.

## 📁 Cấu trúc dự án

```
├── src/
│   ├── agents/           # 🧠 LangGraph Agent
│   │   ├── graph.py      #    State graph (nodes + edges)
│   │   ├── state.py      #    State schema (TypedDict)
│   │   ├── nodes/        #    Node functions
│   │   └── tools/        #    Agent tools (@tool)
│   ├── api/              # 🌐 FastAPI Backend
│   │   └── routes.py     #    API endpoints
│   ├── models/           # 📋 Pydantic schemas
│   ├── services/         # 🔧 Business logic (LLM, etc.)
│   ├── config.py         # ⚙️ Pydantic Settings
│   └── main.py           # 🚀 App entry point
├── tests/                # 🧪 pytest suite
│   ├── test_agents/      #    Agent/graph tests
│   └── test_api/         #    API endpoint tests
├── scripts/              # 🔌 AI Logging Hooks
│   ├── log_hook.py       #    Auto-log cho Claude/Cursor/Codex/Gemini/Copilot
│   ├── log_antigravity.py#    Antigravity IDE prompt scanner
│   ├── log_manual.py     #    Manual log cho ChatGPT / web tools
│   ├── submit_log.py     #    Submit logs on git push
│   └── setup_hooks.sh    #    One-time hook installer
├── .claude/ .codex/ .cursor/ .gemini/  # Per-tool hook configs
├── .agents/              # Antigravity rules + workflows
├── .ai-log/              # 📊 AI usage logs (auto-generated)
├── docs/
│   ├── guide/            # 📖 Technical Guidebook (10 chapters)
│   └── architecture_diagram.md
├── eval/                 # 📊 Evaluation results
├── presentation/         # 🎤 Demo Day slides
├── .github/workflows/    # ⚡ CI/CD (GitHub Actions)
├── .github/hooks/        # 🪝 Copilot hook config
├── Dockerfile            # 🐳 Multi-stage build
├── docker-compose.yml    # 🐙 Full stack orchestration
└── README_boilerplate.md # 📝 README template cho đội của bạn
```

## 📚 Technical Guidebook — 10 Chương

| Chương | Nội dung | Thời gian |
|---------|----------|-----------|
| 1 | Lời mở đầu — Mục tiêu, cách sử dụng | 15 phút |
| 2 | Khởi tạo dự án — Clone, setup, git workflow | 4 giờ |
| 3 | Thiết kế kiến trúc — 3-tier, diagrams, ADR | 6 giờ |
| 4 | **LangGraph Agent** — State, nodes, edges, tools, RAG | 8 giờ |
| 5 | FastAPI — Routes, validation, error handling, streaming | 6 giờ |
| 6 | Giao diện — Next.js + Streamlit quickstart | 6 giờ |
| 7 | DevOps — Docker, CI/CD, deploy, logging | 6 giờ |
| 8 | Kiểm thử — Unit test, integration test, RAGAS | 4 giờ |
| 9 | Demo Day — 10 deliverables, checklist, tips | 2 giờ |
| 10 | Tài nguyên — Khóa học, docs, BMAD method | tham khảo |

📖 **Đọc online:** [phoenix.note.transformerlabs.ai/technical-book](https://phoenix.note.transformerlabs.ai/technical-book)

## 📋 10 Deliverables cho Demo Day

| # | Deliverable | File vị trí | Template có sẵn |
|---|-------------|-------------|:---:|
| 1 | Source Code | `src/` | ✅ |
| 2 | README.md | `README_boilerplate.md` → copy thành `README.md` | ✅ |
| 3 | Architecture Diagram | `docs/architecture_diagram.md` | ✅ |
| 4 | AI Logs | LangSmith (3 env vars) + Auto AI Usage Logging | ✅ |
| 5 | Live URL | Deploy lên Render/Vercel | ⚡ CI/CD sẵn |
| 6 | Video Demo | `presentation/` | 📝 |
| 7 | Pitch Deck | `presentation/` | 📝 |
| 8 | Development Journal | `JOURNAL.md` | ✅ |
| 9 | Worklog | `WORKLOG.md` | ✅ |
| 10 | Evaluation Evidence | `eval/` | 📝 |

## 🛠 Tech Stack

| Layer | Technology | Version |
|-------|-----------|---------|
| AI Agent | LangGraph + LangChain | Latest |
| Backend | FastAPI + Uvicorn | 0.100+ |
| LLM | OpenAI GPT-4o-mini | API |
| Frontend | Next.js / Streamlit | 14+ / 1.30+ |
| Database | Supabase PostgreSQL + pgvector; SQLite chỉ cho unit test cô lập | — |
| DevOps | Docker + GitHub Actions | — |
| Testing | pytest + pytest-asyncio | 8+ |

## 📊 AI Usage Logging

Template đã tích hợp sẵn auto-logging hooks cho 6 AI tools:

| Tool | Cơ chế | Config |
|------|--------|--------|
| Claude Code | `.claude/settings.json` hooks | Tự động |
| Cursor | `.cursor/hooks.json` | Tự động |
| OpenAI Codex CLI | `.codex/hooks.json` | Tự động |
| Gemini CLI | `.gemini/settings.json` | Tự động |
| GitHub Copilot | `.github/hooks/hooks.json` | Tự động |
| Antigravity IDE | Pre-push scan transcript | Tự động trên `git push` |

Tất cả prompts và tool calls được log vào `.ai-log/session.jsonl` và tự động submit lên grading server mỗi khi `git push`.

**ChatGPT / web tools khác** — log thủ công:
```bash
bash scripts/_pyrun.sh scripts/log_manual.py --tool chatgpt --prompt "What you asked"
```

> ⚠️ Chạy `bash scripts/setup_hooks.sh` một lần sau khi clone để cài pre-push hook.

## 📖 Đọc Technical Guidebook

**Online (khuyến nghị):** [phoenix.note.transformerlabs.ai/technical-book](https://phoenix.note.transformerlabs.ai/technical-book)

Đăng nhập bằng GitHub (cùng account đã được BTC mời vào org `AI20K-Build-Cohort-2`)
→ chọn tab **Technical Book** ở sidebar trái → đọc 10 chương + topic sections,
có table of contents bên phải, hỗ trợ light/dark/cyberpunk theme.

**Offline:** mọi chương đều ở thư mục `docs/guide/` trong template này — mở bằng
bất kỳ markdown viewer/editor nào (VS Code, Obsidian, GitHub UI, …).

## 🔗 Liên kết

- 📖 **Technical Guidebook:** [phoenix.note.transformerlabs.ai/technical-book](https://phoenix.note.transformerlabs.ai/technical-book)
- 🏫 **AI20K Program:** VinUni AI20K Build Phase
- 👨‍🏫 **Mentor:** Đặng Hải Lộc

## 📄 License

MIT — Sử dụng tự do cho mục đích giáo dục.
-->
