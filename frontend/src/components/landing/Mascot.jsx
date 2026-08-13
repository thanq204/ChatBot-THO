import "./mascot.css";

/**
 * Small abstract AI assistant. Built from primitives (rounded rects, ovals, an
 * arc) rather than drawn illustration, and kept to a supporting size so it
 * never turns the page into a cartoon.
 *
 * `variant` only exists to keep gradient ids unique when two are on one page.
 */
export default function Mascot({ size = 64, variant = "a", className = "" }) {
  const bodyId = `mascot-body-${variant}`;
  const visorId = `mascot-visor-${variant}`;

  return (
    <span className={`mascot ${className}`} style={{ width: size, height: size }} aria-hidden="true">
      <svg viewBox="0 0 64 64" fill="none">
        <defs>
          <linearGradient id={bodyId} x1="12" y1="14" x2="52" y2="58" gradientUnits="userSpaceOnUse">
            <stop stopColor="var(--sk-pink-mist)" />
            <stop offset="1" stopColor="var(--sk-lavender-mist)" />
          </linearGradient>
          <linearGradient id={visorId} x1="18" y1="26" x2="46" y2="44" gradientUnits="userSpaceOnUse">
            <stop stopColor="var(--sk-pink-wash)" />
            <stop offset="1" stopColor="var(--sk-lavender)" />
          </linearGradient>
        </defs>

        {/* Antenna */}
        <path d="M32 15V8" stroke="var(--sk-pink-soft)" strokeWidth="2.4" strokeLinecap="round" />
        <path
          d="M32 0.5C32 3.6 34.4 6 37.5 6C34.4 6 32 8.4 32 11.5C32 8.4 29.6 6 26.5 6C29.6 6 32 3.6 32 0.5Z"
          fill="var(--sk-accent)"
        />

        {/* Side panels */}
        <rect x="4" y="30" width="7" height="14" rx="3.5" fill="var(--sk-pink-wash)" />
        <rect x="53" y="30" width="7" height="14" rx="3.5" fill="var(--sk-pink-wash)" />

        {/* Head */}
        <rect
          x="12"
          y="15"
          width="40"
          height="38"
          rx="14"
          fill={`url(#${bodyId})`}
          stroke="var(--sk-pink-soft)"
          strokeWidth="2"
        />

        {/* Visor */}
        <rect x="18.5" y="24" width="27" height="19" rx="9.5" fill={`url(#${visorId})`} opacity="0.55" />

        {/* Eyes */}
        <rect x="24" y="30" width="4.6" height="7.5" rx="2.3" fill="var(--sk-eye)" />
        <rect x="35.4" y="30" width="4.6" height="7.5" rx="2.3" fill="var(--sk-eye)" />

        {/* Smile */}
        <path
          d="M28.5 42.5C30 44.2 34 44.2 35.5 42.5"
          stroke="var(--sk-eye)"
          strokeWidth="1.9"
          strokeLinecap="round"
          opacity="0.75"
        />

        {/* Blush */}
        <ellipse cx="20.5" cy="39.5" rx="3.1" ry="2" fill="var(--sk-pink-soft)" opacity="0.5" />
        <ellipse cx="43.5" cy="39.5" rx="3.1" ry="2" fill="var(--sk-pink-soft)" opacity="0.5" />
      </svg>
    </span>
  );
}
