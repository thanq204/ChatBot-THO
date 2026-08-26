import { useEffect, useMemo, useState } from "react";
import { ChatCircleText, Trash, Clock, SignOut, Prohibit, WarningCircle, CheckCircle } from "@phosphor-icons/react";
import { ops } from "../api/client.js";
import { useAuth } from "../auth/AuthProvider.jsx";

/**
 * Manual moderation against one case. Every action here is irreversible on the
 * platform side, so the flow is deliberately slow: pick a message, pick an
 * action, read what it does, tick the confirmation, then run it.
 *
 * The backend rejects any request without confirmed=true, so the checkbox is a
 * real gate rather than decoration.
 */

const ACTIONS = [
  {
    key: "dm",
    label: "Nhắn riêng",
    icon: ChatCircleText,
    tone: "safe",
    needs: "text",
    help: "Gửi tin nhắn riêng cho thành viên. Không ảnh hưởng tới tài khoản hay nội dung đã đăng.",
  },
  {
    key: "delete_message",
    label: "Xoá tin nhắn",
    icon: Trash,
    tone: "warn",
    help: "Gỡ đúng tin nhắn đang chọn khỏi kênh. Nội dung không khôi phục được.",
  },
  {
    key: "timeout",
    label: "Tạm khoá chat",
    icon: Clock,
    tone: "warn",
    needs: "duration",
    help: "Chặn thành viên gửi tin trong khoảng thời gian đã chọn, sau đó tự mở lại.",
  },
  {
    key: "kick",
    label: "Mời ra khỏi nhóm",
    icon: SignOut,
    tone: "danger",
    help: "Đuổi thành viên khỏi cộng đồng. Họ vẫn có thể quay lại nếu có link mời.",
  },
  {
    key: "ban",
    label: "Cấm vĩnh viễn",
    icon: Prohibit,
    tone: "danger",
    help: "Chặn vĩnh viễn. Chỉ dùng cho vi phạm nghiêm trọng, rất khó đảo ngược.",
  },
];

const DURATIONS = [
  { value: 5, label: "5 phút" },
  { value: 60, label: "1 giờ" },
  { value: 1440, label: "1 ngày" },
  { value: 10080, label: "7 ngày" },
];

const SUPPORTED_PLATFORMS = new Set(["discord", "telegram"]);

