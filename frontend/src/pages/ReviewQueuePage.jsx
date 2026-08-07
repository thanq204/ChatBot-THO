import {
  ArrowsClockwiseIcon,
  CheckIcon,
  ClipboardTextIcon,
  EyeSlashIcon,
  ScrollIcon,
  WarningCircleIcon,
} from "@phosphor-icons/react";
import { useCallback, useEffect, useState } from "react";
import { moderation } from "../api/client.js";
import { Empty, Notice, Panel, SkeletonRows, dateText, percent } from "../components/ui.jsx";

export default function ReviewQueuePage() {
  const [queue, setQueue] = useState([]);
  const [audit, setAudit] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setError("");
    try {
      const [pending, entries] = await Promise.all([moderation.reviewQueue(), moderation.auditLogs()]);
      setQueue(pending);
      setAudit(entries);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Review queue</h1>
          <p>Nội dung model không tự quyết được sẽ dừng ở đây chờ Admin allow, warn hoặc hide.</p>
        </div>
        <button className="secondary icon-btn" onClick={load} disabled={loading}>
          <ArrowsClockwiseIcon size={14} className={loading ? "spin-icon" : undefined} />
          {loading ? "Đang tải..." : "Refresh queue"}
        </button>
      </div>

      {error && <Notice tone="error">{error}</Notice>}

      <section className="kpis">
        <div className="kpi">
          <span>Pending review</span>
          <strong>{loading ? "-" : queue.length}</strong>
        </div>
        <div className="kpi">
          <span>Decisions logged</span>
          <strong>{loading ? "-" : audit.length}</strong>
        </div>
        <div className="kpi">
          <span>Persistence</span>
          <strong style={{ fontSize: 18 }}>SQLite</strong>
        </div>
        <div className="kpi">
          <span>Audit trail</span>
          <strong style={{ fontSize: 18 }}>Enabled</strong>
        </div>
      </section>

      <Panel title="Cases đang chờ" subtitle="Allow, warn hoặc hide nội dung ở mức câu.">
        {loading ? (
          <SkeletonRows count={2} />
        ) : queue.length === 0 ? (
          <Empty icon={ClipboardTextIcon}>Không có nội dung nào đang chờ review.</Empty>
        ) : (
          <div className="stack">
            {queue.map((item) => (
              <ReviewCase key={item.review_id} item={item} onDecided={load} onError={setError} />
            ))}
          </div>
        )}
      </Panel>

      <Panel title="Audit log" subtitle="Mọi quyết định của Admin đều được ghi lại.">
        {loading ? (
          <SkeletonRows count={2} />
        ) : audit.length === 0 ? (
          <Empty icon={ScrollIcon}>Chưa có quyết định nào.</Empty>
        ) : (
          <div className="stack">
            {audit.map((item, index) => (
              <div className="record" key={index}>
                <b>{String(item.admin_action).toUpperCase()}</b>
                <span className="meta">
                  {" "}
                  · {item.review_id} · {item.user_id}
                </span>
                <small>
                  {item.model_category} ({percent(item.model_confidence)}) → {item.reviewer} lúc{" "}
                  {dateText(item.reviewed_at)}
                  {item.admin_note ? ` · ${item.admin_note}` : ""}
                </small>
              </div>
            ))}
          </div>
        )}
      </Panel>
    </>
  );
}

function ReviewCase({ item, onDecided, onError }) {
  const [reviewer, setReviewer] = useState("Admin");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState("");

  async function decide(action) {
    setBusy(action);
    try {
      await moderation.decide(item.review_id, {
        action,
        reviewer: reviewer.trim() || "Admin",
        admin_note: note.trim(),
      });
      await onDecided();
    } catch (requestError) {
      onError(requestError.message);
    } finally {
      setBusy("");
    }
  }

  return (
    <article className="record">
      <div className="button-row" style={{ justifyContent: "space-between" }}>
        <span className="meta">{item.review_id}</span>
        <span className="pill-row">
          <span className={`badge ${item.model_action}`}>{item.model_action}</span>
          {item.fallback_used && <span className="badge">mock fallback</span>}
        </span>
      </div>

      <p style={{ margin: "13px 0 9px", color: "var(--ink)", fontSize: 16, whiteSpace: "pre-wrap" }}>{item.content}</p>
      <div className="meta">
        User: {item.user_id} · #{item.channel} · Gửi lúc {dateText(item.created_at)}
      </div>

      {(item.recent_context || []).length > 0 && (
        <div className="evidence" style={{ marginTop: 11 }}>
          <b>Recent context</b>
          <div style={{ marginTop: 6, whiteSpace: "pre-wrap" }}>{item.recent_context.join("\n")}</div>
        </div>
      )}

      <small style={{ display: "block", marginTop: 10, color: "var(--ink-muted)", fontSize: 13 }}>
        <b style={{ color: "var(--ink)" }}>{item.model_category}</b> · {item.model_risk_level} risk ·{" "}
        {percent(item.model_confidence)} confidence · model: {item.model_used}
        <br />
        {item.model_reason}
        <br />
        Evidence: {(item.evidence || []).join(" · ") || "không có"}
      </small>

      <div className="field-row" style={{ marginTop: 13 }}>
        <input value={reviewer} onChange={(event) => setReviewer(event.target.value)} maxLength={100} aria-label="Tên reviewer" />
        <input
          value={note}
          onChange={(event) => setNote(event.target.value)}
          maxLength={1000}
          placeholder="Ghi chú của Admin (tùy chọn)"
          aria-label="Ghi chú của Admin"
        />
      </div>

      <div className="record-actions">
        <button type="button" className="small icon-btn" onClick={() => decide("allow")} disabled={Boolean(busy)}>
          <CheckIcon size={13} weight="bold" />
          {busy === "allow" ? "..." : "Allow"}
        </button>
        <button type="button" className="secondary small icon-btn" onClick={() => decide("warn")} disabled={Boolean(busy)}>
          <WarningCircleIcon size={13} weight="bold" />
          {busy === "warn" ? "..." : "Warn"}
        </button>
        <button type="button" className="danger small icon-btn" onClick={() => decide("hide")} disabled={Boolean(busy)}>
          <EyeSlashIcon size={13} weight="bold" />
          {busy === "hide" ? "..." : "Hide"}
        </button>
      </div>
    </article>
  );
}
