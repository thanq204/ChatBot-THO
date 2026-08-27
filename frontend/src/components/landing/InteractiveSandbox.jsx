import React, { useState } from "react";
import { motion, AnimatePresence, useReducedMotion } from "motion/react";
import {
  ShieldCheck,
  Warning,
  Sparkle,
  PaperPlaneRight,
  ArrowsClockwise,
  CheckCircle,
  Brain,
  Scales,
  Gavel,
  Check,
  Lightning,
} from "@phosphor-icons/react";
import { DiscordIcon3D, TelegramIcon3D } from "./CommunityCard3D.jsx";

const PRESET_MESSAGES = [
  {
    label: "🚨 Thử nghiệm Spam & Rao vặt",
    platform: "discord",
    channel: "#general-chat",
    author: "User_Spammer#9999",
    avatar: "https://images.unsplash.com/photo-1535713875002-d1d0cf377fde?w=64&auto=format&fit=crop&q=60",
    text: "Cần bán nick Discord / Telegram Full nitro giá rẻ 50k, uy tín 100%, bảo hành trọn đời, ai mua ib riêng nha!",
    verdict: "Ẩn tin nhắn & Cảnh cáo",
    tone: "danger",
    category: "Spam / Quảng cáo trái phép",
    reason: "Vi phạm Điều 4 (Nghiêm cấm mua bán tài khoản và quảng cáo ngoài khu vực cho phép).",
    steps: [
      { agent: "Context", result: "Tin nhắn chứa từ khoá rao bán tài khoản không qua trung gian." },
      { agent: "Policy", result: "Khớp điều khoản #4: Cấm spam liên kết thương mại." },
      { agent: "Risk Score", result: "Rủi ro: 9.2/10 (High Risk - Lừa đảo giao dịch)" },
      { agent: "Decision", result: "Auto-Delete & Gửi cảnh cáo riêng cho thành viên." },
    ],
  },
  {
    label: "❓ Thử nghiệm Hỏi đáp FAQ",
    platform: "telegram",
    channel: "THO Support Group",
    author: "Linh_Dao_24",
    avatar: "https://images.unsplash.com/photo-1494790108377-be9c29b29330?w=64&auto=format&fit=crop&q=60",
    text: "Cho mình hỏi bot có hỗ trợ tuỳ chỉnh bộ luật kiểm duyệt theo từng kênh riêng biệt không ạ?",
    verdict: "Tự động trả lời FAQ",
    tone: "success",
    category: "Câu hỏi thường gặp (FAQ Khớp)",
    reason: "Khớp mục Tri thức #FAQ-29. Đã trích xuất hướng dẫn từ Knowledge Base.",
    steps: [
      { agent: "Context", result: "Thành viên hỏi về tính năng cấu hình luật riêng cho channel." },
      { agent: "Policy", result: "Nội dung an toàn, mang tính xây dựng." },
      { agent: "Knowledge", result: "Khớp 98% câu hỏi FAQ mục Cài đặt kênh." },
      { agent: "Decision", result: "Gửi phản hồi hướng dẫn chi tiết kèm liên kết docs." },
    ],
  },
  {
    label: "⚠️ Thử nghiệm Quấy rối / Ngôn từ thù địch",
    platform: "discord",
    channel: "#thao-luan",
    author: "AngryGamer",
    avatar: "https://images.unsplash.com/photo-1570295999919-56ceb5ecca61?w=64&auto=format&fit=crop&q=60",
    text: "Thằng này óc chó thật sự, ngu thế này cũng làm admin được à?",
    verdict: "Cảnh báo & Gắn cờ",
    tone: "warning",
    category: "Xúc phạm & Quấy rối",
    reason: "Ngôn từ công kích cá nhân, vi phạm chuẩn mực văn minh cộng đồng.",
    steps: [
      { agent: "Context", result: "Phát hiện ngôn từ thù địch nhắm vào ban quản trị." },
      { agent: "Policy", result: "Khớp điều khoản #1: Tôn trọng thành viên khác." },
      { agent: "Risk Score", result: "Rủi ro: 7.5/10 (Vi phạm mức trung bình - lần đầu)" },
      { agent: "Decision", result: "Tạm ẩn bình luận, gửi tin nhắn nhắc nhở quy tắc ứng xử." },
    ],
  },
];

