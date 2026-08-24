import { QueryClient } from "@tanstack/react-query";

/**
 * Shared cache for every dashboard read.
 *
 * The dashboard used to hold each page's data in component state, so React
 * Router unmounting a page threw the data away and returning to it re-fetched
 * from scratch behind a full screen of skeletons. Keeping the data here instead
 * means a revisit renders the previous answer immediately and only refreshes in
 * the background when it has gone stale.
 */

/** How long a fetched answer is served without hitting the network again. */
export const STALE_TIME_MS = 60_000;

/** How long an unused answer survives in memory, so a revisit still paints instantly. */
const GC_TIME_MS = 15 * 60_000;

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: STALE_TIME_MS,
      gcTime: GC_TIME_MS,
      // These stay at their defaults on purpose. `staleTime` already decides
      // when a refetch is worth doing, and a refetch that finds cached data
      // renders it immediately while refreshing underneath — the page never
      // drops back to skeletons. Turning them off instead would leave an
      // operator staring at hour-old incident counts.
      refetchOnMount: true,
      refetchOnWindowFocus: true,
      refetchOnReconnect: true,
      // Operator data, not a flaky public API. One retry covers a dropped
      // connection without making a genuine failure take four round-trips to
      // surface.
      retry: 1,
    },
  },
});

/**
 * Query keys in one place so a mutation can invalidate exactly what it changed.
 * Keys are arrays: `["incidents"]` invalidates every incident query, including
 * the filtered variants underneath it.
 */
export const queryKeys = {
  analytics: ["analytics"],
  timeline: (windowHours, bucketHours) => ["analytics", "timeline", windowHours, bucketHours],
  communityHealth: (windowHours) => ["community-health", windowHours],
  platforms: ["platforms"],
  discordChannels: ["platforms", "discord", "channels"],
  incidents: (filters) => ["incidents", filters ?? {}],
  incident: (id) => ["incidents", "detail", id],
  audit: (incidentId) => ["audit", incidentId ?? null],
  memberReports: ["member-reports"],
  commandContents: ["command-content"],
  faqs: (activeOnly) => ["faqs", Boolean(activeOnly)],
  faqTopTopics: (limit) => ["faq-top-topics", limit],
  policies: ["policies"],
  knowledge: ["knowledge"],
  knowledgeImports: ["knowledge", "imports"],
  reputation: ["reputation"],
  reputationRules: ["reputation-rules"],
  experience: ["experience"],
  experienceRules: ["experience-rules"],
  flaggedLinks: ["flagged-links"],
  trades: (status) => ["trades", status ?? null],
  sellerReviews: (sellerId) => ["seller-reviews", sellerId ?? null],
  sellers: ["sellers"],
  sellerAssessments: (status) => ["seller-assessments", status ?? null],
  users: ["auth", "users"],
  modInvites: ["auth", "mod-invites"],
  moderationAuditLogs: ["moderation", "audit-logs"],
  agentStatus: ["agent", "status"],
};
