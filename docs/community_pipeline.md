# Discord + Telegram operations pipeline

Runtime sử dụng Supabase PostgreSQL + pgvector làm source of truth. `data/` chỉ chứa contract/example để chuẩn hóa input, không phải nơi đọc dữ liệu production.

## Tin nhắn realtime không tag chatbot

```mermaid
flowchart TD
    A[Discord/Telegram message] --> B[Normalize + lưu operations_messages]
    B --> C[Gate 1: fast filter theo policy]
    C --> D[Gate 2: context review, tối đa 12 tin/10 phút]
    D --> E[Gate 3: reviewed-case embedding + LLM verify tùy cấu hình]
    E --> F{Có cần cảnh báo?}
    F -->|Không| G[Lưu gate runs/audit, không gửi alert]
    F -->|Có| H[Tạo hoặc cập nhật incident]
    H --> I[Gửi Admin/Mod qua dashboard và Telegram nếu bật]
    H --> J[Gửi DM cảnh báo thành viên nếu bật]
    I --> K[Admin/Mod review và quyết định hành động]
    K --> L[Lưu moderation mark + embedding + audit]
    L -. dùng cho case tương tự .-> E
```

Gate chỉ giúp giảm cảnh báo sai và cảnh báo trùng. AI không tự xóa message, timeout, kick hoặc ban; mọi tác động trực tiếp do Admin/Mod xác nhận.

## Tin nhắn tag chatbot hoặc chat riêng

```mermaid
flowchart TD
    A[Tag CHAT-10/private message] --> B[Rule command?]
    B -->|Có| C[Trả command deterministic]
    B -->|Không| D[Moderation]
    D -->|Không cho trả lời| E[Cảnh báo thành viên, ghi nhận review]
    D -->|An toàn| F[Ghi operations_faq_questions]
    F --> G[FAQ semantic match]
    G -->|Đã duyệt| H[Trả operations_faqs, không gọi LLM/RAG]
    G -->|Chưa có| O{Câu hội thoại chung?}
    O -->|Có| P[LLM thật, nhãn LLM]
    O -->|Không| I[Knowledge retrieval]
    I --> J[Reranking]
    J --> K[Relevance gate]
    K -->|Đạt| L[Trả canonical source + citation, nhãn RAG]
    K -->|Không đạt| M[Ghi unanswered, không bịa câu trả lời]
    F -. gom topic .-> N[faq_topic_clusters -> Top 10 cho Admin]
    N -->|Admin nhập đáp án| H
```

## Nơi lưu dữ liệu

| Bước | Bảng Supabase |
|---|---|
| Message, context | `community_members`, `operations_messages` |
| Ba gate và audit | `operations_gate_runs`, `operations_incidents`, `operations_audit` |
| Case đã Admin/Mod xác nhận | `operations_moderation_marks`, `operations_moderation_embeddings` |
| FAQ analytics và Top 10 | `operations_faq_questions`, `faq_question_embeddings`, `faq_topic_clusters`, `faq_topic_members`, view `faq_top_10_topics` |
| FAQ đã duyệt | `operations_faqs`, `operations_faq_embeddings` |
| Knowledge import và RAG | `operations_knowledge_imports`, `knowledge_import_raw`, `knowledge_normalized_records`, `knowledge_documents`, `knowledge_sections`, `knowledge_section_embeddings` |

Discord listener nhận message realtime; Telegram nhận alert khi decision vượt ngưỡng và được bật trong environment. Mọi decision và feedback vẫn đi qua Admin/Mod và được ghi audit trail.
