import { memo, useCallback, useEffect, useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  MagnifyingGlass,
  X,
  SquaresFour,
  Columns,
  ListDashes,
  Flame,
  ClockCountdown,
  Flag,
  CheckCircle,
  DiscordLogo,
  TelegramLogo,
  ChatsCircle,
  ArrowsClockwise,
  ArrowSquareOut,
} from "@phosphor-icons/react";
import Card from "../components/Card.jsx";
import Badge from "../components/Badge.jsx";
import MemberReportInbox from "../components/MemberReportInbox.jsx";
import IncidentDetailModal from "../components/IncidentDetailModal.jsx";
import IncidentDetailPanel from "../components/IncidentDetailPanel.jsx";
import LoadMore from "../components/LoadMore.jsx";
import { SkeletonBlock, SkeletonLine } from "../components/Skeleton.jsx";
import { ErrorState, EmptyState } from "../components/StatePanels.jsx";
import { ops } from "../api/client.js";
import { queryKeys } from "../lib/queryClient.js";
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
import { safeExternalUrl } from "../lib/urls.js";

const PLATFORMS = [
  { value: "", label: "Tất cả", icon: ChatsCircle },
  { value: "discord", label: "Discord", icon: DiscordLogo },
  { value: "telegram", label: "Telegram", icon: TelegramLogo },
  { value: "web", label: "Web", icon: ChatsCircle },
];

const STATUS_LIST = [
  { value: "open", label: "Đang mở" },
  { value: "monitoring", label: "Đang theo dõi" },
  { value: "resolved", label: "Đã xử lý" },
  { value: "snoozed", label: "Tạm hoãn" },
  { value: "", label: "Mọi trạng thái" },
];

const SORT_OPTIONS = [
  { value: "severity", label: "Theo mức độ" },
  { value: "time", label: "Theo thời gian" },
  { value: "risk", label: "Theo điểm rủi ro" },
];

const TIME_RANGE_OPTIONS = [
  { value: "", label: "Mọi thời gian" },
  { value: "1d", label: "1 ngày qua" },
  { value: "7d", label: "1 tuần qua" },
  { value: "30d", label: "1 tháng qua" },
];

const TIME_RANGE_MS = { "1d": 86400000, "7d": 7 * 86400000, "30d": 30 * 86400000 };
const SEVERITY_ORDER = ["critical", "high", "medium", "low"];
const PAGE_SIZE = 15;

/** Rich Scannable Card for Split View & Full List */
const IncidentCardRich = memo(function IncidentCardRich({
  incident,
  channelName,
  isSelected,
  onSelect,
}) {
  const actor = actorFromTitle(incident.title);
  const category = primaryCategory(incident);
  const isSettled = incident.status === "resolved" || incident.status === "snoozed";
  const sevColor = SEVERITY_COLORS[incident.severity] || "var(--text-muted)";
  const riskPct = Math.round((incident.risk_score || 0) * 100);

  const PlatformIcon =
    incident.platform === "discord"
      ? DiscordLogo
      : incident.platform === "telegram"
      ? TelegramLogo
      : ChatsCircle;

  return (
    <div
      role="button"
      tabIndex={0}
      className={`incident-card-rich${isSelected ? " is-selected" : ""}${isSettled ? " case-row--settled" : ""}`}
      style={{ "--card-severity-color": sevColor }}
      onClick={() => onSelect(incident.incident_id)}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onSelect(incident.incident_id);
        }
      }}
    >
      <div className="incident-card-rich__top">
        <span
          className={`incident-card-rich__platform incident-card-rich__platform--${incident.platform}`}
        >
          <PlatformIcon size={15} weight="fill" />
          {platformLabel(incident.platform)}
          {channelName ? ` · #${channelName}` : incident.channel_id ? ` · #${incident.channel_id}` : ""}
        </span>

        <div className="incident-card-rich__badges">
          <Badge tone={SEVERITY_COLORS[incident.severity]}>{severityLabel(incident.severity)}</Badge>
          <Badge tone={STATUS_COLORS[incident.status]}>{statusLabel(incident.status)}</Badge>
        </div>
      </div>

      <div className="incident-card-rich__title-row">
        <span className="incident-card-rich__headline">
          {categoryLabel(category)}
          {actor ? ` · @${actor}` : ""}
        </span>
      </div>

      {incident.summary && (
        <p className="incident-card-rich__snippet">{incident.summary}</p>
      )}

      <div className="incident-card-rich__foot">
        <div className="incident-card-rich__risk-bar">
          <span style={{ color: sevColor }}>Rủi ro {riskPct}%</span>
          <div className="incident-card-rich__track">
            <div
              className="incident-card-rich__fill"
              style={{ width: `${riskPct}%`, background: sevColor }}
            />
          </div>
        </div>
        <span>{incident.message_count} tin · {relativeTime(incident.updated_at)}</span>
      </div>
    </div>
  );
});

