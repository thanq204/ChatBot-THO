import { useEffect, useRef } from "react";
import { useReducedMotion } from "motion/react";
import "./sakura.css";

/**
 * Ambient sakura layer plus a cursor trail.
 *
 * Petals and idle sparkles run on CSS animations rather than Motion: negative
 * animation-delay means the field is already populated on first paint, and the
 * work stays off the main thread.
 *
 * The trail writes to the DOM directly through refs and the Web Animations API.
 * Pointer position is a continuous value, so putting it in React state would
 * re-render the page on every mouse move.
 *
 * Both layers disappear entirely under prefers-reduced-motion, and the trail
 * never arms on touch input.
 */

const PETAL_PATH = "M10 0.5C14.6 4.6 15.8 12 10 19.5C4.2 12 5.4 4.6 10 0.5Z";
const SPARK_PATH =
  "M12 0C12 6.6 17.4 12 24 12C17.4 12 12 17.4 12 24C12 17.4 6.6 12 0 12C6.6 12 12 6.6 12 0Z";

const PETALS = [
  { left: "2%", size: 15, duration: 27, delay: -3, drift: "34px", tilt: 12 },
  { left: "8%", size: 11, duration: 34, delay: -19, drift: "-26px", tilt: -18 },
  { left: "14%", size: 18, duration: 23, delay: -8, drift: "42px", tilt: 26 },
  { left: "20%", size: 12, duration: 38, delay: -26, drift: "-38px", tilt: -8 },
  { left: "26%", size: 16, duration: 29, delay: -12, drift: "28px", tilt: 20 },
  { left: "32%", size: 10, duration: 33, delay: -31, drift: "-22px", tilt: -30 },
  { left: "38%", size: 19, duration: 25, delay: -6, drift: "46px", tilt: 8 },
  { left: "44%", size: 13, duration: 36, delay: -22, drift: "-30px", tilt: -14 },
  { left: "50%", size: 15, duration: 30, delay: -15, drift: "24px", tilt: 34 },
  { left: "56%", size: 11, duration: 40, delay: -35, drift: "-44px", tilt: -22 },
  { left: "62%", size: 17, duration: 26, delay: -10, drift: "36px", tilt: 16 },
  { left: "68%", size: 13, duration: 32, delay: -28, drift: "-28px", tilt: -26 },
  { left: "74%", size: 20, duration: 24, delay: -4, drift: "40px", tilt: 6 },
  { left: "80%", size: 12, duration: 37, delay: -20, drift: "-34px", tilt: -12 },
  { left: "86%", size: 16, duration: 28, delay: -13, drift: "30px", tilt: 24 },
  { left: "91%", size: 10, duration: 35, delay: -33, drift: "-24px", tilt: -20 },
  { left: "95%", size: 18, duration: 31, delay: -17, drift: "38px", tilt: 10 },
  { left: "98%", size: 13, duration: 39, delay: -24, drift: "-40px", tilt: -28 },
];

const SPARKLES = [
  { left: "12%", top: "22%", size: 12, duration: 5.5, delay: 0 },
  { left: "27%", top: "58%", size: 10, duration: 7.5, delay: 2.1 },
  { left: "38%", top: "12%", size: 9, duration: 6.5, delay: 1.4 },
  { left: "51%", top: "72%", size: 13, duration: 6.8, delay: 4.2 },
  { left: "57%", top: "34%", size: 14, duration: 7, delay: 2.6 },
  { left: "71%", top: "16%", size: 10, duration: 6, delay: 0.8 },
  { left: "84%", top: "44%", size: 11, duration: 8, delay: 3.4 },
  { left: "93%", top: "68%", size: 12, duration: 6.2, delay: 5 },
];

/** Sparkles are recycled round robin, so the DOM never grows past this. */
const TRAIL_POOL = 16;
/** Minimum cursor travel between emissions, in px. Keeps the trail sparse. */
const TRAIL_STEP = 26;

