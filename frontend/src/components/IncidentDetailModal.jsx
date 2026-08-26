import { useCallback, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowSquareOut, CheckCircle } from "@phosphor-icons/react";
import Badge from "./Badge.jsx";
import CaseActions from "./CaseActions.jsx";
import Modal from "./Modal.jsx";
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

// "resolved" is deliberately excluded here: it's only reachable through the
// Xác nhận vi phạm/Không vi phạm buttons below, which record who reviewed the
// case. That keeps "Phụ trách" accurate instead of a manually-typed guess.
const STATUS_OPTIONS = ["open", "monitoring", "snoozed"];

/**
 * Case detail as a dialog, shared by the community list and the overview feed.
 * `onClose` must be a stable reference — Modal keys its Escape/scroll-lock
 * effect on it.
 */
export default function IncidentDetailModal({ incidentId, headline, onClose, onUpdated }) {
  const queryClient = useQueryClient();
  const [actionError, setActionError] = useState("");
  const [savingStatus, setSavingStatus] = useState(false);
  const [savingReputation, setSavingReputation] = useState(false);

  // `enabled` keeps the query dormant until a case is actually opened; reopening
  // the same case then renders from cache instead of re-fetching.
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

  /** Pull the case back from the server and let the parent list refresh too. */
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
        note: outcome === "confirmed" ? "Admin/Mod xác nhận trường hợp vi phạm." : "Admin/Mod xác nhận trường hợp không vi phạm.",
      });
      await refreshAfterWrite();
    } catch (err) {
      setActionError(err.message);
    } finally {
      setSavingReputation(false);
    }
  }

  return (
    <Modal open={Boolean(incidentId)} title={headline || "Chi tiết trường hợp"} onClose={onClose}>
      {loading && (
        <div className="stack">
          <SkeletonLine width="70%" />
          <SkeletonBlock height={260} />
        </div>
      )}
      {!loading && error && <ErrorState message={error} onRetry={() => loadDetail(incidentId)} />}
      {!loading && !error && detail && (
        <DetailBody
          detail={detail}
          onStatusChange={updateStatus}
          savingStatus={savingStatus}
          onReputationDecision={decideReputation}
          savingReputation={savingReputation}
          onActed={() => {
            // A completed action writes an audit entry, so refresh the case.
            loadDetail(incidentId);
            onUpdated?.();
          }}
        />
      )}
    </Modal>
  );
}

function Fact({ label, value }) {
  return (
    <div className="case-fact">
      <dt>{label}</dt>
      <dd>{value}</dd>
    </div>
  );
}

