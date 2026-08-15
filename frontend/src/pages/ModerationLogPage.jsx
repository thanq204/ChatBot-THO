import { useCallback, useEffect, useState } from "react";
import { Check, WarningCircle, EyeSlash, ArrowsClockwise } from "@phosphor-icons/react";
import Card from "../components/Card.jsx";
import StatTile from "../components/StatTile.jsx";
import Badge from "../components/Badge.jsx";
import { SkeletonBlock } from "../components/Skeleton.jsx";
import { ErrorState, EmptyState } from "../components/StatePanels.jsx";
import { moderation, ops } from "../api/client.js";
import {
  moderationCategoryLabel,
  moderationActionLabel,
  MODERATION_ACTION_COLORS,
  severityLabel,
  auditEventLabel,
  ADMIN_ACTION_EVENT_TYPES,
  describeAuditEntry,
  auditToneFor,
} from "../lib/taxonomy.js";
import { relativeTime, percent } from "../lib/format.js";

export default function ModerationLogPage() {
  const [queue, setQueue] = useState([]);
  const [audit, setAudit] = useState([]);
  const [adminActions, setAdminActions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const load = useCallback(() => {
    setError(null);
    return Promise.all([moderation.reviewQueue(), moderation.auditLogs(), ops.audit()])
      .then(([pending, entries, realAudit]) => {
        setQueue(pending);
        setAudit(entries);
        setAdminActions(realAudit.filter((item) => ADMIN_ACTION_EVENT_TYPES.has(item.event_type)));
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  if (error) {
    return (
      <div className="page-grid">
        <ErrorState message={`Không lấy được nhật ký kiểm duyệt: ${error}`} onRetry={load} />
      </div>
    );
  }

  return (
    <div className="page-grid">
      <div className="page-grid__row">
        <div className="span-3">
          <StatTile label="Đang chờ review (thử nghiệm)" value={loading ? 0 : queue.length} tone="alert" />
        </div>
        <div className="span-3">
          <StatTile label="Hành động Admin đã ghi" value={loading ? 0 : adminActions.length} tone="brand" />
        </div>
        <div className="span-3">
          <StatTile label="Quyết định thử nghiệm đã ghi" value={loading ? 0 : audit.length} tone="brand" />
        </div>
      </div>

      <div className="page-grid__row">
        <Card
          title="Cases đang chờ (thử nghiệm)"
          className="span-7"
          action={
            <button type="button" className="btn btn--ghost" onClick={load} disabled={loading}>
              <ArrowsClockwise size={14} className={loading ? "spin-icon" : undefined} /> Làm mới
            </button>
          }
        >
          <p className="muted small">
            Danh sách này đến từ tin nhắn giả lập gửi ở "Khu thử nghiệm AI", không phải tin nhắn thật từ Discord/Telegram.
          </p>
          {loading && <SkeletonBlock height={260} />}
          {!loading && queue.length === 0 && <EmptyState message="Không có nội dung nào đang chờ review." />}
          {!loading && queue.length > 0 && (
            <div className="list">
              {queue.map((item) => (
                <ReviewRow key={item.review_id} item={item} onDecided={load} onError={setError} />
              ))}
            </div>
          )}
        </Card>

        <Card title="Nhật ký hành động Admin" className="span-5" delay={0.05}>
          <p className="muted small">Những gì Admin/Mod đã thực sự làm trên các case thật: xoá tin, timeout, kick, ban, gửi thông báo...</p>
          {loading && <SkeletonBlock height={260} />}
          {!loading && adminActions.length === 0 && <EmptyState message="Chưa có hành động Admin nào được ghi nhận." />}
          {!loading && adminActions.length > 0 && (
            <div className="list">
              {adminActions.map((item) => (
                <div className="list-row" key={item.audit_id}>
                  <div className="list-row__head">
                    <span className="list-row__title">{item.actor}</span>
                    <Badge tone={auditToneFor(item)}>{auditEventLabel(item.event_type)}</Badge>
                  </div>
                  <p className="list-row__body">{describeAuditEntry(item)}</p>
                  <span className="list-row__meta">
                    {item.incident_id ? `${item.incident_id} · ` : ""}
                    {relativeTime(item.created_at)}
                  </span>
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>

      <div className="page-grid__row">
        <Card title="Nhật ký quyết định (thử nghiệm)" className="span-12" delay={0.1}>
          <p className="muted small">
            Quyết định allow/warn/hide trên các tin nhắn giả lập gửi ở "Khu thử nghiệm AI" — không phải hành động trên tin nhắn
            thật.
          </p>
          {loading && <SkeletonBlock height={160} />}
          {!loading && audit.length === 0 && <EmptyState message="Chưa có quyết định thử nghiệm nào." />}
          {!loading && audit.length > 0 && (
            <div className="list">
              {audit.map((item) => (
                <div className="list-row" key={item.audit_id}>
                  <div className="list-row__head">
                    <span className="list-row__title">{item.user_id}</span>
                    <Badge tone={MODERATION_ACTION_COLORS[item.admin_action]}>{moderationActionLabel(item.admin_action)}</Badge>
                  </div>
                  <span className="list-row__meta">
                    {moderationCategoryLabel(item.model_category)} ({percent(item.model_confidence)}) → {item.reviewer} ·{" "}
                    {relativeTime(item.reviewed_at)}
                  </span>
                  {item.admin_note && <p className="list-row__body">{item.admin_note}</p>}
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}

function ReviewRow({ item, onDecided, onError }) {
  const [reviewer, setReviewer] = useState("Admin");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState("");

  async function decide(action) {
    setBusy(action);
    try {
      await moderation.decide(item.review_id, { action, reviewer: reviewer.trim() || "Admin", admin_note: note.trim() });
      await onDecided();
    } catch (err) {
      onError(err.message);
    } finally {
      setBusy("");
    }
  }

  return (
    <div className="list-row">
      <div className="list-row__head">
        <span className="list-row__meta">{item.review_id}</span>
        <div className="chip-row" style={{ marginTop: 0 }}>
          <Badge tone={MODERATION_ACTION_COLORS[item.model_action]}>{moderationActionLabel(item.model_action)}</Badge>
          {item.fallback_used && <span className="chip">mock fallback</span>}
        </div>
      </div>

      <p className="list-row__title" style={{ fontSize: 14 }}>
        {item.content}
      </p>
      <span className="list-row__meta">
        User: {item.user_id} · #{item.channel} · {relativeTime(item.created_at)}
      </span>

      {(item.recent_context || []).length > 0 && (
        <div className="quote" style={{ marginTop: 4 }}>
          <span className="section-heading">Recent context</span>
          <p style={{ marginTop: 6, whiteSpace: "pre-wrap" }}>{item.recent_context.join("\n")}</p>
        </div>
      )}

      <p className="list-row__body">
        <strong>{moderationCategoryLabel(item.model_category)}</strong> · {severityLabel(item.model_risk_level)} risk ·{" "}
        {percent(item.model_confidence)} confidence · model: {item.model_used}
        <br />
        {item.model_reason}
        <br />
        Evidence: {(item.evidence || []).join(" · ") || "không có"}
      </p>

      <div className="field-row">
        <input value={reviewer} onChange={(event) => setReviewer(event.target.value)} maxLength={100} aria-label="Tên reviewer" placeholder="Reviewer" />
        <input value={note} onChange={(event) => setNote(event.target.value)} maxLength={1000} placeholder="Ghi chú (tùy chọn)" aria-label="Ghi chú" />
      </div>

      <div className="list-row__actions">
        <button type="button" className="btn btn--primary" onClick={() => decide("allow")} disabled={Boolean(busy)}>
          <Check size={13} weight="bold" /> {busy === "allow" ? "..." : "Cho phép"}
        </button>
        <button type="button" className="btn btn--ghost" onClick={() => decide("warn")} disabled={Boolean(busy)}>
          <WarningCircle size={13} weight="bold" /> {busy === "warn" ? "..." : "Cảnh báo"}
        </button>
        <button type="button" className="btn btn--ghost" onClick={() => decide("hide")} disabled={Boolean(busy)}>
          <EyeSlash size={13} weight="bold" /> {busy === "hide" ? "..." : "Ẩn"}
        </button>
      </div>
    </div>
  );
}
