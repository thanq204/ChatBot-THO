import { useId, useState } from "react";
import { CaretRight } from "@phosphor-icons/react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";

/**
 * Collapsed-by-default section. Keeps a dense panel scannable: the summary stays
 * on screen and the supporting detail only costs a click when it is actually wanted.
 */
export default function Disclosure({ label, count, defaultOpen = false, children }) {
  const [open, setOpen] = useState(defaultOpen);
  const reduceMotion = useReducedMotion();
  const panelId = useId();

  return (
    <div className={`disclosure ${open ? "is-open" : ""}`.trim()}>
      <button
        type="button"
        className="disclosure__trigger"
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => setOpen((value) => !value)}
      >
        <CaretRight size={13} weight="bold" className="disclosure__caret" />
        <span className="disclosure__label">{label}</span>
        {count != null && <span className="disclosure__count">{count}</span>}
        <span className="disclosure__hint">{open ? "Thu gọn" : "Xem chi tiết"}</span>
      </button>
      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            id={panelId}
            className="disclosure__panel"
            initial={reduceMotion ? false : { height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={reduceMotion ? { opacity: 0 } : { height: 0, opacity: 0 }}
            transition={{ duration: 0.24, ease: [0.16, 1, 0.3, 1] }}
          >
            <div className="disclosure__inner">{children}</div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
