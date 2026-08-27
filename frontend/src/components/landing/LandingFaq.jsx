import React, { useState } from "react";
import { motion, AnimatePresence } from "motion/react";
import { CaretDown, Question, ShieldCheck, Sparkle, ChatCircleDots } from "@phosphor-icons/react";

const FAQ_ITEMS = [
  {
    q: "Làm sao để mời và kích hoạt bot trên Discord hoặc Telegram của tôi?",
    a: "Rất đơn giản! Bạn chỉ cần vào mục Quản lý Kênh trong Bảng điều khiển, nhấp 'Thêm Bot', cấp quyền cơ bản (đọc tin nhắn, gửi tin nhắn, quản lý tin nhắn vi phạm). Toàn bộ quá trình cài đặt mất chưa đầy 60 giây và không cần biết lập trình.",
  },
  {
    q: "Tôi có thể thử nghiệm bot trước khi đưa vào nhóm chính thức không?",
    a: "Hoàn toàn được! Bạn có thể bấm vào 2 liên kết Discord và Telegram thử nghiệm ở trên để trò chuyện, thử nghiệm các lệnh kiểm duyệt, gửi tin spam hoặc hỏi đáp kiến thức ngay trong nhóm mẫu của chúng tôi.",
  },
  {
    q: "Bot xử lý tiếng Việt và ngôn ngữ lóng (slang/teencode) tốt không?",
    a: "THO AI được huấn luyện chuyên sâu trên dữ liệu hội thoại tiếng Việt thực tế, hiểu chính xác teencode, từ lóng, nói giảm nói tránh và các sắc thái châm biếm, mỉa mai qua ngữ cảnh trước và sau của kênh chat.",
  },
  {
    q: "Dữ liệu trò chuyện của nhóm có được bảo mật và an toàn không?",
    a: "Chúng tôi tuân thủ nghiêm ngặt chuẩn bảo mật doanh nghiệp. Dữ liệu tin nhắn chỉ được nạp vào bộ nhớ ngữ cảnh tạm thời để AI phân tích và tự động hủy sau khi hoàn thành chu trình. Không bao giờ chia sẻ dữ liệu cho bên thứ ba.",
  },
  {
    q: "Tôi có thể tự viết bộ luật (policy) riêng cho cộng đồng của mình không?",
    a: "Chắc chắn rồi! Bạn có toàn quyền định nghĩa quy tắc cấm bằng ngôn ngữ tự nhiên (ví dụ: 'Cấm tuyển dụng trái phép', 'Cấm link shopee/affiliate'). AI Agent sẽ tự động đối chiếu từng tin nhắn theo đúng văn phong quy chế của bạn.",
  },
];

export default function LandingFaq() {
  const [openIndex, setOpenIndex] = useState(0);

  const toggleItem = (index) => {
    setOpenIndex(openIndex === index ? -1 : index);
  };

  return (
    <div className="lfaq-container">
      {FAQ_ITEMS.map((item, idx) => {
        const isOpen = openIndex === idx;
        return (
          <div key={idx} className={`lfaq-item ${isOpen ? "is-open" : ""}`}>
            <button
              type="button"
              className="lfaq-trigger"
              onClick={() => toggleItem(idx)}
              aria-expanded={isOpen}
            >
              <span className="lfaq-q-text">
                <span className="lfaq-icon-bullet">
                  <Question size={16} weight="bold" />
                </span>
                {item.q}
              </span>
              <motion.span
                className="lfaq-caret"
                animate={{ rotate: isOpen ? 180 : 0 }}
                transition={{ duration: 0.24 }}
              >
                <CaretDown size={18} weight="bold" />
              </motion.span>
            </button>

            <AnimatePresence initial={false}>
              {isOpen && (
                <motion.div
                  className="lfaq-answer-wrapper"
                  initial={{ height: 0, opacity: 0 }}
                  animate={{ height: "auto", opacity: 1 }}
                  exit={{ height: 0, opacity: 0 }}
                  transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
                >
                  <p className="lfaq-answer-text">{item.a}</p>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        );
      })}
    </div>
  );
}
