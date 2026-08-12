import { useCallback, useEffect, useState } from "react";
import { PaperPlaneRight, Sparkle, CheckCircle, WarningCircle, EyeSlash, Hourglass } from "@phosphor-icons/react";
import Card from "../components/Card.jsx";
import Badge from "../components/Badge.jsx";
import { SkeletonBlock } from "../components/Skeleton.jsx";
import { ErrorState, EmptyState } from "../components/StatePanels.jsx";
import { moderation } from "../api/client.js";
import { moderationCategoryLabel, moderationActionLabel, MODERATION_ACTION_COLORS, severityLabel, SEVERITY_COLORS } from "../lib/taxonomy.js";
import { percent } from "../lib/format.js";

const ACTION_ICONS = { allow: CheckCircle, warn: WarningCircle, hide: EyeSlash, review: Hourglass };
const BLANK_FORM = { userId: "U001", channel: "general", text: "" };

export default function UserManagementPage() {
  const [status, setStatus] = useState(null);
  const [samples, setSamples] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [form, setForm] = useState(BLANK_FORM);
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState(null);
  const [resultError, setResultError] = useState(null);

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    Promise.all([moderation.status(), moderation.demoCases()])
      .then(([statusRes, cases]) => {
        setStatus(statusRes);
        setSamples(cases);
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const applySample = (sample) => {
    setForm({ userId: sample.user_id, channel: sample.channel, text: sample.text });
    setResult(null);
    setResultError(null);
  };

  const submit = async (event) => {
    event.preventDefault();
    if (!form.text.trim() || submitting) return;
    setSubmitting(true);
    setResultError(null);
    try {
      const res = await moderation.submit({ user_id: form.userId.trim() || "U001", text: form.text.trim(), channel: form.channel.trim() || "general" });
      setResult(res);
    } catch (err) {
      setResultError(err.message);
      setResult(null);
    } finally {
      setSubmitting(false);
    }
  };

  if (error) {
    return (
      <div className="page-grid">
        <ErrorState message={`Không lấy được dữ liệu người dùng: ${error}`} onRetry={load} />
      </div>
    );
  }

  return (
    <div className="page-grid">
      <div className="page-grid__row">
        <Card title="Trạng thái hệ thống kiểm duyệt" className="span-5">
          {loading && <SkeletonBlock height={160} />}
          {!loading && status && (
            <div className="sandbox-grid">
              <div className="sandbox-stat">
                <span className="muted small">Chế độ</span>
                <strong>{status.mode}</strong>
              </div>
              <div className="sandbox-stat">
                <span className="muted small">Provider</span>
                <strong>{status.provider}</strong>
              </div>
              <div className="sandbox-stat">
                <span className="muted small">Đã cấu hình API key</span>
                <strong>{status.configured ? "Có" : "Chưa"}</strong>
              </div>
              <div className="sandbox-stat">
                <span className="muted small">Cho phép fallback mock</span>
                <strong>{status.allow_mock_fallback ? "Có" : "Không"}</strong>
              </div>
              <div className="sandbox-stat">
                <span className="muted small">Model triage</span>
                <strong>{status.triage_model}</strong>
              </div>
              <div className="sandbox-stat">
                <span className="muted small">Model review</span>
                <strong>{status.review_model}</strong>
              </div>
            </div>
          )}
        </Card>

        <Card title="Bộ dữ liệu demo" className="span-7" delay={0.05}>
          {loading && <SkeletonBlock height={160} />}
          {!loading && (!samples || samples.length === 0) && <EmptyState message="Chưa có case demo nào." />}
          {!loading && samples && samples.length > 0 && (
            <div className="list">
              {samples.map((sample, index) => (
                <button key={index} type="button" className="list-row" onClick={() => applySample(sample)}>
                  <div className="list-row__head">
                    <span className="list-row__title">{sample.user_id}</span>
                    <span className="list-row__meta">#{sample.channel}</span>
                  </div>
                  <p className="list-row__body">{sample.text}</p>
                </button>
              ))}
            </div>
          )}
        </Card>
      </div>

      <div className="page-grid__row">
        <Card title="Giả lập gửi tin theo người dùng" className="span-6">
          <form className="stack" onSubmit={submit}>
            <div className="field-row">
              <label className="field">
                User ID
                <input value={form.userId} onChange={(event) => setForm((prev) => ({ ...prev, userId: event.target.value }))} maxLength={100} />
              </label>
              <label className="field">
                Kênh
                <input value={form.channel} onChange={(event) => setForm((prev) => ({ ...prev, channel: event.target.value }))} maxLength={100} />
              </label>
            </div>
            <label className="field">
              Nội dung tin nhắn
              <textarea
                value={form.text}
                onChange={(event) => setForm((prev) => ({ ...prev, text: event.target.value }))}
                rows={4}
                maxLength={5000}
                placeholder="Nhập tin nhắn như một thành viên trong cộng đồng..."
                required
              />
            </label>
            <div className="form-actions">
              <button type="submit" className="btn btn--primary" disabled={submitting || !form.text.trim()}>
                <PaperPlaneRight size={16} /> {submitting ? "Đang gửi..." : "Gửi để kiểm duyệt"}
              </button>
            </div>
          </form>
        </Card>

        <Card title="Kết quả" className="span-6" delay={0.05}>
          {submitting && <SkeletonBlock height={200} />}
          {!submitting && resultError && <ErrorState message={resultError} onRetry={submit} />}
          {!submitting && !resultError && !result && (
            <EmptyState message="Chọn một case demo bên trên hoặc nhập tin nhắn để xem AI xử lý." action={<Sparkle size={22} weight="duotone" />} />
          )}
          {!submitting && !resultError && result && <SubmissionResult response={result} />}
        </Card>
      </div>
    </div>
  );
}

function SubmissionResult({ response }) {
  const result = response.moderation;
  const ActionIcon = ACTION_ICONS[result.action] ?? WarningCircle;
  const actionColor = MODERATION_ACTION_COLORS[result.action];

  return (
    <div className="stack">
      <div className="sandbox-result__header" style={{ borderColor: actionColor }}>
        <span className="sandbox-result__action" style={{ color: actionColor }}>
          <ActionIcon size={20} weight="bold" />
          {moderationActionLabel(result.action)}
        </span>
        <span className="muted small">{percent(result.confidence)} tin cậy</span>
      </div>

      <p className="muted">{response.message}</p>

      {response.queue_item_created && (
        <div className="quote">
          <span className="section-heading">Đã tạo review case</span>
          <p style={{ marginTop: 6 }}>Mã case: {response.review_id} — vào "Nhật ký kiểm duyệt" để Admin xử lý.</p>
        </div>
      )}

      <div className="sandbox-grid">
        <div className="sandbox-stat">
          <span className="muted small">Phân loại</span>
          <strong>{moderationCategoryLabel(result.category)}</strong>
        </div>
        <div className="sandbox-stat">
          <span className="muted small">Mức độ rủi ro</span>
          <strong style={{ color: SEVERITY_COLORS[result.risk_level] }}>{severityLabel(result.risk_level)}</strong>
        </div>
        <div className="sandbox-stat">
          <span className="muted small">Rule ID</span>
          <strong>{result.policy_id ?? "Không có"}</strong>
        </div>
        <div className="sandbox-stat">
          <span className="muted small">Model</span>
          <strong>
            {result.model_used} <span className="muted small">({result.mode})</span>
          </strong>
        </div>
      </div>

      <div>
        <span className="section-heading">Diễn giải</span>
        <p style={{ marginTop: 6 }}>{result.reason}</p>
        {result.evidence.length > 0 && (
          <div className="chip-row">
            {result.evidence.map((item) => (
              <span key={item} className="chip">
                {item}
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
