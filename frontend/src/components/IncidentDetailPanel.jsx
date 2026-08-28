import { useCallback, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowSquareOut,
  CheckCircle,
  ShieldCheck,
  ShieldWarning,
  WarningCircle,
  ChatsCircle,
  DiscordLogo,
  TelegramLogo,
  User,
  Clock,
  ChatCircleText,
} from "@phosphor-icons/react";
import Badge from "./Badge.jsx";
import CaseActions from "./CaseActions.jsx";
import Disclosure from "./Disclosure.jsx";
import { SkeletonBlock, SkeletonLine } from "./Skeleton.jsx";
import { ErrorState, EmptyState } from "./StatePanels.jsx";
import { ops } from "../api/client.js";
import { queryKeys } from "../lib/queryClient.js";
import {
  platformLabel,
  severityLabel,
  SEVERITY_COLORS,
  statusLabel,
  STATUS_COLORS,
  categoryLabel,
  CATEGORY_COLORS,
  decisionLabel,
  DECISION_COLORS,
  auditEventLabel,
  vietnameseModerationText,
} from "../lib/taxonomy.js";
import { primaryCategory } from "../lib/incidents.js";
import { relativeTime, percent } from "../lib/format.js";
import { safeExternalUrl } from "../lib/urls.js";

const STATUS_OPTIONS = ["open", "monitoring", "snoozed"];

function FactItem({ label, value, icon: Icon }) {
  return (
    <div className="incident-fact-item">
      <span className="incident-fact-item__label">
        {Icon && <Icon size={13} weight="fill" />}
        {label}
      </span>
      <strong className="incident-fact-item__val">{value}</strong>
    </div>
  );
}

