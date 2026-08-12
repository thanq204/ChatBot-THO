import { createContext, useCallback, useContext, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import "./transition.css";

/**
 * Pink portal transition between the landing page and /login.
 *
 * A soft disc grows out of the exact point that was clicked until it covers the
 * viewport. The route swaps while the screen is fully covered, then the disc
 * fades away to reveal the new page underneath. Total cost is 720ms, and only
 * transform and opacity animate.
 *
 * Reduced motion skips the portal and navigates immediately.
 */

const PageTransitionContext = createContext(null);

/** Base diameter of the unscaled disc, in px. Scale is derived from this. */
const DISC = 100;
const EXPAND_S = 0.38;
const FADE_S = 0.34;

const SPARKS = [
  { left: "18%", top: "26%", size: 16, delay: 0.02 },
  { left: "72%", top: "18%", size: 12, delay: 0.1 },
  { left: "34%", top: "68%", size: 20, delay: 0.06 },
  { left: "84%", top: "58%", size: 14, delay: 0.14 },
  { left: "54%", top: "38%", size: 11, delay: 0.18 },
  { left: "10%", top: "74%", size: 13, delay: 0.12 },
];

export function PageTransitionProvider({ children }) {
  const navigate = useNavigate();
  const reduce = useReducedMotion();
  const busy = useRef(false);
  const [phase, setPhase] = useState("idle"); // idle -> expanding -> fading
  const [portal, setPortal] = useState({ x: 0, y: 0, scale: 1 });
  const [target, setTarget] = useState(null);

  const transitionTo = useCallback(
    (to, origin) => {
      if (reduce) {
        navigate(to);
        window.scrollTo(0, 0);
        return;
      }
      if (busy.current) return; // a second click must not queue another portal
      busy.current = true;

      const x = origin?.x ?? window.innerWidth / 2;
      const y = origin?.y ?? window.innerHeight / 2;
      // Reach the furthest corner from the click point, then a little past it.
      const reach = Math.hypot(
        Math.max(x, window.innerWidth - x),
        Math.max(y, window.innerHeight - y),
      );

      setPortal({ x, y, scale: (reach * 2.1) / DISC });
      setTarget(to);
      setPhase("expanding");
    },
    [navigate, reduce],
  );

  const handleAnimationComplete = () => {
    if (phase === "expanding") {
      if (target) {
        navigate(target);
        window.scrollTo(0, 0);
      }
      setTarget(null);
      setPhase("fading");
      return;
    }
    if (phase === "fading") {
      setPhase("idle");
      busy.current = false;
    }
  };

  return (
    <PageTransitionContext.Provider value={{ transitionTo, phase }}>
      <div className={`pt-stage${phase === "expanding" ? " pt-stage--leaving" : ""}`}>{children}</div>

      <AnimatePresence>
        {phase !== "idle" && (
          <div className="pt-portal" key="pt-portal" aria-hidden="true">
            <motion.span
              className="pt-portal__disc"
              style={{ left: portal.x - DISC / 2, top: portal.y - DISC / 2 }}
              initial={{ scale: 0, opacity: 1 }}
              animate={{ scale: portal.scale, opacity: phase === "expanding" ? 1 : 0 }}
              transition={
                phase === "expanding"
                  ? { duration: EXPAND_S, ease: [0.4, 0, 0.2, 1] }
                  : { duration: FADE_S, ease: "easeOut" }
              }
              onAnimationComplete={handleAnimationComplete}
            />

            {SPARKS.map((spark, i) => (
              <motion.span
                key={`spark-${i}`}
                className="pt-portal__spark"
                style={{ left: spark.left, top: spark.top, width: spark.size, height: spark.size }}
                initial={{ opacity: 0, scale: 0.4, rotate: -25 }}
                animate={{
                  opacity: phase === "expanding" ? [0, 0.9, 0.5] : 0,
                  scale: phase === "expanding" ? 1 : 0.6,
                  rotate: 0,
                }}
                transition={{ duration: 0.5, delay: spark.delay, ease: "easeOut" }}
              >
                <svg viewBox="0 0 24 24" fill="none">
                  <path
                    d="M12 0C12 6.6 17.4 12 24 12C17.4 12 12 17.4 12 24C12 17.4 6.6 12 0 12C6.6 12 12 6.6 12 0Z"
                    fill="currentColor"
                  />
                </svg>
              </motion.span>
            ))}
          </div>
        )}
      </AnimatePresence>
    </PageTransitionContext.Provider>
  );
}

export function usePageTransition() {
  const context = useContext(PageTransitionContext);
  if (!context) throw new Error("usePageTransition must be used inside PageTransitionProvider");
  return context;
}

/**
 * Renders a real anchor so keyboard activation, focus order and modifier-clicks
 * keep working. Only a plain left click is intercepted for the portal.
 */
export function TransitionLink({ to, className, children, ...rest }) {
  const { transitionTo } = usePageTransition();

  const handleClick = (event) => {
    if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey || event.button !== 0) return;
    event.preventDefault();

    // Keyboard activation reports 0,0. Fall back to the middle of the control.
    const rect = event.currentTarget.getBoundingClientRect();
    const origin = {
      x: event.clientX || rect.left + rect.width / 2,
      y: event.clientY || rect.top + rect.height / 2,
    };
    transitionTo(to, origin);
  };

  return (
    <a href={to} className={className} onClick={handleClick} {...rest}>
      {children}
    </a>
  );
}
