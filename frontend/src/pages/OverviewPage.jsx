import { useCallback, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowRight,
  ArrowsClockwise,
  UsersThree,
  ChatCircleDots,
  ShieldWarning,
  ClockCountdown,
  WarningCircle,
  ShieldCheck,
  DiscordLogo,
  TelegramLogo,
  Sparkle,
  Flame,
  LinkBreak,
  Flag,
  CheckCircle,
  Broadcast,
  TrendUp,
  Tag,
  Check,
} from "@phosphor-icons/react";
import Card from "../components/Card.jsx";
import Counter from "../components/Counter.jsx";
import IncidentDetailModal from "../components/IncidentDetailModal.jsx";
import RankList from "../components/RankList.jsx";
import TrendChart from "../components/TrendChart.jsx";
import ActivityFeed from "../components/ActivityFeed.jsx";
import { SkeletonLine, SkeletonBlock } from "../components/Skeleton.jsx";
import { ErrorState, EmptyState } from "../components/StatePanels.jsx";
import { ops } from "../api/client.js";
import { useAuth } from "../auth/AuthProvider.jsx";
import { queryKeys } from "../lib/queryClient.js";
import {
  categoryLabel,
  platformLabel,
  CATEGORY_COLORS,
  decisionLabel,
  DECISION_COLORS,
  severityLabel,
} from "../lib/taxonomy.js";
import { caseHeadline } from "../lib/incidents.js";
import { relativeTime } from "../lib/format.js";

const TIME_WINDOWS = [
  { hours: 24, label: "24 Giờ", bucketHours: 1 },
  { hours: 48, label: "48 Giờ", bucketHours: 2 },
  { hours: 168, label: "7 Ngày", bucketHours: 6 },
];

function buildCategoryRanks(summary) {
  const entries = Object.entries(summary.by_category || {}).filter(([category]) => category !== "safe");
  const total = entries.reduce((sum, [, count]) => sum + count, 0) || 1;
  return entries
    .sort((a, b) => b[1] - a[1])
    .slice(0, 5)
    .map(([category, count]) => ({
      key: category,
      label: categoryLabel(category),
      value: count,
      share: Math.round((count / total) * 100),
      color: CATEGORY_COLORS[category] ?? "var(--accent-solid)",
    }));
}

/** Rich Headline KPI Card with tone, icon and sub-breakdown */
function KpiCard({ label, value, tone, meta, icon: Icon, subbar, isPercent = false }) {
  return (
    <div className={`kpi${tone ? ` kpi--${tone}` : " kpi--total"}`}>
      <div className="kpi__head">
        <span className="kpi__label">{label}</span>
        {Icon && (
          <span className="kpi__icon">
            <Icon size={18} weight="bold" />
          </span>
        )}
      </div>
      <span className="kpi__value">
        {isPercent ? `${value}%` : <Counter value={value} />}
      </span>
      {meta && <span className="kpi__meta">{meta}</span>}
      {subbar}
    </div>
  );
}

