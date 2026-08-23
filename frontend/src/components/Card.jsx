import { motion } from "motion/react";

/**
 * `animate`, not `whileInView`.
 *
 * A card that starts at `opacity: 0` and only reveals itself when a scroll
 * observer fires is a card that can stay invisible forever. With
 * `viewport={{ amount: 0.3 }}` the reveal needed 30% of the card inside the
 * viewport, and a card holding the full case list measures ~1850px against an
 * ~800px viewport — it can never expose more than 43% of itself, and in practice
 * the observer did not fire at all, leaving the whole page blank but scrollable.
 *
 * These are dashboard panels, not a scroll-telling landing page: they should
 * simply appear when mounted. `animate` runs on mount unconditionally, so the
 * content can never be held hostage by an observer.
 */
export default function Card({ title, action, className = "", children, delay = 0 }) {
  return (
    <motion.section
      className={`card ${className}`}
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay, ease: [0.16, 1, 0.3, 1] }}
    >
      {(title || action) && (
        <header className="card__header">
          {title && <h2 className="card__title">{title}</h2>}
          {action}
        </header>
      )}
      {children}
    </motion.section>
  );
}
