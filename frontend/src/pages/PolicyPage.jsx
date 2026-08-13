import { useCallback, useEffect, useMemo, useState } from "react";
import { MagnifyingGlass, PencilSimple, Trash, FloppyDisk, Plus } from "@phosphor-icons/react";
import Card from "../components/Card.jsx";
import Badge from "../components/Badge.jsx";
import Modal from "../components/Modal.jsx";
import { SkeletonBlock } from "../components/Skeleton.jsx";
import { ErrorState, EmptyState } from "../components/StatePanels.jsx";
import { ops } from "../api/client.js";
import { decisionLabel, DECISION_COLORS, categoryLabel } from "../lib/taxonomy.js";

const BLANK = { name: "", category: "other", action: "hold_for_review", description: "", terms: "" };

function matches(item, query) {
  return [item.name, item.description, item.category, item.action, (item.trigger_terms || []).join(" ")]
    .join(" ")
    .toLowerCase()
    .includes(query);
}

export default function PolicyPage() {
  const [policies, setPolicies] = useState(null);
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
      .policies()
      .then(setPolicies)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const visible = useMemo(() => {
    if (!policies) return [];
    const needle = query.trim().toLowerCase();
    return needle ? policies.filter((item) => matches(item, needle)) : policies;
  }, [policies, query]);

  const update = (key) => (event) => setForm((prev) => ({ ...prev, [key]: event.target.value }));

  function startCreate() {
    setEditingId(null);
    setForm(BLANK);
    setFormError("");
    setFormOpen(true);
  }

  function startEdit(item) {
    setEditingId(item.policy_id);
    setForm({
      name: item.name,
      category: item.category,
      action: item.action,
      description: item.description,
      terms: (item.trigger_terms || []).join(", "),
    });
    setFormError("");
    setFormOpen(true);
  }

  // Memoised: Modal keys its Escape/scroll-lock effect on onClose, and a fresh
  // identity every render would re-focus the dialog on every keystroke.
  const cancelEdit = useCallback(() => {
    setEditingId(null);
    setForm(BLANK);
    setFormError("");
    setFormOpen(false);
  }, []);

  async function submit(event) {
    event.preventDefault();
    setFormError("");
    setSaving(true);
    try {
      await ops.savePolicy(editingId || `POL-CUSTOM-${Date.now()}`, {
        name: form.name,
        description: form.description,
        category: form.category,
        action: form.action,
        trigger_terms: form.terms.split(",").map((value) => value.trim()).filter(Boolean),
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
    if (!window.confirm(`Xóa policy "${item.name}"?`)) return;
    try {
      await ops.deletePolicy(item.policy_id);
      if (editingId === item.policy_id) cancelEdit();
      load();
    } catch (err) {
      setError(err.message);
    }
  }

  if (error) {
    return (
      <div className="page-grid">
        <ErrorState message={`Không lấy được policy: ${error}`} onRetry={load} />
      </div>
    );
  }

  return (
    <div className="page-grid">
      <div className="page-grid__row">
        <Card
          title="Rules đang áp dụng"
          className="span-12"
          action={
            <button type="button" className="btn btn--primary" onClick={startCreate}>
              <Plus size={14} weight="bold" /> Thêm policy
            </button>
          }
        >
          <div className="search-box">
            <MagnifyingGlass size={15} />
            <input
              type="search"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Tìm policy theo tên, category, từ khóa..."
              aria-label="Tìm policy"
            />
          </div>

          {loading && <SkeletonBlock height={240} />}
          {!loading && (!policies || policies.length === 0) && <EmptyState message="Chưa có policy nào." />}
          {!loading && policies && policies.length > 0 && visible.length === 0 && (
            <EmptyState message={`Không có policy nào khớp "${query}".`} />
          )}
          {!loading && visible.length > 0 && (
            <div className="list">
              {visible.map((item) => (
                <div className="list-row" key={item.policy_id}>
                  <div className="list-row__head">
                    <span className="list-row__title">{item.name}</span>
                    <Badge tone={DECISION_COLORS[item.action]}>{decisionLabel(item.action)}</Badge>
                  </div>
                  <p className="list-row__body">{item.description}</p>
                  <span className="list-row__meta">
                    {categoryLabel(item.category)} · từ khóa: {(item.trigger_terms || []).join(", ") || "không có"} · v
                    {item.version}
                  </span>
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
      </div>

      <Modal open={formOpen} title={editingId ? "Sửa policy" : "Thêm policy mới"} onClose={cancelEdit}>
        <form className="stack" onSubmit={submit}>
          <label className="field">
            Tên policy
            <input value={form.name} onChange={update("name")} placeholder="Tên policy" required maxLength={200} />
          </label>
          <div className="field-row">
            <label className="field">
              Category
              <select value={form.category} onChange={update("category")}>
                <option value="other">Khác</option>
                <option value="spam">Spam</option>
                <option value="harassment">Công kích</option>
                <option value="violence">Đe dọa / bạo lực</option>
                <option value="hate">Thù ghét</option>
              </select>
            </label>
            <label className="field">
              Action
              <select value={form.action} onChange={update("action")}>
                <option value="hold_for_review">Chờ review</option>
                <option value="allow">Cho phép</option>
                <option value="warn">Cảnh báo</option>
                <option value="hide">Ẩn</option>
              </select>
            </label>
          </div>
          <label className="field">
            Từ khóa kích hoạt
            <input value={form.terms} onChange={update("terms")} placeholder="Từ khóa, cách nhau bằng dấu phẩy" />
          </label>
          <label className="field">
            Mô tả
            <textarea value={form.description} onChange={update("description")} rows={3} placeholder="Mô tả policy" required maxLength={1000} />
          </label>
          {formError && <p style={{ color: "var(--sev-critical)", fontSize: 12.5 }}>{formError}</p>}
          <div className="form-actions">
            <button type="submit" className="btn btn--primary" disabled={saving}>
              <FloppyDisk size={14} weight="bold" /> {editingId ? "Cập nhật" : "Lưu policy"}
            </button>
            <button type="button" className="btn btn--ghost" onClick={cancelEdit}>
              Hủy
            </button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
