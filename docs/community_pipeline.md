# Community Health pipeline

```mermaid
flowchart TD
    A[Local Web App] --> B{Data source}
    B -->|Public read-only| C[YouTube API: video + commentThreads]
    B -->|Offline demo| D[Imported dataset]
    B -->|Owner consent| E[Google OAuth]
    C --> F[Normalize and deduplicate]
    D --> F
    E --> F
    F --> G[Group comment + replies into thread]
    G --> H[Context Agent]
    H --> I[Escalation Agent]
    I --> J[Trigger + root cause + participants]
    J --> K[Intervention Agent]
    K --> L[Admin review and edit]
    L --> M{Approved action}
    M -->|Publish / reply / hide| N[YouTube action: simulated by default]
    M -->|Hold / observe| O[Keep under review]
    N --> P[Audit trail + outcome]
    O --> P
    P --> Q[Reviewed case examples]
    Q -. similar context .-> H
```

Public API mode never calls a YouTube write endpoint. The UI labels the default action as `SIMULATED ACTION`; real channel actions require explicit OAuth configuration and Admin approval.
