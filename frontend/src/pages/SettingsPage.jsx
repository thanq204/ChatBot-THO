import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { MagnifyingGlass, PencilSimple, Trash, FloppyDisk, Plus, X, UploadSimple, PaperPlaneRight } from "@phosphor-icons/react";
import Card from "../components/Card.jsx";
import { SkeletonBlock, SkeletonLine } from "../components/Skeleton.jsx";
import { ErrorState, EmptyState } from "../components/StatePanels.jsx";
import { ops, fileToBase64 } from "../api/client.js";
import { relativeTime } from "../lib/format.js";

const BLANK = { title: "", dataset: "", body: "", tags: "" };

function matches(item, query) {
  return [item.title, item.body, item.dataset, (item.tags || []).join(" ")].join(" ").toLowerCase().includes(query);
}

export default function SettingsPage() {
  const [knowledge, setKnowledge] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState("");
  const [form, setForm] = useState(BLANK);
  const [editingId, setEditingId] = useState(null);
  const [formOpen, setFormOpen] = useState(false);
  const [formError, setFormError] = useState("");
  const [saving, setSaving] = useState(false);

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    ops
      .knowledge()
      .then(setKnowledge)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const visible = useMemo(() => {
    if (!knowledge) return [];
    const needle = query.trim().toLowerCase();
    return needle ? knowledge.filter((item) => matches(item, needle)) : knowledge;
  }, [knowledge, query]);

  const update = (key) => (event) => setForm((prev) => ({ ...prev, [key]: event.target.value }));

  function startCreate() {
    setEditingId(null);
    setForm(BLANK);
    setFormError("");
    setFormOpen(true);
  }

  function startEdit(item) {
    setEditingId(item.document_id);
    setForm({ title: item.title, dataset: item.dataset || "", body: item.body, tags: (item.tags || []).join(", ") });
    setFormError("");
    setFormOpen(true);
  }

  function cancelEdit() {
    setEditingId(null);
    setForm(BLANK);
    setFormError("");
    setFormOpen(false);
  }

  async function submit(event) {
    event.preventDefault();
    setFormError("");
    setSaving(true);
    try {
      await ops.saveKnowledge(editingId || `KN-CUSTOM-${Date.now()}`, {
        title: form.title,
        body: form.body,
        dataset: form.dataset.trim() || "general",
        tags: form.tags.split(",").map((value) => value.trim()).filter(Boolean),
        active: true,
      });
      cancelEdit();
      load();
    } catch (err) {
      setFormError(err.message);
    } finally {
      setSaving(false);
    }
  }

  async function remove(item) {
    if (!window.confirm(`Xóa tài liệu "${item.title}"?`)) return;
    try {
      await ops.deleteKnowledge(item.document_id);
      if (editingId === item.document_id) cancelEdit();
      load();
    } catch (err) {
      setError(err.message);
    }
  }

  if (error) {
    return (
      <div className="page-grid">
        <ErrorState message={`Không lấy được knowledge base: ${error}`} onRetry={load} />
      </div>
    );
  }

  return (
    <div className="page-grid">
      <div className="page-grid__row">
        <Card
          title="Tài liệu tri thức (RAG)"
          className={formOpen ? "span-7" : "span-12"}
          action={
            !formOpen && (
              <button type="button" className="btn btn--primary" onClick={startCreate}>
                <Plus size={14} weight="bold" /> Thêm tài liệu
              </button>
            )
          }
        >
          <div className="search-box">
            <MagnifyingGlass size={15} />
            <input
              type="search"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Tìm tài liệu theo tiêu đề, nội dung, dataset..."
              aria-label="Tìm tài liệu"
            />
          </div>

          {loading && <SkeletonBlock height={240} />}
          {!loading && (!knowledge || knowledge.length === 0) && <EmptyState message="Chưa có tài liệu nào." />}
          {!loading && knowledge && knowledge.length > 0 && visible.length === 0 && (
            <EmptyState message={`Không có tài liệu nào khớp "${query}".`} />
          )}
          {!loading && visible.length > 0 && (
            <div className="list">
              {visible.map((item) => (
                <div className="list-row" key={item.document_id}>
                  <div className="list-row__head">
                    <span className="list-row__title">{item.title}</span>
                    <span className="list-row__meta">{item.dataset}</span>
                  </div>
                  <p className="list-row__body">{item.body}</p>
                  <span className="list-row__meta">tags: {(item.tags || []).join(", ") || "không có"}</span>
                  <div className="list-row__actions">
                    <button type="button" className="btn btn--ghost" onClick={() => startEdit(item)}>
                      <PencilSimple size={13} /> Sửa
                    </button>
                    <button type="button" className="btn btn--ghost" onClick={() => remove(item)}>
                      <Trash size={13} /> Xoá
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </Card>

        {formOpen && (
          <Card
            title={editingId ? "Sửa tài liệu" : "Thêm tài liệu mới"}
            className="span-5"
            delay={0.05}
            action={
              <button type="button" className="btn btn--ghost" onClick={cancelEdit} aria-label="Đóng">
                <X size={16} />
              </button>
            }
          >
          <form className="stack" onSubmit={submit}>
            <label className="field">
              Tiêu đề
              <input value={form.title} onChange={update("title")} placeholder="Tiêu đề tài liệu" required maxLength={200} />
            </label>
            <div className="field-row">
              <label className="field">
                Dataset
                <input value={form.dataset} onChange={update("dataset")} placeholder="channel_policy, events..." />
              </label>
              <label className="field">
                Tags
                <input value={form.tags} onChange={update("tags")} placeholder="event, rules, schedule" />
              </label>
            </div>
            <label className="field">
              Nội dung
              <textarea value={form.body} onChange={update("body")} rows={4} maxLength={10000} placeholder="Nội dung policy/event/playbook" required />
            </label>
            {formError && <p style={{ color: "var(--sev-critical)", fontSize: 12.5 }}>{formError}</p>}
            <div className="form-actions">
              <button type="submit" className="btn btn--primary" disabled={saving}>
                <FloppyDisk size={14} weight="bold" /> {editingId ? "Cập nhật" : "Lưu tài liệu"}
              </button>
              <button type="button" className="btn btn--ghost" onClick={cancelEdit}>
                Hủy
              </button>
            </div>
          </form>
          </Card>
        )}
      </div>

      <div className="page-grid__row">
        <ImportCard onImported={load} />
        <RagAskCard />
      </div>
    </div>
  );
}

function ImportCard({ onImported }) {
  const fileRef = useRef(null);
  const [target, setTarget] = useState("auto");
  const [state, setState] = useState(null);
  const [imports, setImports] = useState(null);
  const [loadingImports, setLoadingImports] = useState(true);

  const loadImports = useCallback(() => {
    setLoadingImports(true);
    ops
      .knowledgeImports()
      .then(setImports)
      .catch(() => setImports([]))
      .finally(() => setLoadingImports(false));
  }, []);

  useEffect(() => {
    loadImports();
  }, [loadImports]);

  async function runImport(event) {
    event.preventDefault();
    const file = fileRef.current?.files?.[0];
    if (!file) return;
    setState({ tone: "", text: `Đang đọc và chuẩn hóa ${file.name}...` });
    try {
      const data = await ops.importKnowledge({ filename: file.name, content_base64: await fileToBase64(file), target });
      setState({
        tone: "success",
        text: `Đã xử lý ${data.normalized_count} bản ghi bằng ${data.normalized_by}. Bỏ qua: ${data.skipped_count}.${
          data.warnings?.length ? ` ${data.warnings.join(" | ")}` : ""
        }`,
      });
      if (fileRef.current) fileRef.current.value = "";
      loadImports();
      onImported();
    } catch (err) {
      setState({ tone: "error", text: err.message });
    }
  }

  return (
    <Card title="Import tài liệu" className="span-5">
      <p className="muted small">JSON, JSONL, CSV, Markdown, TXT hoặc DOCX. Hệ thống tự chuẩn hóa về schema canonical.</p>
      <form className="stack" onSubmit={runImport}>
        <label className="field">
          File
          <input ref={fileRef} type="file" accept=".json,.jsonl,.csv,.md,.markdown,.txt,.docx" required />
        </label>
        <label className="field">
          Đích đến
          <select value={target} onChange={(event) => setTarget(event.target.value)}>
            <option value="auto">Tự nhận diện knowledge/policy</option>
            <option value="knowledge">Knowledge document</option>
            <option value="policy">Policy / rule</option>
          </select>
        </label>
        <div className="form-actions">
          <button type="submit" className="btn btn--primary">
            <UploadSimple size={14} /> Import và chuẩn hóa
          </button>
        </div>
        {state && (
          <p style={{ fontSize: 12.5, color: state.tone === "error" ? "var(--sev-critical)" : state.tone === "success" ? "var(--sev-low)" : "var(--text-secondary)" }}>
            {state.text}
          </p>
        )}
      </form>

      <span className="section-heading">Lịch sử import</span>
      {loadingImports && <SkeletonLine width="80%" />}
      {!loadingImports && (!imports || imports.length === 0) && <EmptyState message="Chưa import lần nào." />}
      {!loadingImports && imports && imports.length > 0 && (
        <div className="list">
          {imports.map((item) => (
            <div className="list-row" key={item.import_id}>
              <div className="list-row__head">
                <span className="list-row__title">{item.filename}</span>
                <span className="list-row__meta">{relativeTime(item.created_at)}</span>
              </div>
              <span className="list-row__meta">
                {item.format} → {item.target} · {item.normalized_count} bản ghi · bỏ qua {item.skipped_count}
              </span>
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}

function RagAskCard() {
  const [question, setQuestion] = useState("");
  const [dataset, setDataset] = useState("");
  const [state, setState] = useState({ status: "idle", data: null, error: "" });

  async function submit(event) {
    event.preventDefault();
    setState({ status: "loading", data: null, error: "" });
    try {
      setState({ status: "done", data: await ops.ask(question, dataset || undefined), error: "" });
    } catch (err) {
      setState({ status: "error", data: null, error: err.message });
    }
  }

  return (
    <Card title="Hỏi tri thức nội bộ (RAG)" className="span-7" delay={0.05}>
      <form className="stack" onSubmit={submit}>
        <label className="field">
          Câu hỏi
          <textarea
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            rows={3}
            maxLength={2000}
            placeholder="Ví dụ: Khi nào nên hold for review?"
            required
          />
        </label>
        <label className="field">
          Dataset (tùy chọn)
          <input value={dataset} onChange={(event) => setDataset(event.target.value)} placeholder="community_rules, events..." maxLength={80} />
        </label>
        <div className="form-actions">
          <button type="submit" className="btn btn--primary" disabled={state.status === "loading" || !question.trim()}>
            <PaperPlaneRight size={14} /> {state.status === "loading" ? "Đang tìm..." : "Hỏi knowledge hub"}
          </button>
        </div>
      </form>

      <div style={{ marginTop: 6 }}>
        {state.status === "loading" && <SkeletonBlock height={100} />}
        {state.status === "error" && <ErrorState message={state.error} onRetry={submit} />}
        {state.status === "done" && state.data && (
          <div className="quote">
            <p style={{ whiteSpace: "pre-wrap" }}>{state.data.answer}</p>
            <span className="muted small" style={{ display: "block", marginTop: 8 }}>
              Nguồn: {(state.data.sources || []).map((source) => source.title).join(", ") || "không có"} · {state.data.model_used}
            </span>
          </div>
        )}
      </div>
    </Card>
  );
}
