import { useCallback, useEffect, useState } from "react";
import { Tray } from "@phosphor-icons/react";
import Card from "../components/Card.jsx";
import Badge from "../components/Badge.jsx";
import { SkeletonBlock, SkeletonLine } from "../components/Skeleton.jsx";
import { ErrorState, EmptyState } from "../components/StatePanels.jsx";
import { ops } from "../api/client.js";
import {
  platformLabel,
  severityLabel,
  SEVERITY_COLORS,
  statusLabel,
  STATUS_COLORS,
  categoryLabel,
  decisionLabel,
  DECISION_COLORS,
} from "../lib/taxonomy.js";
import { relativeTime, percent } from "../lib/format.js";

const PLATFORM_OPTIONS = [
  { value: "", label: "Mọi nền tảng" },
  { value: "discord", label: "Discord" },
  { value: "telegram", label: "Telegram" },
  { value: "web", label: "Web" },
  { value: "zalo", label: "Zalo" },
  { value: "messenger", label: "Messenger" },
];

const STATUS_OPTIONS = ["open", "monitoring", "resolved", "snoozed"];

export default function CommunityPage() {
  const [incidents, setIncidents] = useState(null);
  const [platformFilter, setPlatformFilter] = useState("");
  const [selectedId, setSelectedId] = useState(null);
  const [detail, setDetail] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [savingStatus, setSavingStatus] = useState(false);

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    ops
      .incidents({ platform: platformFilter || undefined })
      .then((rows) => {
        setIncidents(rows);
        setSelectedId((current) => {
          if (rows.length === 0) return null;
          if (current && rows.some((item) => item.incident_id === current)) return current;
          return rows[0].incident_id;
        });
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [platformFilter]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (!selectedId) {
      setDetail(null);
      return;
    }
    setDetailLoading(true);
    setDetailError(null);
    ops
      .incident(selectedId)
      .then(setDetail)
      .catch((err) => setDetailError(err.message))
      .finally(() => setDetailLoading(false));
  }, [selectedId]);

  const updateStatus = async (status) => {
    if (!selectedId) return;
    setSavingStatus(true);
    try {
      await ops.updateIncident(selectedId, { status });
      const refreshed = await ops.incident(selectedId);
      setDetail(refreshed);
      load();
    } catch (err) {
      setDetailError(err.message);
    } finally {
      setSavingStatus(false);
    }
  };

  if (error) {
    return (
      <div className="page-grid">
        <ErrorState message={`Không lấy được danh sách case: ${error}`} onRetry={load} />
      </div>
    );
  }

  return (
    <div className="page-grid">
      <div className="page-grid__row">
        <Card
          title="Cases cần Admin xem"
          className="span-5"
          action={
            <select value={platformFilter} onChange={(event) => setPlatformFilter(event.target.value)} aria-label="Lọc theo nền tảng">
              {PLATFORM_OPTIONS.map((item) => (
                <option key={item.value} value={item.value}>
                  {item.label}
                </option>
              ))}
            </select>
          }
        >
          {loading && (
            <div className="stack">
              <SkeletonLine width="90%" />
              <SkeletonBlock height={220} />
            </div>
          )}
          {!loading && (!incidents || incidents.length === 0) && (
            <EmptyState message="Chưa có case nào cho bộ lọc này. Hãy quét connector ở trang Tổng quan." />
          )}
          {!loading && incidents && incidents.length > 0 && (
            <div className="list">
              {incidents.map((item) => (
                <button
                  key={item.incident_id}
                  type="button"
                  className={`list-row ${selectedId === item.incident_id ? "is-active" : ""}`.trim()}
                  onClick={() => setSelectedId(item.incident_id)}
                >
                  <div className="list-row__head">
                    <span className="list-row__title">{item.title}</span>
                    <Badge tone={SEVERITY_COLORS[item.severity]}>{severityLabel(item.severity)}</Badge>
                  </div>
                  <p className="list-row__body">{item.summary}</p>
                  <span className="list-row__meta">
                    {platformLabel(item.platform)} · {item.message_count} tin · risk {percent(item.risk_score)} ·{" "}
                    {statusLabel(item.status)} · {relativeTime(item.updated_at)}
                  </span>
                </button>
              ))}
            </div>
          )}
        </Card>

        <Card title="Chi tiết case" className="span-7" delay={0.05}>
          {detailLoading && (
            <div className="stack">
              <SkeletonLine width="70%" />
              <SkeletonBlock height={260} />
            </div>
          )}
          {!detailLoading && detailError && <ErrorState message={detailError} onRetry={() => setSelectedId(selectedId)} />}
          {!detailLoading && !detailError && !detail && (
            <EmptyState message="Chọn một case bên trái để xem message, evidence và audit trail." action={<Tray size={22} weight="duotone" />} />
          )}
          {!detailLoading && !detailError && detail && (
            <IncidentDetailBody detail={detail} onStatusChange={updateStatus} savingStatus={savingStatus} />
          )}
        </Card>
      </div>
    </div>
  );
}

