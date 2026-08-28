import { useState } from "react";
import { motion } from "motion/react";
import {
  PaperPlaneRight,
  Trash,
  CheckCircle,
  WarningCircle,
  EyeSlash,
  Hourglass,
  Sparkle,
  ShieldCheck,
  Cpu,
} from "@phosphor-icons/react";
import Card from "../components/Card.jsx";
import Counter from "../components/Counter.jsx";
import { SkeletonBlock } from "../components/Skeleton.jsx";
import { ErrorState, EmptyState } from "../components/StatePanels.jsx";
import { moderation } from "../api/client.js";
import {
  moderationCategoryLabel,
  moderationActionLabel,
  MODERATION_ACTION_COLORS,
  severityLabel,
  SEVERITY_COLORS,
  agentStepLabel,
  vietnameseModerationText,
} from "../lib/taxonomy.js";

const MAX_LENGTH = 5000;
const SANDBOX_USER_ID = "admin-sandbox";

const ACTION_ICONS = { allow: CheckCircle, warn: WarningCircle, hide: EyeSlash, review: Hourglass };

const QUICK_SCENARIOS = [
  {
    label: "Bạo lực / Đe dọa",
    text: "Mày cẩn thận đấy, tao biết chỗ làm của mày rồi, liệu hồn mà né ra!",
    channel: "hoi-dap",
  },
  {
    label: "Spam link lừa đảo",
    text: "Tặng ngay 500k quà tri ân không cần nạp tiền tại link: http://nhanqua-tri-an-free.xyz/claim nhanh tay số lượng có hạn!",
    channel: "thao-luan",
  },
  {
    label: "Tranh chấp người bán",
    text: "Shop này lừa đảo nhé mọi người, chuyển khoản xong không gửi hàng rồi chặn số luôn, cạch mặt ra!",
    channel: "giao-dich",
  },
  {
    label: "Hỏi đáp an toàn / FAQ",
    text: "Cho mình hỏi nhóm mình có quy định gì về việc chia sẻ tài liệu học tập và template đồ án không ạ?",
    channel: "hoi-dap",
  },
];

