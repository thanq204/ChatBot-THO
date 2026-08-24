# Architecture Diagram

## Tổng quan CHAT-10

CHAT-10 nhận dữ liệu từ Discord, Telegram hoặc web/API. FastAPI khởi tạo bot listener và các service dùng chung; Supabase PostgreSQL + pgvector lưu message, incident, FAQ, knowledge, audit và embedding runtime. LLM chỉ được gọi ở các nhánh đã định nghĩa, còn RAG phải qua reranking và relevance gate trước khi trả nguồn.

```mermaid
flowchart LR
    Member["Member"] --> Discord["Discord Bot"]
    Member --> Telegram["Telegram Bot"]
    Admin["Admin / Moderator"] --> UI["React + Vite Dashboard"]
    Discord --> Chat["Chat Orchestrator"]
    Telegram --> Chat
    UI --> API["FastAPI REST API"]
    API --> Ops["Operations Services"]
    API --> ModerationGraph["LangGraph Moderation"]
    Chat --> Ops
    Chat --> Models["src/ai_models"]
    Ops --> Supabase[("Supabase PostgreSQL + pgvector")]
    Models --> Supabase
    Models --> OpenAI["OpenAI LLM / Embeddings"]
    ModerationGraph --> OpenAI
    ModerationGraph --> Gemini["Gemini optional"]
    Ops --> Incidents["Incident + Review + Audit"]
    Incidents --> UI
    Discord --> Trade["Verified trade workflow"]
    Trade --> Supabase
    Supabase --> Seller["Seller evidence summary"]
    Seller --> UI
    Chat --> Discord
    Chat --> Telegram
```

## Luồng hỏi đáp

```mermaid
flowchart TD
    Input["Tin nhắn tag CHAT-10 hoặc chat riêng"] --> Rule{"Lệnh / rule?"}
    Rule -->|"Có"| RuleAnswer["Rule response"]
    Rule -->|"Không"| Moderate["Moderation 3 gate"]
    Moderate --> Safe{"Được phép tiếp tục?"}
    Safe -->|"Không"| ModerationAnswer["Cảnh báo / hold / incident"]
    Safe -->|"Có"| FAQ["FAQ similarity search"]
    FAQ --> FAQHit{"FAQ đã duyệt đủ gần?"}
    FAQHit -->|"Có"| FAQAnswer["FAQ answer, không gọi LLM"]
    FAQHit -->|"Không"| General{"Tên bot / khả năng / ngày giờ?"}
    General -->|"Có"| LLM["OpenAI gpt-4o-mini"]
    LLM --> LLMAnswer["[LLM] response"]
    General -->|"Không"| Retrieve["Knowledge retrieval"]
    Retrieve --> Rerank["Reranker"]
    Rerank --> Relevance{"Relevance gate đạt?"}
    Relevance -->|"Không"| Unanswered["Ghi câu chưa có đáp án"]
    Relevance -->|"Có"| RAG["[RAG] source body + citation"]
```

FAQ và RAG chỉ chạy khi bot được tag trong group hoặc nhận tin nhắn riêng. Tin nhắn group bình thường chỉ chạy moderation realtime.

## Luồng moderation

```mermaid
flowchart TD
    Message["Message + recent context"] --> Gate1["Gate 1: regex / spam / threat fast filter"]
    Gate1 --> Gate2["Gate 2: context review"]
    Gate2 --> Gate3["Gate 3: reviewed-case retrieval"]
    Gate3 --> Decision{"allow / warn / hide / hold"}
    Decision -->|"allow"| Persist["Lưu message + decision"]
    Decision -->|"risk"| Incident["Tạo hoặc cập nhật incident"]
    Incident --> Review["Admin/Mod review"]
    Review --> Action["DM / delete / timeout / kick / ban khi xác nhận"]
    Action --> Audit["Audit trail"]
```