export default function CommunityPage() {
  const queryClient = useQueryClient();

  // Search & Filter States
  const [searchQuery, setSearchQuery] = useState("");
  const [platformFilter, setPlatformFilter] = useState("");
  const [channelFilter, setChannelFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("open");
  const [severityFilter, setSeverityFilter] = useState("");
  const [sortMode, setSortMode] = useState("severity");
  const [timeRange, setTimeRange] = useState("");
  const [viewMode, setViewMode] = useState(() => {
    return window.localStorage.getItem("community-view-mode") || "list";
  });

  const handleViewModeChange = (mode) => {
    setViewMode(mode);
    window.localStorage.setItem("community-view-mode", mode);
  };
  const [visibleCount, setVisibleCount] = useState(PAGE_SIZE);

  // Selection & Modal States
  const [selectedId, setSelectedId] = useState(null);
  const [modalOpenId, setModalOpenId] = useState(null);

  const filters = useMemo(
    () => ({ platform: platformFilter || undefined, status: statusFilter || undefined }),
    [platformFilter, statusFilter],
  );

  const incidentsQuery = useQuery({
    queryKey: queryKeys.incidents(filters),
    queryFn: () => ops.incidents(filters),
    placeholderData: (previous) => previous,
  });

  const channelsQuery = useQuery({
    queryKey: queryKeys.discordChannels,
    queryFn: ops.discordChannels,
    staleTime: 15 * 60_000,
    retry: false,
  });

  const memberReportsQuery = useQuery({
    queryKey: ["member-reports"],
    queryFn: ops.memberReports,
  });

  const incidents = incidentsQuery.data ?? null;
  const discordChannels = channelsQuery.data ?? [];
  const memberReports = memberReportsQuery.data ?? [];
  const loading = incidentsQuery.isPending;
  const refreshing = incidentsQuery.isPlaceholderData;
  const error = incidentsQuery.error?.message ?? null;

  const load = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: ["incidents"] });
    queryClient.invalidateQueries({ queryKey: ["member-reports"] });
  }, [queryClient]);

  useEffect(() => {
    setChannelFilter("");
  }, [platformFilter]);

  useEffect(() => {
    setVisibleCount(PAGE_SIZE);
  }, [platformFilter, channelFilter, statusFilter, severityFilter, timeRange, sortMode, searchQuery]);

  const channelNameById = useMemo(
    () => Object.fromEntries(discordChannels.map((c) => [c.channel_id, c.channel_name])),
    [discordChannels],
  );

  // Queue Tally Counts (All incidents in memory)
  const queueStats = useMemo(() => {
    const all = incidents ?? [];
    const criticalOpen = all.filter(
      (i) => (i.severity === "critical" || i.severity === "high") && i.status === "open",
    ).length;
    const monitoringCount = all.filter((i) => i.status === "monitoring").length;
    const resolvedCount = all.filter((i) => i.status === "resolved").length;
    const openReportsCount = memberReports.filter((r) => r.status === "open").length;

    return { criticalOpen, monitoringCount, resolvedCount, openReportsCount };
  }, [incidents, memberReports]);

  // Scoped & Filtered Incidents
  const scopedIncidents = useMemo(() => {
    let rows = incidents ?? [];

    // Discord channel filter
    if (platformFilter === "discord" && channelFilter) {
      rows = rows.filter((item) => item.channel_id === channelFilter);
    }

    // Time range filter
    const spanMs = TIME_RANGE_MS[timeRange];
    if (spanMs) {
      const cutoff = Date.now() - spanMs;
      rows = rows.filter((item) => new Date(item.updated_at).getTime() >= cutoff);
    }

    // Search Query (Author, summary, ID, channel)
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase().trim();
      rows = rows.filter((item) => {
        const actor = actorFromTitle(item.title) || "";
        const title = (item.title || "").toLowerCase();
        const summary = (item.summary || "").toLowerCase();
        const id = (item.incident_id || "").toLowerCase();
        const channel = (item.channel_id || "").toLowerCase();
        const channelName = (channelNameById[item.channel_id] || "").toLowerCase();
        return (
          actor.toLowerCase().includes(q) ||
          title.includes(q) ||
          summary.includes(q) ||
          id.includes(q) ||
          channel.includes(q) ||
          channelName.includes(q)
        );
      });
    }

    // Sorting
    if (sortMode === "time") {
      rows = [...rows].sort((a, b) => new Date(b.updated_at) - new Date(a.updated_at));
    } else if (sortMode === "risk") {
      rows = [...rows].sort((a, b) => (b.risk_score || 0) - (a.risk_score || 0));
    } else {
      // Default severity order
      const order = { critical: 4, high: 3, medium: 2, low: 1 };
      rows = [...rows].sort((a, b) => (order[b.severity] || 0) - (order[a.severity] || 0));
    }

    return rows;
  }, [incidents, platformFilter, channelFilter, timeRange, searchQuery, sortMode, channelNameById]);

  // Severity counts for chips
  const severityCounts = useMemo(() => {
    const counts = { critical: 0, high: 0, medium: 0, low: 0 };
    for (const item of scopedIncidents) {
      if (counts[item.severity] !== undefined) counts[item.severity] += 1;
    }
    return counts;
  }, [scopedIncidents]);

  const visibleIncidents = useMemo(() => {
    if (!severityFilter) return scopedIncidents;
    return scopedIncidents.filter((item) => item.severity === severityFilter);
  }, [scopedIncidents, severityFilter]);

  const pageRows = useMemo(
    () => visibleIncidents.slice(0, visibleCount),
    [visibleIncidents, visibleCount],
  );
  const remainingCount = visibleIncidents.length - pageRows.length;

  // Auto-select first incident in Split View if none is selected
  useEffect(() => {
    if (viewMode === "split" && pageRows.length > 0) {
      if (!selectedId || !pageRows.some((r) => r.incident_id === selectedId)) {
        setSelectedId(pageRows[0].incident_id);
      }
    }
  }, [viewMode, pageRows, selectedId]);

  const handleCardClick = (id) => {
    if (viewMode === "split") {
      setSelectedId(id);
    } else {
      setModalOpenId(id);
    }
  };

  const modalIncident = useMemo(
    () => (incidents ?? []).find((item) => item.incident_id === modalOpenId) ?? null,
    [incidents, modalOpenId],
  );

  if (error) {
    return (
      <div className="page-grid">
        <ErrorState message={`Không lấy được danh sách trường hợp: ${error}`} onRetry={load} />
      </div>
    );
  }

  return (
    <div className="page-grid">
      {/* 1. Top Header & Queue Summary Badges */}
      <div className="span-12">
        <div className="overview-header" style={{ borderBottom: "none", paddingBottom: 6 }}>
          <div className="overview-header__main">
            <div className="overview-header__title-row">
              <h1 className="overview-header__title">Hàng đợi Kiểm duyệt Cộng đồng</h1>
              <span className="overview-header__live-tag">
                <span className="live-pulse" />
                Giám sát Discord & Telegram
              </span>
            </div>
            <p className="overview-header__desc">
              Xử lý các sự cố vi phạm do AI phát hiện và xem xét báo cáo khiếu nại của thành viên.
            </p>
          </div>

          <div className="overview-header__controls">
            <button
              type="button"
              className="btn btn--ghost"
              onClick={load}
              title="Làm mới hàng đợi"
            >
              <ArrowsClockwise size={14} className={loading ? "spin-icon" : undefined} />
              Làm mới
            </button>
          </div>
        </div>

        {/* 4 Mini Stat Badges */}
        <div className="community-queue-summary">
          <div className="queue-stat-card">
            <div className="queue-stat-card__icon queue-stat-card__icon--critical">
              <Flame size={20} weight="fill" />
            </div>
            <div className="queue-stat-card__body">
              <span className="queue-stat-card__value">{queueStats.criticalOpen}</span>
              <span className="queue-stat-card__label">Khẩn cấp cần xử lý</span>
            </div>
          </div>

          <div className="queue-stat-card">
            <div className="queue-stat-card__icon queue-stat-card__icon--monitoring">
              <ClockCountdown size={20} weight="fill" />
            </div>
            <div className="queue-stat-card__body">
              <span className="queue-stat-card__value">{queueStats.monitoringCount}</span>
              <span className="queue-stat-card__label">Đang theo dõi</span>
            </div>
          </div>

          <div className="queue-stat-card">
            <div className="queue-stat-card__icon queue-stat-card__icon--reports">
              <Flag size={20} weight="fill" />
            </div>
            <div className="queue-stat-card__body">
              <span className="queue-stat-card__value">{queueStats.openReportsCount}</span>
              <span className="queue-stat-card__label">Báo cáo thành viên</span>
            </div>
          </div>

          <div className="queue-stat-card">
            <div className="queue-stat-card__icon queue-stat-card__icon--resolved">
              <CheckCircle size={20} weight="fill" />
            </div>
            <div className="queue-stat-card__body">
              <span className="queue-stat-card__value">{queueStats.resolvedCount}</span>
              <span className="queue-stat-card__label">Đã giải quyết</span>
            </div>
          </div>
        </div>
      </div>

      {/* 2. Interactive Search & Smart Filter Toolbar */}
      <div className="span-12 community-toolbar">
        <div className="community-toolbar__top">
          {/* Instant Search Bar */}
          <div className="community-search-box">
            <MagnifyingGlass size={16} className="community-search-box__icon" />
            <input
              type="text"
              className="community-search-box__input"
              placeholder="Tìm theo tên thành viên, ID, kênh hoặc nội dung vi phạm..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
            {searchQuery && (
              <button
                type="button"
                className="community-search-box__clear"
                onClick={() => setSearchQuery("")}
                title="Xóa tìm kiếm"
              >
                <X size={14} />
              </button>
            )}
          </div>

          {/* View Mode Switcher */}
          <div className="community-view-toggle">
            <button
              type="button"
              className={`community-view-toggle__btn${viewMode === "list" ? " is-active" : ""}`}
              onClick={() => handleViewModeChange("list")}
              title="Chế độ danh sách chuẩn (Mặc định)"
            >
              <ListDashes size={15} weight={viewMode === "list" ? "fill" : "regular"} />
              Danh sách
            </button>
            <button
              type="button"
              className={`community-view-toggle__btn${viewMode === "split" ? " is-active" : ""}`}
              onClick={() => handleViewModeChange("split")}
              title="Chế độ 2 cột (Master-Detail)"
            >
              <Columns size={15} weight={viewMode === "split" ? "fill" : "regular"} />
              2 Cột (Split)
            </button>
          </div>
        </div>

        {/* Filter Pills Row */}
        <div className="community-toolbar__filters">
          {/* Platform Pills */}
          <div className="community-filter-group">
            <span className="muted small" style={{ marginRight: 2 }}>Nền tảng:</span>
            {PLATFORMS.map((p) => {
              const Icon = p.icon;
              return (
                <button
                  key={p.value}
                  type="button"
                  className={`community-pill-btn${platformFilter === p.value ? " is-active" : ""}`}
                  onClick={() => setPlatformFilter(p.value)}
                >
                  <Icon size={14} />
                  {p.label}
                </button>
              );
            })}
          </div>

          {/* Status Pills */}
          <div className="community-filter-group">
            <span className="muted small" style={{ marginRight: 2 }}>Trạng thái:</span>
            {STATUS_LIST.map((s) => (
              <button
                key={s.value}
                type="button"
                className={`community-pill-btn${statusFilter === s.value ? " is-active" : ""}`}
                onClick={() => setStatusFilter(s.value)}
              >
                {s.label}
              </button>
            ))}
          </div>

          {/* Discord Channel Dropdown (if active) */}
          {platformFilter === "discord" && discordChannels.length > 0 && (
            <select
              value={channelFilter}
              onChange={(e) => setChannelFilter(e.target.value)}
              style={{
                borderRadius: "var(--radius-pill)",
                fontSize: 12,
                padding: "4px 10px",
                border: "1px solid var(--border)",
                background: "var(--surface-alt)",
                color: "var(--text-primary)",
              }}
            >
              <option value="">Mọi kênh Discord</option>
              {Object.entries(
                discordChannels.reduce((byGuild, c) => {
                  (byGuild[c.guild_name] ??= []).push(c);
                  return byGuild;
                }, {}),
              ).map(([guildName, channels]) => (
                <optgroup key={guildName} label={guildName}>
                  {channels.map((c) => (
                    <option key={c.channel_id} value={c.channel_id}>
                      #{c.channel_name}
                    </option>
                  ))}
                </optgroup>
              ))}
            </select>
          )}

          {/* Sort & Time Range Dropdowns */}
          <div className="community-filter-group">
            <select
              value={sortMode}
              onChange={(e) => setSortMode(e.target.value)}
              style={{
                borderRadius: "var(--radius-pill)",
                fontSize: 12,
                padding: "4px 8px",
                border: "1px solid var(--border)",
                background: "var(--surface-alt)",
                color: "var(--text-primary)",
              }}
            >
              {SORT_OPTIONS.map((item) => (
                <option key={item.value} value={item.value}>
                  {item.label}
                </option>
              ))}
            </select>

            <select
              value={timeRange}
              onChange={(e) => setTimeRange(e.target.value)}
              style={{
                borderRadius: "var(--radius-pill)",
                fontSize: 12,
                padding: "4px 8px",
                border: "1px solid var(--border)",
                background: "var(--surface-alt)",
                color: "var(--text-primary)",
              }}
            >
              {TIME_RANGE_OPTIONS.map((item) => (
                <option key={item.value} value={item.value}>
                  {item.label}
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* Severity Chips */}
        <div className="case-tally" style={{ marginBottom: 0, marginTop: 4 }}>
          <p className="case-tally__line">
            Hiển thị <strong>{visibleIncidents.length}</strong> / {scopedIncidents.length} trường hợp
            {severityFilter ? ` (${severityLabel(severityFilter).toLowerCase()})` : ""}
            {searchQuery ? ` khớp từ khóa "${searchQuery}"` : ""}
          </p>

          <div className="case-chip-row" role="group" aria-label="Lọc theo mức độ">
            {SEVERITY_ORDER.filter((sev) => severityCounts[sev] > 0).map((sev) => (
              <button
                key={sev}
                type="button"
                className={`case-chip${severityFilter === sev ? " is-active" : ""}`}
                style={{ "--chip-accent": SEVERITY_COLORS[sev] }}
                onClick={() => setSeverityFilter((cur) => (cur === sev ? "" : sev))}
              >
                {severityLabel(sev)} <span className="case-chip__count">{severityCounts[sev]}</span>
              </button>
            ))}
            {severityFilter && (
              <button
                type="button"
                className="case-chip case-chip--reset"
                onClick={() => setSeverityFilter("")}
              >
                Bỏ lọc
              </button>
            )}
          </div>
        </div>
      </div>

      {/* 3. Main Incident Stream: Split View or Full List */}
      <div className="span-12">
        {loading && (
          <div className="stack">
            <SkeletonLine width="90%" />
            <SkeletonBlock height={260} />
          </div>
        )}

        {!loading && visibleIncidents.length === 0 && (
          <Card>
            <EmptyState
              message={
                searchQuery
                  ? `Không tìm thấy trường hợp nào khớp với từ khóa "${searchQuery}".`
                  : "Không có trường hợp nào khớp với bộ lọc đã chọn."
              }
            />
          </Card>
        )}

        {!loading && visibleIncidents.length > 0 && viewMode === "split" && (
          <div className={`community-split-layout${refreshing ? " is-refreshing" : ""}`}>
            {/* Left Column: List of Rich Cards */}
            <div className="community-list-pane">
              {pageRows.map((item) => (
                <IncidentCardRich
                  key={item.incident_id}
                  incident={item}
                  channelName={channelNameById[item.channel_id]}
                  isSelected={selectedId === item.incident_id}
                  onSelect={handleCardClick}
                />
              ))}

              <LoadMore
                remaining={remainingCount}
                step={PAGE_SIZE}
                unit="trường hợp"
                onMore={() => setVisibleCount((c) => c + PAGE_SIZE)}
                canCollapse={visibleCount > PAGE_SIZE}
                onCollapse={() => setVisibleCount(PAGE_SIZE)}
              />
            </div>

            {/* Right Column: Sticky Detail Panel */}
            <div className="community-detail-pane">
              <IncidentDetailPanel incidentId={selectedId} onUpdated={load} />
            </div>
          </div>
        )}

        {!loading && visibleIncidents.length > 0 && viewMode === "list" && (
          <Card>
            <div className={`case-list${refreshing ? " is-refreshing" : ""}`}>
              {pageRows.map((item) => (
                <IncidentCardRich
                  key={item.incident_id}
                  incident={item}
                  channelName={channelNameById[item.channel_id]}
                  isSelected={false}
                  onSelect={handleCardClick}
                />
              ))}
            </div>

            <LoadMore
              remaining={remainingCount}
              step={PAGE_SIZE}
              unit="trường hợp"
              onMore={() => setVisibleCount((c) => c + PAGE_SIZE)}
              canCollapse={visibleCount > PAGE_SIZE}
              onCollapse={() => setVisibleCount(PAGE_SIZE)}
            />
          </Card>
        )}
      </div>

      {/* 4. Member Reports Inbox (/report) */}
      <div className="span-12">
        <Card title="Hộp thư Báo cáo từ Thành viên (/report)" delay={0.05}>
          <MemberReportInbox />
        </Card>
      </div>

      {/* Modal for Full List View */}
      {viewMode === "list" && (
        <IncidentDetailModal
          incidentId={modalOpenId}
          headline={modalIncident ? caseHeadline(modalIncident) : ""}
          onClose={() => setModalOpenId(null)}
          onUpdated={load}
        />
      )}
    </div>
  );
}
