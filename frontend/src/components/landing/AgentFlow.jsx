import { useEffect, useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { Brain, Scales, Warning, ShieldCheck, Gavel } from "@phosphor-icons/react";

/**
 * Hero visual. Replays the real pipeline from backend/agents/moderation_graph.py
 * (context -> policy -> risk -> safety gate -> decision) over three sample
 * messages so the value prop is shown instead of described.
 *
 * The driver is a discrete step index on a timer chain, not a per-frame value,
 * so useState is the correct tool here.
 */

const STEPS = [
  { key: "context", label: "Agent ngữ cảnh", hint: "Đọc lịch sử kênh", icon: Brain },
  { key: "policy", label: "Agent chính sách", hint: "Đối chiếu quy tắc của bạn", icon: Scales },
  { key: "risk", label: "Agent rủi ro", hint: "Chấm mức nghiêm trọng", icon: Warning },
  { key: "gate", label: "Cổng an toàn", hint: "Kiểm tra ngưỡng an toàn", icon: ShieldCheck },
  { key: "decision", label: "Agent quyết định", hint: "Chốt hành động cuối", icon: Gavel },
];

const SCENARIOS = [
  {
    id: "spam",
    platform: "Discord",
    channel: "#gioi-thieu",
    author: "Trần Bảo Khang",
    text: "Ai cần acc xịn giá rẻ thì ib mình nhé, bao uy tín, có bảo hành 6 tháng.",
    category: "Spam / Lừa đảo",
    decision: "Ẩn nội dung",
    tone: "hide",
    note: "Trùng mẫu quảng cáo đã bị gỡ trong kênh này.",
  },
  {
    id: "harassment",
    platform: "Telegram",
    channel: "Nhóm học viên",
    author: "Lê Minh Quân",
    text: "Nói chuyện kiểu đó mà cũng đòi vào nhóm này à, biến đi cho nhanh.",
    category: "Quấy rối",
    decision: "Cảnh báo",
    tone: "warn",
    note: "Vi phạm lần đầu, agent nhắc riêng thay vì khoá.",
  },
  {
    id: "faq",
    platform: "Discord",
    channel: "#hoi-dap",
    author: "Phạm Hà Vy",
    text: "Cho mình hỏi đợt đăng ký khoá tiếp theo mở lại vào lúc nào ạ?",
    category: "An toàn",
    decision: "Cho phép",
    tone: "allow",
    note: "Khớp FAQ trong kho tri thức, agent trả lời tự động.",
  },
];

const STEP_MS = 520;
const LEAD_MS = 700;
const HOLD_MS = 2600;

export default function AgentFlow() {
  const reduce = useReducedMotion();
  const [index, setIndex] = useState(0);
  const [step, setStep] = useState(reduce ? STEPS.length : -1);

  useEffect(() => {
    if (reduce) {
      setStep(STEPS.length);
      return undefined;
    }

    setStep(-1);
    const timers = STEPS.map((_, i) => setTimeout(() => setStep(i), LEAD_MS + i * STEP_MS));
    const settle = LEAD_MS + STEPS.length * STEP_MS;
    timers.push(setTimeout(() => setStep(STEPS.length), settle));
    timers.push(
      setTimeout(() => setIndex((current) => (current + 1) % SCENARIOS.length), settle + HOLD_MS),
    );

    return () => timers.forEach(clearTimeout);
  }, [index, reduce]);

  const scenario = SCENARIOS[index];
  const settled = step >= STEPS.length;

  return (
    <div className="flow" aria-live="polite">
      <div className="flow__head">
        <span className="flow__source">
          {scenario.platform}
          <span className="flow__channel">{scenario.channel}</span>
        </span>
        <span className="flow__state">{settled ? "Đã xử lý" : "Đang phân tích"}</span>
      </div>

      <AnimatePresence mode="wait">
        <motion.div
          key={scenario.id}
          className="flow__message"
          initial={reduce ? false : { opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          exit={reduce ? undefined : { opacity: 0, y: -8 }}
          transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
        >
          <span className="flow__author">{scenario.author}</span>
          <p className="flow__text">{scenario.text}</p>
        </motion.div>
      </AnimatePresence>

      <ol className="flow__steps">
        {STEPS.map((item, i) => {
          const Icon = item.icon;
          const done = step > i;
          const active = step === i;
          return (
            <li
              key={item.key}
              className={`flow__step${active ? " is-active" : ""}${done ? " is-done" : ""}`}
            >
              <span className="flow__rail" aria-hidden="true" />
              <span className="flow__icon">
                <Icon size={15} weight={done || active ? "fill" : "regular"} />
              </span>
              <span className="flow__label">
                {item.label}
                <span className="flow__hint">{item.hint}</span>
              </span>
            </li>
          );
        })}
      </ol>

      <div className="flow__result-slot">
        <AnimatePresence mode="wait">
          {settled ? (
            <motion.div
              key={`${scenario.id}-result`}
              className={`flow__result flow__result--${scenario.tone}`}
              initial={reduce ? false : { opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={reduce ? undefined : { opacity: 0, y: -4 }}
              transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
            >
              <span className="flow__verdict">{scenario.decision}</span>
              <span className="flow__category">{scenario.category}</span>
              <p className="flow__note">{scenario.note}</p>
            </motion.div>
          ) : (
            <motion.div
              key="analyzing-slot"
              className="flow__result-placeholder"
              initial={reduce ? false : { opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.2 }}
            >
              <span className="flow__placeholder-pulse" />
              <span className="flow__placeholder-text">Agent đang phân tích & đối chiếu ngữ cảnh...</span>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}