function IncidentDetailBody({ detail, onStatusChange, savingStatus }) {
  const { incident, messages = [], audit = [] } = detail;
  const root = messages.find((item) => !item.parent_message_id) || messages[0];

  return (
    <div className="stack">
      <div>
        <h3>{incident.title}</h3>
        <p className="muted">{incident.summary}</p>
      </div>

      <div className="chip-row">
        <Badge tone={SEVERITY_COLORS[incident.severity]}>{severityLabel(incident.severity)}</Badge>
        <Badge tone={STATUS_COLORS[incident.status]}>{statusLabel(incident.status)}</Badge>
        <span className="chip">{platformLabel(incident.platform)}</span>
        <span className="chip">risk {percent(incident.risk_score)}</span>
        {(incident.categories || []).map((category) => (
          <span key={category} className="chip">
            {categoryLabel(category)}
          </span>
        ))}
      </div>

      <div className="field-row">
        <label className="field">
          Trạng thái
          <select value={incident.status} disabled={savingStatus} onChange={(event) => onStatusChange(event.target.value)}>
            {STATUS_OPTIONS.map((status) => (
              <option key={status} value={status}>
                {statusLabel(status)}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          Phụ trách
          <span className="muted small">{incident.assigned_to || "Chưa gán"}</span>
        </label>
      </div>

      {root && (
        <div className="quote">
          <span className="section-heading">Message gốc</span>
          <p style={{ marginTop: 6 }}>{root.text}</p>
          <span className="muted small">
            {root.author_id} · {relativeTime(root.timestamp)}
          </span>
        </div>
      )}

      <div>
        <span className="section-heading">Messages trong case ({messages.length})</span>
        {messages.length === 0 ? (
          <EmptyState message="Case này chưa có message chi tiết." />
        ) : (
          <div className="list" style={{ marginTop: 8 }}>
            {messages.map((item, index) => (
              <div className="list-row" key={item.message_id || index}>
                <div className="list-row__head">
                  <span className="list-row__title">
                    {item.parent_message_id ? "Reply" : "Message gốc"} · {item.author_id}
                  </span>
                  <span className="list-row__meta">{relativeTime(item.timestamp)}</span>
                </div>
                <p className="list-row__body">{item.text}</p>
                <div className="chip-row">
                  {item.decision && <Badge tone={DECISION_COLORS[item.decision]}>{decisionLabel(item.decision)}</Badge>}
                  {item.category && <span className="chip">{categoryLabel(item.category)}</span>}
                  {item.risk_score != null && <span className="chip">risk {percent(item.risk_score)}</span>}
                </div>
                {item.explanation && <p className="muted small">Vì sao: {item.explanation}</p>}
              </div>
            ))}
          </div>
        )}
      </div>

      <div>
        <span className="section-heading">Audit trail</span>
        {audit.length === 0 ? (
          <EmptyState message="Chưa có audit trail cho case này." />
        ) : (
          <div className="list" style={{ marginTop: 8 }}>
            {audit.map((item) => (
              <div key={item.audit_id} className="list-row">
                <span className="list-row__meta">{relativeTime(item.created_at)}</span>
                <span className="list-row__title">
                  {item.event_type} · {item.actor}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