Endpoint `/api/v1/moderation/submit` có thêm workflow LangGraph chuyên biệt: Context Agent, Policy Agent, Risk Agent, Safety Gate, Decision Agent và deterministic guardrail.

## Luồng EXP và người bán

```mermaid
flowchart TD
    Reaction["3 phản hồi ✅ từ người thật"] --> EXP["Cộng EXP có giới hạn"]
    Moderation["Incident / vi phạm"] --> Audit["Audit riêng, không trừ EXP"]
    Open["/trade_open trong kênh giao dịch"] --> ConfirmBuyer["Buyer xác nhận"]
    Open --> ConfirmSeller["Seller xác nhận"]
    ConfirmBuyer --> Completed{"Cả hai đã xác nhận?"}
    ConfirmSeller --> Completed
    Completed -->|"Có"| Review["Buyer review đúng trade_id"]
    Review --> Metrics["Số giao dịch, buyer khác nhau, rating từng tiêu chí"]
    Check["/seller_check"] --> AISummary["AI tóm tắt dữ kiện, không phán quyết"]
    Metrics --> AISummary
    AISummary --> Human["Admin/Mod xem bằng chứng và quyết định"]
```

- EXP chỉ cộng từ sự kiện đóng góp dương; bot, tự reaction và event trùng không được tính.
- Review chỉ mang nhãn giao dịch xác thực khi buyer và seller đã cùng xác nhận; mỗi `trade_id` có tối đa một review.
- AI chỉ nhận chỉ số tổng hợp, không nhận Discord User ID, và không được kết luận “an toàn”, “lừa đảo” hoặc đưa tư vấn pháp lý/tài chính.
- Mốc mặc định `3` giao dịch và `3` buyer chỉ xác định đủ cỡ mẫu để hiển thị lịch sử, không phải huy hiệu bảo đảm.
- Từ `5` review trong `24` giờ cho cùng seller được gắn cờ burst để Admin/Mod kiểm tra, không bị tự động loại.

## Thành phần

| Thành phần | Vị trí | Trách nhiệm |
|---|---|---|
| FastAPI app | `backend/main.py` | Lifespan, REST API, CORS, static frontend và bot listeners |
| Chat orchestrator | `backend/services/chat_orchestrator.py` | Rule, moderation, FAQ, LLM/RAG routing và response labels |
| Operations pipeline | `backend/services/operations_pipeline.py` | Ba gate moderation và incident orchestration |
| Model pipeline | `src/ai_models/` | Routing contracts, FAQ, reranking, relevance, citation, moderation memory |
| Operations store | `backend/services/operations_store.py` | Supabase persistence, retrieval, FAQ suggestions, analytics và audit |
| EXP và seller trust | `backend/services/operations_store.py`, `frontend/src/pages/ExperiencePage.jsx`, `frontend/src/pages/SellerTrustPage.jsx` | EXP dương, giao dịch xác thực, review từng tiêu chí và human review |
| Platform adapters | `backend/services/discord/`, `backend/services/telegram/` | Nhận/gửi message, mention/private-chat detection và alerts |
| Admin dashboard | `frontend/` | Review, incident, knowledge, FAQ và analytics UI |
| Eval | `eval/`, `tests/` | Manual reproducible cases, unit và integration tests |

## Dữ liệu và lưu trữ