export default function CaseActions({ incident, messages, onDone }) {
  const { user } = useAuth();
  const [actionKey, setActionKey] = useState("dm");
  const [messageId, setMessageId] = useState("");
  const [text, setText] = useState("");
  const [duration, setDuration] = useState(60);
  const [confirmed, setConfirmed] = useState(false);
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState(null);

  const rootId = useMemo(() => {
    const root = messages.find((item) => !item.parent_message_id) || messages[0];
    return root?.message_id ?? "";
  }, [messages]);

  const availableActions = useMemo(
    () => (incident.platform === "telegram" ? ACTIONS.filter((item) => item.key !== "ban") : ACTIONS),
    [incident.platform],
  );

  useEffect(() => {
    setMessageId(rootId);
  }, [rootId]);

  useEffect(() => {
    if (!availableActions.some((item) => item.key === actionKey)) {
      setActionKey("dm");
    }
  }, [actionKey, availableActions]);

  const action = availableActions.find((item) => item.key === actionKey) ?? availableActions[0];
  const target = messages.find((item) => item.message_id === messageId) ?? null;
  const supported = SUPPORTED_PLATFORMS.has(incident.platform);

  // Any change to the plan invalidates the confirmation the Admin already gave.
  const changePlan = (apply) => {
    apply();
    setConfirmed(false);
    setResult(null);
  };

  const missingText = action.needs === "text" && !text.trim();
  const blocked = !supported || !target || missingText || !confirmed || running;

  async function run() {
    if (blocked) return;
    setRunning(true);
    setResult(null);
    try {
      const response = await ops.executeAction(incident.incident_id, {
        action: action.key,
        message_id: messageId,
        message: text,
        duration_minutes: action.needs === "duration" ? Number(duration) : null,
        actor: user?.display_name || user?.email || "Admin",
        confirmed: true,
      });
      setResult({
        ok: response.completed,
        text: response.detail || (response.completed ? "Đã thực hiện." : "Nền tảng từ chối hành động."),
      });
      setConfirmed(false);
      if (response.completed) onDone?.();
    } catch (err) {
      setResult({ ok: false, text: err.message });
    } finally {
      setRunning(false);
    }
  }

  if (!supported) {
    return (
      <p className="muted small">
        Nền tảng {incident.platform} chưa hỗ trợ hành động quản trị trực tiếp. Hiện chỉ Discord và Telegram làm được.
      </p>
    );
  }

  return (
    <div className="actions">
      <div className="actions__picker" role="radiogroup" aria-label="Chọn hành động">
        {availableActions.map((item) => {
          const Icon = item.icon;
          const active = item.key === actionKey;
          return (
            <button
              key={item.key}
              type="button"
              role="radio"
              aria-checked={active}
              className={`actions__option actions__option--${item.tone}${active ? " is-active" : ""}`}
              onClick={() => changePlan(() => setActionKey(item.key))}
            >
              <Icon size={15} weight={active ? "fill" : "regular"} />
              {item.label}
            </button>
          );
        })}
      </div>

      <p className="actions__help">{action.help}</p>

      <label className="field">
        Áp dụng cho tin nhắn
        <select value={messageId} onChange={(event) => changePlan(() => setMessageId(event.target.value))}>
          {messages.map((item) => (
            <option key={item.message_id} value={item.message_id}>
              {item.author_id} · {(item.text || "").slice(0, 60)}
              {(item.text || "").length > 60 ? "..." : ""}
            </option>
          ))}
        </select>
      </label>

      {action.needs === "text" && (
        <label className="field">
          Nội dung gửi cho thành viên
          <textarea
            rows={3}
            maxLength={1900}
            value={text}
            onChange={(event) => changePlan(() => setText(event.target.value))}
            placeholder="Ví dụ: Tin nhắn của bạn vi phạm nội quy mục 3. Vui lòng điều chỉnh."
          />
        </label>
      )}

      {action.needs === "duration" && (
        <label className="field">
          Thời gian khoá
          <select value={duration} onChange={(event) => changePlan(() => setDuration(event.target.value))}>
            {DURATIONS.map((item) => (
              <option key={item.value} value={item.value}>
                {item.label}
              </option>
            ))}
          </select>
        </label>
      )}

      {target && (
        <div className={`actions__preview actions__preview--${action.tone}`}>
          <WarningCircle size={15} weight="fill" />
          <span>
            <strong>{action.label}</strong> đối với <strong>{target.author_id}</strong> trên{" "}
            {incident.platform === "discord" ? "Discord" : "Telegram"}.
          </span>
        </div>
      )}

      <label className="actions__confirm">
        <input type="checkbox" checked={confirmed} onChange={(event) => setConfirmed(event.target.checked)} />
        Tôi đã xem lại trường hợp và xác nhận thực hiện hành động này.
      </label>

      <div className="form-actions">
        <button
          type="button"
          className={action.tone === "danger" ? "btn btn--danger" : "btn btn--primary"}
          onClick={run}
          disabled={blocked}
        >
          {running ? "Đang thực hiện..." : `Thực hiện: ${action.label}`}
        </button>
      </div>

      {missingText && <p className="muted small">Hành động nhắn riêng cần có nội dung.</p>}

      {result && (
        <p className={`actions__result actions__result--${result.ok ? "ok" : "fail"}`} role="status">
          {result.ok ? <CheckCircle size={15} weight="fill" /> : <WarningCircle size={15} weight="fill" />}
          {result.text}
        </p>
      )}
    </div>
  );
}
