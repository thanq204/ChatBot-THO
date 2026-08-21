import { useCallback, useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { FloppyDisk, WarningCircle, CheckCircle, Plus, Trash } from "@phosphor-icons/react";
import { SkeletonBlock } from "./Skeleton.jsx";
import { ErrorState } from "./StatePanels.jsx";
import Modal from "./Modal.jsx";
import { ops } from "../api/client.js";
import { queryKeys } from "../lib/queryClient.js";
import { relativeTime } from "../lib/format.js";

/**
 * Rewrites the text the bot replies with for /event, /daily, /weekly and
 * friends, and lets Admin add brand new commands beyond that seeded set. The
 * backend seeds every built-in command with a "Chưa có thông báo mới..."
 * placeholder, which is exactly what members see until an Admin fills it in, so
 * the editor flags any command still sitting on that placeholder.
 */

// Built-ins the backend always seeds; Admin can rewrite but never delete them.
const CORE_COMMANDS = new Set(["event", "daily", "weekly", "resources", "admin"]);

// Names the chat orchestrator already handles with dedicated logic; a new
// command can't reuse them (mirrors the backend's own validation).
const RESERVED_NAMES = new Set(["start", "help", "rule", "rules", "faq", "report", "settings"]);
const COMMAND_NAME_PATTERN = /^[a-z0-9_]{2,32}$/;

const PLATFORM_OPTIONS = [
  { value: "telegram", label: "Telegram" },
  { value: "discord", label: "Discord" },
];

/** The seeded defaults all open this way. Close enough to detect reliably. */
const isPlaceholder = (body) => /^chưa có/i.test((body || "").trim());

function sortCommands(list) {
  const order = ["event", "daily", "weekly", "resources", "admin"];
  return [...list].sort((a, b) => {
    const ai = order.indexOf(a.command);
    const bi = order.indexOf(b.command);
    if (ai !== -1 || bi !== -1) return (ai === -1 ? 999 : ai) - (bi === -1 ? 999 : bi);
    return a.command.localeCompare(b.command);
  });
}

function samePlatforms(a, b) {
  const left = [...(a || [])].sort();
  const right = [...(b || [])].sort();
  return left.length === right.length && left.every((value, index) => value === right[index]);
}

function PlatformCheckboxes({ value, onToggle }) {
  return (
    <div className="chip-row">
      {PLATFORM_OPTIONS.map((option) => (
        <label key={option.value} className="platform-check">
          <input type="checkbox" checked={value.includes(option.value)} onChange={() => onToggle(option.value)} />
          {option.label}
        </label>
      ))}
    </div>
  );
}

export default function CommandContentEditor() {
  const queryClient = useQueryClient();
  const [active, setActive] = useState(null);
  const [draft, setDraft] = useState("");
  const [draftDescription, setDraftDescription] = useState("");
  const [draftPlatforms, setDraftPlatforms] = useState(["telegram", "discord"]);
  const [actionError, setActionError] = useState("");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const [creating, setCreating] = useState(false);
  const [newKey, setNewKey] = useState("");
  const [newDescription, setNewDescription] = useState("");
  const [newBody, setNewBody] = useState("");
  const [newPlatforms, setNewPlatforms] = useState(["telegram", "discord"]);
  const [createError, setCreateError] = useState("");
  const [createBusy, setCreateBusy] = useState(false);

  const commandsQuery = useQuery({
    queryKey: queryKeys.commandContents,
    queryFn: ops.commandContents,
    select: sortCommands,
  });

  const commands = commandsQuery.data ?? null;
  const loading = commandsQuery.isPending;
  const error = actionError || commandsQuery.error?.message || "";

  /** Rewrite the cached list in place; every write here returns the saved row. */
  const patchCommands = useCallback(
    (updater) =>
      queryClient.setQueryData(queryKeys.commandContents, (list) => updater(list ?? [])),
    [queryClient],
  );

  const load = useCallback(() => {
    setActionError("");
    queryClient.invalidateQueries({ queryKey: queryKeys.commandContents });
  }, [queryClient]);

  // Selection follows the list: keep the current command if it survived the last
  // change, otherwise fall back to the first one.
  useEffect(() => {
    if (!commands) return;
    setActive((current) =>
      current && commands.some((item) => item.command === current) ? current : commands[0]?.command ?? null,
    );
  }, [commands]);

  useEffect(() => {
    const item = commands?.find((command) => command.command === active);
    setDraft(item?.body ?? "");
    setDraftDescription(item?.description ?? "");
    setDraftPlatforms(item?.platforms?.length ? item.platforms : ["telegram", "discord"]);
    setSaved(false);
  }, [active]); // eslint-disable-line react-hooks/exhaustive-deps

  function toggleDraftPlatform(value) {
    setDraftPlatforms((prev) => (prev.includes(value) ? prev.filter((item) => item !== value) : [...prev, value]));
    setSaved(false);
  }

  async function save() {
    if (!draft.trim() || !active || draftPlatforms.length === 0) return;
    setSaving(true);
    setActionError("");
    try {
      const updated = await ops.saveCommandContent(active, {
        body: draft,
        description: draftDescription.trim(),
        platforms: draftPlatforms,
      });
      patchCommands((list) => list.map((item) => (item.command === active ? updated : item)));
      setDraft(updated.body);
      setDraftDescription(updated.description);
      setDraftPlatforms(updated.platforms);
      setSaved(true);
    } catch (err) {
      setActionError(err.message);
    } finally {
      setSaving(false);
    }
  }

  async function removeActive() {
    if (!active || CORE_COMMANDS.has(active)) return;
    if (!window.confirm(`Xoá lệnh /${active}? Thành viên sẽ không dùng được lệnh này nữa.`)) return;
    setDeleting(true);
    setActionError("");
    try {
      await ops.deleteCommandContent(active);
      // Dropping the active command leaves the selection dangling; the effect
      // above notices and moves it to the first surviving command.
      patchCommands((list) => list.filter((item) => item.command !== active));
    } catch (err) {
      setActionError(err.message);
    } finally {
      setDeleting(false);
    }
  }

  function openCreate() {
    setNewKey("");
    setNewDescription("");
    setNewBody("");
    setNewPlatforms(["telegram", "discord"]);
    setCreateError("");
    setCreating(true);
  }

  // Stable identity: an inline arrow here would change on every keystroke in
  // the form, re-running Modal's focus effect and stealing focus mid-type.
  const closeCreate = useCallback(() => setCreating(false), []);

  function toggleNewPlatform(value) {
    setNewPlatforms((prev) => (prev.includes(value) ? prev.filter((item) => item !== value) : [...prev, value]));
  }

  async function submitCreate(event) {
    event.preventDefault();
    const key = newKey.trim().toLowerCase();
    if (!COMMAND_NAME_PATTERN.test(key)) {
      setCreateError("Tên lệnh chỉ gồm chữ thường, số và dấu gạch dưới, dài 2-32 ký tự.");
      return;
    }
    if (RESERVED_NAMES.has(key)) {
      setCreateError("Tên lệnh này đã được hệ thống dùng cho chức năng khác, hãy chọn tên khác.");
      return;
    }
    if (commands?.some((item) => item.command === key)) {
      setCreateError("Lệnh này đã tồn tại.");
      return;
    }
    if (!newBody.trim()) {
      setCreateError("Nhập nội dung bot sẽ trả lời cho lệnh này.");
      return;
    }
    if (newPlatforms.length === 0) {
      setCreateError("Chọn ít nhất một nền tảng để lệnh hoạt động.");
      return;
    }
    setCreateBusy(true);
    setCreateError("");
    try {
      const created = await ops.saveCommandContent(key, {
        body: newBody,
        description: newDescription.trim(),
        platforms: newPlatforms,
      });
      patchCommands((list) => [...list, created]);
      setActive(created.command);
      setCreating(false);
    } catch (err) {
      setCreateError(err.message);
    } finally {
      setCreateBusy(false);
    }
  }

  const activeItem = commands?.find((item) => item.command === active) ?? null;
  const empty = isPlaceholder(draft);
  const dirty =
    activeItem !== null &&
    (draft !== activeItem.body || draftDescription !== (activeItem.description || "") || !samePlatforms(draftPlatforms, activeItem.platforms));
  const isCore = active !== null && CORE_COMMANDS.has(active);

  return (
    <div className="cmd">
      <div className="cmd__tabs" role="tablist" aria-label="Chọn lệnh">
        {commands?.map((command) => (
          <button
            key={command.command}
            type="button"
            role="tab"
            aria-selected={active === command.command}
            className={`cmd__tab${active === command.command ? " is-active" : ""}`}
            onClick={() => setActive(command.command)}
          >
            /{command.command}
            {isPlaceholder(command.body) && <span className="cmd__dot" title="Chưa có nội dung thật" />}
          </button>
        ))}
        <button type="button" className="cmd__tab cmd__tab--add" onClick={openCreate}>
          <Plus size={13} weight="bold" /> Thêm lệnh
        </button>
      </div>

      {loading && <SkeletonBlock height={170} />}
      {!loading && error && <ErrorState message={error} onRetry={load} />}

      {!loading && !error && activeItem && (
        <>
          <p className="muted small">
            Thành viên gõ <code>/{active}</code> sẽ nhận đúng nội dung dưới đây.
          </p>

          {empty && (
            <p className="cmd__flag">
              <WarningCircle size={15} weight="fill" />
              Lệnh này chưa có nội dung thật. Thành viên đang nhận câu báo mặc định “chưa có thông báo mới”.
            </p>
          )}

          <label className="field">
            Mô tả ngắn (hiện trong /help cho thành viên)
            <input
              value={draftDescription}
              onChange={(event) => {
                setDraftDescription(event.target.value);
                setSaved(false);
              }}
              placeholder="Lệnh này dùng để làm gì?"
              maxLength={300}
            />
          </label>

          <label className="field">
            Nội dung bot trả lời
            <textarea
              rows={6}
              maxLength={5000}
              value={draft}
              onChange={(event) => {
                setDraft(event.target.value);
                setSaved(false);
              }}
            />
          </label>

          <div className="field">
            Hoạt động trên
            <PlatformCheckboxes value={draftPlatforms} onToggle={toggleDraftPlatform} />
          </div>

          <div className="form-actions">
            <button
              type="button"
              className="btn btn--primary"
              onClick={save}
              disabled={saving || !dirty || !draft.trim() || draftPlatforms.length === 0}
            >
              <FloppyDisk size={14} weight="bold" /> {saving ? "Đang lưu..." : "Lưu nội dung"}
            </button>
            {!isCore && (
              <button type="button" className="btn btn--ghost" onClick={removeActive} disabled={deleting}>
                <Trash size={13} /> {deleting ? "Đang xoá..." : "Xoá lệnh"}
              </button>
            )}
            <span className="muted small">
              {saved && !dirty ? (
                <>
                  <CheckCircle size={13} weight="fill" /> Đã lưu
                </>
              ) : (
                `Cập nhật lần cuối ${relativeTime(activeItem.updated_at)}`
              )}
            </span>
          </div>
        </>
      )}

      <Modal open={creating} title="Thêm lệnh mới" onClose={closeCreate}>
        <form className="stack" onSubmit={submitCreate}>
          <p className="muted small">
            Tạo một lệnh bot mới, ví dụ <code>/rules2</code>. Thành viên gõ lệnh này trong Discord/Telegram sẽ nhận đúng nội dung
            bạn nhập bên dưới.
          </p>
          <label className="field">
            Tên lệnh
            <input
              value={newKey}
              onChange={(event) => setNewKey(event.target.value)}
              placeholder="vi_du_lenh"
              maxLength={32}
              required
            />
          </label>
          <label className="field">
            Mô tả ngắn (hiện trong /help cho thành viên)
            <input
              value={newDescription}
              onChange={(event) => setNewDescription(event.target.value)}
              placeholder="Lệnh này dùng để làm gì?"
              maxLength={300}
            />
          </label>
          <label className="field">
            Nội dung bot trả lời
            <textarea
              rows={4}
              maxLength={5000}
              value={newBody}
              onChange={(event) => setNewBody(event.target.value)}
              placeholder="Nội dung bot sẽ gửi lại khi thành viên gõ lệnh này"
              required
            />
          </label>
          <div className="field">
            Hoạt động trên
            <PlatformCheckboxes value={newPlatforms} onToggle={toggleNewPlatform} />
          </div>
          {createError && <p style={{ color: "var(--sev-critical)", fontSize: 12.5 }}>{createError}</p>}
          <div className="form-actions">
            <button type="submit" className="btn btn--primary" disabled={createBusy}>
              <Plus size={14} weight="bold" /> {createBusy ? "Đang tạo..." : "Tạo lệnh"}
            </button>
            <button type="button" className="btn btn--ghost" onClick={closeCreate}>
              Hủy
            </button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
