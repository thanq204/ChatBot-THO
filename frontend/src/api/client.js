const API_ROOT = "/api/v1";
const TOKEN_KEY = "acm-access-token";

export function getAccessToken() { return window.localStorage.getItem(TOKEN_KEY); }
export function setAccessToken(token) { window.localStorage.setItem(TOKEN_KEY, token); }
export function clearAccessToken() { window.localStorage.removeItem(TOKEN_KEY); }

async function request(path, options = {}) {
  const response = await fetch(`${API_ROOT}${path}`, {
    headers: { "Content-Type": "application/json", ...(getAccessToken() ? { Authorization: `Bearer ${getAccessToken()}` } : {}), ...(options.headers || {}) },
    ...options,
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.detail || "Request failed");
  return body;
}

const get = (path) => request(path);
const post = (path, payload) =>
  request(path, { method: "POST", body: payload === undefined ? undefined : JSON.stringify(payload) });
const put = (path, payload) => request(path, { method: "PUT", body: JSON.stringify(payload) });
const patch = (path, payload) => request(path, { method: "PATCH", body: JSON.stringify(payload) });
const del = (path) => request(path, { method: "DELETE" });

/** Operations surface: incidents, connectors, policies, knowledge, RAG. */
export const ops = {
  analytics: () => get("/analytics"),
  timeline: (windowHours = 48, bucketHours = 1) =>
    get(`/analytics/timeline?window_hours=${windowHours}&bucket_hours=${bucketHours}`),
  communityHealth: (windowHours = 24) => get(`/community-health?window_hours=${windowHours}`),
  platforms: () => get("/platforms"),
  discordChannels: () => get("/platforms/discord/channels"),
  pullPlatform: (platform, limit) => post(`/platforms/${platform}/pull?limit=${limit}`),
  incidents: (filters = {}) => {
    const params = new URLSearchParams();
    if (filters.platform) params.set("platform", filters.platform);
    if (filters.status) params.set("status", filters.status);
    const query = params.toString();
    return get(`/incidents${query ? `?${query}` : ""}`);
  },
  incident: (id) => get(`/incidents/${encodeURIComponent(id)}`),
  updateIncident: (id, payload) => patch(`/incidents/${encodeURIComponent(id)}`, payload),
  audit: (incidentId) => get(`/audit${incidentId ? `?incident_id=${encodeURIComponent(incidentId)}` : ""}`),
  analyze: (message) => post("/messages/analyze", { message }),
  ingest: (payload) => post("/messages/ingest", payload),
  ask: (question, dataset) => post("/rag/ask", { question, dataset: dataset || null }),
  policies: () => get("/policies"),
  savePolicy: (id, payload) => put(`/policies/${encodeURIComponent(id)}`, payload),
  deletePolicy: (id) => del(`/policies/${encodeURIComponent(id)}`),
  knowledge: () => get("/knowledge"),
  saveKnowledge: (id, payload) => put(`/knowledge/${encodeURIComponent(id)}`, payload),
  deleteKnowledge: (id) => del(`/knowledge/${encodeURIComponent(id)}`),
  importKnowledge: (payload) => post("/knowledge/import", payload),
  knowledgeImports: () => get("/knowledge/imports"),
  seedDemo: () => post("/demo/seed"),
  sendAnnouncement: (payload) => post("/admin/announcements", payload),

  /** Admin-confirmed platform action against one case. Never fires automatically. */
  executeAction: (incidentId, payload) =>
    post(`/incidents/${encodeURIComponent(incidentId)}/actions`, payload),

  /** Bot command bodies the Admin manages: the seeded built-ins plus any custom command created from the dashboard. */
  commandContents: () => get("/admin/command-content"),
  commandContent: (command) => get(`/admin/command-content/${encodeURIComponent(command)}`),
  /** payload: { body, description, platforms: ["telegram"|"discord", ...] } */
  saveCommandContent: (command, payload) =>
    put(`/admin/command-content/${encodeURIComponent(command)}`, payload),
  deleteCommandContent: (command) => del(`/admin/command-content/${encodeURIComponent(command)}`),

  /** Inbox of /report submissions from members. */
  memberReports: () => get("/admin/member-reports"),
  updateMemberReport: (reportId, payload) =>
    patch(`/admin/member-reports/${encodeURIComponent(reportId)}`, payload),
};

/** Sentence-level moderation surface used by the member and review-queue pages. */
export const moderation = {
  status: () => get("/moderation/status"),
  demoCases: () => get("/moderation/demo-cases"),
  submit: (payload) => post("/moderation/submit", payload),
  reviewQueue: () => get("/moderation/review-queue"),
  decide: (reviewId, payload) => post(`/moderation/review-queue/${encodeURIComponent(reviewId)}/decision`, payload),
  auditLogs: () => get("/moderation/audit-logs"),
};

export const auth = {
  login: (payload) => post("/auth/login", payload),
  google: (credential, password) => post("/auth/google", { credential, ...(password ? { password } : {}) }),
  googleConfig: () => get("/auth/google/config"),
  me: () => get("/auth/me"),
  users: () => get("/auth/users"),
    createUser: (payload) => post("/auth/users", payload),
    modInvites: () => get("/auth/mod-invites"),
    inviteMod: (email) => post("/auth/mod-invites", { email }),
    deleteModInvite: (email) => del(`/auth/mod-invites/${encodeURIComponent(email)}`),
  updateRole: (id, role) => patch(`/auth/users/${encodeURIComponent(id)}/role`, { role }),
  updateStatus: (id, is_active) => patch(`/auth/users/${encodeURIComponent(id)}/status`, { is_active }),
  deleteUser: (id) => del(`/auth/users/${encodeURIComponent(id)}`),
};

/** Agent surface exposed by the LangGraph routes. */
export const agent = {
  status: () => get("/status"),
  chat: (payload) => post("/chat", payload),
};

/** Liveness probe. It sits outside /api/v1, so it bypasses `request`. */
export async function health() {
  const response = await fetch("/health");
  if (!response.ok) throw new Error("Health check failed");
  return response.json();
}

/** Browsers cannot send raw bytes as JSON, so files travel base64-encoded. */
export async function fileToBase64(file) {
  const bytes = new Uint8Array(await file.arrayBuffer());
  let binary = "";
  for (let index = 0; index < bytes.length; index += 0x8000) {
    binary += String.fromCharCode(...bytes.subarray(index, index + 0x8000));
  }
  return btoa(binary);
}
