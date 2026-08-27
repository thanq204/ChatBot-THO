import React, { useState } from "react";
import { motion, useMotionValue, useReducedMotion, useSpring, useTransform } from "motion/react";
import {
  ArrowRight,
  ArrowUpRight,
  BookOpen,
  Broadcast,
  ChartLine,
  CheckCircle,
  Clock,
  Cpu,
  Flask,
  GameController,
  Gavel,
  GithubLogo,
  Globe,
  Lightning,
  LockSimple,
  Moon,
  Notebook,
  PaperPlaneTilt,
  Robot,
  Scales,
  ShieldCheck,
  Sparkle,
  Sun,
  Users,
  Warning,
  XCircle,
} from "@phosphor-icons/react";
import AgentFlow from "../components/landing/AgentFlow.jsx";
import SakuraField from "../components/landing/SakuraField.jsx";
import CommunityCard3D, { DiscordIcon3D, TelegramIcon3D } from "../components/landing/CommunityCard3D.jsx";
import InteractiveSandbox from "../components/landing/InteractiveSandbox.jsx";
import LandingFaq from "../components/landing/LandingFaq.jsx";
import { TransitionLink } from "../transitions/PageTransition.jsx";
import { useAuth } from "../auth/AuthProvider.jsx";
import { useTheme } from "../theme/ThemeProvider.jsx";
import "../landing.css";
import { BRAND } from "../lib/brand.js";
import ThoMascot from "../components/ThoMascot.jsx";

const DISCORD_INVITE_URL = "https://discord.gg/aDmxHeWBW";
const TELEGRAM_INVITE_URL = "https://t.me/+7RNdxcwOkwtmODI9";
const REPO_URL = "https://github.com/AI20K-Build-Phase-Cohort-3/P-232";

/** Shared scroll entrance so every section enters on the same rhythm. */
function Reveal({ children, delay = 0, className, as = "div" }) {
  const reduce = useReducedMotion();
  const Component = motion[as];
  return (
    <Component
      className={className}
      initial={reduce ? false : { opacity: 0, y: 24 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, amount: 0.15 }}
      transition={{ duration: 0.65, delay, ease: [0.16, 1, 0.3, 1] }}
    >
      {children}
    </Component>
  );
}

const STATS = [
  { value: "< 350ms", label: "Tốc độ xử lý vi phạm", icon: Lightning },
  { value: "99.4%", label: "Độ chính xác nhận diện", icon: ShieldCheck },
  { value: "24/7/365", label: "Giám sát tự động liên tục", icon: Clock },
  { value: "Multi-Agent", label: "5 Tác tử suy luận đồng thời", icon: Cpu },
];

const PAINS = [
  {
    title: "Vi phạm không đợi giờ hành chính",
    body: "Tin nhắn lừa đảo, chửi bới lúc 2 giờ sáng vẫn hiển thị hàng giờ liền cho đến khi ban quản trị thức dậy.",
    tag: "Chậm trễ",
  },
  {
    title: "Mỗi nền tảng một cửa sổ riêng",
    body: "Discord một tab, Telegram một tab. Mod nhảy qua lại liên tục dẫn đến sót vi phạm và thiếu cái nhìn tổng thể.",
    tag: "Phân mảnh",
  },
  {
    title: "Cùng một câu hỏi, trả lời lại từ đầu",
    body: "Thành viên mới liên tục hỏi trùng lặp. Đội ngũ tốn 40% thời gian chỉ để gõ lại những hướng dẫn đã có.",
    tag: "Lãng phí",
  },
  {
    title: "Xử phạt cảm tính, không có bằng chứng",
    body: "Khi xảy ra khiếu nại, không ai nhớ vì sao tin nhắn bị gỡ hay tài khoản bị mute, gây mất lòng cộng đồng.",
    tag: "Thiếu minh bạch",
  },
];

