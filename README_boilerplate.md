# CHAT-10 — Community Health & Conflict Mediation Copilot

> Cộng đồng trực tuyến khó theo dõi xung đột và trả lời câu hỏi lặp lại theo thời gian thực → CHAT-10 kết hợp moderation nhiều tầng, FAQ và RAG có kiểm tra độ liên quan cho Admin/Mod và thành viên trên Discord, Telegram.

## Vấn đề (Problem)

- Admin/Mod của cộng đồng học tập phải theo dõi message trên nhiều nền tảng, đọc lại ngữ cảnh hội thoại, phát hiện xung đột và trả lời các câu hỏi lặp lại.
- Việc review thủ công tốn thời gian theo số lượng message và dễ tạo cảnh báo trùng. Dự án chưa có baseline thực tế về số giờ hoặc chi phí tiết kiệm; hệ thống đang lưu số message, incident, quyết định và audit log để đo trong giai đoạn evaluation.
- Bộ lọc từ khóa đơn giản không hiểu ngữ cảnh, còn chatbot không có relevance gate có thể chọn sai tài liệu hoặc tạo câu trả lời không được nguồn hỗ trợ.

## Giải pháp (Solution)

- Feature 1: Phân tích moderation nhiều tầng, gom message liên quan thành incident và chuyển trường hợp cần thiết tới Admin/Mod kèm bằng chứng.
- Feature 2: Quản lý policy, knowledge, audit trail và moderation memory để tham khảo quyết định đã được người kiểm duyệt xác nhận.
- Feature 3: Chatbot hỏi đáp theo luồng Rule → Moderation → FAQ → LLM hoặc RAG. Câu hội thoại chung dùng LLM thật; câu kiến thức dùng retrieval, reranking và relevance gate rồi trả nội dung canonical kèm nguồn, không dùng LLM viết dài thêm.

## Target User

- Primary: Admin và Moderator quản lý cộng đồng học tập trên Discord, Telegram.
- Secondary: Thành viên cần xem nội quy, gửi báo cáo hoặc hỏi chatbot về FAQ và knowledge đã được duyệt.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| AI Agent | LangGraph + OpenAI/Gemini |
| Backend | FastAPI + Python 3.11+ |
| Frontend | React 18 + Vite + JavaScript |
| Database | Supabase PostgreSQL + pgvector |
| DevOps | Docker + GitHub Actions |

## Quick Start

```bash
# 1. Clone repo
git clone https://github.com/AI20K-Build-Phase-Cohort-3/P-232.git
cd P-232

# 2. Setup environment
cp .env.example .env
# Edit .env with your API keys
# Add FAQ_PG_DSN for the team's Supabase project

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run FastAPI backend
python -m uvicorn backend.main:app --reload --port 8000

# 5. Run frontend development server in another terminal
cd frontend
npm install
npm run dev
```

## Project Structure

```
├── backend/
│   ├── agents/          # LangGraph và moderation graph
│   ├── api/             # FastAPI routes
│   ├── models/          # Pydantic schemas
│   ├── services/        # Moderation, RAG, FAQ và platform services
│   ├── config.py        # Settings
│   └── main.py          # FastAPI entry point
├── frontend/            # React 18 + Vite admin dashboard
├── src/ai_models/       # Model-only routing, reranking, relevance và memory
├── data/                # Data contracts, examples và schema hướng dẫn; runtime ở Supabase
├── tests/               # pytest test suite
├── docs/                # Architecture và technical guide
├── eval/                # Evaluation results
├── presentation/        # Demo materials
├── Dockerfile
├── docker-compose.yml
└── .github/workflows/   # CI/CD pipelines
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | /health | Health check |
| POST | /api/v1/chat | Chat với agent mẫu |
| POST | /api/v1/messages/analyze | Phân tích một message qua moderation pipeline |
| POST | /api/v1/rag/ask | Hỏi đáp trên Knowledge Hub bằng RAG |
| GET | /api/v1/faq-top-topics | Top 10 topic FAQ đang được hỏi nhiều (Admin) |

## Deliverables Checklist

- [x] Source Code (GitHub)
- [x] README.md
- [x] Architecture Diagram (`docs/architecture_diagram.md`)
- [x] AI Logs (auto-collected)
- [ ] Live URL / Deploy
- [x] Video Demo ([YouTube - Không công khai](https://youtu.be/1EdQj81X47M))
- [ ] Pitch Deck (`presentation/`)
- [x] Weekly Journal (`JOURNAL.md`)
- [x] Worklog (`WORKLOG.md`)
- [x] Evaluation Evidence (`eval/results/report.md`: 5/5 case Discord PASS)

### Gate 2

| Deliverable | Trạng thái |
|---|---|
| MVP demo video tối đa 3 phút | Đạt - [xem video](https://youtu.be/1EdQj81X47M) |
| Architecture diagram | Đạt |
| Repo có ít nhất 10 PR merged | Đạt - 12 PR merge riêng biệt |
| README có setup, env vars và sample queries | Đạt - xem `README.md` |
| Ít nhất 5 manual eval với output thật | Đạt - 5/5 case Discord |

**Tổng: 5/5.**

## Runtime data

Supabase PostgreSQL + pgvector là nguồn dữ liệu duy nhất khi chạy thật. Các bảng chính gồm `operations_messages`, `operations_gate_runs`, `operations_incidents`, `operations_audit`, `operations_moderation_marks`, `operations_faq_questions`, `faq_topic_clusters`, `operations_faqs`, `knowledge_documents`, `knowledge_sections` và các bảng embedding liên quan. Thư mục `data/` chỉ mô tả contract, ví dụ và quy tắc chuẩn hóa; không phải nơi chatbot đọc dữ liệu production.

## Team

| Member | Role | Student ID |
|--------|------|-----------|
| Nguyễn Chiến Thắng | QA | 2A202601734 |
| Bùi Hữu Nghĩa | Model | 2A202601880 |
| Nguyễn Thái Tú | Web Developer | 2A202601504 |
| Hà Nhật Khánh Duy | Data Analyst | 2A202602031 |

## License

MIT
