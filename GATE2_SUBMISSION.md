# Bản đồ nộp bài Gate 2

Trang này giúp người chấm đi thẳng từ yêu cầu Gate 2 tới code, tài liệu và bằng chứng tương ứng mà không phải tự tìm trong toàn bộ repository.

## Liên kết nộp bài

| Hạng mục | Liên kết | Trạng thái |
|---|---|---|
| Source code | [GitHub repository](https://github.com/AI20K-Build-Phase-Cohort-3/P-232) | Đạt |
| Architecture diagram | [docs/architecture_diagram.md](docs/architecture_diagram.md) | Đạt |
| README cài đặt và sample queries | [README.md](README.md) | Đạt |
| Evaluation thực tế | [eval/results/report.md](eval/results/report.md) | Đạt, 5/5 case Discord |
| Video demo tối đa 3 phút | [Xem video MVP trên YouTube](https://youtu.be/1EdQj81X47M) | Đạt |

Video được chia sẻ ở chế độ YouTube `Không công khai` (`Unlisted`) để người chấm có đường liên kết xem được mà không công khai video trên kênh.

## Luồng end-to-end cần chấm

```text
Discord/Telegram input
        |
        +--> Lệnh slash --------------------------> Rule
        |
        +--> Tin nhắn realtime không tag bot ----> Moderation Gate 1 -> Gate 2 -> Gate 3
        |                                                     |
        |                                                     +--> cảnh báo Admin/Mod và DM thành viên
        |
        +--> Tin nhắn tag bot/chat riêng --------> Moderation -> FAQ -> LLM hoặc RAG
                                                                      |
                                                                      +--> Retrieval -> Reranking
                                                                           -> Relevance gate -> Citation
```

## Bản đồ source code

| Phần cần kiểm tra | File chính | Symbol hoặc điểm bắt đầu | Vai trò |
|---|---|---|---|
| Nhận input Discord | [backend/services/discord/bot.py](backend/services/discord/bot.py) | `on_message` | Tin nhắn thường đi moderation realtime; tin nhắn tag bot đi luồng hỏi đáp |
| Nhận input Telegram | [backend/services/telegram/bot.py](backend/services/telegram/bot.py) | `_handle_update` | Dùng chung orchestrator và moderation pipeline |
| Chia bốn luồng input | [src/ai_models/routing.py](src/ai_models/routing.py) | `InputRouter` | Chọn `Rule`, `Moderation`, `FAQ`, `LLM_RAG` |
| Điều phối model | [src/ai_models/pipeline.py](src/ai_models/pipeline.py) | `CommunityAIPipeline` | FAQ trước; chưa có FAQ mới chuyển sang LLM/RAG |
| Điều phối chatbot runtime | [backend/services/chat_orchestrator.py](backend/services/chat_orchestrator.py) | `ChatOrchestrator.reply` | Kết nối routing, moderation, FAQ, retrieval và format output |
| Reranking và relevance | [src/ai_models/retrieval.py](src/ai_models/retrieval.py) | `SemanticReranker`, `RelevanceGate`, `GenerationRouter` | Xếp hạng lại nguồn, chặn nguồn yếu và chọn cách sinh câu trả lời |
| Nhãn và citation | [src/ai_models/answering.py](src/ai_models/answering.py) | `AnswerComposer` | Phân biệt FAQ, LLM, RAG và gắn nguồn cho RAG |
| Knowledge runtime | [backend/services/operations_store.py](backend/services/operations_store.py) | `list_knowledge`, `search_knowledge` | Đọc knowledge từ PostgreSQL hoặc fallback SQLite |

## Ba gate moderation realtime

Ba gate chỉ xử lý moderation realtime. Chúng không phải ba bước RAG và không yêu cầu người dùng tag chatbot.

| Gate | Code | Input | Kết quả |
|---|---|---|---|
| Gate 1 - Fast filter | [backend/services/operations_pipeline.py](backend/services/operations_pipeline.py) | Nội dung message và policy đang active | Loại message lành tính; tạo ứng viên rủi ro theo policy/từ khóa |
| Gate 2 - Context review | [backend/services/operations_pipeline.py](backend/services/operations_pipeline.py) | Message hiện tại và các message gần đó | Phân biệt đùa, ngữ cảnh game, giảm căng thẳng và công kích/đe dọa thật |
| Gate 3 - Reviewed-case retrieval | [backend/services/operations_pipeline.py](backend/services/operations_pipeline.py) | Kết quả Gate 2, moderation memory và cảnh báo gần đây | Chặn case trùng đã được Admin/Mod duyệt hoặc thông báo lặp |
| Lấy context và moderation memory | [backend/services/operations_store.py](backend/services/operations_store.py) | SQLite runtime | Cung cấp lịch sử gần và case đã được người thật xác nhận |
| Cảnh báo Telegram cho Admin/Mod | [backend/services/telegram/alerts.py](backend/services/telegram/alerts.py) | Chỉ decision vượt đủ gate và ngưỡng risk | Gửi cảnh báo có evidence, lý do và link message |
| DM Discord cho thành viên | [backend/services/platform_moderation.py](backend/services/platform_moderation.py) | Dùng cùng quyết định đã qua ba gate | Không DM nếu cảnh báo đã bị một gate chặn |

## Bằng chứng kiểm thử

| Nội dung | Test |
|---|---|
| Bốn luồng input | [tests/test_ai_model_pipeline.py](tests/test_ai_model_pipeline.py) |
| FAQ không gọi RAG/LLM khi đã có đáp án | [tests/test_ai_model_pipeline.py](tests/test_ai_model_pipeline.py) |
| Reranking, relevance và citation | [tests/test_rag_flow.py](tests/test_rag_flow.py) |
| Moderation chạy trước FAQ | [tests/test_chat_orchestrator.py](tests/test_chat_orchestrator.py) |
| Gate 1, Gate 2, Gate 3 và Telegram alert | [tests/test_realtime_notification_gates.py](tests/test_realtime_notification_gates.py) |
| Discord DM dùng cùng ba gate | [tests/test_platform_moderation.py](tests/test_platform_moderation.py) |
| Năm output Discord thực tế | [eval/results/report.md](eval/results/report.md) |

Chạy nhóm test cốt lõi:

```powershell
python -m pytest tests/test_ai_model_pipeline.py tests/test_realtime_notification_gates.py tests/test_chat_orchestrator.py tests/test_rag_flow.py tests/test_platform_moderation.py -q
```

Kết quả kiểm tra gần nhất ngày 14/08/2026: `40 passed, 1 warning`.