function ResultPanel({ response }) {
  const result = response.moderation;
  const ActionIcon = ACTION_ICONS[result.action] ?? WarningCircle;
  const actionColor = MODERATION_ACTION_COLORS[result.action];
  const confPercent = Math.round(result.confidence * 100);

  return (
    <motion.div
      className="sandbox-result"
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
    >
      <div className="sandbox-result__header" style={{ borderColor: actionColor }}>
        <span className="sandbox-result__action" style={{ color: actionColor }}>
          <ActionIcon size={22} weight="bold" />
          {moderationActionLabel(result.action)}
        </span>
        <div className="sandbox-result__confidence">
          <span className="sandbox-result__confidence-value">
            <Counter value={confPercent} duration={0.7} />%
          </span>
          <span className="muted small">Độ tin cậy</span>
        </div>
      </div>

      {/* Confidence Gauge Bar */}
      <div className="confidence-gauge">
        <div className="confidence-gauge__track">
          <div
            className="confidence-gauge__fill"
            style={{
              width: `${confPercent}%`,
              backgroundColor: confPercent >= 80 ? "#10b981" : confPercent >= 50 ? "#f59e0b" : "#ef4444",
            }}
          />
        </div>
      </div>

      <p className="muted" style={{ marginTop: 12 }}>{response.message}</p>

      {result.fallback_used && (
        <div className="sandbox-fallback">
          <WarningCircle size={16} weight="bold" />
          <span>
            Đã chuyển sang chế độ dự phòng: {vietnameseModerationText(
              result.fallback_reason,
              result.category,
              "Mô hình chính gặp lỗi hoặc trả dữ liệu không hợp lệ.",
            )}
          </span>
        </div>
      )}

      <div className="sandbox-grid">
        <div className="sandbox-stat">
          <span className="muted small">Phân loại</span>
          <strong>{moderationCategoryLabel(result.category)}</strong>
        </div>
        <div className="sandbox-stat">
          <span className="muted small">Mức độ rủi ro</span>
          <strong style={{ color: SEVERITY_COLORS[result.risk_level] }}>{severityLabel(result.risk_level)}</strong>
        </div>
        <div className="sandbox-stat">
          <span className="muted small">Mã quy tắc</span>
          <strong>{result.policy_id ?? "Không có"}</strong>
        </div>
        <div className="sandbox-stat">
          <span className="muted small">Mô hình</span>
          <strong>
            {result.model_used} <span className="muted small">({result.mode})</span>
          </strong>
        </div>
        <div className="sandbox-stat">
          <span className="muted small">Ngôn ngữ phát hiện</span>
          <strong>{result.detected_language ?? "Không xác định"}</strong>
        </div>
      </div>

      <div>
        <h3 className="sandbox-subheading">Diễn giải phán quyết</h3>
        <p>{vietnameseModerationText(result.reason, result.category)}</p>
        {result.evidence.length > 0 && (
          <div>
            <p className="muted small" style={{ marginTop: 8 }}>Từ khóa & tín hiệu vi phạm đã bóc tách</p>
            <div className="chip-row">
              {result.evidence.map((item) => (
                <span key={item} className="chip">
                  {item}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>

      {result.agent_trace.length > 0 && (
        <div>
          <h3 className="sandbox-subheading">Quy trình phân tích 5 Agent</h3>
          <ol className="stepper">
            {result.agent_trace.map((step, index) => (
              <motion.li
                key={`${step}-${index}`}
                initial={{ opacity: 0, x: -8 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ duration: 0.3, delay: index * 0.08 }}
              >
                <span className="stepper__index">{index + 1}</span>
                <span>{agentStepLabel(step)}</span>
              </motion.li>
            ))}
          </ol>
        </div>
      )}
    </motion.div>
  );
}

export default function AiSandboxPage() {
  const [text, setText] = useState("");
  const [channel, setChannel] = useState("general");
  const [submitting, setSubmitting] = useState(false);
  const [response, setResponse] = useState(null);
  const [error, setError] = useState(null);

  const handleSelectScenario = (scenario) => {
    setText(scenario.text);
    setChannel(scenario.channel);
    setResponse(null);
    setError(null);
  };

  const submit = async () => {
    if (!text.trim() || submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      const res = await moderation.submit({ user_id: SANDBOX_USER_ID, text: text.trim(), channel });
      setResponse(res);
    } catch (err) {
      setError(err.message);
      setResponse(null);
    } finally {
      setSubmitting(false);
    }
  };

  const clear = () => {
    setText("");
    setResponse(null);
    setError(null);
  };

  return (
    <div className="page-grid">
      <div className="page-grid__row">
        <Card title="Mẫu thử nghiệm nội dung" className="span-6">
          <p className="muted small" style={{ marginBottom: 6 }}>
            Chọn nhanh một tình huống mẫu hoặc tự soạn tin nhắn để kiểm thử:
          </p>

          {/* Quick Scenario Chips */}
          <div className="sandbox-scenarios">
            {QUICK_SCENARIOS.map((sc, i) => (
              <button
                key={i}
                type="button"
                className="sandbox-scenario-chip"
                onClick={() => handleSelectScenario(sc)}
              >
                <Sparkle size={13} weight="fill" />
                <span>{sc.label}</span>
              </button>
            ))}
          </div>

          <textarea
            className="sandbox-textarea"
            placeholder="Nhập nội dung tin nhắn hoặc đoạn chat cần kiểm thử..."
            value={text}
            maxLength={MAX_LENGTH}
            onChange={(event) => setText(event.target.value)}
          />

          <div className="sandbox-toolbar">
            <label className="sandbox-channel">
              Kênh
              <input
                type="text"
                value={channel}
                onChange={(event) => setChannel(event.target.value || "general")}
                maxLength={100}
              />
            </label>
            <span className="muted small">
              {text.length} / {MAX_LENGTH}
            </span>
          </div>

          <div className="sandbox-actions">
            <button type="button" className="btn btn--ghost" onClick={clear} disabled={submitting}>
              <Trash size={16} /> Xoá
            </button>
            <button type="button" className="btn btn--primary" onClick={submit} disabled={submitting || !text.trim()}>
              <PaperPlaneRight size={16} /> {submitting ? "Đang phân tích..." : "Bắt đầu phân tích"}
            </button>
          </div>
        </Card>

        <Card title="Kết quả AI & Dấu vết quy trình" className="span-6" delay={0.05}>
          {submitting && <SkeletonBlock height={280} />}
          {!submitting && error && <ErrorState message={error} onRetry={submit} />}
          {!submitting && !error && !response && (
            <EmptyState message="Nhập tin nhắn bên trái (hoặc chọn mẫu nhanh) rồi bấm “Bắt đầu phân tích” để xem kết quả kiểm duyệt thực tế từ hệ thống AI." />
          )}
          {!submitting && !error && response && <ResultPanel response={response} />}
        </Card>
      </div>
    </div>
  );
}