const PIPELINE = [
  {
    step: "01",
    name: "Phân tích Ngữ cảnh",
    body: "Agent đọc chuỗi tin nhắn trước đó trong kênh để hiểu rõ sắc thái đùa vui hay công kích ác ý.",
  },
  {
    step: "02",
    name: "Đối chiếu Chính sách",
    body: "So sánh trực tiếp với bộ quy tắc riêng của server bạn, không phụ thuộc vào danh sách từ khoá cố định.",
  },
  {
    step: "03",
    name: "Chấm điểm Rủi ro",
    body: "Tính toán xác suất nguy hại theo thang điểm chuẩn, đính kèm phân tích nguyên nhân chi tiết.",
  },
  {
    step: "04",
    name: "Cổng kiểm duyệt An toàn",
    body: "Tự động phân luồng: xử lý tức thì với lỗi rõ ràng, đẩy vào hàng đợi duyệt với trường hợp nhạy cảm.",
  },
  {
    step: "05",
    name: "Hành động & Nhật ký",
    body: "Ẩn tin, nhắc nhở hoặc trả lời FAQ, đồng thời ghi lại toàn bộ lộ trình suy luận vào nhật ký kiểm duyệt.",
  },
];

const COMPARISONS = [
  {
    feature: "Thời gian phản hồi",
    traditional: "15 phút - 8 tiếng (phụ thuộc người trực)",
    tho: "Dưới 350ms (Tức thời 24/7)",
  },
  {
    feature: "Độ bao phủ đa kênh",
    traditional: "Thủ công chuyển đổi từng tab Discord/Telegram",
    tho: "Đồng bộ realtime trên một dashboard duy nhất",
  },
  {
    feature: "Giải đáp câu hỏi thường gặp",
    traditional: "Sao chép thủ công từng tin nhắn mẫu",
    tho: "AI tự động tra cứu Knowledge Base & phản hồi",
  },
  {
    feature: "Độ nhất quán quy tắc",
    traditional: "Dễ thiên vị, cảm tính tuỳ tâm trạng mod",
    tho: "100% tuân thủ văn bản chính sách bạn thiết lập",
  },
  {
    feature: "Lưu vết bằng chứng",
    traditional: "Chụp màn hình rời rạc, dễ thất lạc",
    tho: "Lưu trọn vẹn context, nguyên nhân & mức rủi ro",
  },
];

