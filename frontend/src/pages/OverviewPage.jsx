import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowRight, ArrowsClockwise, UsersThree } from "@phosphor-icons/react";
import Card from "../components/Card.jsx";
import Counter from "../components/Counter.jsx";
import IncidentDetailModal from "../components/IncidentDetailModal.jsx";
import RankList from "../components/RankList.jsx";
import PlatformRing from "../components/PlatformRing.jsx";
import TrendChart from "../components/TrendChart.jsx";
import TopicBars from "../components/TopicBars.jsx";
import ActivityFeed from "../components/ActivityFeed.jsx";
import { SkeletonLine, SkeletonBlock } from "../components/Skeleton.jsx";
import { ErrorState, EmptyState } from "../components/StatePanels.jsx";
import { ops } from "../api/client.js";
import { categoryLabel, platformLabel, CATEGORY_COLORS, decisionLabel, DECISION_COLORS } from "../lib/taxonomy.js";
import { caseHeadline } from "../lib/incidents.js";

const TREND_WINDOW_HOURS = 48;

function buildCategoryRanks(summary) {
  const entries = Object.entries(summary.by_category).filter(([category]) => category !== "safe");
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

/** Compact headline number. Four of these read faster than two huge slabs. */
function Kpi({ label, value, tone, meta }) {
  return (
    <div className={`kpi${tone ? ` kpi--${tone}` : ""}`}>
      <span className="kpi__label">{label}</span>
      <span className="kpi__value">
        <Counter value={value} />
      </span>
      {meta && <span className="kpi__meta">{meta}</span>}
    </div>
  );
}

export default function OverviewPage() {
  const [summary, setSummary] = useState(null);
  const [platforms, setPlatforms] = useState(null);
  const [incidents, setIncidents] = useState(null);
  const [timeline, setTimeline] = useState(null);
  const [health, setHealth] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [seeding, setSeeding] = useState(false);
  const [pullLimit, setPullLimit] = useState("100");
  const [syncing, setSyncing] = useState("");
  const [syncResult, setSyncResult] = useState(null);
  const [openId, setOpenId] = useState(null);

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    Promise.all([ops.analytics(), ops.platforms(), ops.incidents(), ops.timeline(TREND_WINDOW_HOURS, 1)])
      .then(([summaryRes, platformsRes, incidentsRes, timelineRes]) => {
        setSummary(summaryRes);
        setPlatforms(platformsRes);
        setIncidents([...incidentsRes].sort((a, b) => new Date(b.updated_at) - new Date(a.updated_at)).slice(0, 4));
        setTimeline(timelineRes);
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));

    // Supporting context only: a failure here must not blank the whole page.
    ops
      .communityHealth(24)
      .then(setHealth)
      .catch(() => setHealth(null));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const closeDetail = useCallback(() => setOpenId(null), []);

  const openIncident = useMemo(
    () => (incidents ?? []).find((item) => item.incident_id === openId) ?? null,
    [incidents, openId],
  );

  const seedDemo = async () => {
    setSeeding(true);
    try {
      await ops.seedDemo();
      load();
    } catch (err) {
      setError(err.message);
    } finally {
      setSeeding(false);
    }
  };

  const syncPlatform = async (platform) => {
    setSyncing(platform);
    // Telegram getUpdates chỉ trả một cửa sổ cố định, không phân trang như Discord.
    const limit = platform === "discord" ? pullLimit : "50";
    setSyncResult({ tone: "", text: `Đang đọc dữ liệu thật từ ${platformLabel(platform)}...` });
    try {
      const pulled = await ops.pullPlatform(platform, limit);
      setSyncResult({
        tone: "success",
        text: `Đã nhận ${pulled.received} tin nhắn và phân tích ${pulled.analyzed} tin từ ${platformLabel(platform)}.`,
      });
      load();
    } catch (err) {
      setSyncResult({ tone: "error", text: err.message });
    } finally {
      setSyncing("");
    }
  };

  if (error) {
    return (
      <div className="page-grid">
        <ErrorState message={`Không lấy được dữ liệu: ${error}`} onRetry={load} />
      </div>
    );
  }

  const categoryRanks = summary ? buildCategoryRanks(summary) : [];
  const decisionRows = summary ? Object.entries(summary.by_decision).sort((a, b) => b[1] - a[1]) : [];
  const violations = summary ? summary.messages_analyzed - (summary.by_decision.allow ?? 0) : 0;

  return (
    <div className="page-grid">
      <div className="kpi-row">
        {loading && <SkeletonBlock height={76} />}
        {!loading && summary && (
          <>
            <Kpi label="Tin nhắn đã quét" value={summary.messages_analyzed} meta="Tổng cộng" />
            <Kpi label="Vi phạm gắn thẻ" value={violations} tone="warn" meta="Mọi mức độ" />
            <Kpi label="Sự cố đang mở" value={summary.open_incidents} tone="alert" meta="Chờ xử lý" />
            <Kpi label="Nghiêm trọng" value={summary.critical_incidents} tone="critical" meta="Ưu tiên cao nhất" />
          </>
        )}
      </div>

      <div className="page-grid__row">
        <Card title={`Vi phạm theo giờ, ${TREND_WINDOW_HOURS} giờ qua`} className="span-7">
          {loading && <SkeletonBlock height={250} />}
          {!loading && timeline && timeline.scanned_total > 0 && <TrendChart buckets={timeline.buckets} />}
          {!loading && (!timeline || timeline.scanned_total === 0) && (
            <EmptyState
              message={`Chưa có tin nhắn nào trong ${TREND_WINDOW_HOURS} giờ qua.`}
              action={
                <button type="button" className="btn btn--primary" onClick={seedDemo} disabled={seeding}>
                  {seeding ? "Đang nạp..." : "Nạp dữ liệu demo"}
                </button>
              }
            />
          )}
        </Card>

        <Card title="Tiến độ giám sát" className="span-5" delay={0.05}>
          {loading && <SkeletonBlock height={250} />}
          {!loading && (
            <>
              <p className="muted small">Trạng thái kết nối theo nền tảng.</p>
              <div className="platform-ring-grid">
                {(platforms ?? []).map((status, index) => (
                  <PlatformRing key={status.platform} status={status} delay={index * 0.1} />
                ))}
              </div>

              <div className="platform-sync">
                <label className="platform-sync__limit">
                  Số tin mỗi lần quét
                  <select value={pullLimit} onChange={(event) => setPullLimit(event.target.value)}>
                    <option value="50">50 tin</option>
                    <option value="100">100 tin</option>
                    <option value="500">500 tin</option>
                  </select>
                </label>
                <div className="platform-sync__actions">
                  <button
                    type="button"
                    className="btn btn--ghost"
                    onClick={() => syncPlatform("discord")}
                    disabled={Boolean(syncing)}
                  >
                    <ArrowsClockwise size={14} className={syncing === "discord" ? "spin-icon" : undefined} />
                    {syncing === "discord" ? "Đang quét..." : "Quét Discord"}
                  </button>
                  <button
                    type="button"
                    className="btn btn--ghost"
                    onClick={() => syncPlatform("telegram")}
                    disabled={Boolean(syncing)}
                  >
                    <ArrowsClockwise size={14} className={syncing === "telegram" ? "spin-icon" : undefined} />
                    {syncing === "telegram" ? "Đang đồng bộ..." : "Đồng bộ Telegram"}
                  </button>
                </div>
                {syncResult && (
                  <p className={`platform-sync__result platform-sync__result--${syncResult.tone}`}>{syncResult.text}</p>
                )}
              </div>
            </>
          )}
        </Card>
      </div>

      <div className="page-grid__row">
        <Card title="Sức khoẻ cộng đồng, 24 giờ" className="span-4">
          {loading && <SkeletonBlock height={200} />}
          {!loading && !health && <EmptyState message="Chưa lấy được chỉ số cộng đồng." />}
          {!loading && health && (
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
                  <span className="health-pair__label">Thành viên mới</span>
                </div>
              </div>
              <ul className="health-list">
                <li>
                  <span>Tin nhắn trong 24 giờ</span>
                  <strong>{health.messages_total.toLocaleString("vi-VN")}</strong>
                </li>
                <li>
                  <span>Bị gắn cờ rủi ro</span>
                  <strong>{health.risky_count.toLocaleString("vi-VN")}</strong>
                </li>
                <li>
                  <span>Spam</span>
                  <strong>{health.spam_count.toLocaleString("vi-VN")}</strong>
                </li>
                <li>
                  <span>Công kích, thù ghét</span>
                  <strong>{health.toxic_count.toLocaleString("vi-VN")}</strong>
                </li>
              </ul>
            </>
          )}
        </Card>

        <Card title="Chủ đề cộng đồng đang bàn" className="span-4" delay={0.05}>
          {loading && <SkeletonBlock height={200} />}
          {!loading &&
            (health?.top_topics?.length ? (
              <TopicBars topics={health.top_topics.slice(0, 7)} />
            ) : (
              <EmptyState message="Chưa đủ tin nhắn để rút ra chủ đề." />
            ))}
        </Card>

        <Card title="Phân loại quyết định" className="span-4" delay={0.1}>
          {loading && <SkeletonBlock height={200} />}
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

      <div className="page-grid__row">
        <Card
          title="Sự cố mới nhất"
          className="span-12"
          delay={0.05}
          action={
            <Link to="/cong-dong" className="btn btn--ghost">
              Xem toàn bộ hàng đợi <ArrowRight size={13} weight="bold" />
            </Link>
          }
        >
          {loading && <SkeletonLine width="70%" />}
          {!loading &&
            (incidents && incidents.length > 0 ? (
              <ActivityFeed incidents={incidents} onSelect={setOpenId} />
            ) : (
              <EmptyState message="Hệ thống chưa ghi nhận sự cố nào gần đây." />
            ))}
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
