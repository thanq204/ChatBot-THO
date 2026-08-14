import { motion } from "motion/react";

/**
 * Most frequent terms from community_health.top_topics.
 *
 * Horizontal bars because the labels are words of varying length, and a single
 * hue because the job is magnitude, not identity: darker simply means more.
 */
export default function TopicBars({ topics }) {
  if (!topics || topics.length === 0) return null;
  const peak = Math.max(...topics.map(([, count]) => count), 1);

  return (
    <ul className="topics">
      {topics.map(([term, count], index) => (
        <li key={term} className="topics__row">
          <span className="topics__term">{term}</span>
          <span className="topics__track">
            <motion.span
              className="topics__fill"
              // One hue, stepped by rank: more frequent reads darker.
              style={{ opacity: 1 - index * 0.09 }}
              initial={{ scaleX: 0 }}
              whileInView={{ scaleX: count / peak }}
              viewport={{ once: true, amount: 0.5 }}
              transition={{ duration: 0.6, delay: index * 0.05, ease: [0.16, 1, 0.3, 1] }}
            />
          </span>
          <span className="topics__count">{count}</span>
        </li>
      ))}
    </ul>
  );
}
