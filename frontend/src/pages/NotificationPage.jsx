import { useCallback, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { PaperPlaneTilt } from "@phosphor-icons/react";
import Card from "../components/Card.jsx";
import LoadMore, { useLoadMore } from "../components/LoadMore.jsx";
import { SkeletonBlock } from "../components/Skeleton.jsx";
import { ErrorState, EmptyState } from "../components/StatePanels.jsx";
import { ops } from "../api/client.js";
import { queryKeys } from "../lib/queryClient.js";
import { platformLabel } from "../lib/taxonomy.js";
import { relativeTime } from "../lib/format.js";
import { useAuth } from "../auth/AuthProvider.jsx";

const NOTIFY_PLATFORM_OPTIONS = [
  { value: "telegram", label: "Telegram" },
  { value: "discord", label: "Discord" },
];

// The history card sits beside the compose form, so it should stay about as
// tall as the form rather than stretching the row to the length of the archive.
const HISTORY_STEP = 5;

export default function NotificationPage() {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const queryClient = useQueryClient();
  const [selectedPlatforms, setSelectedPlatforms] = useState([]);
  const [message, setMessage] = useState("");
  const [sending, setSending] = useState(false);
  const [result, setResult] = useState(null);

  // Shared with the overview page: whichever loads first serves both.
  const platformsQuery = useQuery({ queryKey: queryKeys.platforms, queryFn: ops.platforms, retry: false });
  const platformStatuses = platformsQuery.data ?? (platformsQuery.isError ? [] : null);

  const historyQuery = useQuery({
    queryKey: queryKeys.audit(),
    queryFn: () => ops.audit(),
    enabled: isAdmin,
    select: (rows) => rows.filter((item) => item.event_type === "admin_announcement"),
  });
  const history = historyQuery.data ?? null;
  const historyLoading = isAdmin && historyQuery.isPending;
  const historyError = historyQuery.error?.message ?? null;

  const loadHistory = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: queryKeys.audit() });
  }, [queryClient]);

  const historyFeed = useLoadMore(history, HISTORY_STEP);

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
              <span className="muted small">Người gửi được lấy tự động từ tài khoản Admin đang đăng nhập.</span>
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

        {isAdmin ? <Card title="Lịch sử thông báo" className="span-6" delay={0.05}>
          {historyLoading && <SkeletonBlock height={240} />}
          {!historyLoading && historyError && <ErrorState message={historyError} onRetry={loadHistory} />}
          {!historyLoading && !historyError && (!history || history.length === 0) && (
            <EmptyState message="Chưa có thông báo nào được gửi." />
          )}
          {!historyLoading && !historyError && history && history.length > 0 && (
            <>
              <div className="list">
                {historyFeed.visible.map((item) => (
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
              <LoadMore
                remaining={historyFeed.remaining}
                step={HISTORY_STEP}
                unit="thông báo"
                onMore={historyFeed.showMore}
                canCollapse={historyFeed.canCollapse}
                onCollapse={historyFeed.collapse}
              />
            </>
          )}
        </Card> : <Card title="Thông báo dành cho Mod" className="span-6" delay={0.05}>
          <div className="list">
            <div className="list-row"><strong>Quyền riêng tư</strong><p className="muted small">Lịch sử thông báo chỉ dành cho Admin để bảo vệ dữ liệu vận hành.</p></div>
            <div className="list-row"><strong>Khi cần hỗ trợ</strong><p className="muted small">Hãy liên hệ Admin nếu cần kiểm tra thông báo đã gửi hoặc thay đổi kênh nhận.</p></div>
            <div className="list-row"><strong>Vai trò của bạn</strong><p className="muted small">Bạn vẫn có thể theo dõi và xử lý các trường hợp kiểm duyệt được phân công.</p></div>
          </div>
        </Card>}
      </div>
    </div>
  );
}
