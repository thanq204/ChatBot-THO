import { useCallback, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle, Flag } from "@phosphor-icons/react";
import LoadMore, { useLoadMore } from "./LoadMore.jsx";
import { SkeletonBlock } from "./Skeleton.jsx";
import { ErrorState, EmptyState } from "./StatePanels.jsx";
import { ops } from "../api/client.js";
import { queryKeys } from "../lib/queryClient.js";
import { platformLabel } from "../lib/taxonomy.js";
import { relativeTime } from "../lib/format.js";

const REPORT_STEP = 8;

/**
 * Inbox for /report submissions. These come from members rather than from the
 * agent, so they sit next to the AI queue instead of inside it.
 */
export default function MemberReportInbox() {
  const queryClient = useQueryClient();
  const [actionError, setActionError] = useState("");
  const [busyId, setBusyId] = useState("");
  const [showHandled, setShowHandled] = useState(false);

  const reportsQuery = useQuery({ queryKey: queryKeys.memberReports, queryFn: ops.memberReports });

  const load = useCallback(() => {
    setActionError("");
    queryClient.invalidateQueries({ queryKey: queryKeys.memberReports });
  }, [queryClient]);

  async function setStatus(reportId, status) {
    setBusyId(reportId);
    setActionError("");
    try {
      const updated = await ops.updateMemberReport(reportId, { status });
      // Write the server's row straight into the cache: the list updates without
      // a refetch, and any other mounted view of it stays in step.
      queryClient.setQueryData(queryKeys.memberReports, (current) =>
        (current ?? []).map((item) => (item.report_id === reportId ? updated : item)),
      );
    } catch (err) {
      setActionError(err.message);
    } finally {
      setBusyId("");
    }
  }

  const error = actionError || reportsQuery.error?.message || "";

  // Derived before the early returns below: hooks cannot sit after a
  // conditional return, and useLoadMore needs the filtered list.
  const all = reportsQuery.data ?? [];
  const open = all.filter((item) => item.status === "open");
  const visible = showHandled ? all : open;
  const feed = useLoadMore(visible, REPORT_STEP, String(showHandled));

  if (reportsQuery.isPending) return <SkeletonBlock height={180} />;
  if (error) return <ErrorState message={error} onRetry={load} />;

  if (all.length === 0) {
    return <EmptyState message="Chưa có thành viên nào gửi /report." />;
  }

  return (
    <div className="stack">
      <div className="reports__head">
        <span className="muted small">
          <strong>{open.length}</strong> báo cáo chờ xử lý trên tổng {all.length}
        </span>
        <label className="reports__toggle">
          <input
            type="checkbox"
            checked={showHandled}
            onChange={(event) => setShowHandled(event.target.checked)}
          />
          Hiện cả báo cáo đã xử lý
        </label>
      </div>

      {visible.length === 0 ? (
        <EmptyState message="Không còn báo cáo nào chờ xử lý." />
      ) : (
        <div className="list">
          {feed.visible.map((report) => (
            <div className="list-row" key={report.report_id}>
              <div className="list-row__head">
                <span className="list-row__title">
                  <Flag size={13} weight="fill" /> {report.reporter_id}
                </span>
                <span className="list-row__meta">{relativeTime(report.created_at)}</span>
              </div>
              <p className="list-row__body">{report.details}</p>
              <span className="list-row__meta">
                {platformLabel(report.platform)} · kênh {report.channel_id}
              </span>
              <div className="list-row__actions">
                {report.status === "open" ? (
                  <button
                    type="button"
                    className="btn btn--ghost"
                    onClick={() => setStatus(report.report_id, "reviewed")}
                    disabled={busyId === report.report_id}
                  >
                    <CheckCircle size={13} weight="bold" />
                    {busyId === report.report_id ? "Đang lưu..." : "Đánh dấu đã xử lý"}
                  </button>
                ) : (
                  <>
                    <span className="reports__done">
                      <CheckCircle size={13} weight="fill" /> Đã xử lý
                    </span>
                    <button
                      type="button"
                      className="btn btn--ghost"
                      onClick={() => setStatus(report.report_id, "open")}
                      disabled={busyId === report.report_id}
                    >
                      Mở lại
                    </button>
                  </>
                )}
              </div>
            </div>
          ))}
          <LoadMore
            remaining={feed.remaining}
            step={REPORT_STEP}
            unit="báo cáo"
            onMore={feed.showMore}
            canCollapse={feed.canCollapse}
            onCollapse={feed.collapse}
          />
        </div>
      )}
    </div>
  );
}
