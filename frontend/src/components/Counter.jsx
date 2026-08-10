import { useEffect, useRef } from "react";
import { animate, useMotionValue, useReducedMotion } from "motion/react";
import { formatNumber } from "../lib/format.js";

/** Animates a number count-up without touching React state on every frame. */
export default function Counter({ value, duration = 1.1 }) {
  const spanRef = useRef(null);
  const motionValue = useMotionValue(0);
  const reduceMotion = useReducedMotion();

  useEffect(() => {
    if (spanRef.current) spanRef.current.textContent = formatNumber(reduceMotion ? value : 0);

    if (reduceMotion) {
      motionValue.set(value);
      if (spanRef.current) spanRef.current.textContent = formatNumber(value);
      return;
    }

    const controls = animate(motionValue, value, {
      duration,
      ease: [0.16, 1, 0.3, 1],
      onUpdate: (latest) => {
        if (spanRef.current) spanRef.current.textContent = formatNumber(latest);
      },
    });
    return () => controls.stop();
  }, [value, duration, motionValue, reduceMotion]);

  return <span ref={spanRef} aria-label={formatNumber(value)}>0</span>;
}
