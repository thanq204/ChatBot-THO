import { motion } from "motion/react";

/** items: [{ key, label, value, share, color }] sorted desc by value already. */
export default function RankList({ items }) {
  return (
    <ol className="rank-list">
      {items.map((item, index) => (
        <motion.li
          key={item.key}
          className="rank-list__row"
          initial={{ opacity: 0, x: -12 }}
          whileInView={{ opacity: 1, x: 0 }}
          viewport={{ once: true, amount: 0.4 }}
          transition={{ duration: 0.4, delay: index * 0.05, ease: [0.16, 1, 0.3, 1] }}
        >
          <span className="rank-list__badge" style={{ background: item.color }}>
            {index + 1}
          </span>
          <span className="rank-list__label">{item.label}</span>
          <span className="rank-list__value">
            {item.share != null ? `${item.share}%` : item.value.toLocaleString("vi-VN")}
          </span>
        </motion.li>
      ))}
    </ol>
  );
}
