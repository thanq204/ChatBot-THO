import { FlaskIcon } from "@phosphor-icons/react";
import { useState } from "react";
import { ops } from "../../api/client.js";
import { Notice, Panel, SkeletonText, percent } from "../ui.jsx";

const INITIAL = {
  platform: "web",
  channel: "general",
  thread: "manual-review",
  text: "Mình không đồng ý, bạn check lại nguồn giúp nhé.",
};

export default function MessageAnalyzer({ onAnalyzed }) {
  const [form, setForm] = useState(INITIAL);
  const [state, setState] = useState({ status: "idle", result: null, error: "" });

  const update = (key) => (event) => setForm((prev) => ({ ...prev, [key]: event.target.value }));

  async function submit(event) {
    event.preventDefault();
    setState({ status: "loading", result: null, error: "" });
    try {
      const data = await ops.analyze({
        message_id: `web-${Date.now()}`,
        platform: form.platform,
        channel_id: form.channel,
        thread_key: form.thread,
        author_id: "admin-demo",
        text: form.text,
        timestamp: new Date().toISOString(),
      });
      setState({ status: "done", result: data.result, error: "" });
      await onAnalyzed();
    } catch (error) {
      setState({ status: "error", result: null, error: error.message });
    }
  }

  return (
    <Panel title="Test một message" subtitle="Chạy thử một nội dung qua ba gate mà không cần đợi connector.">
      <form onSubmit={submit}>
        <div className="field-row">
          <label>
            <span>Platform</span>
            <select value={form.platform} onChange={update("platform")}>
              <option value="web">web</option>
              <option value="discord">discord</option>
              <option value="telegram">telegram</option>
            </select>
          </label>
          <label>
            <span>Channel</span>
            <input value={form.channel} onChange={update("channel")} placeholder="channel_id" />
          </label>
        </div>
        <label>
          <span>Thread key</span>
          <input value={form.thread} onChange={update("thread")} placeholder="thread_key" />
        </label>
        <label>
          <span>Nội dung</span>
          <textarea value={form.text} onChange={update("text")} rows={5} placeholder="Dán message cần kiểm tra…" />
        </label>
        <button type="submit" className="icon-btn" disabled={state.status === "loading" || !form.text.trim()}>
          <FlaskIcon size={14} weight="bold" />
          {state.status === "loading" ? "Đang chạy 3 gates..." : "Chạy 3 gates"}
        </button>
      </form>

      <div style={{ marginTop: 16 }}>
        {state.status === "loading" && <SkeletonText lines={4} />}
        {state.status === "error" && <Notice tone="error">{state.error}</Notice>}
        {state.status === "done" && state.result && <Result result={state.result} />}
      </div>
    </Panel>
  );
}

function Result({ result }) {
  return (
    <div className="detail">
      <h3>
        {String(result.decision).toUpperCase()} · {result.category}
      </h3>
      <p>
        Risk {percent(result.risk_score)} · {result.severity} · {result.explanation}
      </p>
      {(result.gates || []).map((gate, index) => (
        <div className="evidence" key={index}>
          <b>{gate.gate}</b> · {gate.label} · {percent(gate.risk_score)}
          <div style={{ marginTop: 6 }}>{gate.explanation}</div>
          <small>Evidence: {(gate.evidence || []).join(", ") || "none"}</small>
        </div>
      ))}
    </div>
  );
}