export default function InteractiveSandbox() {
  const reduce = useReducedMotion();
  const [selectedPreset, setSelectedPreset] = useState(0);
  const [customText, setCustomText] = useState(PRESET_MESSAGES[0].text);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [activeAnalysisStep, setActiveAnalysisStep] = useState(4);

  const currentPreset = PRESET_MESSAGES[selectedPreset];

  const handleSelectPreset = (index) => {
    setSelectedPreset(index);
    setCustomText(PRESET_MESSAGES[index].text);
    triggerAnalysis();
  };

  const triggerAnalysis = () => {
    if (reduce) {
      setActiveAnalysisStep(4);
      return;
    }
    setIsAnalyzing(true);
    setActiveAnalysisStep(0);

    const stepTimers = [
      setTimeout(() => setActiveAnalysisStep(1), 300),
      setTimeout(() => setActiveAnalysisStep(2), 650),
      setTimeout(() => setActiveAnalysisStep(3), 1000),
      setTimeout(() => {
        setActiveAnalysisStep(4);
        setIsAnalyzing(false);
      }, 1350),
    ];

    return () => stepTimers.forEach(clearTimeout);
  };

  return (
    <div className="sandbox-card">
      <div className="sandbox-card__top">
        <div className="sandbox-card__badge">
          <Sparkle size={14} weight="fill" />
          <span>Interactive AI Sandbox • Trải nghiệm thời gian thực</span>
        </div>
        <h3 className="sandbox-card__headline">
          Thử nghiệm khả năng phân tích đa ngữ cảnh của THO AI
        </h3>
        <p className="sandbox-card__subhead">
          Chọn một tình huống mẫu hoặc chỉnh sửa nội dung bên dưới để xem AI Agent phân tích và ra
          quyết định trong chớp mắt.
        </p>

        {/* Preset selection tabs */}
        <div className="sandbox-card__presets">
          {PRESET_MESSAGES.map((preset, idx) => (
            <button
              key={idx}
              type="button"
              className={`sandbox-preset-btn ${selectedPreset === idx ? "is-active" : ""}`}
              onClick={() => handleSelectPreset(idx)}
            >
              {preset.label}
            </button>
          ))}
        </div>
      </div>

      <div className="sandbox-card__grid">
        {/* Left Column: Simulated Chat Message Input */}
        <div className="sandbox-chat-panel">
          <div className="sandbox-chat-panel__header">
            <div className="sandbox-chat-panel__platform">
              {currentPreset.platform === "discord" ? (
                <>
                  <DiscordIcon3D size={24} />
                  <span className="sandbox-platform-name">Discord Server</span>
                  <span className="sandbox-channel-name">{currentPreset.channel}</span>
                </>
              ) : (
                <>
                  <TelegramIcon3D size={24} />
                  <span className="sandbox-platform-name">Telegram Group</span>
                  <span className="sandbox-channel-name">{currentPreset.channel}</span>
                </>
              )}
            </div>
            <span className="sandbox-status-live">
              <span className="sandbox-pulse-dot" />
              Sẵn sàng kiểm tra
            </span>
          </div>

          <div className="sandbox-message-box">
            <div className="sandbox-message-box__avatar">
              <img src={currentPreset.avatar} alt="User avatar" />
            </div>
            <div className="sandbox-message-box__content">
              <div className="sandbox-message-box__author-row">
                <span className="sandbox-author-name">{currentPreset.author}</span>
                <span className="sandbox-timestamp">Hôm nay lúc 14:20</span>
              </div>
              <textarea
                className="sandbox-textarea"
                value={customText}
                onChange={(e) => setCustomText(e.target.value)}
                rows={3}
                placeholder="Nhập tin nhắn để thử nghiệm..."
              />
            </div>
          </div>

          <div className="sandbox-chat-panel__actions">
            <button
              type="button"
              className="sandbox-analyze-btn"
              onClick={triggerAnalysis}
              disabled={isAnalyzing}
            >
              <Lightning size={16} weight="fill" />
              <span>{isAnalyzing ? "Đang phân tích..." : "Chạy AI Agent phân tích"}</span>
            </button>
            <span className="sandbox-hint-text">
              ⏱️ Thời gian phản hồi trung bình: <strong>~320ms</strong>
            </span>
          </div>
        </div>

        {/* Right Column: AI Reasoning Engine Pipeline */}
        <div className="sandbox-decision-panel">
          <div className="sandbox-decision-panel__header">
            <div className="sandbox-decision-panel__title">
              <Brain size={18} weight="fill" className="sandbox-brain-icon" />
              <span>Luồng suy luận đa tác tử (Multi-Agent Reasoning)</span>
            </div>
          </div>

          <div className="sandbox-steps-list">
            {currentPreset.steps.map((step, idx) => {
              const isDone = activeAnalysisStep > idx;
              const isActive = activeAnalysisStep === idx;
              return (
                <motion.div
                  key={idx}
                  className={`sandbox-step-item ${isDone ? "is-done" : ""} ${isActive ? "is-active" : ""}`}
                  animate={isActive ? { x: [0, 4, 0] } : {}}
                  transition={{ duration: 0.3 }}
                >
                  <div className="sandbox-step-item__icon">
                    {isDone ? (
                      <Check size={14} weight="bold" />
                    ) : (
                      <span>{idx + 1}</span>
                    )}
                  </div>
                  <div className="sandbox-step-item__content">
                    <div className="sandbox-step-item__agent">
                      <span>{step.agent}</span>
                      {isActive && <span className="sandbox-typing-dots">...</span>}
                    </div>
                    <p className="sandbox-step-item__result">{step.result}</p>
                  </div>
                </motion.div>
              );
            })}
          </div>

          {/* Final Decision Box */}
          <AnimatePresence>
            {activeAnalysisStep >= 4 && (
              <motion.div
                className={`sandbox-verdict-card sandbox-verdict-card--${currentPreset.tone}`}
                initial={reduce ? false : { opacity: 0, scale: 0.95, y: 10 }}
                animate={{ opacity: 1, scale: 1, y: 0 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.3 }}
              >
                <div className="sandbox-verdict-card__header">
                  <div className="sandbox-verdict-card__action">
                    <ShieldCheck size={20} weight="fill" />
                    <strong>{currentPreset.verdict}</strong>
                  </div>
                  <span className="sandbox-verdict-card__cat">{currentPreset.category}</span>
                </div>
                <p className="sandbox-verdict-card__reason">{currentPreset.reason}</p>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
    </div>
  );
}
