const API_ROOT = "/api/v1";

async function request(path, options = {}) {
  const response = await fetch(`${API_ROOT}${path}`, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
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
  audit: () => get("/audit"),
  platforms: () => get("/platforms"),
  pullPlatform: (platform, limit) => post(`/platforms/${platform}/pull?limit=${limit}`),
  incidents: (platform) => get(`/incidents${platform ? `?platform=${encodeURIComponent(platform)}` : ""}`),
  incident: (id) => get(`/incidents/${encodeURIComponent(id)}`),
  updateIncident: (id, payload) => patch(`/incidents/${encodeURIComponent(id)}`, payload),
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
