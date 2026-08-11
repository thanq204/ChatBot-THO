import { motion } from "motion/react";
import { DiscordLogo, TelegramLogo, ChatsCircle } from "@phosphor-icons/react";
import { platformLabel, severityLabel } from "../lib/taxonomy.js";
import { relativeTime } from "../lib/format.js";

const PLATFORM_ICONS = {
  discord: DiscordLogo,
  telegram: TelegramLogo,
};

const LIVE_WINDOW_MS = 5 * 60 * 1000;

export default function ActivityFeed({ incidents }) {
  return (
    <ul className="activity-feed">
      {incidents.map((incident, index) => {
        const Icon = PLATFORM_ICONS[incident.platform] ?? ChatsCircle;
        const isLive = Date.now() - new Date(incident.updated_at).getTime() < LIVE_WINDOW_MS;

        return (
          <motion.li
            key={incident.incident_id}
            className="activity-feed__item"
            initial={{ opacity: 0, y: 10 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, amount: 0.3 }}
            transition={{ duration: 0.4, delay: index * 0.05, ease: [0.16, 1, 0.3, 1] }}
          >
            <span className="activity-feed__icon">
              <Icon size={18} weight="fill" />
              {isLive && <span className="activity-feed__pulse" aria-hidden="true" />}
            </span>
            <div className="activity-feed__body">
              <div className="activity-feed__meta">
                <span className="activity-feed__author">
                  {platformLabel(incident.platform)} · {incident.community_id}
                </span>
                <span className="activity-feed__time">{relativeTime(incident.updated_at)}</span>
              </div>
              <p className="activity-feed__text">{incident.summary || incident.title}</p>
              <span className={`badge badge--${incident.severity}`}>
                {severityLabel(incident.severity)} · {Math.round(incident.risk_score * 100)}%
              </span>
            </div>
          </motion.li>
        );
      })}
    </ul>
  );
}
