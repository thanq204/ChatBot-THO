import { useState } from "react";
import { WarningCircle, ArrowsClockwise } from "@phosphor-icons/react";
import ThoMascot from "./ThoMascot.jsx";

export function ErrorState({ message, onRetry }) {
  const [retrying, setRetrying] = useState(false);

  const handleRetry = async () => {
    if (!onRetry) return;
    setRetrying(true);
    try {
      await onRetry();
    } finally {
      setTimeout(() => setRetrying(false), 400);
    }
  };

  return (
    <div className="state-panel state-panel--error">
      <WarningCircle size={24} weight="bold" color="var(--sev-critical)" />
      <p>{message || "Không kết nối được với hệ thống."}</p>
      {onRetry && (
        <button
          type="button"
          className="btn btn--ghost"
          onClick={handleRetry}
          disabled={retrying}
          style={{ gap: 6, marginTop: 4 }}
        >
          <ArrowsClockwise
            size={16}
            weight="bold"
            style={{ animation: retrying ? "spin 0.75s linear infinite" : "none" }}
          />
          {retrying ? "Đang tải lại..." : "Thử lại"}
        </button>
      )}
    </div>
  );
}

export function EmptyState({ message, action, showMascot = true }) {
  return (
    <div className="state-panel state-panel--empty" style={{ gap: 12, padding: "28px 20px" }}>
      {showMascot && <ThoMascot height={68} className="anime-badge-pulse" />}
      <p style={{ maxWidth: 420, margin: 0, fontSize: 13.5, lineHeight: 1.5 }}>
        {message || "Chưa có dữ liệu nào cần hiển thị."}
      </p>
      {action && <div style={{ marginTop: 4 }}>{action}</div>}
    </div>
  );
}
