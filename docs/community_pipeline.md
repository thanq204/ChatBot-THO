# Discord + Telegram operations pipeline

```mermaid
flowchart TD
    A[Discord hoặc Telegram message] --> B[Normalize + deduplicate]
    B --> C[Incident grouping]
    C --> D[Context + risk analysis]
    D --> E[Knowledge Hub retrieval]
    E --> F[Admin review / intervention]
    F --> G{Action}
    G -->|Warn / hide / hold| H[Audit trail]
    G -->|Reply / notify| I[Discord hoặc Telegram]
    H --> J[Reviewed feedback]
    J -. tham khảo case tương tự .-> D
```

Discord listener nhận message realtime, nhóm incident theo channel/thread, truy xuất Knowledge Hub rồi mới đề xuất hành động. Telegram chỉ nhận cảnh báo khi risk vượt ngưỡng cấu hình; mọi quyết định vẫn được lưu vào audit trail.
