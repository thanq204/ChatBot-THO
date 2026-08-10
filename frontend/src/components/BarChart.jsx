import { motion } from "motion/react";

/** items: [{ key, label, value }]. Pure CSS/SVG bars, no charting dependency. */
export default function BarChart({ items }) {
  const max = Math.max(1, ...items.map((item) => item.value));

  return (
    <div className="bar-chart" role="img" aria-label="Biểu đồ tin nhắn theo nền tảng">
      {items.map((item, index) => (
        <div className="bar-chart__column" key={item.key}>
          <div className="bar-chart__track">
            <motion.div
              className="bar-chart__bar"
              initial={{ scaleY: 0 }}
              whileInView={{ scaleY: item.value / max }}
              viewport={{ once: true, amount: 0.6 }}
              transition={{ duration: 0.6, delay: index * 0.06, ease: [0.16, 1, 0.3, 1] }}
            />
          </div>
          <span className="bar-chart__value">{item.value.toLocaleString("vi-VN")}</span>
          <span className="bar-chart__label">{item.label}</span>
        </div>
      ))}
    </div>
  );
}