function DetailBody({ detail, onStatusChange, savingStatus, onReputationDecision, savingReputation, onActed }) {
  const { incident, messages = [], audit = [] } = detail;
  const root = messages.find((item) => !item.parent_message_id) || messages[0];
  const rootSourceUrl = safeExternalUrl(incident.source_url || root?.source_url);
  const category = primaryCategory(incident);
  const reputationDecision = audit.find((item) => item.event_type === "incident_reputation_decision");
  const reputationPayload = reputationDecision?.payload || {};

  return (
    <div className="stack">
      <div className="chip-row" style={{ marginTop: 0 }}>
        <Badge tone={CATEGORY_COLORS[category]}>{categoryLabel(category)}</Badge>
        <Badge tone={SEVERITY_COLORS[incident.severity]}>{severityLabel(incident.severity)}</Badge>
        <Badge tone={STATUS_COLORS[incident.status]}>{statusLabel(incident.status)}</Badge>
      </div>

      <div className="case-callout">
        <span className="case-callout__label">Vì sao trường hợp này được mở</span>
        <p>
          {vietnameseModerationText(
            incident.summary,
            category,
            `${categoryLabel(category)} từ ${root?.author_name || root?.author_id || "thành viên"}`,
          )}
        </p>
      </div>

      <dl className="case-facts">
        <Fact label="Nền tảng" value={platformLabel(incident.platform)} />
        <Fact label="Mức rủi ro" value={percent(incident.risk_score)} />
        <Fact label="Số tin nhắn" value={incident.message_count} />
        <Fact label="Cập nhật" value={relativeTime(incident.updated_at)} />
      </dl>

      {root && (
        <div className="quote">
          <span className="section-heading">Tin nhắn gốc</span>
          <p style={{ marginTop: 6 }}>{root.text}</p>
          <span className="muted small">
            {root.author_id} · {relativeTime(root.timestamp)}
          </span>
          {rootSourceUrl && (
            <a
              href={rootSourceUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="quote__link"
            >
              Mở tin nhắn gốc trên {platformLabel(incident.platform)} <ArrowSquareOut size={13} weight="bold" />
            </a>
          )}
        </div>
      )}

      {incident.status === "resolved" ? (
        <div className="case-resolved-banner">
          <CheckCircle size={20} weight="fill" />
          <span className="case-resolved-banner__text">
            <strong>Đã xử lý</strong>
            {incident.assigned_to ? ` bởi ${incident.assigned_to}` : ""} · {relativeTime(incident.updated_at)}
          </span>
        </div>
      ) : (
        <div className="field-row">
          <label className="field">
            Đổi trạng thái
            <select value={incident.status} disabled={savingStatus} onChange={(event) => onStatusChange(event.target.value)}>
              {STATUS_OPTIONS.map((status) => (
                <option key={status} value={status}>
                  {statusLabel(status)}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            Phụ trách
            <span className="muted small">{incident.assigned_to || "Chưa gán · tự ghi nhận khi xử lý"}</span>
          </label>
        </div>
      )}

      <div className="case-reputation-review">
        <div>
          <span className="section-heading">Duyệt vi phạm</span>
          {reputationDecision ? (
            <p className="muted small">
              {reputationPayload.outcome === "confirmed"
                ? `Đã xác nhận vi phạm của ${reputationPayload.affected_members || 0} thành viên. Quyết định được lưu vào audit và không làm thay đổi EXP.`
                : "Đã xác nhận trường hợp không vi phạm. Không có thay đổi EXP."}
            </p>
          ) : (
            <p className="muted small">
              AI chỉ cung cấp bằng chứng. Admin/Mod quyết định trường hợp; kết quả được lưu riêng và không trộn với EXP hoạt động cộng đồng.
            </p>
          )}
        </div>
        {!reputationDecision && incident.status !== "resolved" && (
          <div className="case-reputation-review__actions">
            <button
              type="button"
              className="btn btn--primary"
              disabled={savingReputation || messages.length === 0}
              onClick={() => onReputationDecision("confirmed")}
            >
              Xác nhận vi phạm
            </button>
            <button
              type="button"
              className="btn btn--ghost"
              disabled={savingReputation}
              onClick={() => onReputationDecision("dismissed")}
            >
              Không vi phạm
            </button>
          </div>
        )}
      </div>

      <Disclosure label="Xử lý thủ công người vi phạm" count={messages.length ? undefined : 0}>
        {messages.length === 0 ? (
          <EmptyState message="Trường hợp này chưa có tin nhắn nên chưa xác định được người vi phạm." />
        ) : (
          <CaseActions incident={incident} messages={messages} onDone={onActed} />
        )}
      </Disclosure>

      <Disclosure label="Tất cả tin nhắn trong trường hợp" count={messages.length}>
        {messages.length === 0 ? (
          <EmptyState message="Trường hợp này chưa có tin nhắn chi tiết." />
        ) : (
          <div className="list">
            {messages.map((item, index) => (
              <div className="list-row" key={item.message_id || index}>
                <div className="list-row__head">
                  <span className="list-row__title">
                    {item.parent_message_id ? "Tin trả lời" : "Tin nhắn gốc"} · {item.author_id}
                  </span>
                  <span className="list-row__meta">{relativeTime(item.timestamp)}</span>
                </div>
                <p className="list-row__body">{item.text}</p>
                <div className="chip-row">
                  {item.decision && <Badge tone={DECISION_COLORS[item.decision]}>{decisionLabel(item.decision)}</Badge>}
                  {item.category && <span className="chip">{categoryLabel(item.category)}</span>}
                  {item.risk_score != null && <span className="chip">rủi ro {percent(item.risk_score)}</span>}
                  {safeExternalUrl(item.source_url) && (
                    <a href={safeExternalUrl(item.source_url)} target="_blank" rel="noopener noreferrer" className="chip chip--link">
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

      <Disclosure label="Nhật ký xử lý" count={audit.length}>
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
