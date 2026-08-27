import React, { useRef, useState } from "react";
import { motion, useMotionValue, useSpring, useTransform, useReducedMotion } from "motion/react";
import { ArrowUpRight, CheckCircle, Sparkle, Users, ShieldCheck, Lightning } from "@phosphor-icons/react";

/**
 * 3D Discord SVG Logo with multi-layer depth and glowing gradient
 */
export function DiscordIcon3D({ size = 48, className = "" }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 120 120"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
    >
      <defs>
        <linearGradient id="discord-grad" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#7289DA" />
          <stop offset="60%" stopColor="#5865F2" />
          <stop offset="100%" stopColor="#4752C4" />
        </linearGradient>
        <linearGradient id="discord-sheen" x1="20%" y1="0%" x2="80%" y2="100%">
          <stop offset="0%" stopColor="#FFFFFF" stopOpacity="0.4" />
          <stop offset="100%" stopColor="#FFFFFF" stopOpacity="0" />
        </linearGradient>
        <filter id="discord-glow" x="-20%" y="-20%" width="140%" height="140%">
          <feDropShadow dx="0" dy="8" stdDeviation="12" floodColor="#5865F2" floodOpacity="0.5" />
        </filter>
      </defs>
      {/* Background 3D pill */}
      <rect
        x="10"
        y="10"
        width="100"
        height="100"
        rx="28"
        fill="url(#discord-grad)"
        filter="url(#discord-glow)"
      />
      {/* Inner specular glare */}
      <rect
        x="11"
        y="11"
        width="98"
        height="98"
        rx="27"
        stroke="url(#discord-sheen)"
        strokeWidth="2"
        fill="none"
      />
      {/* Discord Clyde Mark */}
      <path
        d="M84.2 38.6C78.4 35.9 72.2 34 65.6 33C64.8 34.4 63.8 36.5 63.2 38C56.1 36.9 49.1 36.9 42.1 38C41.5 36.5 40.5 34.4 39.7 33C33.1 34 26.9 35.9 21.1 38.6C9.5 55.7 6.3 72.3 7.9 88.6C15.6 94.3 23 98.7 30.3 101C32.1 98.5 33.7 95.8 35.1 92.9C32.4 91.9 29.9 90.6 27.5 89C28.2 88.5 28.8 88 29.4 87.5C43.8 94.2 59.5 94.2 73.8 87.5C74.4 88 75.1 88.5 75.7 89C73.3 90.6 70.8 91.9 68.1 92.9C69.5 95.8 71.1 98.5 72.9 101C80.2 98.7 87.6 94.3 95.3 88.6C97.2 69.8 92.2 53.4 84.2 38.6ZM37.3 76.5C32.9 76.5 29.3 72.5 29.3 67.6C29.3 62.7 32.8 58.7 37.3 58.7C41.8 58.7 45.4 62.7 45.3 67.6C45.3 72.5 41.8 76.5 37.3 76.5ZM67.9 76.5C63.5 76.5 59.9 72.5 59.9 67.6C59.9 62.7 63.4 58.7 67.9 58.7C72.4 58.7 76 62.7 75.9 67.6C75.9 72.5 72.4 76.5 67.9 76.5Z"
        fill="#FFFFFF"
      />
    </svg>
  );
}

/**
 * 3D Telegram SVG Logo with multi-layer depth and glowing gradient
 */
