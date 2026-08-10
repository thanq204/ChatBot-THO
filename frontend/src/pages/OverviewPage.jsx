import { useCallback, useEffect, useState } from "react";
import { ChatsCircle, WarningCircle, SquaresFour, ArrowsClockwise } from "@phosphor-icons/react";
import Card from "../components/Card.jsx";
import StatTile from "../components/StatTile.jsx";
import RankList from "../components/RankList.jsx";
import PlatformRing from "../components/PlatformRing.jsx";
import BarChart from "../components/BarChart.jsx";
import ActivityFeed from "../components/ActivityFeed.jsx";
import { SkeletonLine, SkeletonBlock } from "../components/Skeleton.jsx";
import { ErrorState, EmptyState } from "../components/StatePanels.jsx";
import { ops } from "../api/client.js";
import { categoryLabel, platformLabel, CATEGORY_COLORS } from "../lib/taxonomy.js";

const DECISION_LABELS = { allow: "Cho phép", warn: "Cảnh báo", hide: "Ẩn", hold_for_review: "Chờ review" };
const DECISION_COLORS = { allow: "var(--sev-low)", warn: "var(--sev-medium)", hide: "var(--sev-high)", hold_for_review: "var(--accent-solid)" };

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

export default function OverviewPage() {
  const [summary, setSummary] = useState(null);
  const [platforms, setPlatforms] = useState(null);
  const [incidents, setIncidents] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [seeding, setSeeding] = useState(false);
  const [pullLimit, setPullLimit] = useState("100");
  const [syncing, setSyncing] = useState("");
  const [syncResult, setSyncResult] = useState(null);

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    Promise.all([ops.analytics(), ops.platforms(), ops.incidents()])
      .then(([summaryRes, platformsRes, incidentsRes]) => {
        setSummary(summaryRes);
        setPlatforms(platformsRes);
        setIncidents([...incidentsRes].sort((a, b) => new Date(b.updated_at) - new Date(a.updated_at)).slice(0, 6));
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

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
  const platformBars = summary
    ? Object.entries(summary.by_platform).map(([platform, value]) => ({
        key: platform,
        label: platformLabel(platform),
        value,
      }))
    : [];
  const decisionRows = summary
    ? Object.entries(summary.by_decision).sort((a, b) => b[1] - a[1])
    : [];

  return (
    <div className="page-grid">
      <div className="page-grid__row">
        <Card title="Chào mừng trở lại" className="span-4">
          {loading && (
            <div className="stack">
              <SkeletonLine width="70%" />
              <SkeletonBlock height={160} />
            </div>
          )}
          {!loading && summary && (
            <>
              <p className="muted">
                Bạn có {summary.messages_analyzed.toLocaleString("vi-VN")} tin nhắn đã quét và{" "}
                {(summary.messages_analyzed - (summary.by_decision.allow ?? 0)).toLocaleString("vi-VN")} vi phạm gắn
                thẻ.
              </p>
              {categoryRanks.length > 0 ? (
                <RankList items={categoryRanks} />
              ) : (
                <EmptyState message="Chưa có vi phạm nào được ghi nhận." />
              )}
            </>
          )}
        </Card>

        <Card title="Tin nhắn theo nền tảng" className="span-5" delay={0.05}>
          {loading && <SkeletonBlock height={220} />}
          {!loading && (platformBars.length > 0 ? (
            <BarChart items={platformBars} />
          ) : (
            <EmptyState
              message="Chưa có dữ liệu tin nhắn."
              action={
                <button type="button" className="btn btn--primary" onClick={seedDemo} disabled={seeding}>
                  {seeding ? "Đang nạp..." : "Nạp dữ liệu demo"}
                </button>
              }
            />
          ))}
        </Card>

        <Card title="Tiến độ giám sát" className="span-3" delay={0.1}>
          {loading && <SkeletonBlock height={160} />}
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
                {syncResult && <p className={`platform-sync__result platform-sync__result--${syncResult.tone}`}>{syncResult.text}</p>}
              </div>
            </>
          )}
        </Card>
      </div>

      <div className="page-grid__row">
        <Card title="Phân loại quyết định" className="span-4" delay={0.05}>
          {loading && <SkeletonBlock height={180} />}
          {!loading && (decisionRows.length > 0 ? (
            <ul className="decision-list">
              {decisionRows.map(([decision, count]) => (
                <li key={decision} className="decision-list__row">
                  <span className="decision-list__dot" style={{ background: DECISION_COLORS[decision] }} />
                  <span className="decision-list__label">{DECISION_LABELS[decision] ?? decision}</span>
                  <span className="decision-list__value">{count.toLocaleString("vi-VN")}</span>
                </li>
              ))}
            </ul>
          ) : (
            <EmptyState message="Chưa có quyết định kiểm duyệt nào." />
          ))}
        </Card>

        <Card title="Luồng hoạt động thời gian thực" className="span-5" delay={0.1}>
          {loading && <SkeletonBlock height={260} />}
          {!loading && (incidents && incidents.length > 0 ? (
            <ActivityFeed incidents={incidents} />
          ) : (
            <EmptyState message="Hệ thống chưa ghi nhận sự cố nào gần đây." />
          ))}
        </Card>

        <div className="span-3 stack">
          <StatTile
            label="Tin nhắn đã quét"
            value={summary?.messages_analyzed ?? 0}
            icon={ChatsCircle}
            tone="brand"
            meta="Tổng cộng"
            delay={0.15}
          />
          <StatTile
            label="Sự cố đang mở"
            value={summary?.open_incidents ?? 0}
            icon={WarningCircle}
            tone="alert"
            meta={summary ? `${summary.critical_incidents} nghiêm trọng` : ""}
            delay={0.2}
          />
        </div>
      </div>
    </div>
  );
}
