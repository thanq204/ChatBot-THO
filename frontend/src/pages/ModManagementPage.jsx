import { useCallback, useEffect, useMemo, useState } from "react";
import Card from "../components/Card.jsx";
import StatTile from "../components/StatTile.jsx";
import Badge from "../components/Badge.jsx";
import { SkeletonBlock } from "../components/Skeleton.jsx";
import { ErrorState, EmptyState } from "../components/StatePanels.jsx";
import { ops } from "../api/client.js";
import { ADMIN_ACTION_EVENT_TYPES, describeAuditEntry, auditToneFor, auditEventLabel } from "../lib/taxonomy.js";
import { relativeTime } from "../lib/format.js";

// Short chip labels for the per-mod breakdown row. admin_platform_action
// entries are keyed by their platform action (ban/kick/...); everything
// else is keyed by its own event_type and falls back to auditEventLabel.
const ACTION_SHORT_LABELS = {
  dm: "DM cảnh báo",
  delete_message: "Xoá tin",
  timeout: "Timeout",
  kick: "Kick",
  ban: "Ban",
};

function breakdownKey(item) {
  return item.event_type === "admin_platform_action" ? item.payload?.action || "khác" : item.event_type;
}

function breakdownLabel(key) {
  return ACTION_SHORT_LABELS[key] || auditEventLabel(key);
}

/** No real Mod-account system exists yet, so "who are the mods" is derived
 * from whoever shows up as the actor on a real admin action — not a mocked
 * list, just the only identity source currently available. */
function groupByMod(entries) {
  const groups = new Map();
  for (const item of entries) {
    const actor = item.actor?.trim() || "Không rõ";
    if (actor.toLowerCase() === "system") continue;
    if (!groups.has(actor)) groups.set(actor, []);
    groups.get(actor).push(item);
  }
  return [...groups.entries()]
    .map(([actor, items]) => {
      const sorted = [...items].sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
      const counts = {};
      for (const item of sorted) {
        const key = breakdownKey(item);
        counts[key] = (counts[key] || 0) + 1;
      }
      return { actor, items: sorted, count: sorted.length, lastActive: sorted[0]?.created_at, counts };
    })
    .sort((a, b) => b.count - a.count);
}

export default function ModManagementPage() {
  const [audit, setAudit] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedMod, setSelectedMod] = useState(null);

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    ops
      .audit()
      .then((entries) => setAudit(entries.filter((item) => ADMIN_ACTION_EVENT_TYPES.has(item.event_type))))
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const mods = useMemo(() => groupByMod(audit || []), [audit]);
  const last24h = useMemo(() => {
    const since = Date.now() - 24 * 60 * 60 * 1000;
    return (audit || []).filter((item) => new Date(item.created_at).getTime() >= since).length;
  }, [audit]);

  const activeMod = mods.find((mod) => mod.actor === selectedMod) ?? mods[0] ?? null;

  return (
    <div className="page-grid">
      {error && (
        <div className="page-grid__row">
          <ErrorState message={`Không lấy được nhật ký Mod: ${error}`} onRetry={load} />
        </div>
      )}

      {!error && (
        <>
          <div className="page-grid__row">
            <div className="span-4">
              <StatTile label="Mod có hoạt động" value={loading ? 0 : mods.length} tone="brand" />
            </div>
            <div className="span-4">
              <StatTile label="Tổng hành động đã ghi" value={loading ? 0 : (audit || []).length} tone="brand" />
            </div>
            <div className="span-4">
              <StatTile label="Hành động trong 24h qua" value={loading ? 0 : last24h} tone="alert" />
            </div>
          </div>

          <div className="page-grid__row">
            <Card title="Danh sách Mod" className="span-5">
              <p className="muted small">
                Danh sách này lấy từ ai đã thực hiện hành động thật trên case (không phải danh bạ tài khoản — hệ thống chưa
                có bảng người dùng/Mod riêng).
              </p>
              {loading && <SkeletonBlock height={260} />}
              {!loading && mods.length === 0 && <EmptyState message="Chưa có Mod nào thực hiện hành động." />}
              {!loading && mods.length > 0 && (
                <div className="list">
                  {mods.map((mod) => (
                    <button
                      key={mod.actor}
                      type="button"
                      className={`list-row${activeMod?.actor === mod.actor ? " is-active" : ""}`}
                      onClick={() => setSelectedMod(mod.actor)}
                    >
                      <div className="list-row__head">
                        <span className="list-row__title">{mod.actor}</span>
                        <span className="list-row__meta">{mod.count} hành động</span>
                      </div>
                      <div className="chip-row">
                        {Object.entries(mod.counts).map(([key, count]) => (
                          <span key={key} className="chip">
                            {breakdownLabel(key)} ×{count}
                          </span>
                        ))}
                      </div>
                      <span className="list-row__meta">Hoạt động gần nhất: {relativeTime(mod.lastActive)}</span>
                    </button>
                  ))}
                </div>
              )}
            </Card>

            <Card title={activeMod ? `Nhật ký của ${activeMod.actor}` : "Nhật ký Mod"} className="span-7" delay={0.05}>
              {loading && <SkeletonBlock height={260} />}
              {!loading && !activeMod && <EmptyState message="Chọn một Mod bên trái để xem nhật ký chi tiết." />}
              {!loading && activeMod && (
                <div className="list">
                  {activeMod.items.map((item) => (
                    <div className="list-row" key={item.audit_id}>
                      <div className="list-row__head">
                        <Badge tone={auditToneFor(item)}>{auditEventLabel(item.event_type)}</Badge>
                        <span className="list-row__meta">{relativeTime(item.created_at)}</span>
                      </div>
                      <p className="list-row__body">{describeAuditEntry(item)}</p>
                      {item.incident_id && <span className="list-row__meta">{item.incident_id}</span>}
                    </div>
                  ))}
                </div>
              )}
            </Card>
          </div>
        </>
      )}
    </div>
  );
}