function SparkleTrail() {
  const reduce = useReducedMotion();
  const nodesRef = useRef([]);
  const animsRef = useRef([]);

  useEffect(() => {
    if (reduce) return undefined;
    // Touch and coarse pointers get nothing: there is no cursor to trail.
    if (!window.matchMedia("(hover: hover) and (pointer: fine)").matches) return undefined;

    let cursor = 0;
    let lastX = -999;
    let lastY = -999;
    let frame = 0;
    let pending = null;

    const emit = (x, y) => {
      const node = nodesRef.current[cursor];
      if (!node) return;
      const slot = cursor;
      cursor = (cursor + 1) % TRAIL_POOL;

      node.style.left = `${x}px`;
      node.style.top = `${y}px`;

      const spin = (slot * 47) % 360;
      animsRef.current[slot]?.cancel();
      animsRef.current[slot] = node.animate(
        [
          { opacity: 0, transform: `scale(0.25) rotate(${spin}deg)` },
          { opacity: 0.9, transform: `scale(1) rotate(${spin + 40}deg)`, offset: 0.28 },
          { opacity: 0, transform: `scale(0.45) translateY(-22px) rotate(${spin + 110}deg)` },
        ],
        { duration: 760, easing: "cubic-bezier(0.16, 1, 0.3, 1)", fill: "forwards" },
      );
    };

    const flush = () => {
      frame = 0;
      if (!pending) return;
      const { x, y } = pending;
      pending = null;
      if (Math.hypot(x - lastX, y - lastY) < TRAIL_STEP) return;
      lastX = x;
      lastY = y;
      emit(x, y);
    };

    const handleMove = (event) => {
      // Coalesce to one emission per frame no matter how fast the mouse moves.
      pending = { x: event.clientX, y: event.clientY };
      if (!frame) frame = window.requestAnimationFrame(flush);
    };

    window.addEventListener("pointermove", handleMove, { passive: true });
    return () => {
      window.removeEventListener("pointermove", handleMove);
      if (frame) window.cancelAnimationFrame(frame);
      animsRef.current.forEach((animation) => animation?.cancel());
    };
  }, [reduce]);

  if (reduce) return null;

  return (
    <div className="sakura-trail" aria-hidden="true">
      {Array.from({ length: TRAIL_POOL }, (_, i) => (
        <span
          key={`trail-${i}`}
          ref={(node) => {
            nodesRef.current[i] = node;
          }}
          className={`sakura-trail__bit${i % 3 === 0 ? " sakura-trail__bit--petal" : ""}`}
          style={{ "--sk-size": `${10 + (i % 4) * 3}px` }}
        >
          <svg viewBox={i % 3 === 0 ? "0 0 20 20" : "0 0 24 24"} fill="none">
            <path d={i % 3 === 0 ? PETAL_PATH : SPARK_PATH} fill="currentColor" />
          </svg>
        </span>
      ))}
    </div>
  );
}

export default function SakuraField({ variant = "block" }) {
  return (
    <>
      <div className={`sakura sakura--${variant}`} aria-hidden="true">
        {PETALS.map((petal, i) => (
          <span
            key={`petal-${i}`}
            className="sakura__petal"
            style={{
              left: petal.left,
              "--sk-size": `${petal.size}px`,
              "--sk-dur": `${petal.duration}s`,
              "--sk-delay": `${petal.delay}s`,
              "--sk-drift": petal.drift,
              "--sk-tilt": `${petal.tilt}deg`,
            }}
          >
            <svg viewBox="0 0 20 20" fill="none">
              <path d={PETAL_PATH} fill="currentColor" />
            </svg>
          </span>
        ))}

        {SPARKLES.map((sparkle, i) => (
          <span
            key={`sparkle-${i}`}
            className="sakura__sparkle"
            style={{
              left: sparkle.left,
              top: sparkle.top,
              "--sk-size": `${sparkle.size}px`,
              "--sk-dur": `${sparkle.duration}s`,
              "--sk-delay": `${sparkle.delay}s`,
            }}
          >
            <svg viewBox="0 0 24 24" fill="none">
              <path d={SPARK_PATH} fill="currentColor" />
            </svg>
          </span>
        ))}
      </div>

      <SparkleTrail />
    </>
  );
}