export default function IncidentDetailPanel({ incidentId, onUpdated, isModal = false }) {
  const queryClient = useQueryClient();
  const [actionError, setActionError] = useState("");
  const [savingStatus, setSavingStatus] = useState(false);
  const [savingReputation, setSavingReputation] = useState(false);

  const detailQuery = useQuery({
    queryKey: queryKeys.incident(incidentId),
    queryFn: () => ops.incident(incidentId),
    enabled: Boolean(incidentId),
  });

  const detail = incidentId ? detailQuery.data ?? null : null;
  const loading = Boolean(incidentId) && detailQuery.isPending;
  const error = actionError || (incidentId ? detailQuery.error?.message ?? "" : "");

  const loadDetail = useCallback(
    (id) => {
      setActionError("");
      queryClient.invalidateQueries({ queryKey: queryKeys.incident(id) });
    },
    [queryClient],
  );

  const refreshAfterWrite = useCallback(async () => {
    queryClient.setQueryData(queryKeys.incident(incidentId), await ops.incident(incidentId));
    onUpdated?.();
  }, [incidentId, onUpdated, queryClient]);

  async function updateStatus(status) {
    if (!incidentId) return;
    setSavingStatus(true);
    setActionError("");
    try {
      await ops.updateIncident(incidentId, { status });
      await refreshAfterWrite();
    } catch (err) {
      setActionError(err.message);
    } finally {
      setSavingStatus(false);
    }
  }

  async function decideReputation(outcome) {
    if (!incidentId) return;
    setSavingReputation(true);
    setActionError("");
    try {
      await ops.decideIncidentReputation(incidentId, {
        outcome,
        note:
          outcome === "confirmed"
            ? "Admin/Mod xác nhận trường hợp vi phạm."
            : "Admin/Mod xác nhận trường hợp không vi phạm.",
      });
      await refreshAfterWrite();
    } catch (err) {
      setActionError(err.message);
    } finally {
      setSavingReputation(false);
    }
  }

  if (!incidentId) {
    return (
      <div className="incident-detail-empty">
        <ChatsCircle size={48} weight="duotone" className="incident-detail-empty__icon" />
        <h3 className="incident-detail-empty__title">Chưa chọn trường hợp nào</h3>
        <p className="incident-detail-empty__desc">
          Hãy chọn một sự cố trong danh sách bên trái để xem toàn bộ ngữ cảnh hội thoại và thao tác xử lý.
        </p>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="stack" style={{ padding: isModal ? 0 : 20 }}>
        <SkeletonLine width="60%" />
        <SkeletonBlock height={180} />
        <SkeletonBlock height={220} />
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ padding: isModal ? 0 : 20 }}>
        <ErrorState message={error} onRetry={() => loadDetail(incidentId)} />
      </div>
    );
  }

  if (!detail) return null;

  const { incident, messages = [], audit = [] } = detail;
  const root = messages.find((item) => !item.parent_message_id) || messages[0];
  const rootSourceUrl = safeExternalUrl(incident.source_url || root?.source_url);
  const category = primaryCategory(incident);
  const reputationDecision = audit.find((item) => item.event_type === "incident_reputation_decision");
  const reputationPayload = reputationDecision?.payload || {};

  const PlatformIcon = incident.platform === "discord" ? DiscordLogo : incident.platform === "telegram" ? TelegramLogo : ChatsCircle;

  return (
    <div className={`incident-detail-panel${isModal ? " incident-detail-panel--modal" : ""}`}>
      {/* Panel Header */}
      <div className="incident-detail-header">
        <div className="incident-detail-header__top">
          <div className="incident-detail-header__badges">
            <span className="incident-platform-badge">
              <PlatformIcon size={16} weight="fill" />
              {platformLabel(incident.platform)}
              {incident.channel_id && ` · #${incident.channel_id}`}
            </span>
            <Badge tone={CATEGORY_COLORS[category]}>{categoryLabel(category)}</Badge>
            <Badge tone={SEVERITY_COLORS[incident.severity]}>{severityLabel(incident.severity)}</Badge>
            <Badge tone={STATUS_COLORS[incident.status]}>{statusLabel(incident.status)}</Badge>
          </div>
          <span className="incident-detail-header__id">#{incident.incident_id}</span>
        </div>

        <h2 className="incident-detail-title">{incident.title || "Trường hợp kiểm duyệt"}</h2>
      </div>

      {/* AI Summary Box */}
      <div className="case-callout">
        <span className="case-callout__label">
          <ShieldWarning size={14} weight="fill" /> Đánh giá từ AI Moderation Engine
        </span>
        <p>
          {vietnameseModerationText(
            incident.summary,
            category,
            `${categoryLabel(category)} từ ${root?.author_name || root?.author_id || "thành viên"}`,
          )}
        </p>
      </div>

      {/* Grid of Key Facts */}
      <div className="incident-facts-grid">
        <FactItem label="Mức rủi ro" value={percent(incident.risk_score)} icon={WarningCircle} />
        <FactItem label="Tổng tin nhắn" value={`${incident.message_count} tin`} icon={ChatCircleText} />
        <FactItem label="Đối tượng" value={root?.author_name || root?.author_id || "Ẩn danh"} icon={User} />
        <FactItem label="Cập nhật" value={relativeTime(incident.updated_at)} icon={Clock} />
      </div>

      {/* Root Violating Message */}
      {root && (
        <div className="incident-root-section">
          <span className="section-heading" style={{ marginBottom: 8, display: "block" }}>
            Tin nhắn vi phạm chính
          </span>
          <div className={`chat-bubble chat-bubble--${incident.platform || "discord"}`}>
            <div className="chat-bubble__avatar">
              {(root.author_name || root.author_id || "U").slice(0, 2).toUpperCase()}
            </div>
            <div className="chat-bubble__body">
              <div className="chat-bubble__meta">
                <span className="chat-bubble__author">{root.author_name || root.author_id}</span>
                <span className="chat-bubble__platform-tag">{platformLabel(incident.platform)}</span>
                <span className="chat-bubble__time">{relativeTime(root.timestamp)}</span>
              </div>
              <p className="chat-bubble__text">{root.text}</p>
              {rootSourceUrl && (
                <a
                  href={rootSourceUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="quote__link"
                  style={{ marginTop: 6 }}
                >
                  Mở tin gốc trên {platformLabel(incident.platform)} <ArrowSquareOut size={13} weight="bold" />
                </a>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Quick Action Decision Bar */}
      {incident.status === "resolved" ? (
        <div className="case-resolved-banner">
          <CheckCircle size={20} weight="fill" />
          <span className="case-resolved-banner__text">
            <strong>Đã xử lý xong</strong>
            {incident.assigned_to ? ` bởi ${incident.assigned_to}` : ""} · {relativeTime(incident.updated_at)}
          </span>
        </div>
      ) : (
        <div className="incident-action-box">
          <div className="incident-action-box__head">
            <div>
              <span className="section-heading" style={{ fontSize: 13.5 }}>
                Quyết định xử lý nhanh
              </span>
              <p className="muted small">
                Xác nhận vi phạm để lưu audit log và cảnh cáo, hoặc đóng trường hợp nếu an toàn.
              </p>
            </div>
          </div>

          <div className="incident-action-box__buttons">
            <button
              type="button"
              className="btn btn--primary"
              disabled={savingReputation || messages.length === 0}
              onClick={() => decideReputation("confirmed")}
            >
              <ShieldWarning size={14} weight="fill" />
              {savingReputation ? "Đang lưu..." : "Xác nhận vi phạm"}
            </button>
            <button
              type="button"
              className="btn btn--ghost"
              disabled={savingReputation}
              onClick={() => decideReputation("dismissed")}
            >
              <ShieldCheck size={14} weight="fill" />
              Không vi phạm
            </button>
          </div>

          <div className="field-row" style={{ marginTop: 12, paddingTop: 10, borderTop: "1px solid var(--border)" }}>
            <label className="field" style={{ flex: 1 }}>
              Trạng thái
              <select
                value={incident.status}
                disabled={savingStatus}
                onChange={(e) => updateStatus(e.target.value)}
              >
                {STATUS_OPTIONS.map((status) => (
                  <option key={status} value={status}>
                    {statusLabel(status)}
                  </option>
                ))}
              </select>
            </label>
            <label className="field" style={{ flex: 1 }}>
              Phụ trách
              <span className="muted small" style={{ paddingTop: 6 }}>
                {incident.assigned_to || "Chưa gán"}
              </span>
            </label>
          </div>
        </div>
      )}

      {/* Manual Actions Accordion */}
      <Disclosure label="Trừng phạt & Can thiệp Bot trực tiếp" count={messages.length ? undefined : 0}>
        {messages.length === 0 ? (
          <EmptyState message="Trường hợp này chưa có tin nhắn nên chưa xác định được đối tượng." />
        ) : (
          <CaseActions incident={incident} messages={messages} onDone={() => { loadDetail(incidentId); onUpdated?.(); }} />
        )}
      </Disclosure>

      {/* Thread Messages Accordion */}
      <Disclosure label="Toàn bộ tin nhắn trong chuỗi" count={messages.length}>
        {messages.length === 0 ? (
          <EmptyState message="Trường hợp này chưa có tin nhắn chi tiết." />
        ) : (
          <div className="list">
            {messages.map((item, index) => (
              <div className="list-row" key={item.message_id || index}>
                <div className="list-row__head">
                  <span className="list-row__title">
                    {item.parent_message_id ? "Tin trả lời" : "Tin gốc"} · {item.author_id}
                  </span>
                  <span className="list-row__meta">{relativeTime(item.timestamp)}</span>
                </div>
                <p className="list-row__body">{item.text}</p>
                <div className="chip-row">
                  {item.decision && (
                    <Badge tone={DECISION_COLORS[item.decision]}>{decisionLabel(item.decision)}</Badge>
                  )}
                  {item.category && <span className="chip">{categoryLabel(item.category)}</span>}
                  {item.risk_score != null && <span className="chip">rủi ro {percent(item.risk_score)}</span>}
                  {safeExternalUrl(item.source_url) && (
                    <a
                      href={safeExternalUrl(item.source_url)}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="chip chip--link"
                    >
                      Mở gốc <ArrowSquareOut size={11} weight="bold" />
                    </a>
                  )}
                </div>
                {item.explanation && (
                  <p className="muted small">
                    Vì sao: {vietnameseModerationText(item.explanation, item.category)}
                  </p>
                )}
              </div>
            ))}
          </div>
        )}
      </Disclosure>

      {/* Audit Log Accordion */}
      <Disclosure label="Nhật ký xử lý (Audit Trail)" count={audit.length}>
        {audit.length === 0 ? (
          <EmptyState message="Chưa có nhật ký xử lý cho trường hợp này." />
        ) : (
          <ol className="case-timeline">
            {audit.map((item) => (
              <li key={item.audit_id} className="case-timeline__row">
                <span className="case-timeline__event">{auditEventLabel(item.event_type)}</span>
                <span className="muted small">
                  {item.actor} · {relativeTime(item.created_at)}
                </span>
              </li>
            ))}
          </ol>
        )}
      </Disclosure>
    </div>
  );
}