export default function OverviewPage() {
  const queryClient = useQueryClient();
  const { user } = useAuth();

  const [timeWindow, setTimeWindow] = useState(24);
  const [triageTab, setTriageTab] = useState("incidents");
  const [seeding, setSeeding] = useState(false);
  const [pullLimit, setPullLimit] = useState("100");
  const [syncing, setSyncing] = useState("");
  const [syncResult, setSyncResult] = useState(null);
  const [openId, setOpenId] = useState(null);
  const [actionError, setActionError] = useState(null);

  const activeWindowConfig = useMemo(
    () => TIME_WINDOWS.find((w) => w.hours === timeWindow) || TIME_WINDOWS[0],
    [timeWindow],
  );

  const summaryQuery = useQuery({ queryKey: queryKeys.analytics, queryFn: ops.analytics });
  const platformsQuery = useQuery({ queryKey: queryKeys.platforms, queryFn: ops.platforms });
  const timelineQuery = useQuery({
    queryKey: queryKeys.timeline(activeWindowConfig.hours, activeWindowConfig.bucketHours),
    queryFn: () => ops.timeline(activeWindowConfig.hours, activeWindowConfig.bucketHours),
  });
  const incidentsQuery = useQuery({
    queryKey: queryKeys.incidents(),
    queryFn: () => ops.incidents(),
  });
  const healthQuery = useQuery({
    queryKey: queryKeys.communityHealth(timeWindow <= 48 ? timeWindow : 48),
    queryFn: () => ops.communityHealth(timeWindow <= 48 ? timeWindow : 48),
  });
  const memberReportsQuery = useQuery({
    queryKey: ["member-reports"],
    queryFn: ops.memberReports,
  });
  const flaggedLinksQuery = useQuery({
    queryKey: ["flagged-links"],
    queryFn: ops.flaggedLinks,
  });

  const summary = summaryQuery.data ?? null;
  const platforms = platformsQuery.data ?? [];
  const timeline = timelineQuery.data ?? null;
  const incidents = incidentsQuery.data ?? [];
  const health = healthQuery.data ?? null;
  const memberReports = memberReportsQuery.data ?? [];
  const flaggedLinks = flaggedLinksQuery.data ?? [];

  const loading =
    summaryQuery.isPending || platformsQuery.isPending || timelineQuery.isPending || incidentsQuery.isPending;
  const healthLoading = healthQuery.isPending;

  const error =
    actionError ??
    (summaryQuery.error || platformsQuery.error || timelineQuery.error || incidentsQuery.error)?.message ??
    null;

  const load = useCallback(() => {
    setActionError(null);
    queryClient.invalidateQueries();
  }, [queryClient]);

  const closeDetail = useCallback(() => setOpenId(null), []);

  const openIncident = useMemo(
    () => incidents.find((item) => item.incident_id === openId) ?? null,
    [incidents, openId],
  );

  const recentIncidents = useMemo(
    () => [...incidents].sort((a, b) => new Date(b.updated_at) - new Date(a.updated_at)).slice(0, 5),
    [incidents],
  );

  const openReports = useMemo(
    () => memberReports.filter((r) => r.status === "open"),
    [memberReports],
  );

  const seedDemo = async () => {
    setSeeding(true);
    try {
      await ops.seedDemo();
      load();
    } catch (err) {
      setActionError(err.message);
    } finally {
      setSeeding(false);
    }
  };

  const syncPlatform = async (platform) => {
    setSyncing(platform);
    const limit = platform === "discord" ? pullLimit : "50";
    setSyncResult({ tone: "", text: `Đang quét dữ liệu từ ${platformLabel(platform)}...` });
    try {
      const pulled = await ops.pullPlatform(platform, limit);
      const text =
        pulled.received > 0
          ? `Đã nhận ${pulled.received} tin nhắn và phân tích ${pulled.analyzed} tin từ ${platformLabel(platform)}.`
          : `Không có tin nhắn mới từ ${platformLabel(platform)} kể từ lần quét trước.`;
      setSyncResult({ tone: "success", text });
      load();
    } catch (err) {
      setSyncResult({ tone: "error", text: err.message });
    } finally {
      setSyncing("");
    }
  };

  const handleMarkReportReviewed = async (reportId) => {
    try {
      await ops.updateMemberReport(reportId, {
        status: "reviewed",
        actor: user?.display_name || user?.email || "Admin",
      });
      queryClient.invalidateQueries({ queryKey: ["member-reports"] });
    } catch (err) {
      setActionError(err.message);
    }
  };

  const retry = () => {
    setActionError(null);
    queryClient.invalidateQueries();
  };

  if (error) {
    return (
      <div className="page-grid">
        <ErrorState message={`Không lấy được dữ liệu: ${error}`} onRetry={retry} />
      </div>
    );
  }

  // Calculated Metrics
  const totalAnalyzed = summary?.messages_analyzed || 0;
  const allowCount = summary?.by_decision?.allow || 0;
  const violations = totalAnalyzed - allowCount;
  const safetyRate = totalAnalyzed > 0 ? ((allowCount / totalAnalyzed) * 100).toFixed(1) : "100.0";
  const safetyTone = Number(safetyRate) >= 95 ? "safety" : Number(safetyRate) >= 85 ? "warn" : "critical";

  const discordCount = summary?.by_platform?.discord || 0;
  const teleCount = summary?.by_platform?.telegram || 0;
  const platformTotal = discordCount + teleCount || 1;
  const discordPct = Math.round((discordCount / platformTotal) * 100);
  const telePct = Math.round((teleCount / platformTotal) * 100);

  const categoryRanks = summary ? buildCategoryRanks(summary) : [];
  const decisionRows = summary ? Object.entries(summary.by_decision).sort((a, b) => b[1] - a[1]) : [];

  // Filter platforms: only discord and telegram
  const activePlatforms = platforms.filter(
    (p) => p.platform === "discord" || p.platform === "telegram",
  );

  return (
    <div className="page-grid">
      {/* 1. Header: Command Center & Dynamic Filter Bar */}
      <div className="span-12 overview-header">
        <div className="overview-header__main">
          <div className="overview-header__title-row">
            <h1 className="overview-header__title">Trung tâm Giám sát AI</h1>
            <span className="overview-header__live-tag">
              <span className="live-pulse" />
              Bot Discord & Telegram Trực tuyến
            </span>
          </div>
          <p className="overview-header__desc">
            Chào mừng trở lại{user?.display_name ? `, ${user.display_name}` : ""}! Hệ sinh thái bảo vệ cộng đồng đang hoạt động theo thời gian thực.
          </p>
        </div>

        <div className="overview-header__controls">
          <div className="time-filter-group" role="group" aria-label="Bộ lọc thời gian">
            {TIME_WINDOWS.map((win) => (
              <button
                key={win.hours}
                type="button"
                className={`time-filter-btn${timeWindow === win.hours ? " is-active" : ""}`}
                onClick={() => setTimeWindow(win.hours)}
              >
                {win.label}
              </button>
            ))}
          </div>

          <button
            type="button"
            className="btn btn--ghost"
            onClick={load}
            title="Làm mới dữ liệu toàn hệ thống"
          >
            <ArrowsClockwise size={14} className={loading ? "spin-icon" : undefined} />
            Làm mới
          </button>

          <button
            type="button"
            className="btn btn--primary"
            onClick={seedDemo}
            disabled={seeding}
          >
            <Sparkle size={14} weight="fill" />
            {seeding ? "Đang nạp demo..." : "Nạp demo"}
          </button>
        </div>
      </div>

      {/* 2. Smart Multi-Dimensional KPI Grid */}
      <div className="kpi-row span-12">
        {loading && (
          <>
            <SkeletonBlock height={100} />
            <SkeletonBlock height={100} />
            <SkeletonBlock height={100} />
            <SkeletonBlock height={100} />
          </>
        )}
        {!loading && summary && (
          <>
            <KpiCard
              label="Tin nhắn đã quét"
              value={summary.messages_analyzed}
              icon={ChatCircleDots}
              meta="Tổng lưu lượng tin nhắn đã qua AI"
              subbar={
                <div className="kpi-subbar">
                  <div className="kpi-subbar__track">
                    <span className="kpi-subbar__fill--discord" style={{ width: `${discordPct}%` }} />
                    <span className="kpi-subbar__fill--telegram" style={{ width: `${telePct}%` }} />
                  </div>
                  <div className="kpi-subbar__labels">
                    <span className="kpi-subbar__item">
                      <em className="kpi-subbar__dot kpi-subbar__dot--discord" /> Discord {discordPct}%
                    </span>
                    <span className="kpi-subbar__item">
                      <em className="kpi-subbar__dot kpi-subbar__dot--telegram" /> Telegram {telePct}%
                    </span>
                  </div>
                </div>
              }
            />

            <KpiCard
              label="Tỷ lệ An toàn Cộng đồng"
              value={safetyRate}
              tone={safetyTone}
              icon={ShieldCheck}
              isPercent={true}
              meta={`${allowCount.toLocaleString("vi-VN")} tin an toàn · ${violations} vi phạm chặn`}
            />

            <KpiCard
              label="Sự cố đang mở"
              value={summary.open_incidents}
              tone={summary.critical_incidents > 0 ? "critical" : summary.open_incidents > 0 ? "alert" : "total"}
              icon={ClockCountdown}
              meta={
                summary.critical_incidents > 0
                  ? `⚠️ Có ${summary.critical_incidents} sự cố Nghiêm trọng cần xử lý`
                  : "Chờ Quản trị viên xử lý"
              }
            />

            <KpiCard
              label="Thành viên & Hoạt động"
              value={health?.unique_members ?? 0}
              icon={UsersThree}
              meta={
                health
                  ? `+${health.new_members} mới · ${health.messages_total.toLocaleString("vi-VN")} tin/${activeWindowConfig.label}`
                  : "Chỉ số tương tác cộng đồng"
              }
            />
          </>
        )}
      </div>

      {/* 3. Analytics & Platform Gateway Row */}
      <div className="page-grid__row">
        <Card
          title={`Xu hướng Vi phạm theo Giờ (${activeWindowConfig.label} qua)`}
          className="span-7"
          delay={0.02}
        >
          {loading && <SkeletonBlock height={260} />}
          {!loading && timeline && timeline.scanned_total > 0 && <TrendChart buckets={timeline.buckets} />}
          {!loading && (!timeline || timeline.scanned_total === 0) && (
            <EmptyState
              message={`Chưa có dữ liệu tin nhắn trong ${activeWindowConfig.label} qua.`}
              action={
                <button type="button" className="btn btn--primary" onClick={seedDemo} disabled={seeding}>
                  {seeding ? "Đang nạp..." : "Nạp dữ liệu demo"}
                </button>
              }
            />
          )}
        </Card>

        <Card
          title="Trung tâm Giám sát Bot (Gateway)"
          className="span-5"
          delay={0.05}
        >
          {loading && <SkeletonBlock height={260} />}
          {!loading && (
            <>
              <p className="muted small">
                Bot Discord và Telegram tự động phân loại vi phạm theo thời gian thực khi kết nối.
              </p>

              <div className="platform-gateway-grid">
                {activePlatforms.map((status) => {
                  const isDiscord = status.platform === "discord";
                  const Icon = isDiscord ? DiscordLogo : TelegramLogo;
                  const count = isDiscord ? discordCount : teleCount;

                  return (
                    <div key={status.platform} className="platform-gateway-card">
                      <div className="platform-gateway-card__head">
                        <div className="platform-gateway-card__title">
                          <Icon
                            size={22}
                            weight="fill"
                            className={
                              isDiscord
                                ? "platform-gateway-card__icon--discord"
                                : "platform-gateway-card__icon--telegram"
                            }
                          />
                          {platformLabel(status.platform)}
                        </div>
                        <span
                          className={`platform-gateway-card__badge ${
                            status.connected
                              ? "platform-gateway-card__badge--active"
                              : "platform-gateway-card__badge--inactive"
                          }`}
                        >
                          {status.connected && <span className="live-pulse" />}
                          {status.connected ? "Đang hoạt động" : "Chờ kết nối"}
                        </span>
                      </div>

                      <div className="platform-gateway-card__body">
                        <span className="platform-gateway-card__count">
                          {count.toLocaleString("vi-VN")}
                        </span>
                        <span className="platform-gateway-card__sub">tin nhắn đã phân tích</span>
                      </div>

                      <div className="platform-gateway-card__foot">
                        <button
                          type="button"
                          className="btn btn--ghost"
                          style={{ width: "100%", justifyContent: "center", fontSize: 12 }}
                          onClick={() => syncPlatform(status.platform)}
                          disabled={Boolean(syncing)}
                        >
                          <ArrowsClockwise
                            size={14}
                            className={syncing === status.platform ? "spin-icon" : undefined}
                          />
                          {syncing === status.platform ? "Đang quét..." : `Quét ${platformLabel(status.platform)}`}
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>

              <div className="platform-sync" style={{ marginTop: 14 }}>
                <label className="platform-sync__limit">
                  Số tin quét bù:
                  <select value={pullLimit} onChange={(e) => setPullLimit(e.target.value)}>
                    <option value="50">50 tin</option>
                    <option value="100">100 tin</option>
                    <option value="500">500 tin</option>
                  </select>
                </label>
                {syncResult && (
                  <p className={`platform-sync__result platform-sync__result--${syncResult.tone}`}>
                    {syncResult.text}
                  </p>
                )}
              </div>
            </>
          )}
        </Card>
      </div>

      {/* 4. Community Vibe & AI Insights Row */}
      <div className="page-grid__row">
        <Card title={`Sức khoẻ Cộng đồng (${activeWindowConfig.label})`} className="span-4" delay={0.08}>
          {healthLoading && <SkeletonBlock height={220} />}
          {!healthLoading && !health && <EmptyState message="Chưa có dữ liệu cộng đồng." />}
          {!healthLoading && health && (
            <>
              <div className="health-pair">
                <div className="health-pair__item">
                  <span className="health-pair__value">
                    <Counter value={health.unique_members} />
                  </span>
                  <span className="health-pair__label">
                    <UsersThree size={13} weight="fill" /> Thành viên hoạt động
                  </span>
                </div>
                <div className="health-pair__item">
                  <span className="health-pair__value">
                    <Counter value={health.new_members} />
                  </span>
                  <span className="health-pair__label">
                    <Sparkle size={13} weight="fill" /> Thành viên mới
                  </span>
                </div>
              </div>

              {/* Risk Breakdown Meter */}
              <div className="risk-meter">
                <div className="risk-meter__item">
                  <div className="risk-meter__header">
                    <span className="risk-meter__label">
                      <ShieldCheck size={14} color="var(--sev-low)" weight="fill" /> Tin an toàn
                    </span>
                    <span className="risk-meter__value">
                      {Math.max(
                        0,
                        health.messages_total - health.risky_count - health.spam_count - health.toxic_count,
                      ).toLocaleString("vi-VN")}
                    </span>
                  </div>
                  <div className="risk-meter__track">
                    <div
                      className="risk-meter__fill risk-meter__fill--safe"
                      style={{
                        width: `${Math.max(
                          0,
                          Math.round(
                            ((health.messages_total - health.risky_count - health.spam_count - health.toxic_count) /
                              (health.messages_total || 1)) *
                              100,
                          ),
                        )}%`,
                      }}
                    />
                  </div>
                </div>

                <div className="risk-meter__item">
                  <div className="risk-meter__header">
                    <span className="risk-meter__label">
                      <ShieldWarning size={14} color="var(--cat-spam)" weight="fill" /> Spam
                    </span>
                    <span className="risk-meter__value">{health.spam_count.toLocaleString("vi-VN")}</span>
                  </div>
                  <div className="risk-meter__track">
                    <div
                      className="risk-meter__fill risk-meter__fill--spam"
                      style={{
                        width: `${Math.min(
                          100,
                          Math.round((health.spam_count / (health.messages_total || 1)) * 100),
                        )}%`,
                      }}
                    />
                  </div>
                </div>

                <div className="risk-meter__item">
                  <div className="risk-meter__header">
                    <span className="risk-meter__label">
                      <WarningCircle size={14} color="var(--cat-violence)" weight="fill" /> Công kích, thù ghét
                    </span>
                    <span className="risk-meter__value">{health.toxic_count.toLocaleString("vi-VN")}</span>
                  </div>
                  <div className="risk-meter__track">
                    <div
                      className="risk-meter__fill risk-meter__fill--toxic"
                      style={{
                        width: `${Math.min(
                          100,
                          Math.round((health.toxic_count / (health.messages_total || 1)) * 100),
                        )}%`,
                      }}
                    />
                  </div>
                </div>

                <div className="risk-meter__item">
                  <div className="risk-meter__header">
                    <span className="risk-meter__label">
                      <Flame size={14} color="var(--sev-high)" weight="fill" /> Rủi ro cao / Bị gắn cờ
                    </span>
                    <span className="risk-meter__value">{health.risky_count.toLocaleString("vi-VN")}</span>
                  </div>
                  <div className="risk-meter__track">
                    <div
                      className="risk-meter__fill risk-meter__fill--risky"
                      style={{
                        width: `${Math.min(
                          100,
                          Math.round((health.risky_count / (health.messages_total || 1)) * 100),
                        )}%`,
                      }}
                    />
                  </div>
                </div>
              </div>
            </>
          )}
        </Card>

        <Card
          title="Chủ đề Nóng Đang Thảo luận"
          className="span-4"
          delay={0.1}
          action={
            <Link to="/quan-ly-faq" className="btn btn--ghost" style={{ fontSize: 11 }}>
              <Tag size={12} /> Tạo FAQ
            </Link>
          }
        >
          {healthLoading && <SkeletonBlock height={220} />}
          {!healthLoading &&
            (health?.top_topics?.length ? (
              <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                <p className="muted small">Cụm chủ đề được quan tâm nhiều nhất trong phiên:</p>
                <div className="topic-pill-cloud">
                  {health.top_topics.slice(0, 10).map(([topic, count]) => (
                    <span key={topic} className="topic-pill">
                      {topic}
                      <span className="topic-pill__count">{count}</span>
                    </span>
                  ))}
                </div>
                {health.open_faq_suggestions > 0 && (
                  <p className="platform-sync__hint" style={{ marginTop: 8 }}>
                    💡 Có {health.open_faq_suggestions} đề xuất FAQ mới cần xem xét.
                  </p>
                )}
              </div>
            ) : (
              <EmptyState message="Chưa đủ tin nhắn để rút ra cụm chủ đề." />
            ))}
        </Card>

        <Card title="Phân loại Quyết định AI" className="span-4" delay={0.12}>
          {loading && <SkeletonBlock height={220} />}
          {!loading &&
            (decisionRows.length > 0 ? (
              <>
                <ul className="decision-list">
                  {decisionRows.map(([decision, count]) => (
                    <li key={decision} className="decision-list__row">
                      <span className="decision-list__dot" style={{ background: DECISION_COLORS[decision] }} />
                      <span className="decision-list__label">{decisionLabel(decision)}</span>
                      <span className="decision-list__value">{count.toLocaleString("vi-VN")}</span>
                    </li>
                  ))}
                </ul>
                {categoryRanks.length > 0 && (
                  <>
                    <p className="muted small card__divider">Nhóm vi phạm nhiều nhất</p>
                    <RankList items={categoryRanks.slice(0, 3)} />
                  </>
                )}
              </>
            ) : (
              <EmptyState message="Chưa có quyết định kiểm duyệt nào." />
            ))}
        </Card>
      </div>

      {/* 5. Actionable Multi-Tab Triage Hub */}
      <div className="page-grid__row">
        <Card
          title="Điều phối Tác vụ & Hàng đợi Khẩn cấp"
          className="span-12"
          delay={0.15}
          action={
            <Link to="/cong-dong" className="btn btn--ghost">
              Xem toàn bộ hàng đợi <ArrowRight size={13} weight="bold" />
            </Link>
          }
        >
          {/* Tab Navigation */}
          <div className="triage-tab-bar">
            <button
              type="button"
              className={`triage-tab-btn${triageTab === "incidents" ? " is-active" : ""}`}
              onClick={() => setTriageTab("incidents")}
            >
              <Flame size={15} weight={triageTab === "incidents" ? "fill" : "regular"} />
              Sự cố kiểm duyệt
              <span className="triage-tab-btn__badge">{incidents.length}</span>
            </button>

            <button
              type="button"
              className={`triage-tab-btn${triageTab === "reports" ? " is-active" : ""}`}
              onClick={() => setTriageTab("reports")}
            >
              <Flag size={15} weight={triageTab === "reports" ? "fill" : "regular"} />
              Báo cáo thành viên (/report)
              <span className="triage-tab-btn__badge">{openReports.length}</span>
            </button>

            <button
              type="button"
              className={`triage-tab-btn${triageTab === "links" ? " is-active" : ""}`}
              onClick={() => setTriageTab("links")}
            >
              <LinkBreak size={15} weight={triageTab === "links" ? "fill" : "regular"} />
              Liên kết bị chặn
              <span className="triage-tab-btn__badge">{flaggedLinks.length}</span>
            </button>
          </div>

          {/* Tab 1: Incidents */}
          {triageTab === "incidents" && (
            <>
              {loading && <SkeletonLine width="70%" />}
              {!loading && recentIncidents.length > 0 && (
                <ActivityFeed incidents={recentIncidents} onSelect={setOpenId} />
              )}
              {!loading && recentIncidents.length === 0 && (
                <EmptyState message="Hệ thống chưa ghi nhận sự cố nào gần đây." />
              )}
            </>
          )}

          {/* Tab 2: Member Reports */}
          {triageTab === "reports" && (
            <div className="triage-list">
              {memberReportsQuery.isPending && <SkeletonLine width="60%" />}
              {!memberReportsQuery.isPending && memberReports.length === 0 && (
                <EmptyState message="Chưa có báo cáo nào từ thành viên." />
              )}
              {!memberReportsQuery.isPending &&
                memberReports.slice(0, 6).map((report) => (
                  <div key={report.report_id} className="triage-item">
                    <div className="triage-item__left">
                      <div className="triage-item__icon">
                        {report.platform === "discord" ? (
                          <DiscordLogo size={20} color="#5865f2" weight="fill" />
                        ) : (
                          <TelegramLogo size={20} color="#229ed9" weight="fill" />
                        )}
                      </div>
                      <div className="triage-item__content">
                        <span className="triage-item__title">{report.details}</span>
                        <div className="triage-item__meta">
                          <span>Người báo cáo: <strong>{report.reporter_id}</strong></span>
                          <span>·</span>
                          <span>Kênh: {report.channel_id}</span>
                          <span>·</span>
                          <span>{relativeTime(report.created_at)}</span>
                        </div>
                      </div>
                    </div>

                    <div className="triage-item__actions">
                      <span
                        className={`badge ${
                          report.status === "open" ? "badge--critical" : "badge--low"
                        }`}
                      >
                        {report.status === "open" ? "Đang mở" : "Đã xem"}
                      </span>
                      {report.status === "open" && (
                        <button
                          type="button"
                          className="btn btn--ghost"
                          style={{ fontSize: 11, padding: "4px 8px" }}
                          onClick={() => handleMarkReportReviewed(report.report_id)}
                        >
                          <Check size={12} /> Đã xem
                        </button>
                      )}
                    </div>
                  </div>
                ))}
            </div>
          )}

          {/* Tab 3: Flagged Links */}
          {triageTab === "links" && (
            <div className="triage-list">
              {flaggedLinksQuery.isPending && <SkeletonLine width="60%" />}
              {!flaggedLinksQuery.isPending && flaggedLinks.length === 0 && (
                <EmptyState message="Chưa có liên kết độc hại nào bị phát hiện." />
              )}
              {!flaggedLinksQuery.isPending &&
                flaggedLinks.map((link) => (
                  <div key={link.link_id} className="triage-item">
                    <div className="triage-item__left">
                      <div className="triage-item__icon">
                        <LinkBreak size={20} color="var(--sev-critical)" weight="bold" />
                      </div>
                      <div className="triage-item__content">
                        <span className="triage-item__title">{link.canonical_url}</span>
                        <div className="triage-item__meta">
                          <span>Tên miền: <strong>{link.domain}</strong></span>
                          <span>·</span>
                          <span>Đã chặn: {link.flag_count} lần</span>
                          <span>·</span>
                          <span>Cập nhật: {relativeTime(link.last_seen_at)}</span>
                        </div>
                      </div>
                    </div>

                    <div className="triage-item__actions">
                      <span className="badge badge--critical">
                        {link.status === "blocked" ? "Đã chặn" : "Được phép"}
                      </span>
                    </div>
                  </div>
                ))}
            </div>
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
