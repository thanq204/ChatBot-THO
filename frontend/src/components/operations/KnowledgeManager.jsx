import {
  BooksIcon,
  FloppyDiskIcon,
  MagnifyingGlassIcon,
  PencilSimpleIcon,
  TrashIcon,
  UploadSimpleIcon,
  XIcon,
} from "@phosphor-icons/react";
import { useMemo, useRef, useState } from "react";
import { fileToBase64, ops } from "../../api/client.js";
import { Empty, Notice, Panel } from "../ui.jsx";

const BLANK = { title: "", dataset: "", body: "", tags: "" };

const matches = (item, query) =>
  [item.title, item.body, item.dataset, (item.tags || []).join(" ")].join(" ").toLowerCase().includes(query);

export default function KnowledgeManager({ knowledge, onChanged }) {
  const [query, setQuery] = useState("");
  const [form, setForm] = useState(BLANK);
  const [editingId, setEditingId] = useState(null);
  const [error, setError] = useState("");
  const [importState, setImportState] = useState(null);
  // After an import, the list scopes to just-imported ids so the admin can review
  // exactly what landed instead of hunting for it in the full corpus.
  const [batchIds, setBatchIds] = useState(null);
  const fileRef = useRef(null);
  const [importTarget, setImportTarget] = useState("auto");

  const visible = useMemo(() => {
    const scoped = batchIds ? knowledge.filter((item) => batchIds.has(item.document_id)) : knowledge;
    const needle = query.trim().toLowerCase();
    if (batchIds) return needle ? scoped.filter((item) => matches(item, needle)) : scoped;
    return needle ? scoped.filter((item) => matches(item, needle)) : [];
  }, [knowledge, query, batchIds]);

  const update = (key) => (event) => setForm((prev) => ({ ...prev, [key]: event.target.value }));

  function startEdit(item) {
    setEditingId(item.document_id);
    setForm({
      title: item.title,
      dataset: item.dataset || "",
      body: item.body,
      tags: (item.tags || []).join(", "),
    });
  }

  function cancelEdit() {
    setEditingId(null);
    setForm(BLANK);
  }

  async function submit(event) {
    event.preventDefault();
    setError("");
    try {
      await ops.saveKnowledge(editingId || `KN-CUSTOM-${Date.now()}`, {
        title: form.title,
        body: form.body,
        dataset: form.dataset.trim() || "general",
        tags: form.tags.split(",").map((value) => value.trim()).filter(Boolean),
        active: true,
      });
      cancelEdit();
      await onChanged();
    } catch (requestError) {
      setError(requestError.message);
    }
  }

  async function remove(item) {
    if (!window.confirm(`Xóa tài liệu "${item.title}"? Các tài liệu khác không bị ảnh hưởng.`)) return;
    setError("");
    try {
      await ops.deleteKnowledge(item.document_id);
      if (editingId === item.document_id) cancelEdit();
      await onChanged();
    } catch (requestError) {
      setError(requestError.message);
    }
  }

  async function runImport(event) {
    event.preventDefault();
    const file = fileRef.current?.files?.[0];
    if (!file) return;
    setImportState({ tone: "", text: `Đang đọc và chuẩn hóa ${file.name}...` });
    try {
      const data = await ops.importKnowledge({
        filename: file.name,
        content_base64: await fileToBase64(file),
        target: importTarget,
      });
      setBatchIds(new Set(data.knowledge_ids || []));
      setQuery("");
      setImportState({
        tone: "success",
        text: `Đã xử lý ${data.normalized_count} bản ghi bằng ${data.normalized_by}. Bỏ qua: ${data.skipped_count}.${
          data.warnings?.length ? ` ${data.warnings.join(" | ")}` : ""
        }`,
      });
      if (fileRef.current) fileRef.current.value = "";
      await onChanged();
    } catch (requestError) {
      setImportState({ tone: "error", text: requestError.message });
    }
  }

  return (
    <Panel title="Tài liệu cho RAG" subtitle={`${knowledge.length} tài liệu trong knowledge hub.`}>
      <div style={{ position: "relative" }}>
        <MagnifyingGlassIcon
          size={15}
          style={{ position: "absolute", left: 12, top: "50%", transform: "translateY(-50%)", color: "var(--ink-faint)" }}
        />
        <input
          type="search"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Tìm tài liệu theo tiêu đề, nội dung, dataset..."
          aria-label="Tìm tài liệu"
          style={{ paddingLeft: 34 }}
        />
      </div>

      {batchIds && (
        <div className="button-row" style={{ marginTop: 10 }}>
          <span className="meta">Đang xem {batchIds.size} bản ghi vừa import.</span>
          <button type="button" className="link" onClick={() => setBatchIds(null)}>
            Xem tất cả
          </button>
        </div>
      )}

      <div className="stack" style={{ margin: "14px 0" }}>
        {!query.trim() && !batchIds ? (
          <Empty icon={BooksIcon}>Nhập từ khóa để tìm tài liệu cần sửa hoặc xóa.</Empty>
        ) : visible.length === 0 ? (
          <Empty icon={BooksIcon}>Không có tài liệu nào khớp.</Empty>
        ) : (
          visible.map((item) => (
            <div className="record" key={item.document_id}>
              <span className="meta">Dataset: {item.dataset}</span>
              <br />
              <b>{item.title}</b>
              <small>
                {item.body}
                <br />
                tags: {(item.tags || []).join(", ") || "không có"}
              </small>
              <div className="record-actions">
                <button type="button" className="secondary small icon-btn" onClick={() => startEdit(item)}>
                  <PencilSimpleIcon size={13} />
                  Sửa
                </button>
                <button type="button" className="danger small icon-btn" onClick={() => remove(item)}>
                  <TrashIcon size={13} />
                  Xóa riêng
                </button>
              </div>
            </div>
          ))
        )}
      </div>

      <form onSubmit={submit}>
        <label>
          <span>Tiêu đề</span>
          <input value={form.title} onChange={update("title")} placeholder="Tiêu đề tài liệu" required />
        </label>
        <div className="field-row">
          <label>
            <span>Dataset</span>
            <input value={form.dataset} onChange={update("dataset")} placeholder="channel_policy, events..." />
          </label>
          <label>
            <span>Tags</span>
            <input value={form.tags} onChange={update("tags")} placeholder="event, rules, schedule" />
          </label>
        </div>
        <label>
          <span>Nội dung</span>
          <textarea value={form.body} onChange={update("body")} rows={3} placeholder="Nội dung policy/event/playbook" />
        </label>
        <Notice tone="error">{error}</Notice>
        <div className="button-row">
          <button type="submit" className="icon-btn">
            <FloppyDiskIcon size={14} weight="bold" />
            {editingId ? "Cập nhật tài liệu" : "Lưu tài liệu"}
          </button>
          {editingId && (
            <button type="button" className="secondary icon-btn" onClick={cancelEdit}>
              <XIcon size={14} />
              Hủy
            </button>
          )}
        </div>
      </form>

      <hr style={{ margin: "20px 0", border: 0, borderTop: "1px solid var(--line)" }} />

      <form onSubmit={runImport}>
        <p style={{ fontSize: 13 }}>
          Import file JSON, JSONL, CSV, Markdown, TXT hoặc DOCX. Hệ thống tự chuẩn hóa về schema canonical.
        </p>
        <label>
          <span>File</span>
          <input ref={fileRef} type="file" accept=".json,.jsonl,.csv,.md,.markdown,.txt,.docx" required />
        </label>
        <label>
          <span>Đích đến</span>
          <select value={importTarget} onChange={(event) => setImportTarget(event.target.value)}>
            <option value="auto">Tự nhận diện knowledge/policy</option>
            <option value="knowledge">Knowledge document</option>
            <option value="policy">Policy / rule</option>
          </select>
        </label>
        <button type="submit" className="secondary icon-btn">
          <UploadSimpleIcon size={14} />
          Import và chuẩn hóa
        </button>
        {importState && <Notice tone={importState.tone}>{importState.text}</Notice>}
      </form>
    </Panel>
  );
}
