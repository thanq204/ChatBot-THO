import { useEffect, useRef } from "react";
import { createPortal } from "react-dom";
import { X } from "@phosphor-icons/react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";

const FOCUSABLE =
  'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

/**
 * Centered dialog rendered into document.body. The portal matters: cards in the
 * page animate with transforms, and a transformed ancestor would break the
 * fixed positioning of an in-tree overlay.
 */
export default function Modal({ open, title, onClose, children }) {
  const panelRef = useRef(null);
  const reduceMotion = useReducedMotion();
  // Whatever the operator was on when the dialog opened, so focus can go back
  // there on close instead of resetting to the top of the document.
  const returnFocusRef = useRef(null);

  // onClose is read through a ref so the effects below can key on `open` alone.
  // Most callers pass a fresh closure every render (an inline arrow, or a plain
  // `function closeModal()` in the component body). With onClose in the
  // dependency array, the effect re-ran on every keystroke and re-focused the
  // panel — which stole focus out of whatever field was being typed into, so
  // only the first character ever landed.
  const onCloseRef = useRef(onClose);
  useEffect(() => { onCloseRef.current = onClose; });

  // Focus handover and the body scroll lock: strictly once per open/close.
  useEffect(() => {
    if (!open) return undefined;
    returnFocusRef.current = document.activeElement;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    panelRef.current?.focus();

    return () => {
      document.body.style.overflow = previousOverflow;
      // Guard the call: the trigger may have been unmounted by the very action
      // that closed the dialog (deleting the row you opened it from).
      if (typeof returnFocusRef.current?.focus === "function" && document.contains(returnFocusRef.current)) {
        returnFocusRef.current.focus();
      }
    };
  }, [open]);

  useEffect(() => {
    if (!open) return undefined;

    const handleKeyDown = (event) => {
      if (event.key === "Escape") {
        onCloseRef.current();
        return;
      }
      if (event.key !== "Tab") return;

      // Keep Tab inside the dialog. Without this, tabbing walks out onto the
      // page behind the scrim — invisible under the overlay, but still
      // focusable and still actionable with Enter.
      const items = [...(panelRef.current?.querySelectorAll(FOCUSABLE) ?? [])].filter(
        (node) => node.offsetParent !== null || node === document.activeElement,
      );
      if (items.length === 0) {
        event.preventDefault();
        panelRef.current?.focus();
        return;
      }
      const first = items[0];
      const last = items[items.length - 1];
      if (event.shiftKey && (document.activeElement === first || document.activeElement === panelRef.current)) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };

    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [open]);

  return createPortal(
    <AnimatePresence>
      {open && (
        <motion.div
          className="modal"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.18 }}
        >
          <button type="button" className="modal__scrim" aria-label="Đóng" onClick={onClose} />
          <motion.div
            ref={panelRef}
            className="modal__panel"
            role="dialog"
            aria-modal="true"
            aria-label={title}
            tabIndex={-1}
            initial={reduceMotion ? false : { opacity: 0, y: 24, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={reduceMotion ? { opacity: 0 } : { opacity: 0, y: 16, scale: 0.98 }}
            transition={{ duration: 0.26, ease: [0.16, 1, 0.3, 1] }}
          >
            <header className="modal__header">
              <h2 className="modal__title">{title}</h2>
              <button type="button" className="modal__close" onClick={onClose} aria-label="Đóng chi tiết trường hợp">
                <X size={17} weight="bold" />
              </button>
            </header>
            <div className="modal__body">{children}</div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>,
    document.body,
  );
}
