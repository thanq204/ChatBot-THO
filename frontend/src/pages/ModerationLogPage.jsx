import { useCallback } from "react";
import { useQueries, useQueryClient } from "@tanstack/react-query";
import Card from "../components/Card.jsx";
import StatTile from "../components/StatTile.jsx";
import Badge from "../components/Badge.jsx";
import { SkeletonBlock } from "../components/Skeleton.jsx";
import { ErrorState, EmptyState } from "../components/StatePanels.jsx";
import { moderation, ops } from "../api/client.js";
import { queryKeys } from "../lib/queryClient.js";
import {
  moderationCategoryLabel,
  moderationActionLabel,
  MODERATION_ACTION_COLORS,
  auditEventLabel,
  ADMIN_ACTION_EVENT_TYPES,
  describeAuditEntry,
  auditToneFor,
} from "../lib/taxonomy.js";
import { relativeTime, percent } from "../lib/format.js";

export default function ModerationLogPage() {
  const queryClient = useQueryClient();

  const [auditQuery, adminActionsQuery] = useQueries({
    queries: [
      { queryKey: queryKeys.moderationAuditLogs, queryFn: moderation.auditLogs },
      {
        queryKey: queryKeys.audit(),
        queryFn: () => ops.audit(),
        select: (rows) => rows.filter((item) => ADMIN_ACTION_EVENT_TYPES.has(item.event_type)),
      },
    ],
  });

  const audit = auditQuery.data ?? [];
  const adminActions = adminActionsQuery.data ?? [];
  const loading = auditQuery.isPending || adminActionsQuery.isPending;
  const error = (auditQuery.error || adminActionsQuery.error)?.message ?? null;

  const load = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: queryKeys.moderationAuditLogs });
    queryClient.invalidateQueries({ queryKey: queryKeys.audit() });
  }, [queryClient]);

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
        <div className="span-6">
          <StatTile label="Hành động Admin đã ghi" value={loading ? 0 : adminActions.length} tone="brand" />
        </div>
        <div className="span-6">
          <StatTile label="Quyết định thử nghiệm đã ghi" value={loading ? 0 : audit.length} tone="brand" />
        </div>
      </div>

      <div className="page-grid__row">
        <Card title="Nhật ký hành động Admin" className="span-12">
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
        <Card title="Nhật ký quyết định (thử nghiệm)" className="span-12" delay={0.05}>
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