export function TelegramIcon3D({ size = 48, className = "" }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 120 120"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
    >
      <defs>
        <linearGradient id="tg-grad" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#2AABEE" />
          <stop offset="60%" stopColor="#229ED9" />
          <stop offset="100%" stopColor="#1788BF" />
        </linearGradient>
        <linearGradient id="tg-sheen" x1="20%" y1="0%" x2="80%" y2="100%">
          <stop offset="0%" stopColor="#FFFFFF" stopOpacity="0.4" />
          <stop offset="100%" stopColor="#FFFFFF" stopOpacity="0" />
        </linearGradient>
        <filter id="tg-glow" x="-20%" y="-20%" width="140%" height="140%">
          <feDropShadow dx="0" dy="8" stdDeviation="12" floodColor="#229ED9" floodOpacity="0.5" />
        </filter>
      </defs>
      {/* Background 3D Circle/Squircle */}
      <rect
        x="10"
        y="10"
        width="100"
        height="100"
        rx="28"
        fill="url(#tg-grad)"
        filter="url(#tg-glow)"
      />
      {/* Inner specular glare */}
      <rect
        x="11"
        y="11"
        width="98"
        height="98"
        rx="27"
        stroke="url(#tg-sheen)"
        strokeWidth="2"
        fill="none"
      />
      {/* Telegram Paper Plane */}
      <path
        d="M26 58.5L88 33.5C90.8 32.3 93.3 34.2 92.4 38.2L81.8 88.2C81 92.1 78.5 93.1 75.2 91.2L59 79.3L51.2 86.8C50.3 87.7 49.6 88.5 47.7 88.5L48.8 72.8L77.4 46.9C78.6 45.8 77.2 45.2 75.5 46.3L40.1 68.6L24.8 63.8C21.5 62.8 21.4 60.5 26 58.5Z"
        fill="#FFFFFF"
      />
    </svg>
  );
}

/**
 * Interactive 3D Card with spring-driven tilt, mouse glare, and floating 3D layers
 */
