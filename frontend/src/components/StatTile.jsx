import { motion } from "motion/react";
import Counter from "./Counter.jsx";

export default function StatTile({ label, value, icon: Icon, tone = "brand", meta, delay = 0 }) {
  return (
    <motion.div
      className={`stat-tile stat-tile--${tone}`}
      initial={{ opacity: 0, y: 16 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, amount: 0.4 }}
      transition={{ duration: 0.5, delay, ease: [0.16, 1, 0.3, 1] }}
    >
      <div className="stat-tile__top">
        <span className="stat-tile__label">{label}</span>
        {Icon && (
          <span className="stat-tile__icon">
            <Icon size={20} weight="bold" />
          </span>
        )}
      </div>
      <p className="stat-tile__value">
        <Counter value={value} />
      </p>
      {meta && <p className="stat-tile__meta">{meta}</p>}
    </motion.div>
  );
}
