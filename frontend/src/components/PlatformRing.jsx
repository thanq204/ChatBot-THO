import { motion, useReducedMotion } from "motion/react";
import { DiscordLogo, TelegramLogo, ChatsCircle } from "@phosphor-icons/react";
import { platformLabel } from "../lib/taxonomy.js";

const PLATFORM_ICONS = {
  discord: DiscordLogo,
  telegram: TelegramLogo,
};

const RADIUS = 30;
const CIRCUMFERENCE = 2 * Math.PI * RADIUS;

function statusMeta(status) {
  if (status.connected) return { color: "var(--sev-low)", text: "Đang hoạt động" };
  if (status.configured) return { color: "var(--sev-medium)", text: "Chờ kết nối" };
  return { color: "var(--text-muted)", text: "Chưa cấu hình" };
}

export default function PlatformRing({ status, delay = 0 }) {
  const reduceMotion = useReducedMotion();
  const Icon = PLATFORM_ICONS[status.platform] ?? ChatsCircle;
  const { color, text } = statusMeta(status);

  return (
    <div className="platform-ring">
      <svg viewBox="0 0 68 68" width={68} height={68}>
        <circle cx={34} cy={34} r={RADIUS} className="platform-ring__track" />
        <motion.circle
          cx={34}
          cy={34}
          r={RADIUS}
          stroke={color}
          strokeWidth={4}
          strokeLinecap="round"
          fill="none"
          transform="rotate(-90 34 34)"
          strokeDasharray={CIRCUMFERENCE}
          initial={{ strokeDashoffset: reduceMotion ? 0 : CIRCUMFERENCE }}
          whileInView={{ strokeDashoffset: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 1, delay, ease: [0.16, 1, 0.3, 1] }}
        />
        <foreignObject x={17} y={17} width={34} height={34}>
          <div className="platform-ring__icon">
            <Icon size={26} weight="fill" />
          </div>
        </foreignObject>
      </svg>
      <span className="platform-ring__label">{platformLabel(status.platform)}</span>
      <span
        className="platform-ring__status"
        style={{ color, display: "inline-flex", alignItems: "center", gap: 5, justifyContent: "center" }}
      >
        {status.connected && <span className="live-pulse" />}
        {text}
      </span>
    </div>
  );
}
