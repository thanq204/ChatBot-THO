import { TrayIcon } from "@phosphor-icons/react";
import { PlatformMark, hasPlatformMark, platformLabel } from "../PlatformIcon.jsx";
import SeverityIcon from "../SeverityIcon.jsx";
import { Empty, Panel, SkeletonRows, dateText, percent } from "../ui.jsx";

/** The connectors can deliver the same message twice (a re-scan, or a reply that
 *  reopens a thread). The old build stripped duplicate rows out of the DOM with a
 *  MutationObserver; here the list is filtered before it is ever rendered. */
export function dedupeIncidents(incidents) {
  const seen = new Set();
  return incidents.filter((item) => {
    const key = `${item.platform}|${item.title}|${item.summary}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

export default function IncidentQueue({ incidents, loading, platform, onPlatformChange, onSelect, selectedId }) {
  const rows = dedupeIncidents(incidents);

  return (
    <Panel
      title="Cases cần Admin xem"
      subtitle="Các message có rủi ro hoặc cần người duyệt. Bấm vào từng case để mở message gốc."
      actions={
        <select value={platform} onChange={(event) => onPlatformChange(event.target.value)} aria-label="Lọc theo nền tảng">
          <option value="">All platforms</option>
          <option value="discord">Discord</option>
          <option value="telegram">Telegram</option>
          <option value="web">Web</option>
          <option value="zalo">Zalo</option>
          <option value="messenger">Messenger</option>
        </select>
      }
    >
      {loading ? (
        <SkeletonRows count={3} />
      ) : rows.length === 0 ? (
        <Empty icon={TrayIcon}>Chưa có incident cho bộ lọc này. Hãy Scan connector thật.</Empty>
      ) : (
        <div className="stack">
          {rows.map((item) => (
            <button
              key={item.incident_id}
              type="button"
              className={`row-card ${selectedId === item.incident_id ? "is-active" : ""}`.trim()}
              onClick={() => onSelect(item.incident_id)}
            >
              <span className="pill-row">
                <span className={`pill pill-icon ${item.severity}`}>
                  <SeverityIcon severity={item.severity} />
                  {item.severity}
                </span>
                <span className="pill pill-icon">
                  {hasPlatformMark(item.platform) && <PlatformMark platform={item.platform} size={11} />}
                  {platformLabel(item.platform)}
                </span>
              </span>
              <strong>{item.title}</strong>
              <p>{item.summary}</p>
              <div className="meta" style={{ marginTop: 8 }}>
                {item.incident_id} · {item.message_count} message · risk {percent(item.risk_score)} · {item.status} ·{" "}
                {dateText(item.updated_at)}
              </div>
            </button>
          ))}
        </div>
      )}
    </Panel>
  );
}
