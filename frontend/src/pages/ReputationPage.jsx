import { useCallback, useDeferredValue, useEffect, useState } from "react";
import {
  ArrowClockwise,
  CheckCircle,
  LinkBreak,
  MagnifyingGlass,
  ShieldWarning,
  Trophy,
} from "@phosphor-icons/react";
import Badge from "../components/Badge.jsx";
import Card from "../components/Card.jsx";
import { EmptyState, ErrorState } from "../components/StatePanels.jsx";
import { SkeletonBlock } from "../components/Skeleton.jsx";
import { ops } from "../api/client.js";
import { formatNumber, relativeTime } from "../lib/format.js";

const STATUS_META = {
  trusted: ["Uy tín tốt", "var(--sev-low)"],
  neutral: ["Bình thường", "var(--text-muted)"],
  watch: ["Cần theo dõi", "var(--sev-medium)"],
  risk: ["Rủi ro", "var(--sev-critical)"],
};

const TRIGGER_LABELS = {
  automatic: "Tự động có giới hạn",
  community_signal: "Phản hồi cộng đồng",
  admin_review: "Admin/Mod duyệt",
  event_confirmation: "Xác nhận sự kiện",
};

export default function ReputationPage() {
  const [members, setMembers] = useState(null);
  const [links, setLinks] = useState(null);
  const [rules, setRules] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("");
  const deferredQuery = useDeferredValue(query);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [memberRows, linkRows, ruleRows] = await Promise.all([
        ops.reputation(),
        ops.flaggedLinks(),
        ops.reputationRules(),
      ]);
      setMembers(memberRows);
      setLinks(linkRows);
      setRules(ruleRows);
      setError("");
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const needle = deferredQuery.trim().toLowerCase();
  const visibleMembers = (members || []).filter((member) => {
    const matchesText = !needle || [member.display_name, member.platform_user_id, member.community_id]
      .filter(Boolean)
      .join(" ")
      .toLowerCase()
      .includes(needle);
    return matchesText && (!status || member.status === status);
  });
  const trusted = (members || []).filter((member) => member.status === "trusted").length;
  const risky = (members || []).filter((member) => ["watch", "risk"].includes(member.status)).length;
  const blockedLinks = (links || []).filter((link) => link.status === "blocked");

  return (
    <div className="page-grid reputation-page">
      <div className="page-grid__row">
        <Card title="Uy tín cộng đồng" className="span-12 reputation-hero" action={(
          <button type="button" className="btn btn--ghost" onClick={load} disabled={loading}>
            <ArrowClockwise size={15} /> Làm mới
          </button>
        )}>
          <p className="muted small">
            AI không tự trừ điểm. Admin/Mod duyệt case ngay tại mục Cộng đồng; chỉ khi xác nhận vi phạm, hệ thống mới trừ một lần vào đúng User ID trong case.
          </p>
          <div className="reputation-stats">
            <ReputationStat icon={Trophy} label="Thành viên đã ghi nhận" value={(members || []).length} />
            <ReputationStat icon={CheckCircle} label="Uy tín tốt" value={trusted} tone="positive" />
            <ReputationStat icon={ShieldWarning} label="Cần theo dõi" value={risky} tone="warning" />
            <ReputationStat icon={LinkBreak} label="Link đang chặn" value={blockedLinks.length} tone="danger" />
          </div>
        </Card>
      </div>

      {error && <ErrorState message={`Không tải được bảng uy tín: ${error}`} onRetry={load} />}
      {!error && (
        <div className="page-grid__row">
          <Card title="Bảng thành tích thành viên" className="span-12">
            <div className="reputation-toolbar">
              <label className="search-field">
                <MagnifyingGlass size={17} />
                <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Tìm tên hoặc User ID..." />
              </label>
              <select value={status} onChange={(event) => setStatus(event.target.value)} aria-label="Lọc mức uy tín">
                <option value="">Tất cả mức uy tín</option>
                <option value="trusted">Uy tín tốt</option>
                <option value="neutral">Bình thường</option>
                <option value="watch">Cần theo dõi</option>
                <option value="risk">Rủi ro</option>
              </select>
            </div>
            {loading && <SkeletonBlock height={280} />}
            {!loading && visibleMembers.length === 0 && <EmptyState message="Chưa có thành viên phù hợp bộ lọc." />}
            {!loading && visibleMembers.length > 0 && (
              <div className="reputation-table-wrap">
                <table className="reputation-table">
                  <thead><tr><th>Hạng</th><th>Thành viên</th><th>Điểm</th><th>Cộng</th><th>Trừ</th><th>Sự kiện</th><th>Trạng thái</th><th>Cập nhật</th></tr></thead>
                  <tbody>
                    {visibleMembers.map((member) => {
                      const rank = (members || []).findIndex((item) => item.member_id === member.member_id) + 1;
                      const [label, tone] = STATUS_META[member.status] || STATUS_META.neutral;
                      return (
                        <tr key={member.member_id}>
                          <td><span className="reputation-rank">{rank}</span></td>
                          <td><strong>{member.display_name || "Chưa có tên"}</strong><small>User ID: {member.platform_user_id}</small></td>
                          <td className={member.reputation_score < 0 ? "score-negative" : "score-positive"}>{member.reputation_score > 0 ? "+" : ""}{formatNumber(member.reputation_score)}</td>
                          <td className="score-positive">+{formatNumber(member.positive_points)}</td>
                          <td className="score-negative">-{formatNumber(member.penalty_points)}</td>
                          <td>{formatNumber(member.event_count)}</td>
                          <td><Badge tone={tone}>{label}</Badge></td>
                          <td>{relativeTime(member.last_event_at || member.last_seen_at)}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </Card>
        </div>
      )}

      {!error && (
        <div className="page-grid__row">
          <Card title="Nhiệm vụ và luật điểm" className="span-12">
            <p className="muted small">
              Các nhiệm vụ gắn nhãn “Chờ duyệt” đã được lưu nhưng chưa chạy. Giới hạn ngày/tuần và yêu cầu nhiều người xác nhận giúp tránh spam hoặc trao đổi phản hồi để cày điểm.
            </p>
            {loading && <SkeletonBlock height={220} />}
            {!loading && (
              <div className="reputation-rule-grid">
                {(rules || []).map((rule) => (
                  <article className={`reputation-rule ${rule.points < 0 ? "reputation-rule--penalty" : ""}`} key={rule.rule_id}>
                    <div className="reputation-rule__head">
                      <strong>{rule.name}</strong>
                      <span className={rule.points < 0 ? "score-negative" : "score-positive"}>
                        {rule.points > 0 ? "+" : ""}{rule.points}
                      </span>
                    </div>
                    <p>{rule.description}</p>
                    <div className="chip-row">
                      <Badge tone={rule.active ? "var(--sev-low)" : "var(--text-muted)"}>
                        {rule.active ? "Đang áp dụng" : "Chờ duyệt"}
                      </Badge>
                      <span className="chip">{TRIGGER_LABELS[rule.trigger_mode] || rule.trigger_mode}</span>
                      {rule.daily_limit != null && <span className="chip">Tối đa {rule.daily_limit}/ngày</span>}
                      {rule.weekly_limit != null && <span className="chip">Tối đa {rule.weekly_limit}/tuần</span>}
                    </div>
                    <ul>
                      {rule.requirements.map((requirement) => <li key={requirement}>{requirement}</li>)}
                    </ul>
                  </article>
                ))}
              </div>
            )}
          </Card>
        </div>
      )}

      {!error && (
        <div className="page-grid__row">
          <Card title="Link bị cộng đồng từ chối" className="span-12">
            <p className="muted small">Link đạt 3 phản hồi ❌ được lưu theo URL chuẩn hóa để bảo vệ realtime. Điểm chỉ bị trừ nếu Admin/Mod xác nhận case tương ứng ở mục Cộng đồng.</p>
            {loading && <SkeletonBlock height={180} />}
            {!loading && blockedLinks.length === 0 && <EmptyState message="Chưa có link nào trong blocklist." />}
            {!loading && blockedLinks.length > 0 && (
              <div className="flagged-link-list">
                {blockedLinks.map((link) => (
                  <article className="flagged-link-row" key={link.link_id}>
                    <LinkBreak size={20} weight="duotone" />
                    <div><strong>{link.domain}</strong><code>{link.canonical_url}</code></div>
                    <div><Badge tone="var(--sev-critical)">Đang chặn</Badge><small>{formatNumber(link.flag_count)} lần gắn cờ · {relativeTime(link.last_seen_at)}</small></div>
                  </article>
                ))}
              </div>
            )}
          </Card>
        </div>
      )}
    </div>
  );
}

function ReputationStat({ icon: Icon, label, value, tone = "" }) {
  return (
    <div className={`reputation-stat ${tone ? `reputation-stat--${tone}` : ""}`}>
      <Icon size={20} weight="duotone" />
      <span>{label}</span>
      <strong>{formatNumber(value)}</strong>
    </div>
  );
}
