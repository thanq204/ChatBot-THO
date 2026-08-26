import { motion, useMotionValue, useReducedMotion, useSpring, useTransform } from "motion/react";
import {
  ArrowRight,
  BookOpen,
  Broadcast,
  ChartLine,
  Flask,
  GithubLogo,
  Moon,
  Notebook,
  Scales,
  Sun,
} from "@phosphor-icons/react";
import AgentFlow from "../components/landing/AgentFlow.jsx";
import SakuraField from "../components/landing/SakuraField.jsx";
import { TransitionLink } from "../transitions/PageTransition.jsx";
import { useAuth } from "../auth/AuthProvider.jsx";
import { useTheme } from "../theme/ThemeProvider.jsx";
import "../landing.css";
import { BRAND } from "../lib/brand.js";
import ThoMascot from "../components/ThoMascot.jsx";

const REPO_URL = "https://github.com/AI20K-Build-Phase-Cohort-3/P-232";

/** Shared scroll entrance so every section enters on the same rhythm. */
function Reveal({ children, delay = 0, className, as = "div" }) {
  const reduce = useReducedMotion();
  const Component = motion[as];
  return (
    <Component
      className={className}
      initial={reduce ? false : { opacity: 0, y: 22 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, amount: 0.2 }}
      transition={{ duration: 0.6, delay, ease: [0.16, 1, 0.3, 1] }}
    >
      {children}
    </Component>
  );
}

const PAINS = [
  {
    title: "Vi phạm không đợi giờ hành chính",
    body: "Tin nhắn xấu lúc hai giờ sáng vẫn nằm nguyên đó tới khi có người trực.",
  },
  {
    title: "Mỗi nền tảng một cửa sổ riêng",
    body: "Discord một tab, Telegram một tab. Không ai giữ được bức tranh tổng thể.",
  },
  {
    title: "Cùng một câu hỏi, trả lời lại từ đầu",
    body: "Thành viên mới hỏi lặp những điều đã được giải đáp hàng chục lần.",
  },
  {
    title: "Quyết định gỡ bài không để lại dấu vết",
    body: "Khi có tranh cãi, không ai nhớ nổi vì sao tin nhắn đó bị xoá.",
  },
];

/** backend/agents/moderation_graph.py, in execution order. */
const PIPELINE = [
  {
    name: "Ngữ cảnh",
    body: "Agent đọc lại các tin trước đó trong kênh để biết câu này là đùa giỡn hay công kích thật.",
  },
  {
    name: "Chính sách",
    body: "Tin nhắn được đối chiếu với bộ quy tắc riêng của cộng đồng bạn, không phải danh sách cấm dùng chung.",
  },
  {
    name: "Rủi ro",
    body: "Agent chấm mức nghiêm trọng từ thấp tới nghiêm trọng, kèm lý do cho từng mức.",
  },
  {
    name: "Cổng an toàn",
    body: "Trường hợp vượt ngưỡng an toàn được tách riêng và không bao giờ tự động xử lý.",
  },
  {
    name: "Quyết định",
    body: "Hành động cuối được chốt, kiểm tra định dạng, rồi ghi vào nhật ký cùng toàn bộ đường đi.",
  },
];

const PLATFORMS_LIVE = [
  { name: "Discord", slug: "discord", color: "5865F2" },
  { name: "Telegram", slug: "telegram", color: "26A5E4" },
];

const PLATFORMS_PLANNED = [
  { name: "Zalo", slug: "zalo", color: "0068FF" },
  { name: "Messenger", slug: "messenger", color: "00B2FF" },
];

