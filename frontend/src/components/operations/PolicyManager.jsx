import { FloppyDiskIcon, MagnifyingGlassIcon, PencilSimpleIcon, ScrollIcon, TrashIcon, XIcon } from "@phosphor-icons/react";
import { useMemo, useState } from "react";
import { ops } from "../../api/client.js";
import { Empty, Notice, Panel } from "../ui.jsx";

const BLANK = { name: "", category: "other", action: "hold_for_review", description: "", terms: "" };

const matches = (item, query) =>
  [item.name, item.description, item.category, item.action, (item.trigger_terms || []).join(" ")]
    .join(" ")
    .toLowerCase()
    .includes(query);

export default function PolicyManager({ policies, onChanged }) {
  const [query, setQuery] = useState("");
  const [form, setForm] = useState(BLANK);
  const [editingId, setEditingId] = useState(null);
  const [error, setError] = useState("");

  // The list stays collapsed until the admin searches; the full policy set is long
  // and scrolling it was never the way anyone found a rule.
  const visible = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return needle ? policies.filter((item) => matches(item, needle)) : [];
  }, [policies, query]);

  const update = (key) => (event) => setForm((prev) => ({ ...prev, [key]: event.target.value }));

  function startEdit(item) {
    setEditingId(item.policy_id);
    setForm({
      name: item.name,
      category: item.category,
      action: item.action,
      description: item.description,
      terms: (item.trigger_terms || []).join(", "),
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
      await ops.savePolicy(editingId || `POL-CUSTOM-${Date.now()}`, {
        name: form.name,
        description: form.description,
        category: form.category,
        action: form.action,
        trigger_terms: form.terms.split(",").map((value) => value.trim()).filter(Boolean),
        active: true,
      });
      cancelEdit();
      await onChanged();
    } catch (requestError) {
      setError(requestError.message);
    }
  }

  async function remove(item) {
    if (!window.confirm(`Xóa quy định "${item.name}"? Các quy định khác không bị ảnh hưởng.`)) return;
    setError("");
    try {
      await ops.deletePolicy(item.policy_id);
      if (editingId === item.policy_id) cancelEdit();
      await onChanged();
    } catch (requestError) {
      setError(requestError.message);
    }
  }

  return (
    <Panel title="Rules đang áp dụng" subtitle={`${policies.length} policy đang hoạt động.`}>
      <div style={{ position: "relative" }}>
        <MagnifyingGlassIcon
          size={15}
          style={{ position: "absolute", left: 12, top: "50%", transform: "translateY(-50%)", color: "var(--ink-faint)" }}
        />
        <input
          type="search"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Tìm policy theo tên, category, từ khóa..."
          aria-label="Tìm policy"
          style={{ paddingLeft: 34 }}
        />
      </div>

      <div className="stack" style={{ margin: "14px 0" }}>
        {!query.trim() ? (
          <Empty icon={ScrollIcon}>Nhập từ khóa để tìm policy cần sửa hoặc xóa.</Empty>
        ) : visible.length === 0 ? (
          <Empty icon={ScrollIcon}>Không có policy nào khớp "{query}".</Empty>
        ) : (
          visible.map((item) => (
            <div className="record" key={item.policy_id}>
              <b>{item.name}</b>
              <span className="meta">
                {" "}
                · {item.category} · {item.action}
              </span>
              <small>
                {item.description}
                <br />
                terms: {(item.trigger_terms || []).join(", ") || "không có"} · version {item.version}
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
          <span>Tên policy</span>
          <input value={form.name} onChange={update("name")} placeholder="Tên policy" required />
        </label>
        <div className="field-row">
          <label>
            <span>Category</span>
            <select value={form.category} onChange={update("category")}>
              <option value="other">Khác</option>
              <option value="spam">Spam</option>
              <option value="harassment">Công kích</option>
              <option value="violence">Đe dọa / bạo lực</option>
            </select>
          </label>
          <label>
            <span>Action</span>
            <select value={form.action} onChange={update("action")}>
              <option value="hold_for_review">Hold for review</option>
              <option value="allow">Allow</option>
              <option value="warn">Warn</option>
              <option value="hide">Hide</option>
            </select>
          </label>
        </div>
        <label>
          <span>Từ khóa kích hoạt</span>
          <input value={form.terms} onChange={update("terms")} placeholder="Từ khóa, cách nhau bằng dấu phẩy" />
        </label>
        <label>
          <span>Mô tả</span>
          <textarea value={form.description} onChange={update("description")} rows={2} placeholder="Mô tả policy" />
        </label>
        <Notice tone="error">{error}</Notice>
        <div className="button-row">
          <button type="submit" className="icon-btn">
            <FloppyDiskIcon size={14} weight="bold" />
            {editingId ? "Cập nhật policy" : "Lưu policy"}
          </button>
          {editingId && (
            <button type="button" className="secondary icon-btn" onClick={cancelEdit}>
              <XIcon size={14} />
              Hủy
            </button>
          )}
        </div>
      </form>
    </Panel>
  );
}
