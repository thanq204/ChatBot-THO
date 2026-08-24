import { useCallback, useDeferredValue, useState } from "react";
import { useQueries, useQueryClient } from "@tanstack/react-query";
import {
  ArrowClockwise,
  LinkBreak,
  MagnifyingGlass,
  Sparkle,
  Star,
  Trophy,
  UsersThree,
} from "@phosphor-icons/react";
import Badge from "../components/Badge.jsx";
import Card from "../components/Card.jsx";
import { EmptyState, ErrorState } from "../components/StatePanels.jsx";
import { SkeletonBlock } from "../components/Skeleton.jsx";
import { ops } from "../api/client.js";
import { queryKeys } from "../lib/queryClient.js";
import { formatNumber, relativeTime } from "../lib/format.js";

const LEVEL_META = {
  new: ["Mới", "var(--text-muted)"],
  active: ["Tích cực", "var(--sev-low)"],
  contributor: ["Đóng góp", "var(--accent-solid)"],
  veteran: ["Kỳ cựu", "var(--sev-medium)"],
};

const TRIGGER_LABELS = {
  automatic: "Tự động có giới hạn",
  community_signal: "Phản hồi cộng đồng",
  admin_review: "Admin/Mod duyệt",
  event_confirmation: "Xác nhận sự kiện",
};