export default function CommunityCard3D({
  platform = "discord",
  title,
  subtitle,
  description,
  url,
  badgeText = "Đang trực tuyến",
  features = [],
  ctaLabel = "Tham gia ngay",
  memberCount = "150+ thành viên",
  accentColor = "#5865F2",
}) {
  const cardRef = useRef(null);
  const reduce = useReducedMotion();
  const [isHovered, setIsHovered] = useState(false);
  const [isClicked, setIsClicked] = useState(false);

  // Mouse tilt motion values
  const mouseX = useMotionValue(0);
  const mouseY = useMotionValue(0);

  // Smooth springs for fluid physics
  const springX = useSpring(mouseX, { stiffness: 220, damping: 20 });
  const springY = useSpring(mouseY, { stiffness: 220, damping: 20 });

  // Map to 3D rotation degrees
  const rotateX = useTransform(springY, [-0.5, 0.5], [14, -14]);
  const rotateY = useTransform(springX, [-0.5, 0.5], [-14, 14]);

  // Glare position on the card
  const glareX = useTransform(springX, [-0.5, 0.5], [15, 85]);
  const glareY = useTransform(springY, [-0.5, 0.5], [15, 85]);

  const handleMouseMove = (e) => {
    if (reduce || !cardRef.current) return;
    const rect = cardRef.current.getBoundingClientRect();
    const x = (e.clientX - rect.left) / rect.width - 0.5;
    const y = (e.clientY - rect.top) / rect.height - 0.5;
    mouseX.set(x);
    mouseY.set(y);
  };

  const handleMouseEnter = () => {
    setIsHovered(true);
  };

  const handleMouseLeave = () => {
    setIsHovered(false);
    mouseX.set(0);
    mouseY.set(0);
  };

  const handleClick = (e) => {
    e.preventDefault();
    if (isClicked) return;
    setIsClicked(true);

    // Give user clear visual feedback with massive logo pop before opening invite link
    setTimeout(() => {
      window.open(url, "_blank", "noopener,noreferrer");
    }, 450);

    // Reset clicked state after 1.5s
    setTimeout(() => {
      setIsClicked(false);
    }, 1500);
  };

  const isDiscord = platform === "discord";

  return (
    <div
      className="card-3d-wrapper"
      style={{ perspective: "1200px" }}
      onMouseMove={handleMouseMove}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
    >
      <motion.a
        ref={cardRef}
        href={url}
        target="_blank"
        rel="noopener noreferrer"
        onClick={handleClick}
        className={`card-3d card-3d--${platform} ${isClicked ? "is-clicked" : ""}`}
        style={{
          transformStyle: "preserve-3d",
          rotateX: reduce ? 0 : rotateX,
          rotateY: reduce ? 0 : rotateY,
        }}
        whileHover={reduce ? {} : { scale: 1.025 }}
        whileTap={reduce ? {} : { scale: 0.98 }}
        transition={{ duration: 0.2 }}
        aria-label={`${title} - ${ctaLabel}`}
      >
        {/* Specular glare shine layer */}
        {!reduce && (
          <motion.div
            className="card-3d__glare"
            style={{
              background: useTransform(
                [glareX, glareY],
                ([gx, gy]) =>
                  `radial-gradient(circle 280px at ${gx}% ${gy}%, rgba(255, 255, 255, 0.18) 0%, rgba(255, 255, 255, 0.02) 50%, transparent 80%)`
              ),
              opacity: isHovered ? 1 : 0,
            }}
          />
        )}

        {/* Top Header: Badge & Status */}
        <div className="card-3d__header" style={{ transform: "translateZ(30px)" }}>
          <div className="card-3d__status">
            <span className="card-3d__pulse" />
            <span className="card-3d__status-text">{badgeText}</span>
          </div>
          <div className="card-3d__members">
            <Users size={14} weight="bold" />
            <span>{memberCount}</span>
          </div>
        </div>

        {/* Center: 3D Floating Vector Logo */}
        <div className="card-3d__hero" style={{ transform: "translateZ(45px)", position: "relative" }}>
          <motion.div
            className="card-3d__logo-box"
            style={{ position: "relative", zIndex: isClicked ? 60 : 2 }}
            animate={
              isClicked
                ? {
                    scale: [1, 2.35, 2.1],
                    y: -36,
                    rotateZ: isDiscord ? -10 : 10,
                    filter: isDiscord
                      ? "drop-shadow(0 24px 50px rgba(88, 101, 242, 0.85))"
                      : "drop-shadow(0 24px 50px rgba(38, 165, 228, 0.85))",
                  }
                : reduce
                ? {}
                : {
                    scale: isHovered ? 1.08 : 1,
                    y: isHovered ? -8 : [0, -6, 0],
                    rotateZ: isHovered ? (isDiscord ? -3 : 3) : 0,
                  }
            }
            transition={
              isClicked
                ? { type: "spring", stiffness: 380, damping: 12 }
                : isHovered
                ? { type: "spring", stiffness: 300, damping: 15 }
                : { repeat: Infinity, duration: 4, ease: "easeInOut" }
            }
          >
            {isDiscord ? <DiscordIcon3D size={72} /> : <TelegramIcon3D size={72} />}
          </motion.div>

          <div className="card-3d__headings">
            <h3 className="card-3d__title">{title}</h3>
            <span className="card-3d__subtitle">{subtitle}</span>
          </div>
        </div>

        {/* Description */}
        <p className="card-3d__desc" style={{ transform: "translateZ(25px)" }}>
          {description}
        </p>

        {/* Feature Checkpoints */}
        <div className="card-3d__features" style={{ transform: "translateZ(20px)" }}>
          {features.map((feat, idx) => (
            <div key={idx} className="card-3d__feature-item">
              <CheckCircle size={15} weight="fill" className="card-3d__check-icon" />
              <span>{feat}</span>
            </div>
          ))}
        </div>

        {/* Action Button Footer */}
        <div className="card-3d__footer" style={{ transform: "translateZ(35px)" }}>
          <span className={`card-3d__btn card-3d__btn--${platform} ${isClicked ? "is-clicked" : ""}`}>
            <span>{isClicked ? "Đang mở phòng chat..." : ctaLabel}</span>
            <ArrowUpRight
              size={16}
              weight="bold"
              className={`card-3d__arrow-icon ${isClicked ? "is-clicked-arrow" : ""}`}
            />
          </span>
        </div>
      </motion.a>
    </div>
  );
}