export default function LandingPage() {
  const { theme, toggleTheme } = useTheme();
  const { isAuthenticated } = useAuth();
  const reduce = useReducedMotion();
  const ThemeIcon = theme === "dark" ? Sun : Moon;
  const ctaTo = isAuthenticated ? "/tong-quan" : "/login";
  const ctaLabel = isAuthenticated ? "Vào bảng điều khiển" : "Đăng nhập";

  /* Blob parallax */
  const pointerX = useMotionValue(0);
  const pointerY = useMotionValue(0);
  const driftX = useSpring(pointerX, { stiffness: 38, damping: 22, mass: 0.6 });
  const driftY = useSpring(pointerY, { stiffness: 38, damping: 22, mass: 0.6 });
  const pinkX = useTransform(driftX, [-1, 1], [-32, 32]);
  const pinkY = useTransform(driftY, [-1, 1], [-22, 22]);
  const lavX = useTransform(driftX, [-1, 1], [24, -24]);
  const lavY = useTransform(driftY, [-1, 1], [18, -18]);

  const trackPointer = (event) => {
    if (reduce) return;
    const bounds = event.currentTarget.getBoundingClientRect();
    pointerX.set(((event.clientX - bounds.left) / bounds.width) * 2 - 1);
    pointerY.set(((event.clientY - bounds.top) / bounds.height) * 2 - 1);
  };

  return (
    <div className="landing">
      <SakuraField variant="page" />

      {/* Navigation */}
      <header className="lnav">
        <div className="lnav__inner">
          <a className="lnav__brand" href="#top">
            <span className="sk-mark" aria-hidden="true">
              ✦
            </span>
            <span className="lnav__brand-text">{BRAND.name}</span>
            <span className="lnav__badge-version">v2.0 AI</span>
          </a>

          <nav className="lnav__links" aria-label="Nội dung trang">
            <a href="#community-hub">Trải Nghiệm Bot Ngay</a>
            <a href="#features">Tính Năng</a>
            <a href="#sandbox">Sandbox AI</a>
            <a href="#how-it-works">Cách Hoạt Động</a>
            <a href="#comparison">So Sánh</a>
            <a href="#faq">Hỏi Đáp</a>
          </nav>

          <div className="lnav__actions">
            <button
              type="button"
              className="lnav__toggle"
              onClick={toggleTheme}
              aria-label={theme === "dark" ? "Chuyển sang giao diện sáng" : "Chuyển sang giao diện tối"}
            >
              <ThemeIcon size={16} />
            </button>
            <TransitionLink to={ctaTo} className="sk-btn">
              {ctaLabel}
            </TransitionLink>
          </div>
        </div>
      </header>

      <main id="top">
        {/* HERO SECTION */}
        <section className="lhero" onPointerMove={trackPointer}>
          <div className="lhero__blobs" aria-hidden="true">
            <motion.span
              className="lhero__blob lhero__blob--pink"
              style={reduce ? undefined : { x: pinkX, y: pinkY }}
            >
              <span className="lhero__blob-core" />
            </motion.span>
            <motion.span
              className="lhero__blob lhero__blob--lavender"
              style={reduce ? undefined : { x: lavX, y: lavY }}
            >
              <span className="lhero__blob-core" />
            </motion.span>
          </div>

          <div className="lhero__inner">
            <div className="lhero__copy">
              <motion.div
                className="lhero__eyebrow-wrapper"
                initial={reduce ? false : { opacity: 0, y: -10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.5 }}
              >
                <span className="lhero__eyebrow">
                  <Sparkle size={14} weight="fill" className="lhero__sparkle-icon" />
                  {BRAND.name} · {BRAND.tagline}
                </span>
                <span className="lhero__pill-pulse">
                  <span className="card-3d__pulse" />
                  Bot Live trên Discord & Telegram
                </span>
              </motion.div>

              <motion.h1
                className="lhero__title"
                initial={reduce ? false : { opacity: 0, y: 26 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.7, delay: 0.08, ease: [0.16, 1, 0.3, 1] }}
              >
                Quản lý cộng đồng thông minh với{" "}
                <span className="lhero__title-gradient">AI Multi-Agent</span>
              </motion.h1>

              <motion.p
                className="lhero__sub"
                initial={reduce ? false : { opacity: 0, y: 18 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.7, delay: 0.16, ease: [0.16, 1, 0.3, 1] }}
              >
                Tự động giám sát, can thiệp vi phạm trong <strong>300ms</strong>, giải đáp câu hỏi
                lặp 24/7 và hợp nhất Discord & Telegram về một trung tâm chỉ huy duy nhất.
              </motion.p>

              {/* Main Action Buttons */}
              <motion.div
                className="lhero__cta"
                initial={reduce ? false : { opacity: 0, y: 14 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.7, delay: 0.24, ease: [0.16, 1, 0.3, 1] }}
              >
                <TransitionLink to={ctaTo} className="sk-btn sk-btn--lg">
                  {ctaLabel}
                  <ArrowRight size={16} weight="bold" />
                </TransitionLink>
                <a href="#community-hub" className="sk-btn sk-btn--quiet sk-btn--lg">
                  <GameController size={18} weight="duotone" />
                  Trải nghiệm Bot ngay ↗
                </a>
              </motion.div>

              {/* Quick 3D Community Banner */}
              <motion.div
                className="lhero__community-quick"
                initial={reduce ? false : { opacity: 0, y: 16 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.7, delay: 0.32, ease: [0.16, 1, 0.3, 1] }}
              >
                <span className="lhero__community-quick-label">Tham gia thử nghiệm bot ngay:</span>
                <div className="lhero__community-pills">
                  <a
                    href={DISCORD_INVITE_URL}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="hero-community-pill hero-community-pill--discord"
                  >
                    <DiscordIcon3D size={26} />
                    <div className="hero-community-pill__text">
                      <strong>Discord Server</strong>
                      <span>#test-bot • Trực tuyến</span>
                    </div>
                    <ArrowUpRight size={14} weight="bold" />
                  </a>

                  <a
                    href={TELEGRAM_INVITE_URL}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="hero-community-pill hero-community-pill--telegram"
                  >
                    <TelegramIcon3D size={26} />
                    <div className="hero-community-pill__text">
                      <strong>Telegram Group</strong>
                      <span>@tho_bot • Hoạt động</span>
                    </div>
                    <ArrowUpRight size={14} weight="bold" />
                  </a>
                </div>
              </motion.div>
            </div>

            <motion.div
              className="lhero__visual"
              initial={reduce ? false : { opacity: 0, y: 30 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.8, delay: 0.2, ease: [0.16, 1, 0.3, 1] }}
            >
              <ThoMascot height={88} className="lhero__mascot" />
              <AgentFlow />
            </motion.div>
          </div>
        </section>

        {/* METRICS / STATS TICKER */}
        <section className="lstats-bar">
          <div className="lshell">
            <div className="lstats-grid">
              {STATS.map((st, i) => {
                const Icon = st.icon;
                return (
                  <Reveal key={i} className="lstats-item" delay={0.06 * i}>
                    <div className="lstats-icon-box">
                      <Icon size={22} weight="duotone" />
                    </div>
                    <div className="lstats-content">
                      <span className="lstats-value">{st.value}</span>
                      <span className="lstats-label">{st.label}</span>
                    </div>
                  </Reveal>
                );
              })}
            </div>
          </div>
        </section>

        {/* DEDICATED COMMUNITY & BOT TESTING HUB */}
        <section className="lcommunity-3d-section" id="community-hub">
          <div className="lshell">
            <div className="lcommunity-head">
              <Reveal as="div" className="lcommunity-badge">
                <Sparkle size={14} weight="fill" />
                <span>Thử Nghiệm Trực Tiếp • Live Bot Testing</span>
              </Reveal>
              <Reveal as="h2" className="lsection-title lsection-title--center" delay={0.05}>
                Gia nhập Server Discord & Nhóm Telegram Test Bot
              </Reveal>
              <Reveal as="p" className="lsection-body lsection-body--center" delay={0.1}>
                Nhấp vào các thẻ bên dưới để vào trực tiếp phòng test bot. Trải
                nghiệm khả năng lọc spam, phân tích ngữ cảnh và phản hồi thông minh trong môi trường
                thực tế!
              </Reveal>
            </div>

            {/* 2 Big 3D Interactive Tilt Cards */}
            <div className="lcommunity-cards-grid">
              <Reveal delay={0.12}>
                <CommunityCard3D
                  platform="discord"
                  title="Discord Community Server"
                  subtitle="#test-bot • Máy chủ Kiểm thử Chính thức"
                  description="Tham gia máy chủ Discord để thử nghiệm các Slash commands, gửi tin nhắn kiểm tra hệ thống lọc ngôn từ vi phạm và xem bot phân loại vai trò tự động."
                  url={DISCORD_INVITE_URL}
                  badgeText="🟢 Bot Đang Hoạt Động (Online)"
                  memberCount="Server Test Bot"
                  ctaLabel="Vào Discord Test Bot ↗"
                  features={[
                    "Kênh #kiem-thu-bot riêng tư",
                    "Kiểm duyệt ngôn từ thời gian thực",
                    "Lệnh Slash /ask và /report",
                    "Đồng bộ cảnh báo về Dashboard",
                  ]}
                />
              </Reveal>

              <Reveal delay={0.2}>
                <CommunityCard3D
                  platform="telegram"
                  title="Telegram Test Group"
                  subtitle="@tho_moderator_bot • Nhóm Học Viên & Thử Nghiệm"
                  description="Vào nhóm Telegram để kiểm tra khả năng tự động chặn tin nhắn rác, phát hiện liên kết lừa đảo và trích xuất câu trả lời FAQ tức thời từ kho tri thức."
                  url={TELEGRAM_INVITE_URL}
                  badgeText="🟢 Bot Đang Kết Nối (Active)"
                  memberCount="Nhóm Test Bot"
                  ctaLabel="Vào Telegram Test Bot ↗"
                  features={[
                    "Chặn tin rác & link spam trong 300ms",
                    "Tự động giải đáp câu hỏi thường gặp",
                    "Cảnh cáo & Mute thành viên vi phạm",
                    "Nhật ký kiểm duyệt minh bạch",
                  ]}
                />
              </Reveal>
            </div>
          </div>
        </section>

        {/* INTERACTIVE AI SANDBOX DEMO */}
        <section className="lsandbox-section" id="sandbox">
          <div className="lshell">
            <Reveal as="div">
              <InteractiveSandbox />
            </Reveal>
          </div>
        </section>

        {/* PAIN POINTS SECTION */}
        <section className="lpain">
          <div className="lshell">
            <Reveal as="h2" className="lsection-title">
              Cộng đồng lớn nhanh hơn đội ngũ trực
            </Reveal>
            <Reveal as="p" className="lsection-body" delay={0.06}>
              Bốn nút thắt lặp đi lặp lại mỗi ngày khiến ban quản trị kiệt sức và thành viên bức xúc.
            </Reveal>

            <div className="lpain__grid">
              {PAINS.map((pain, i) => (
                <Reveal key={pain.title} className="lpain__item" delay={0.06 * i}>
                  <div className="lpain__item-top">
                    <span className="lpain__tag">{pain.tag}</span>
                  </div>
                  <h3>{pain.title}</h3>
                  <p>{pain.body}</p>
                </Reveal>
              ))}
            </div>
          </div>
        </section>

        {/* FEATURES BENTO GRID */}
        <section className="lbento" id="features">
          <div className="lshell">
            <Reveal as="h2" className="lsection-title">
              Những gì AI Agent làm thay bạn
            </Reveal>
            <Reveal as="p" className="lsection-body" delay={0.06}>
              Tự động hoá các tác vụ kiểm duyệt lặp lại để bạn tập trung xây dựng nội dung và gắn kết
              thành viên.
            </Reveal>

            <div className="lbento__grid">
              <Reveal className="lcell lcell--mascot">
                <div className="lcell__stage" aria-hidden="true">
                  <ThoMascot height={120} />
                </div>
                <div className="lcell__body">
                  <Broadcast size={20} weight="fill" />
                  <h3>Giám sát đa nền tảng đồng bộ</h3>
                  <p>
                    Kéo tin nhắn từ Discord và Telegram theo luồng thời gian thực, chuẩn hoá về một
                    hàng đợi phân tích duy nhất.
                  </p>
                </div>
              </Reveal>

              <Reveal className="lcell lcell--ink" delay={0.05}>
                <div className="lcell__body">
                  <Scales size={20} weight="fill" />
                  <h3>Chính sách do bạn viết bằng ngôn ngữ tự nhiên</h3>
                  <p>
                    Thêm quy tắc mới chỉ bằng văn bản tiếng Việt. AI hiểu ý định và áp dụng ngay ở
                    tin nhắn kế tiếp mà không cần cấu hình phức tạp.
                  </p>
                </div>
              </Reveal>

              <Reveal className="lcell lcell--pattern" delay={0.09}>
                <div className="lcell__body">
                  <BookOpen size={20} weight="fill" />
                  <h3>Tự động trả lời FAQ thông minh</h3>
                  <p>
                    Nạp tài liệu, nội quy vào kho tri thức (RAG). Bot giải đáp tức thì các câu hỏi
                    lặp và tự động đề xuất FAQ mới cần bổ sung.
                  </p>
                </div>
              </Reveal>

              <Reveal className="lcell" delay={0.05}>
                <div className="lcell__body">
                  <Notebook size={20} weight="fill" />
                  <h3>Nhật ký truy vết minh bạch</h3>
                  <p>
                    Mỗi quyết định gỡ bài hay cảnh cáo đều lưu trọn vẹn ngữ cảnh gốc, điều luật đã
                    khớp và từng bước suy luận của Agent.
                  </p>
                </div>
              </Reveal>

              <Reveal className="lcell" delay={0.09}>
                <div className="lcell__body">
                  <ChartLine size={20} weight="fill" />
                  <h3>Báo cáo sức khoẻ cộng đồng</h3>
                  <p>
                    Biểu đồ trực quan theo dõi tần suất vi phạm, tỉ lệ người dùng tích cực và cảnh
                    báo sớm khi có dấu hiệu tấn công spam hoặc xung đột.
                  </p>
                </div>
              </Reveal>

              <Reveal className="lcell lcell--wide" delay={0.05}>
                <div className="lcell__body">
                  <Flask size={20} weight="fill" />
                  <h3>Khu vực Sandbox kiểm thử an toàn</h3>
                  <p>
                    Dán thử bất kỳ tin nhắn mẫu nào để theo dõi cách các Agent suy luận từng bước,
                    kiểm chứng độ chính xác trước khi áp dụng vào nhóm thật.
                  </p>
                </div>
              </Reveal>
            </div>
          </div>
        </section>

        {/* PIPELINE SECTION */}
        <section className="lflow" id="how-it-works">
          <div className="lshell">
            <Reveal as="h2" className="lsection-title">
              Mỗi tin nhắn đi qua chuỗi 5 AI Agent chuyên biệt
            </Reveal>
            <Reveal as="p" className="lsection-body" delay={0.06}>
              Kiến trúc Multi-Agent phân rã bài toán kiểm duyệt thành các bước chuyên môn hoá, loại bỏ
              hoàn toàn tình trạng phán đoán sai hoặc ảo giác AI.
            </Reveal>

            <ol className="lflow__rail">
              {PIPELINE.map((stage, i) => (
                <Reveal as="li" key={stage.name} className="lflow__stage" delay={0.06 * i}>
                  <span className="lflow__step-num">{stage.step}</span>
                  <span className="lflow__marker" aria-hidden="true" />
                  <h3 className="lflow__name">{stage.name}</h3>
                  <p className="lflow__body">{stage.body}</p>
                </Reveal>
              ))}
            </ol>
          </div>
        </section>

        {/* COMPARISON TABLE */}
        <section className="lcomparison-section" id="comparison">
          <div className="lshell">
            <Reveal as="h2" className="lsection-title lsection-title--center">
              Tại sao chọn THO AI thay vì kiểm duyệt thủ công?
            </Reveal>
            <Reveal as="p" className="lsection-body lsection-body--center" delay={0.06}>
              Nâng cấp trải nghiệm vận hành cộng đồng với tốc độ và độ chuẩn xác vượt trội.
            </Reveal>

            <Reveal className="lcomparison-table-wrapper" delay={0.12}>
              <table className="lcomparison-table">
                <thead>
                  <tr>
                    <th>Tiêu chí so sánh</th>
                    <th>Quản lý truyền thống</th>
                    <th className="th-highlight">THO AI Agent Hub</th>
                  </tr>
                </thead>
                <tbody>
                  {COMPARISONS.map((row, idx) => (
                    <tr key={idx}>
                      <td className="td-feature">{row.feature}</td>
                      <td className="td-traditional">
                        <XCircle size={16} weight="fill" className="icon-bad" />
                        <span>{row.traditional}</span>
                      </td>
                      <td className="td-tho">
                        <CheckCircle size={16} weight="fill" className="icon-good" />
                        <span>{row.tho}</span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </Reveal>
          </div>
        </section>

        {/* FAQ SECTION */}
        <section className="lfaq-section" id="faq">
          <div className="lshell">
            <Reveal as="h2" className="lsection-title lsection-title--center">
              Câu hỏi thường gặp (FAQ)
            </Reveal>
            <Reveal as="p" className="lsection-body lsection-body--center" delay={0.06}>
              Giải đáp mọi thắc mắc về kết nối bot, chính sách bảo mật và cách vận hành.
            </Reveal>

            <Reveal delay={0.1}>
              <LandingFaq />
            </Reveal>
          </div>
        </section>

        {/* CLOSING CTA BANNER */}
        <section className="lcta">
          <Reveal className="lcta__inner">
            <span className="lcta__glow" aria-hidden="true" />
            <div className="lcta__copy">
              <h2 className="lcta__title">Sẵn sàng bảo vệ cộng đồng của bạn?</h2>
              <p className="lcta__body">
                {isAuthenticated
                  ? "Quay lại bảng điều khiển để tiếp tục giám sát cộng đồng của bạn với AI 24/7."
                  : "Tham gia nhóm Discord/Telegram thử nghiệm hoặc đăng nhập để kết nối bot với máy chủ của bạn ngay hôm nay."}
              </p>
            </div>
            <div className="lcta__actions">
              <TransitionLink to={ctaTo} className="sk-btn sk-btn--lg">
                {ctaLabel}
                <ArrowRight size={16} weight="bold" />
              </TransitionLink>
              <a
                href={DISCORD_INVITE_URL}
                target="_blank"
                rel="noopener noreferrer"
                className="sk-btn sk-btn--quiet sk-btn--lg"
              >
                Vào Discord Test Bot ↗
              </a>
            </div>
          </Reveal>
        </section>
      </main>

      {/* FOOTER */}
      <footer className="lfooter">
        <div className="lfooter__inner">
          <div className="lfooter__brand-col">
            <a className="lnav__brand" href="#top">
              <span className="sk-mark" aria-hidden="true">
                ✦
              </span>
              {BRAND.name}
            </a>
            <p className="lfooter__tagline">
              Hệ thống AI Multi-Agent quản trị cộng đồng thông minh, an toàn và tự động 24/7.
            </p>
          </div>

          <div className="lfooter__links-group">
            <div className="lfooter__col">
              <h4>Trang & Tính năng</h4>
              <a href="#community-hub">Trải Nghiệm Bot Ngay</a>
              <a href="#features">Tính năng</a>
              <a href="#sandbox">Sandbox AI</a>
              <a href="#how-it-works">Cách hoạt động</a>
              <a href="#faq">Hỏi đáp</a>
            </div>

            <div className="lfooter__col">
              <h4>Kênh Thử Nghiệm</h4>
              <a
                href={DISCORD_INVITE_URL}
                target="_blank"
                rel="noopener noreferrer"
                className="lfooter__link-highlight"
              >
                <DiscordIcon3D size={18} />
                Discord Test Server
              </a>
              <a
                href={TELEGRAM_INVITE_URL}
                target="_blank"
                rel="noopener noreferrer"
                className="lfooter__link-highlight"
              >
                <TelegramIcon3D size={18} />
                Telegram Test Group
              </a>
              <a href={REPO_URL} target="_blank" rel="noreferrer">
                <GithubLogo size={16} weight="fill" />
                Mã nguồn GitHub
              </a>
            </div>
          </div>
        </div>

        <div className="lfooter__bottom">
          <div className="lshell">
            <p className="lfooter__copy-text">
              © {new Date().getFullYear()} {BRAND.name} - AI Community Manager. Bảo lưu mọi quyền.
            </p>
          </div>
        </div>
      </footer>
    </div>
  );
}
