import { useCallback, useEffect, useState } from "react";
import { PaperPlaneTilt } from "@phosphor-icons/react";
import Card from "../components/Card.jsx";
import { SkeletonBlock } from "../components/Skeleton.jsx";
import { ErrorState, EmptyState } from "../components/StatePanels.jsx";
import { ops } from "../api/client.js";
import { platformLabel } from "../lib/taxonomy.js";
import { relativeTime } from "../lib/format.js";

const NOTIFY_PLATFORM_OPTIONS = [
  { value: "telegram", label: "Telegram" },
  { value: "discord", label: "Discord" },
];

export default function NotificationPage() {
  const [platformStatuses, setPlatformStatuses] = useState(null);
  const [selectedPlatforms, setSelectedPlatforms] = useState([]);
  const [actor, setActor] = useState("");
  const [message, setMessage] = useState("");
  const [sending, setSending] = useState(false);
  const [result, setResult] = useState(null);
  const [history, setHistory] = useState(null);
  const [historyError, setHistoryError] = useState(null);
  const [historyLoading, setHistoryLoading] = useState(true);

  useEffect(() => {
    ops
      .platforms()
      .then(setPlatformStatuses)
      .catch(() => setPlatformStatuses([]));
  }, []);

  const loadHistory = useCallback(() => {
    setHistoryLoading(true);
    setHistoryError(null);
    ops
      .audit()
      .then((rows) => setHistory(rows.filter((item) => item.event_type === "admin_announcement")))
      .catch((err) => setHistoryError(err.message))
      .finally(() => setHistoryLoading(false));
  }, []);

  useEffect(() => {
    loadHistory();
  }, [loadHistory]);

  const togglePlatform = (value) => {
    setSelectedPlatforms((prev) => (prev.includes(value) ? prev.filter((item) => item !== value) : [...prev, value]));
  };

  const sendAnnouncement = async (event) => {
    event.preventDefault();
    if (selectedPlatforms.length === 0 || !message.trim()) return;
    setSending(true);
    setResult(null);
    try {
      const response = await ops.sendAnnouncement({
        message: message.trim(),
        targets: selectedPlatforms,
        ...(actor.trim() ? { actor: actor.trim() } : {}),
      });
      setResult(response);
      loadHistory();
    } catch (err) {
      setResult({ deliveries: [{ platform: "_error", delivered: false, detail: err.message }] });
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="page-grid">
      <div className="page-grid__row">
        <Card title="Gửi thông báo tới nền tảng" className="span-6">
          <form className="stack" onSubmit={sendAnnouncement}>
            <div className="field">
              Chọn nền tảng
              <div className="chip-row">
                {NOTIFY_PLATFORM_OPTIONS.map(({ value, label }) => {
                  const status = platformStatuses?.find((item) => item.platform === value);
                  const configured = status ? status.configured : true;
                  return (
                    <label key={value} className={`platform-check ${configured ? "" : "platform-check--disabled"}`.trim()}>
                      <input
                        type="checkbox"
                        checked={selectedPlatforms.includes(value)}
                        disabled={!configured}
                        onChange={() => togglePlatform(value)}
                      />
                      {label}
                      <span className="chip">{configured ? "Đã kết nối" : "Chưa cấu hình"}</span>
                    </label>
                  );
                })}
              </div>
            </div>

            <label className="field">
              Người gửi (tuỳ chọn)
              <input value={actor} onChange={(event) => setActor(event.target.value)} placeholder="Admin" maxLength={100} />
            </label>

            <label className="field">
              Nội dung thông báo
              <textarea
                value={message}
                onChange={(event) => setMessage(event.target.value)}
                rows={5}
                maxLength={1900}
                placeholder="Nhập nội dung cần thông báo tới các nền tảng đã chọn..."
                required
              />
            </label>

            <div className="form-actions">
              <button type="submit" className="btn btn--primary" disabled={sending || selectedPlatforms.length === 0 || !message.trim()}>
                <PaperPlaneTilt size={14} weight="bold" /> {sending ? "Đang gửi..." : "Gửi thông báo"}
              </button>
            </div>

            {result && (
              <div className="stack" style={{ gap: 4 }}>
                {result.deliveries.map((delivery, index) => (
                  <p
                    key={`${delivery.platform}-${index}`}
                    className={`platform-sync__result platform-sync__result--${delivery.delivered ? "success" : "error"}`}
                  >
                    {delivery.platform === "_error" ? "Lỗi" : platformLabel(delivery.platform)}: {delivery.detail}
                  </p>
                ))}
              </div>
            )}
          </form>
        </Card>

        <Card title="Lịch sử thông báo" className="span-6" delay={0.05}>
          {historyLoading && <SkeletonBlock height={240} />}
          {!historyLoading && historyError && <ErrorState message={historyError} onRetry={loadHistory} />}
          {!historyLoading && !historyError && (!history || history.length === 0) && (
            <EmptyState message="Chưa có thông báo nào được gửi." />
          )}
          {!historyLoading && !historyError && history && history.length > 0 && (
            <div className="list">
              {history.map((item) => (
                <div className="list-row" key={item.audit_id}>
                  <div className="list-row__head">
                    <span className="list-row__title">{item.payload.announcement_id}</span>
                    <span className="list-row__meta">{relativeTime(item.created_at)}</span>
                  </div>
                  <div className="chip-row">
                    {(item.payload.delivered || []).map((delivery, index) => (
                      <span key={`${delivery.platform}-${index}`} className="chip">
                        {platformLabel(delivery.platform)}: {delivery.delivered ? "OK" : "Lỗi"}
                      </span>
                    ))}
                  </div>
                  <span className="list-row__meta">{item.actor}</span>
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}
