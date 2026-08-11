import {
  ClockCounterClockwiseIcon,
  PaperPlaneTiltIcon,
  SparkleIcon,
  TrashIcon,
} from "@phosphor-icons/react";
import { useCallback, useEffect, useState } from "react";
import { moderation } from "../api/client.js";
import RagAsk from "../components/operations/RagAsk.jsx";
import { Empty, Notice, Panel, SkeletonRows, dateText, percent } from "../components/ui.jsx";

const HISTORY_KEY = "community-channel-conversation-history";
const MAX_HISTORY = 30;

function readHistory() {
  try {
    const saved = JSON.parse(localStorage.getItem(HISTORY_KEY) || "[]");
    return Array.isArray(saved) ? saved.slice(-MAX_HISTORY) : [];
  } catch {
    return [];
  }
}

export default function MemberPage() {
  const [form, setForm] = useState({ userId: "U001", channel: "general", text: "", context: "" });
  const [history, setHistory] = useState(readHistory);
  const [samples, setSamples] = useState([]);
  const [mode, setMode] = useState(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);

  useEffect(() => {
    Promise.all([moderation.status(), moderation.demoCases()])
      .then(([status, cases]) => {
        setMode(status.configured ? `${status.mode} mode` : "Gemini API not configured");
        setSamples(cases);
      })
      .catch((requestError) => setError(requestError.message))
      .finally(() => setLoading(false));
  }, []);

  const update = (key) => (event) => setForm((prev) => ({ ...prev, [key]: event.target.value }));

  const clearHistory = useCallback(() => {
    localStorage.removeItem(HISTORY_KEY);
    setHistory([]);
  }, []);

  function loadSample(sample) {
    setForm({
      userId: sample.user_id,
      channel: sample.channel,
      text: sample.text,
      context: (sample.recent_context || []).join("\n"),
    });
  }

  async function submit(event) {
    event.preventDefault();
    setError("");
    if (!form.text.trim()) {
      setError("Vui lòng nhập nội dung trước khi submit.");
      return;
    }
    setSubmitting(true);
    try {
      // The last few submissions travel with the request so the model can judge a
      // message against what this member said just before it.
      const payload = {
        user_id: form.userId.trim(),
        role: "member",
        text: form.text.trim(),
        channel: form.channel.trim(),
        recent_context: [
          ...history.slice(-5).map((item) => item.text),
          ...form.context.split("\n").map((line) => line.trim()).filter(Boolean),
        ].slice(-10),
      };
      const data = await moderation.submit(payload);
      const next = [...history, { text: payload.text, created_at: new Date().toISOString(), action: data.moderation.action }].slice(
        -MAX_HISTORY,
      );
      localStorage.setItem(HISTORY_KEY, JSON.stringify(next));
      setHistory(next);
      setMode(data.moderation.fallback_used ? "mock fallback" : `${data.moderation.mode} mode`);
      setResult(data);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Member workspace</h1>
          <p>Mọi bài đăng đều qua một lượt kiểm tra an toàn trước khi tới cộng đồng.</p>
        </div>
        {mode && <span className="badge">{mode}</span>}
      </div>

      <div className="split">
        <Panel title="Submit content" subtitle="Cho chúng tôi biết bạn muốn chia sẻ điều gì.">
          <form onSubmit={submit}>
            <div className="field-row">
              <label>
                <span>User ID</span>
                <input value={form.userId} onChange={update("userId")} maxLength={100} required />
              </label>
              <label>
                <span>Channel</span>
                <input value={form.channel} onChange={update("channel")} maxLength={100} required />
              </label>
            </div>
            <label>
              <span>Nội dung</span>
              <textarea
                value={form.text}
                onChange={update("text")}
                maxLength={5000}
                placeholder="Viết bài đăng hoặc bình luận…"
                required
              />
              <small className="counter">{form.text.length} / 5000</small>
            </label>
            <label>
              <span>
                Ngữ cảnh thêm <b className="hint">tùy chọn</b>
              </span>
              <textarea
                value={form.context}
                onChange={update("context")}
                rows={3}
                placeholder="Thêm bất cứ điều gì model nên biết"
              />
            </label>
            {error && <Notice tone="error">{error}</Notice>}
            <button type="submit" className="icon-btn" disabled={submitting}>
              <PaperPlaneTiltIcon size={14} weight="bold" />
              {submitting ? "Đang kiểm tra..." : "Gửi đi kiểm duyệt"}
            </button>
          </form>
        </Panel>

        <div className="stack">
          <Panel
            title="Recent context"
            subtitle="Các bài bạn gửi trước đó được thêm vào đây tự động."
            actions={
              history.length > 0 && (
                <button type="button" className="link icon-btn" onClick={clearHistory}>
                  <TrashIcon size={12} />
                  Xóa lịch sử
                </button>
              )
            }
          >
            {history.length === 0 ? (
              <Empty icon={ClockCounterClockwiseIcon}>Lịch sử sẽ xuất hiện ở đây sau khi bạn gửi bài.</Empty>
            ) : (
              <div className="history">
                {history.map((item, index) => (
                  <div className="history-item" key={index}>
                    <span className="history-index">{String(index + 1).padStart(2, "0")}</span>
                    <div>
                      <p>{item.text}</p>
                      <small>
                        {dateText(item.created_at)}
                        {item.action ? ` · ${item.action.toUpperCase()}` : ""}
                      </small>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </Panel>

          <Panel title="Thử một kịch bản" subtitle="Nạp một mẫu để xem luồng review.">
            {loading ? (
              <SkeletonRows count={3} />
            ) : samples.length === 0 ? (
              <Empty icon={SparkleIcon}>Chưa có kịch bản mẫu.</Empty>
            ) : (
              <div className="stack">
                {samples.map((sample, index) => (
                  <button type="button" className="row-card" key={index} onClick={() => loadSample(sample)}>
                    <span className="meta">Case {index + 1}</span>
                    <strong style={{ fontSize: 13, fontWeight: 500 }}>{sample.text}</strong>
                  </button>
                ))}
              </div>
            )}
          </Panel>
        </div>
      </div>

      {result && <ModerationResult result={result} />}

      <RagAsk
        title="Hỏi về rules hoặc sự kiện"
        subtitle="Câu hỏi được tìm trong policy, rule và event documents mà Admin đã cập nhật."
      />
    </>
  );
}

function ModerationResult({ result }) {
  const { moderation: verdict } = result;
  return (
    <Panel
      title={result.review ? "Đã chuyển tới Admin review queue" : "Đã có quyết định tự động"}
      actions={<span className={`badge ${verdict.action}`}>{verdict.action}</span>}
    >
      <div className="data-grid">
        <div className="data-point">
          <span>Category</span>
          <strong>{verdict.category}</strong>
        </div>
        <div className="data-point">
          <span>Risk level</span>
          <strong>{verdict.risk_level}</strong>
        </div>
        <div className="data-point">
          <span>Confidence</span>
          <strong>{percent(verdict.confidence)}</strong>
        </div>
        <div className="data-point">
          <span>Model</span>
          <strong>{verdict.model_used}</strong>
        </div>
      </div>
      <p style={{ marginBottom: 8 }}>
        <b style={{ color: "var(--ink)" }}>Lý do:</b> {verdict.reason}
      </p>
      <p style={{ marginBottom: 8 }}>
        <b style={{ color: "var(--ink)" }}>Evidence:</b> {(verdict.evidence || []).join(" · ") || "không có"}
      </p>
      <Notice tone={result.review ? "" : "success"}>{result.message}</Notice>
      {verdict.fallback_reason && <p style={{ marginTop: 8, fontSize: 13 }}>{verdict.fallback_reason}</p>}
      {(verdict.agent_trace || []).length > 0 && (
        <div className="trace">
          <span>Agent pipeline</span>
          <strong>{verdict.agent_trace.join(" → ")}</strong>
        </div>
      )}
    </Panel>
  );
}
