import { PaperPlaneTiltIcon } from "@phosphor-icons/react";
import { useState } from "react";
import { ops } from "../../api/client.js";
import { Notice, Panel, SkeletonText } from "../ui.jsx";

export default function RagAsk({ datasets = [], title = "Hỏi policy nội bộ", subtitle }) {
  const [question, setQuestion] = useState("");
  const [dataset, setDataset] = useState("");
  const [state, setState] = useState({ status: "idle", data: null, error: "" });

  async function submit(event) {
    event.preventDefault();
    setState({ status: "loading", data: null, error: "" });
    try {
      setState({ status: "done", data: await ops.ask(question, dataset), error: "" });
    } catch (error) {
      setState({ status: "error", data: null, error: error.message });
    }
  }

  return (
    <Panel title={title} subtitle={subtitle}>
      <form onSubmit={submit}>
        <label>
          <span>Câu hỏi</span>
          <textarea
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            rows={4}
            maxLength={2000}
            placeholder="Ví dụ: Khi nào nên hold for review?"
            required
          />
        </label>
        {datasets.length > 0 && (
          <label>
            <span>Dataset</span>
            <select value={dataset} onChange={(event) => setDataset(event.target.value)}>
              <option value="">Tất cả dataset phù hợp</option>
              {datasets.map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </select>
          </label>
        )}
        <button type="submit" className="icon-btn" disabled={state.status === "loading" || !question.trim()}>
          <PaperPlaneTiltIcon size={14} weight="bold" />
          {state.status === "loading" ? "Đang tìm knowledge..." : "Ask knowledge hub"}
        </button>
      </form>

      <div style={{ marginTop: 16 }}>
        {state.status === "loading" && <SkeletonText lines={3} />}
        {state.status === "error" && <Notice tone="error">{state.error}</Notice>}
        {state.status === "done" && state.data && (
          <div className="detail">
            <p style={{ color: "var(--ink)", whiteSpace: "pre-wrap" }}>{state.data.answer}</p>
            <div className="meta" style={{ marginTop: 10 }}>
              Nguồn: {(state.data.sources || []).map((source) => source.title).join(", ") || "không có"} ·{" "}
              {state.data.model_used}
            </div>
          </div>
        )}
      </div>
    </Panel>
  );
}