export default function ExperiencePage() {
  const queryClient = useQueryClient();
  const [query, setQuery] = useState("");
  const [level, setLevel] = useState("");
  const deferredQuery = useDeferredValue(query);
  const [membersQuery, linksQuery, rulesQuery] = useQueries({
    queries: [
      { queryKey: queryKeys.experience, queryFn: ops.experience },
      { queryKey: queryKeys.flaggedLinks, queryFn: ops.flaggedLinks },
      { queryKey: queryKeys.experienceRules, queryFn: ops.experienceRules },
    ],
  });

  const members = membersQuery.data ?? [];
  const links = linksQuery.data ?? [];
  const rules = rulesQuery.data ?? [];
  const loading = membersQuery.isPending || linksQuery.isPending || rulesQuery.isPending;
  const error = (membersQuery.error || linksQuery.error || rulesQuery.error)?.message ?? "";
  const blockedLinks = links.filter((link) => link.status === "blocked");

  const load = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: queryKeys.experience });
    queryClient.invalidateQueries({ queryKey: queryKeys.flaggedLinks });
    queryClient.invalidateQueries({ queryKey: queryKeys.experienceRules });
  }, [queryClient]);

  const needle = deferredQuery.trim().toLowerCase();
  const visibleMembers = members.filter((member) => {
    const matchesText = !needle || [member.display_name, member.platform_user_id, member.community_id]
      .filter(Boolean)
      .join(" ")
      .toLowerCase()
      .includes(needle);
    return matchesText && (!level || member.level === level);
  });
  const totalExp = members.reduce((total, member) => total + member.exp_score, 0);
  const contributors = members.filter((member) => ["contributor", "veteran"].includes(member.level)).length;

  return (
    <div className="page-grid reputation-page">
      <div className="page-grid__row">
        <Card title="Kinh nghiệm cộng đồng" className="span-12 reputation-hero" action={(
          <button type="button" className="btn btn--ghost" onClick={load} disabled={loading}>
            <ArrowClockwise size={15} /> Làm mới
          </button>
        )}>
          <p className="muted small">
            EXP chỉ ghi nhận hoạt động và đóng góp tích cực của thành viên thật. Vi phạm, tranh chấp và độ tin cậy người bán được xử lý ở hồ sơ riêng, không làm EXP âm.
          </p>
          <div className="reputation-stats">
            <ExperienceStat icon={UsersThree} label="Thành viên" value={members.length} />
            <ExperienceStat icon={Sparkle} label="Tổng EXP" value={totalExp} tone="positive" />
            <ExperienceStat icon={Trophy} label="Người đóng góp" value={contributors} tone="warning" />
            <ExperienceStat icon={LinkBreak} label="Link đang chặn" value={blockedLinks.length} tone="danger" />
          </div>
        </Card>
      </div>

      {error && <ErrorState message={`Không tải được bảng EXP: ${error}`} onRetry={load} />}
      {!error && (
        <div className="page-grid__row">
          <Card title="Bảng xếp hạng EXP" className="span-12">
            <div className="reputation-toolbar">
              <label className="search-field">
                <MagnifyingGlass size={17} />
                <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Tìm tên hoặc User ID..." />
              </label>
              <select value={level} onChange={(event) => setLevel(event.target.value)} aria-label="Lọc cấp EXP">
                <option value="">Tất cả cấp EXP</option>
                {Object.entries(LEVEL_META).map(([value, [label]]) => <option value={value} key={value}>{label}</option>)}
              </select>
            </div>
            {loading && <SkeletonBlock height={280} />}
            {!loading && visibleMembers.length === 0 && <EmptyState message="Chưa có thành viên phù hợp bộ lọc." />}
            {!loading && visibleMembers.length > 0 && (
              <div className="reputation-table-wrap">
                <table className="reputation-table">
                  <thead><tr><th>Hạng</th><th>Thành viên</th><th>EXP</th><th>Cấp</th><th>Sự kiện ghi nhận</th><th>Cập nhật</th></tr></thead>
                  <tbody>
                    {visibleMembers.map((member) => {
                      const rank = members.findIndex((item) => item.platform_user_id === member.platform_user_id) + 1;
                      const [label, tone] = LEVEL_META[member.level] || LEVEL_META.new;
                      return (
                        <tr key={member.platform_user_id}>
                          <td><span className="reputation-rank">{rank}</span></td>
                          <td><strong>{member.display_name || "Chưa có tên"}</strong><small>User ID: {member.platform_user_id}</small></td>
                          <td className="score-positive">+{formatNumber(member.exp_score)}</td>
                          <td><Badge tone={tone}>{label}</Badge></td>
                          <td>{formatNumber(member.event_count)}</td>
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
          <Card title="Nhiệm vụ EXP" className="span-12">
            <p className="muted small">
              Chỉ nhiệm vụ cộng EXP xuất hiện ở đây. Giới hạn ngày/tuần, loại bot, loại tự thả phản hồi và chống ghi nhận trùng giúp giảm cày điểm.
            </p>
            {loading && <SkeletonBlock height={220} />}
            {!loading && (
              <div className="reputation-rule-grid">
                {rules.map((rule) => (
                  <article className="reputation-rule" key={rule.rule_id}>
                    <div className="reputation-rule__head">
                      <strong>{rule.name}</strong>
                      <span className="score-positive">+{rule.points} EXP</span>
                    </div>
                    <p>{rule.description}</p>
                    <div className="chip-row">
                      <Badge tone={rule.active ? "var(--sev-low)" : "var(--text-muted)"}>{rule.active ? "Đang áp dụng" : "Chờ duyệt"}</Badge>
                      <span className="chip">{TRIGGER_LABELS[rule.trigger_mode] || rule.trigger_mode}</span>
                      {rule.daily_limit != null && <span className="chip">Tối đa {rule.daily_limit}/ngày</span>}
                      {rule.weekly_limit != null && <span className="chip">Tối đa {rule.weekly_limit}/tuần</span>}
                    </div>
                    <ul>{rule.requirements.map((requirement) => <li key={requirement}>{requirement}</li>)}</ul>
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
            <p className="muted small">Blocklist là lớp bảo vệ realtime riêng. Phản hồi ❌ không trừ EXP và không phải kết luận người gửi thiếu uy tín.</p>
            {loading && <SkeletonBlock height={160} />}
            {!loading && blockedLinks.length === 0 && <EmptyState message="Chưa có link nào trong blocklist." />}
            {!loading && blockedLinks.map((link) => (
              <article className="flagged-link-row" key={link.link_id}>
                <LinkBreak size={20} weight="duotone" />
                <div><strong>{link.domain}</strong><code>{link.canonical_url}</code></div>
                <div><Badge tone="var(--sev-critical)">Đang chặn</Badge><small>{formatNumber(link.flag_count)} lần gắn cờ · {relativeTime(link.last_seen_at)}</small></div>
              </article>
            ))}
          </Card>
        </div>
      )}
    </div>
  );
}

function ExperienceStat({ icon: Icon = Star, label, value, tone = "" }) {
  return (
    <div className={`reputation-stat ${tone ? `reputation-stat--${tone}` : ""}`}>
      <Icon size={20} weight="duotone" />
      <span>{label}</span>
      <strong>{formatNumber(value)}</strong>
    </div>
  );
}
