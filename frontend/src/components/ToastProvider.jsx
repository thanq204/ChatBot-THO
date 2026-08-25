import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { CheckCircle, Info, WarningCircle, X } from "@phosphor-icons/react";

/**
 * Transient confirmation for actions whose result is otherwise invisible.
 *
 * Deleting an account made the row vanish and said nothing — indistinguishable
 * from a filter quietly re-running. Errors had it worse: they were written into
 * whatever panel happened to be nearby, often below the fold.
 *
 * Errors do not auto-dismiss. Something went wrong is not a message to take
 * away while the operator is still reading it.
 */
const ToastContext = createContext(null);

const ICONS = { success: CheckCircle, error: WarningCircle, info: Info };
const DEFAULT_DURATION = 4000;

let nextId = 0;

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([]);
  const timers = useRef(new Map());
  const reduceMotion = useReducedMotion();

  const dismiss = useCallback((id) => {
    setToasts((current) => current.filter((toast) => toast.id !== id));
    const timer = timers.current.get(id);
    if (timer) {
      window.clearTimeout(timer);
      timers.current.delete(id);
    }
  }, []);

  const push = useCallback(
    (message, tone = "info", duration) => {
      if (!message) return undefined;
      const id = ++nextId;
      setToasts((current) => [...current, { id, message, tone }]);

      const ms = duration ?? (tone === "error" ? 0 : DEFAULT_DURATION);
      if (ms > 0) {
        timers.current.set(id, window.setTimeout(() => dismiss(id), ms));
      }
      return id;
    },
    [dismiss],
  );

  // Clear every pending timer if the provider goes away mid-flight.
  useEffect(() => {
    const pending = timers.current;
    return () => {
      for (const timer of pending.values()) window.clearTimeout(timer);
      pending.clear();
    };
  }, []);

  const value = useMemo(
    () => ({
      toast: push,
      success: (message, duration) => push(message, "success", duration),
      error: (message, duration) => push(message, "error", duration),
      info: (message, duration) => push(message, "info", duration),
      dismiss,
    }),
    [push, dismiss],
  );

  return (
    <ToastContext.Provider value={value}>
      {children}
      {createPortal(
        // aria-live so a screen reader announces the outcome; polite rather
        // than assertive, so it waits for the current utterance to finish.
        <div className="toast-stack" role="status" aria-live="polite">
          <AnimatePresence initial={false}>
            {toasts.map(({ id, message, tone }) => {
              const Icon = ICONS[tone] ?? Info;
              return (
                <motion.div
                  key={id}
                  className={`toast toast--${tone}`}
                  initial={reduceMotion ? { opacity: 0 } : { opacity: 0, y: 12, scale: 0.97 }}
                  animate={{ opacity: 1, y: 0, scale: 1 }}
                  exit={reduceMotion ? { opacity: 0 } : { opacity: 0, y: 8, scale: 0.97 }}
                  transition={{ duration: 0.22, ease: [0.16, 1, 0.3, 1] }}
                  layout={!reduceMotion}
                >
                  <Icon size={17} weight="fill" className="toast__icon" />
                  <span className="toast__message">{message}</span>
                  <button type="button" className="toast__close" onClick={() => dismiss(id)} aria-label="Đóng thông báo">
                    <X size={13} weight="bold" />
                  </button>
                </motion.div>
              );
            })}
          </AnimatePresence>
        </div>,
        document.body,
      )}
    </ToastContext.Provider>
  );
}

export function useToast() {
  const context = useContext(ToastContext);
  if (!context) throw new Error("useToast must be used inside ToastProvider");
  return context;
}
