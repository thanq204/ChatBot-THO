import { useCallback, useEffect, useMemo, useState } from "react";
import Card from "../components/Card.jsx";
import IncidentDetailModal from "../components/IncidentDetailModal.jsx";
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
} from "../lib/taxonomy.js";
import { actorFromTitle, caseHeadline, primaryCategory } from "../lib/incidents.js";
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
  const [statusFilter, setStatusFilter] = useState("");
  const [openId, setOpenId] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    ops
      .incidents({ platform: platformFilter || undefined, status: statusFilter || undefined })
      .then(setIncidents)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [platformFilter, statusFilter]);

  useEffect(() => {
    load();
  }, [load]);

  const closeDetail = useCallback(() => setOpenId(null), []);

  const counts = useMemo(() => {
    const rows = incidents ?? [];
    return {
      total: rows.length,
      critical: rows.filter((item) => item.severity === "critical").length,
      waiting: rows.filter((item) => item.status === "open").length,
    };
  }, [incidents]);

  const openIncident = useMemo(
    () => (incidents ?? []).find((item) => item.incident_id === openId) ?? null,
    [incidents, openId],
  );

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
          className="span-12"
          action={
            <div className="case-filters">
              <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)} aria-label="Lọc theo trạng thái">
                <option value="">Mọi trạng thái</option>
                {STATUS_OPTIONS.map((status) => (
                  <option key={status} value={status}>
                    {statusLabel(status)}
                  </option>
                ))}
              </select>
              <select value={platformFilter} onChange={(event) => setPlatformFilter(event.target.value)} aria-label="Lọc theo nền tảng">
                {PLATFORM_OPTIONS.map((item) => (
                  <option key={item.value} value={item.value}>
                    {item.label}
                  </option>
                ))}
              </select>
            </div>
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
            <>
              <p className="case-tally">
                <strong>{counts.total}</strong> case
                <span className="case-tally__sep">·</span>
                <strong>{counts.critical}</strong> nghiêm trọng
                <span className="case-tally__sep">·</span>
                <strong>{counts.waiting}</strong> chưa ai xử lý
                <span className="case-tally__sep">·</span>
                bấm vào một case để xem chi tiết
              </p>
              <div className="case-list">
                {incidents.map((item) => (
                  <CaseRow key={item.incident_id} incident={item} onOpen={setOpenId} />
                ))}
              </div>
            </>
          )}
        </Card>
      </div>

      <IncidentDetailModal
        incidentId={openId}
        headline={openIncident ? caseHeadline(openIncident) : ""}
        onClose={closeDetail}
        onUpdated={load}
      />
    </div>
  );
}

/**
 * One scannable card per case. The AI explanation is deliberately left out here:
 * it is near-identical across rows, so it hid the fields that actually differ.
 */
function CaseRow({ incident, onOpen }) {
  const actor = actorFromTitle(incident.title);

  return (
    <button
      type="button"
      className="case-row"
      style={{ "--case-accent": SEVERITY_COLORS[incident.severity] ?? "var(--text-muted)" }}
      onClick={() => onOpen(incident.incident_id)}
    >
      <span className="case-row__title">{categoryLabel(primaryCategory(incident))}</span>
      <span className="case-row__status" style={{ color: STATUS_COLORS[incident.status] }}>
        {statusLabel(incident.status)}
      </span>
      <span className="case-row__meta">
        <span className="case-row__severity">{severityLabel(incident.severity)}</span>
        {actor && <span>{actor}</span>}
        <span>{platformLabel(incident.platform)}</span>
        <span>{incident.message_count} tin</span>
        <span>risk {percent(incident.risk_score)}</span>
        <span>{relativeTime(incident.updated_at)}</span>
      </span>
    </button>
  );
}
