import { ArrowsClockwiseIcon } from "@phosphor-icons/react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { ops } from "../api/client.js";
import IncidentDetail from "../components/operations/IncidentDetail.jsx";
import IncidentQueue from "../components/operations/IncidentQueue.jsx";
import KnowledgeManager from "../components/operations/KnowledgeManager.jsx";
import MessageAnalyzer from "../components/operations/MessageAnalyzer.jsx";
import PlatformSync from "../components/operations/PlatformSync.jsx";
import PolicyManager from "../components/operations/PolicyManager.jsx";
import RagAsk from "../components/operations/RagAsk.jsx";
import { Notice } from "../components/ui.jsx";

export default function OperationsPage() {
  const [platform, setPlatform] = useState("");
  const [data, setData] = useState({ analytics: null, incidents: [], platforms: [], policies: [], knowledge: [] });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [selectedId, setSelectedId] = useState(null);
  const [detail, setDetail] = useState({ data: null, loading: false, error: "" });
  const [liveDefaultApplied, setLiveDefaultApplied] = useState(false);

  const load = useCallback(
    async (platformFilter) => {
      setError("");
      try {
        const [analytics, incidents, platforms, policies, knowledge] = await Promise.all([
          ops.analytics(),
          ops.incidents(platformFilter),
          ops.platforms(),
          ops.policies(),
          ops.knowledge(),
        ]);
        setData({ analytics, incidents, platforms, policies, knowledge });
      } catch (requestError) {
        setError(requestError.message);
      } finally {
        setLoading(false);
      }
    },
    [],
  );

  useEffect(() => {
    load(platform);
  }, [load, platform]);

  // On the very first load, jump the filter to whichever connector is actually
  // reading live so the queue is not empty for no reason.
  useEffect(() => {
    if (liveDefaultApplied || platform || data.platforms.length === 0) return;
    const live = data.platforms.find((item) => item.mode === "live-read");
    setLiveDefaultApplied(true);
    if (live) setPlatform(live.platform);
  }, [data.platforms, liveDefaultApplied, platform]);

  const refresh = useCallback(() => load(platform), [load, platform]);

  async function openIncident(id) {
    setSelectedId(id);
    setDetail({ data: null, loading: true, error: "" });
    try {
      setDetail({ data: await ops.incident(id), loading: false, error: "" });
    } catch (requestError) {
      setDetail({ data: null, loading: false, error: requestError.message });
    }
  }

  const datasets = useMemo(
    () => [...new Set(data.knowledge.map((item) => item.dataset).filter(Boolean))].sort(),
    [data.knowledge],
  );

  const configuredPlatforms = data.platforms.filter((item) => item.configured).length;

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Operations</h1>
          <p>Ba lớp kiểm tra lọc nhanh, phân loại chính sách và đọc ngữ cảnh trước khi tạo incident cho Admin.</p>
        </div>
        <button className="secondary icon-btn" onClick={refresh} disabled={loading}>
          <ArrowsClockwiseIcon size={14} className={loading ? "spin-icon" : undefined} />
          {loading ? "Đang tải..." : "Refresh dữ liệu"}
        </button>
      </div>

      {error && <Notice tone="error">{error}</Notice>}

      <PlatformSync platforms={data.platforms} onSynced={refresh} />

      <section className="kpis">
        <Kpi label="Messages analyzed" value={data.analytics?.messages_analyzed} loading={loading} />
        <Kpi label="Open incidents" value={data.analytics?.open_incidents} loading={loading} />
        <Kpi label="Critical" value={data.analytics?.critical_incidents} loading={loading} alert />
        <Kpi label="Platforms" value={configuredPlatforms} loading={loading} />
      </section>

      <div className="split">
        <IncidentQueue
          incidents={data.incidents}
          loading={loading}
          platform={platform}
          onPlatformChange={setPlatform}
          onSelect={openIncident}
          selectedId={selectedId}
        />
        <MessageAnalyzer onAnalyzed={refresh} />
      </div>

      <div className="split">
        <IncidentDetail data={detail.data} loading={detail.loading} error={detail.error} />
        <RagAsk datasets={datasets} subtitle="Trả lời dựa trên policy và tài liệu Admin đã nạp." />
      </div>

      <div className="split">
        <PolicyManager policies={data.policies} onChanged={refresh} />
        <KnowledgeManager knowledge={data.knowledge} onChanged={refresh} />
      </div>
    </>
  );
}

function Kpi({ label, value, loading, alert = false }) {
  return (
    <div className={`kpi ${alert && value > 0 ? "is-alert" : ""}`.trim()}>
      <span>{label}</span>
      <strong>{loading || value === undefined || value === null ? "-" : value}</strong>
    </div>
  );
}