export default function LandingPage() {
  const { theme, toggleTheme } = useTheme();
  const { isAuthenticated } = useAuth();
  const reduce = useReducedMotion();
  const ThemeIcon = theme === "dark" ? Sun : Moon;
  const ctaTo = isAuthenticated ? "/tong-quan" : "/login";
  const ctaLabel = isAuthenticated ? "Vào bảng điều khiển" : "Đăng nhập";

  /* Blob parallax. Motion values stay outside the render cycle, so moving the
     pointer never re-renders the page. */
  const pointerX = useMotionValue(0);
  const pointerY = useMotionValue(0);
  const driftX = useSpring(pointerX, { stiffness: 38, damping: 22, mass: 0.6 });
  const driftY = useSpring(pointerY, { stiffness: 38, damping: 22, mass: 0.6 });
  const pinkX = useTransform(driftX, [-1, 1], [-30, 30]);
  const pinkY = useTransform(driftY, [-1, 1], [-20, 20]);
  const lavX = useTransform(driftX, [-1, 1], [22, -22]);
  const lavY = useTransform(driftY, [-1, 1], [16, -16]);

  const trackPointer = (event) => {
    if (reduce) return;
    const bounds = event.currentTarget.getBoundingClientRect();
    pointerX.set((event.clientX - bounds.left) / bounds.width * 2 - 1);
    pointerY.set((event.clientY - bounds.top) / bounds.height * 2 - 1);
  };

  return (
    <div className="landing">
      <SakuraField variant="page" />
      <header className="lnav">
        <div className="lnav__inner">
          <a className="lnav__brand" href="#top">
            <span className="sk-mark" aria-hidden="true">
              ✦
            </span>
            {BRAND.name}
          </a>

          <nav className="lnav__links" aria-label="Nội dung trang">
            <a href="#features">Features</a>
            <a href="#how-it-works">How it works</a>
            <a href="#platforms">Platforms</a>
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
        <section className="lhero" onPointerMove={trackPointer}>
          <div className="lhero__blobs" aria-hidden="true">
            {/* Outer span carries the pointer parallax, inner carries the idle
                CSS drift. Sharing one element would let the keyframes win. */}
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
              <motion.span
                className="lhero__eyebrow"
                initial={reduce ? false : { opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ duration: 0.5 }}
              >
                <span className="sk-mark" aria-hidden="true">
                  ✦
                </span>
                {BRAND.name} · {BRAND.tagline}
              </motion.span>

              <motion.h1
                className="lhero__title"
                initial={reduce ? false : { opacity: 0, y: 26 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.7, delay: 0.06, ease: [0.16, 1, 0.3, 1] }}
              >
                Quản lý cộng đồng thông minh với AI Agent{" "}
                <span className="sk-mark" aria-hidden="true">
                  ✦
                </span>
              </motion.h1>

              <motion.p
                className="lhero__sub"
                initial={reduce ? false : { opacity: 0, y: 18 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.7, delay: 0.16, ease: [0.16, 1, 0.3, 1] }}
              >
                Tự động giám sát, phản hồi và quản lý cộng đồng trên nhiều nền tảng từ một nơi.
              </motion.p>

              <motion.div
                className="lhero__cta"
                initial={reduce ? false : { opacity: 0, y: 14 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.7, delay: 0.26, ease: [0.16, 1, 0.3, 1] }}
              >
                <TransitionLink to={ctaTo} className="sk-btn sk-btn--lg">
                  {ctaLabel}
                  <ArrowRight size={16} weight="bold" />
                </TransitionLink>
                <a href="#how-it-works" className="sk-btn sk-btn--quiet sk-btn--lg">
                  Xem cách hoạt động
                </a>
              </motion.div>
            </div>

            <motion.div
              className="lhero__visual"
              initial={reduce ? false : { opacity: 0, y: 30 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.8, delay: 0.2, ease: [0.16, 1, 0.3, 1] }}
            >
              <ThoMascot height={78} className="lhero__mascot" />
              <AgentFlow />
            </motion.div>
          </div>
        </section>

        <section className="lpain">
          <div className="lshell">
            <Reveal as="h2" className="lsection-title">
              Cộng đồng lớn nhanh hơn đội ngũ trực
            </Reveal>
            <Reveal as="p" className="lsection-body" delay={0.06}>
              Bốn việc lặp lại mỗi ngày, và không việc nào chờ được tới ca làm tiếp theo.
            </Reveal>

            <div className="lpain__grid">
              {PAINS.map((pain, i) => (
                <Reveal key={pain.title} className="lpain__item" delay={0.06 * i}>
                  <h3>{pain.title}</h3>
                  <p>{pain.body}</p>
                </Reveal>
              ))}
            </div>
          </div>
        </section>

        <section className="lbento" id="features">
          <div className="lshell">
            <Reveal as="h2" className="lsection-title">
              Những gì agent làm thay bạn
            </Reveal>

            <div className="lbento__grid">
              <Reveal className="lcell lcell--mascot">
                <div className="lcell__stage" aria-hidden="true">
                  <ThoMascot height={112} />
                </div>
                <div className="lcell__body">
                  <Broadcast size={19} weight="fill" />
                  <h3>Giám sát đa nền tảng</h3>
                  <p>Kéo tin nhắn thật từ Discord và Telegram theo lô, chuẩn hoá về một hàng đợi duy nhất.</p>
                </div>
              </Reveal>

              <Reveal className="lcell lcell--ink" delay={0.05}>
                <div className="lcell__body">
                  <Scales size={19} weight="fill" />
                  <h3>Chính sách do bạn viết</h3>
                  <p>Thêm, sửa hoặc gỡ quy tắc bất cứ lúc nào. Agent áp dụng ngay ở lượt phân tích kế tiếp.</p>
                </div>
              </Reveal>

              <Reveal className="lcell lcell--pattern" delay={0.09}>
                <div className="lcell__body">
                  <BookOpen size={19} weight="fill" />
                  <h3>Trả lời FAQ tự động</h3>
                  <p>Nạp tài liệu vào kho tri thức, agent trả lời câu hỏi lặp và đề xuất FAQ mới cho bạn duyệt.</p>
                </div>
              </Reveal>

              <Reveal className="lcell" delay={0.05}>
                <div className="lcell__body">
                  <Notebook size={19} weight="fill" />
                  <h3>Nhật ký truy vết</h3>
                  <p>Mỗi quyết định lưu lại tin nhắn gốc, quy tắc đã khớp và các bước agent đã đi qua.</p>
                </div>
              </Reveal>

              <Reveal className="lcell" delay={0.09}>
                <div className="lcell__body">
                  <ChartLine size={19} weight="fill" />
                  <h3>Sức khoẻ cộng đồng</h3>
                  <p>Theo dõi xu hướng vi phạm và số sự cố đang mở theo cửa sổ thời gian bạn chọn.</p>
                </div>
              </Reveal>

              <Reveal className="lcell lcell--wide" delay={0.05}>
                <div className="lcell__body">
                  <Flask size={19} weight="fill" />
                  <h3>Khu thử nghiệm trước khi bật thật</h3>
                  <p>
                    Dán thử một tin nhắn và xem agent suy luận từng bước, trước khi cho nó chạm vào cộng đồng
                    thật.
                  </p>
                </div>
              </Reveal>
            </div>
          </div>
        </section>

        <section className="lflow" id="how-it-works">
          <div className="lshell">
            <Reveal as="h2" className="lsection-title">
              Mỗi tin nhắn đi qua năm agent
            </Reveal>
            <Reveal as="p" className="lsection-body" delay={0.06}>
              Cùng một chuỗi cho mọi tin nhắn. Bạn luôn xem lại được nó dừng ở đâu và vì sao.
            </Reveal>

            <ol className="lflow__rail">
              {PIPELINE.map((stage, i) => (
                <Reveal as="li" key={stage.name} className="lflow__stage" delay={0.05 * i}>
                  <span className="lflow__marker" aria-hidden="true" />
                  <h3 className="lflow__name">{stage.name}</h3>
                  <p className="lflow__body">{stage.body}</p>
                </Reveal>
              ))}
            </ol>
          </div>
        </section>

        <section className="lplatforms" id="platforms">
          <div className="lshell lshell--center">
            <Reveal as="h2" className="lsection-title lsection-title--center">
              Nối kênh, agent bắt đầu đọc
            </Reveal>
            <Reveal as="p" className="lsection-body lsection-body--center" delay={0.06}>
              Discord và Telegram đọc được dữ liệu thật ngay hôm nay.
            </Reveal>

            <Reveal className="lplatforms__row" delay={0.12}>
              {PLATFORMS_LIVE.map((platform) => (
                <img
                  key={platform.slug}
                  className="lplatforms__logo"
                  src={`https://cdn.simpleicons.org/${platform.slug}/${platform.color}`}
                  alt={platform.name}
                  width="36"
                  height="36"
                  loading="lazy"
                />
              ))}
              <span className="lplatforms__divider" aria-hidden="true" />
              {PLATFORMS_PLANNED.map((platform) => (
                <img
                  key={platform.slug}
                  className="lplatforms__logo lplatforms__logo--planned"
                  src={`https://cdn.simpleicons.org/${platform.slug}/${platform.color}`}
                  alt={platform.name}
                  width="36"
                  height="36"
                  loading="lazy"
                />
              ))}
            </Reveal>

            <Reveal as="p" className="lplatforms__note" delay={0.18}>
              Zalo và Messenger đã có sẵn lớp kết nối, chờ bạn cấp credentials để bật.
            </Reveal>
          </div>
        </section>

        <section className="lcta">
          <Reveal className="lcta__inner">
            <span className="lcta__glow" aria-hidden="true" />
            <div className="lcta__copy">
              <h2 className="lcta__title">Bắt đầu với cộng đồng của bạn</h2>
              <p className="lcta__body">
                {isAuthenticated
                  ? "Quay lại bảng điều khiển để tiếp tục theo dõi cộng đồng của bạn."
                  : "Đăng nhập để nối kênh đầu tiên và xem agent chạy trên dữ liệu thật."}
              </p>
            </div>
            <TransitionLink to={ctaTo} className="sk-btn sk-btn--lg">
              {ctaLabel}
              <ArrowRight size={16} weight="bold" />
            </TransitionLink>
          </Reveal>
        </section>
      </main>

      <footer className="lfooter">
        <div className="lfooter__inner">
          <a className="lnav__brand" href="#top">
            <span className="sk-mark" aria-hidden="true">
              ✦
            </span>
            {BRAND.name}
          </a>
          <nav className="lfooter__links" aria-label="Liên kết chân trang">
            <a href="#features">Features</a>
            <a href="#how-it-works">How it works</a>
            <a href="#platforms">Platforms</a>
            <a href={REPO_URL} target="_blank" rel="noreferrer">
              <GithubLogo size={15} weight="fill" />
              GitHub
            </a>
          </nav>
        </div>
      </footer>
    </div>
  );
}