| Dữ liệu | Nơi lưu | Ghi chú |
|---|---|---|
| Runtime records | Supabase PostgreSQL | Message, incident, policy, FAQ, knowledge, audit và gate runs |
| EXP | `member_reputation_events` (legacy ledger) + API `/admin/experience` | Chỉ tổng hợp event dương; penalty cũ không được tính vào EXP |
| Giao dịch người bán | `operations_trade_cases`, `operations_seller_reviews`, `operations_seller_assessments` | Xác nhận hai phía, verified review và quyết định Admin/Mod |
| Raw upload | `knowledge_import_raw` trong Supabase | Lưu bytes, checksum và metadata của file import |
| Normalized records | `knowledge_normalized_records` trong Supabase | Bản chuẩn hóa liên kết với `import_id` |
| Chunks và embeddings | `knowledge_sections`, `knowledge_section_embeddings` và các bảng embedding Supabase | pgvector dùng cho retrieval; không đọc file raw trực tiếp |
| Data contracts/examples | `data/00_inbox` đến `data/50_indexes` | Hợp đồng, ví dụ và hướng dẫn cho Data team; không phải runtime store |
| AI usage logs | `.ai-log/session.jsonl` | Hook ghi local và submit Phoenix |
| Secret | `.env` | Không commit; `.env.example` chỉ chứa placeholder |

## Retrieval và model

- `KNOWLEDGE_EMBEDDING_ENABLED=true`: dùng OpenAI embedding và lưu vector trong các bảng pgvector của Supabase.
- Embedding không bật hoặc provider lỗi: dùng deterministic lexical/concept retrieval trên dữ liệu Supabase; không tự chuyển runtime sang SQLite.
- Candidate được rerank và qua relevance gate trong `src/ai_models`.
- Runtime knowledge trả nội dung canonical trực tiếp, không dùng LLM viết dài thêm.
- General conversation dùng `gpt-4o-mini`; nếu API lỗi, response được ghi nhãn `[Hệ thống]`, không giả là LLM.

## Deployment

```mermaid
flowchart LR
    GitHub["GitHub repository"] --> CI["GitHub Actions: Ruff + pytest"]
    GitHub --> Build["Docker multi-stage build"]
    Build --> Image["React static files + FastAPI image"]
    Image --> Runtime["Uvicorn :8000"]
    Runtime --> Volume["Mounted data volume"]
```

Docker build frontend bằng Node 22, cài Python dependencies trên Python 3.11, chạy production bằng non-root user và expose health check `/health`.

## Quyết định an toàn

- API keys chỉ đọc từ environment; không đưa vào source hoặc log.
- Hành động moderation nhạy cảm yêu cầu Admin xác nhận.
- Relevance gate chặn citation từ tài liệu yếu.
- LLM không được tự bịa dữ liệu cá nhân, dự án hoặc sự kiện hiện tại ngoài system context.
- Moderation memory chỉ chống review trùng và cung cấp bằng chứng; không tự ban/kick/delete.
- Điểm EXP không được dùng để suy luận độ tin cậy người bán.
- Seller summary luôn hiển thị cỡ mẫu; AI không có quyền chứng nhận, kết tội hoặc thực hiện action.

<!-- Sơ đồ starter template cũ được giữ ẩn để tránh thao tác replace file bị Windows khóa.

## System Overview

```mermaid
graph TB
    User([User]) --> UI[Frontend<br/>React/Next.js]
    UI -->|REST API| API[FastAPI Backend]
    API --> Agent[LangGraph Agent]
    Agent --> LLM[LLM Service<br/>GPT-4o / Gemini]
    Agent --> Tools[Agent Tools]
    Tools --> DB[(Database)]
    Agent --> VS[Vector Store<br/>ChromaDB]
```

## Agent Flow

```mermaid
graph LR
    START((Start)) --> Input[Parse Input]
    Input --> Analyze[Analyze Query]
    Analyze --> Decide{Need Tool?}
    Decide -->|Yes| CallTool[Call Tool]
    CallTool --> Analyze
    Decide -->|No| Generate[Generate Response]
    Generate --> END((End))
```

## Component Details

| Component | Technology | Purpose |
|-----------|-----------|---------|
| Frontend | React/Next.js | User interface |
| Backend | FastAPI | API server |
| Agent | LangGraph | AI agent orchestration |
| LLM | OpenAI/Gemini | Language model |
| Database | PostgreSQL/SQLite | Data persistence |
| Vector Store | ChromaDB | RAG / embeddings |
-->
