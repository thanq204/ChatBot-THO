import { memo, useCallback, useEffect, useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowSquareOut } from "@phosphor-icons/react";
import Card from "../components/Card.jsx";
import MemberReportInbox from "../components/MemberReportInbox.jsx";
import IncidentDetailModal from "../components/IncidentDetailModal.jsx";
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

const PLATFORM_OPTIONS = [
  { value: "", label: "Mọi nền tảng" },
  { value: "discord", label: "Discord" },
  { value: "telegram", label: "Telegram" },
  { value: "web", label: "Web" },
  { value: "zalo", label: "Zalo" },
  { value: "messenger", label: "Messenger" },
];

const STATUS_OPTIONS = ["open", "monitoring", "resolved", "snoozed"];

const SORT_OPTIONS = [
  { value: "severity", label: "Theo mức độ" },
  { value: "time", label: "Theo thời gian" },
];

const TIME_RANGE_OPTIONS = [
  { value: "", label: "Mọi thời gian" },
  { value: "1d", label: "1 ngày qua" },
  { value: "7d", label: "1 tuần qua" },
  { value: "30d", label: "1 tháng qua" },
];

const TIME_RANGE_MS = { "1d": 86400000, "7d": 7 * 86400000, "30d": 30 * 86400000 };

export default function CommunityPage() {
  const queryClient = useQueryClient();
  const [platformFilter, setPlatformFilter] = useState("");
  const [channelFilter, setChannelFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [sortMode, setSortMode] = useState("severity");
  const [timeRange, setTimeRange] = useState("");
  const [openId, setOpenId] = useState(null);

  // Each filter combination is its own cache entry, so flipping back to one you
  // already looked at is instant instead of another round-trip.
  const filters = useMemo(
    () => ({ platform: platformFilter || undefined, status: statusFilter || undefined }),
    [platformFilter, statusFilter],
  );
  const incidentsQuery = useQuery({
    queryKey: queryKeys.incidents(filters),
    queryFn: () => ops.incidents(filters),
    // Keep the current rows on screen while the next filter loads, so changing a
    // dropdown dims the table instead of replacing it with skeletons.
    placeholderData: (previous) => previous,
  });

  // Chỉ cần cho bộ lọc kênh Discord; im lặng bỏ qua nếu Discord chưa cấu hình.
  // Costs a round-trip to Discord per guild — measured at ~1.7s — and only fills
  // a dropdown whose contents almost never change, so it refreshes far less
  // often than the case list and never blocks it.
  const channelsQuery = useQuery({
    queryKey: queryKeys.discordChannels,
    queryFn: ops.discordChannels,
    staleTime: 15 * 60_000,
    retry: false,
  });

  const incidents = incidentsQuery.data ?? null;
  const discordChannels = channelsQuery.data ?? [];
  const loading = incidentsQuery.isPending;
  // Only while the previous filter's rows stand in for a new one. Deliberately
  // not `isFetching`: that is also true for background refreshes on mount and on
  // window focus, which would dim the list out from under the operator.
  const refreshing = incidentsQuery.isPlaceholderData;
  const error = incidentsQuery.error?.message ?? null;

  const load = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: ["incidents"] });
  }, [queryClient]);

  useEffect(() => {
    setChannelFilter("");
  }, [platformFilter]);

  const closeDetail = useCallback(() => setOpenId(null), []);

  const channelNameById = useMemo(
    () => Object.fromEntries(discordChannels.map((channel) => [channel.channel_id, channel.channel_name])),
    [discordChannels],
  );

  const visibleIncidents = useMemo(() => {
    let rows = incidents ?? [];
    if (platformFilter === "discord" && channelFilter) {
      rows = rows.filter((item) => item.channel_id === channelFilter);
    }
    const spanMs = TIME_RANGE_MS[timeRange];
    if (spanMs) {
      const cutoff = Date.now() - spanMs;
      rows = rows.filter((item) => new Date(item.updated_at).getTime() >= cutoff);
    }
    if (sortMode === "time") {
      rows = [...rows].sort((a, b) => new Date(b.updated_at) - new Date(a.updated_at));
    }
    return rows;
  }, [incidents, platformFilter, channelFilter, timeRange, sortMode]);

  const counts = useMemo(
    () => ({
      total: visibleIncidents.length,
      critical: visibleIncidents.filter((item) => item.severity === "critical").length,
      waiting: visibleIncidents.filter((item) => item.status === "open").length,
    }),
    [visibleIncidents],
  );

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
              <select value={sortMode} onChange={(event) => setSortMode(event.target.value)} aria-label="Sắp xếp theo">
                {SORT_OPTIONS.map((item) => (
                  <option key={item.value} value={item.value}>
                    {item.label}
                  </option>
                ))}
              </select>
              <select value={timeRange} onChange={(event) => setTimeRange(event.target.value)} aria-label="Lọc theo khoảng thời gian">
                {TIME_RANGE_OPTIONS.map((item) => (
                  <option key={item.value} value={item.value}>
                    {item.label}
                  </option>
                ))}
              </select>
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
              {platformFilter === "discord" && discordChannels.length > 0 && (
                <select value={channelFilter} onChange={(event) => setChannelFilter(event.target.value)} aria-label="Lọc theo kênh Discord">
                  <option value="">Mọi kênh</option>
                  {Object.entries(
                    discordChannels.reduce((byGuild, channel) => {
                      (byGuild[channel.guild_name] ??= []).push(channel);
                      return byGuild;
                    }, {}),
                  ).map(([guildName, channels]) => (
                    <optgroup key={guildName} label={guildName}>
                      {channels.map((channel) => (
                        <option key={channel.channel_id} value={channel.channel_id}>
                          #{channel.channel_name}
                        </option>
                      ))}
                    </optgroup>
                  ))}
                </select>
              )}
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
          {!loading && incidents && incidents.length > 0 && visibleIncidents.length === 0 && (
            <EmptyState message="Không có case nào khớp với bộ lọc đã chọn." />
          )}
          {!loading && visibleIncidents.length > 0 && (
            <div className={refreshing ? "is-refreshing" : undefined}>
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
                {visibleIncidents.map((item) => (
                  <CaseRow key={item.incident_id} incident={item} channelName={channelNameById[item.channel_id]} onOpen={setOpenId} />
                ))}
              </div>
            </div>
          )}
        </Card>
      </div>

      <div className="page-grid__row">
        {/* Member-submitted reports, kept beside the AI queue rather than inside
            it: different origin, different trust level. */}
        <Card title="Báo cáo từ thành viên (/report)" className="span-12" delay={0.05}>
          <MemberReportInbox />
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
const CaseRow = memo(function CaseRow({ incident, channelName, onOpen }) {
  const actor = actorFromTitle(incident.title);

  // A <button> can't legally contain the <a> jump-to-Discord/Telegram link
  // below, so the row itself is a keyboard-accessible div instead.
  return (
    <div
      role="button"
      tabIndex={0}
      className="case-row"
      style={{ "--case-accent": SEVERITY_COLORS[incident.severity] ?? "var(--text-muted)" }}
      onClick={() => onOpen(incident.incident_id)}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          onOpen(incident.incident_id);
        }
      }}
    >
      <span className="case-row__title">{categoryLabel(primaryCategory(incident))}</span>
      <span className="case-row__status" style={{ color: STATUS_COLORS[incident.status] }}>
        {statusLabel(incident.status)}
      </span>
      <span className="case-row__meta">
        <span className="case-row__severity">{severityLabel(incident.severity)}</span>
        {actor && <span>{actor}</span>}
        <span>{platformLabel(incident.platform)}</span>
        {channelName && <span>#{channelName}</span>}
        <span>{incident.message_count} tin</span>
        <span>risk {percent(incident.risk_score)}</span>
        <span>{relativeTime(incident.updated_at)}</span>
        {incident.source_url && (
          <a
            href={incident.source_url}
            target="_blank"
            rel="noopener noreferrer"
            className="case-row__link"
            onClick={(event) => event.stopPropagation()}
          >
            Xem tin gốc <ArrowSquareOut size={11} weight="bold" />
          </a>
        )}
      </span>
    </div>
  );
});
