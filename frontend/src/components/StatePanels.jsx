import { WarningCircle, TrayArrowDown } from "@phosphor-icons/react";

export function ErrorState({ message, onRetry }) {
  return (
    <div className="state-panel state-panel--error">
      <WarningCircle size={22} weight="bold" />
      <p>{message || "Không kết nối được với backend."}</p>
      {onRetry && (
        <button type="button" className="btn btn--ghost" onClick={onRetry}>
          Thử lại
        </button>
      )}
    </div>
  );
}

export function EmptyState({ message, action }) {
  return (
    <div className="state-panel state-panel--empty">
      <TrayArrowDown size={22} weight="bold" />
      <p>{message || "Chưa có dữ liệu."}</p>
      {action}
    </div>
  );
}
