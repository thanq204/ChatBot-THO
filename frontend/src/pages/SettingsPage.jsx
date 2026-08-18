import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { MagnifyingGlass, PencilSimple, Trash, FloppyDisk, Plus, UploadSimple, PaperPlaneRight } from "@phosphor-icons/react";
import Card from "../components/Card.jsx";
import Modal from "../components/Modal.jsx";
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
  const [selectedIds, setSelectedIds] = useState(() => new Set());
  const [bulkDeleting, setBulkDeleting] = useState(false);

  // "manual" types one document, "file" uploads a batch. Both write to the same
  // knowledge store, so they belong behind the same "Thêm tài liệu" action.
  const [mode, setMode] = useState("manual");
  const fileRef = useRef(null);
  const [importTarget, setImportTarget] = useState("auto");
  const [importState, setImportState] = useState(null);
  const [importing, setImporting] = useState(false);

  const [imports, setImports] = useState(null);
  const [loadingImports, setLoadingImports] = useState(true);

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    ops
      .knowledge()
      .then(setKnowledge)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  const loadImports = useCallback(() => {
    setLoadingImports(true);
    ops
      .knowledgeImports()
      .then(setImports)
      .catch(() => setImports([]))
      .finally(() => setLoadingImports(false));
  }, []);

  useEffect(() => {
    load();
    loadImports();
  }, [load, loadImports]);

  const visible = useMemo(() => {
    if (!knowledge) return [];
    const needle = query.trim().toLowerCase();
    return needle ? knowledge.filter((item) => matches(item, needle)) : knowledge;
  }, [knowledge, query]);

  const allVisibleSelected = visible.length > 0 && visible.every((item) => selectedIds.has(item.document_id));

  function toggleSelect(id) {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function toggleSelectAll() {
    setSelectedIds((prev) => {
      if (allVisibleSelected) {
        const next = new Set(prev);
        for (const item of visible) next.delete(item.document_id);
        return next;
      }
      const next = new Set(prev);
      for (const item of visible) next.add(item.document_id);
      return next;
    });
  }

  async function bulkRemove() {
    const ids = [...selectedIds];
    if (ids.length === 0) return;
    if (!window.confirm(`Xóa ${ids.length} tài liệu đã chọn?`)) return;
    setBulkDeleting(true);
    try {
      await Promise.all(ids.map((id) => ops.deleteKnowledge(id)));
      if (editingId && ids.includes(editingId)) cancelEdit();
      setSelectedIds(new Set());
      load();
    } catch (err) {
      setError(err.message);
    } finally {
      setBulkDeleting(false);
    }
  }

  const update = (key) => (event) => setForm((prev) => ({ ...prev, [key]: event.target.value }));

  function resetImport() {
    if (fileRef.current) fileRef.current.value = "";
    setImportTarget("auto");
    setImportState(null);
  }

  function startCreate() {
    setEditingId(null);
    setForm(BLANK);
    setFormError("");
    setMode("manual");
    resetImport();
    setFormOpen(true);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function startEdit(item) {
    setEditingId(item.document_id);
    setForm({
      title: item.title,
      dataset: item.dataset || "",
      body: item.body || "",
      tags: (item.tags || []).join(", "),
    });
    setFormError("");
    setMode("manual");
    setFormOpen(true);
  }
  // identity every render would re-focus the dialog on every keystroke.
  const cancelEdit = useCallback(() => {
    setEditingId(null);
    setForm(BLANK);
    setFormError("");
    setImportState(null);
    setFormOpen(false);
  }, []);

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

  async function runImport(event) {
    event.preventDefault();
    const file = fileRef.current?.files?.[0];
    if (!file) return;
    setImporting(true);
    setImportState({ tone: "", text: `Đang đọc và chuẩn hóa ${file.name}...` });
    try {
      const data = await ops.importKnowledge({ filename: file.name, content_base64: await fileToBase64(file), target: importTarget });
      setImportState({
        tone: "success",
        text: `Đã xử lý ${data.normalized_count} bản ghi bằng ${data.normalized_by}. Bỏ qua: ${data.skipped_count}.${
          data.warnings?.length ? ` ${data.warnings.join(" | ")}` : ""
        }`,
      });
      if (fileRef.current) fileRef.current.value = "";
      load();
      loadImports();
    } catch (err) {
      setImportState({ tone: "error", text: err.message });
    } finally {
      setImporting(false);
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
        <ImportHistoryCard imports={imports} loading={loadingImports} />
        <RagAskCard />
      </div>

      <div className="page-grid__row">
        <Card
          title="Tài liệu tri thức (RAG)"
          className="span-12"
          action={
            <div style={{ display: "flex", gap: 8 }}>
              {selectedIds.size > 0 && (
                <button type="button" className="btn btn--ghost" onClick={bulkRemove} disabled={bulkDeleting}>
                  <Trash size={13} /> {bulkDeleting ? "Đang xoá..." : `Xoá đã chọn (${selectedIds.size})`}
                </button>
              )}
              <button type="button" className="btn btn--primary" onClick={startCreate}>
                <Plus size={14} weight="bold" /> Thêm tài liệu
              </button>
            </div>
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
            <>
              <label className="list-row__meta" style={{ display: "flex", alignItems: "center", gap: 6, margin: "2px 0 8px" }}>
                <input type="checkbox" checked={allVisibleSelected} onChange={toggleSelectAll} />
                Chọn tất cả ({visible.length})
              </label>
              <div className="list">
                {visible.map((item) => (
                  <div className="list-row" key={item.document_id}>
                    <div className="list-row__head">
                      <span className="list-row__title" style={{ display: "flex", alignItems: "center", gap: 8 }}>
                        <input
                          type="checkbox"
                          checked={selectedIds.has(item.document_id)}
                          onChange={() => toggleSelect(item.document_id)}
                        />
                        {item.title}
                      </span>
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
            </>
          )}
        </Card>
      </div>

      <Modal open={formOpen} title={editingId ? "Sửa tài liệu" : "Thêm tài liệu"} onClose={cancelEdit}>
        {!editingId && (
          <div className="segmented" role="tablist" aria-label="Cách thêm tài liệu">
            <button
              type="button"
              role="tab"
              aria-selected={mode === "manual"}
              className={`segmented__option ${mode === "manual" ? "is-active" : ""}`.trim()}
              onClick={() => setMode("manual")}
            >
              <PencilSimple size={14} /> Nhập tay
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={mode === "file"}
              className={`segmented__option ${mode === "file" ? "is-active" : ""}`.trim()}
              onClick={() => setMode("file")}
            >
              <UploadSimple size={14} /> Tải file lên
            </button>
          </div>
        )}

        {(editingId || mode === "manual") && (
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
        )}

        {!editingId && mode === "file" && (
          <form className="stack" onSubmit={runImport}>
            <p className="muted small">
              JSON, JSONL, CSV, Markdown, TXT, DOCX hoặc PDF, tối đa 5MB. Hệ thống tự chuẩn hóa về schema canonical và có thể
              tách một file thành nhiều tài liệu.
            </p>
            <label className="field">
              File
              <input ref={fileRef} type="file" accept=".json,.jsonl,.csv,.md,.markdown,.txt,.docx,.pdf" required />
            </label>
            <label className="field">
              Đích đến
              <select value={importTarget} onChange={(event) => setImportTarget(event.target.value)}>
                <option value="auto">Tự nhận diện knowledge/policy</option>
                <option value="knowledge">Knowledge document</option>
                <option value="policy">Policy / rule</option>
              </select>
            </label>
            <div className="form-actions">
              <button type="submit" className="btn btn--primary" disabled={importing}>
                <UploadSimple size={14} /> {importing ? "Đang xử lý..." : "Import và chuẩn hóa"}
              </button>
              <button type="button" className="btn btn--ghost" onClick={cancelEdit}>
                Đóng
              </button>
            </div>
            {importState && (
              <p
                style={{
                  fontSize: 12.5,
                  color:
                    importState.tone === "error"
                      ? "var(--sev-critical)"
                      : importState.tone === "success"
                        ? "var(--sev-low)"
                        : "var(--text-secondary)",
                }}
              >
                {importState.text}
              </p>
            )}
          </form>
        )}
      </Modal>
    </div>
  );
}

function ImportHistoryCard({ imports, loading }) {
  return (
    <Card title="Lịch sử import" className="span-5">
      {loading && <SkeletonLine width="80%" />}
      {!loading && (!imports || imports.length === 0) && (
        <EmptyState message="Chưa import lần nào. Dùng “Thêm tài liệu → Tải file lên” để nạp hàng loạt." />
      )}
      {!loading && imports && imports.length > 0 && (
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
