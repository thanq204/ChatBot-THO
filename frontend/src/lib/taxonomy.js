/**
 * Vietnamese labels and colors for the enums defined in backend/models/operations.py.
 * Kept in one place so every component maps the same backend value to the same word/color.
 */

export const CATEGORY_LABELS = {
  spam: "Spam / Lừa đảo",
  harassment: "Quấy rối",
  violence: "Bạo lực / Đe doạ",
  hate: "Thù ghét",
  disagreement: "Tranh luận gay gắt",
  friendly_teasing: "Đùa giỡn thân thiện",
  safe: "An toàn",
  sexual: "Nội dung nhạy cảm",
  self_harm: "Tự gây hại",
  ambiguous: "Chưa rõ ràng",
  benign_activity: "Hoạt động thông thường",
  quoted_or_educational: "Trích dẫn / giáo dục",
  other: "Khác",
};

export const CATEGORY_COLORS = {
  spam: "var(--cat-spam)",
  harassment: "var(--cat-harassment)",
  violence: "var(--cat-violence)",
  hate: "var(--cat-hate)",
  disagreement: "var(--cat-disagreement)",
  friendly_teasing: "var(--cat-teasing)",
  safe: "var(--cat-safe)",
};

export const SEVERITY_LABELS = {
  low: "Thấp",
  medium: "Trung bình",
  high: "Cao",
  critical: "Nghiêm trọng",
};

export const SEVERITY_COLORS = {
  low: "var(--sev-low)",
  medium: "var(--sev-medium)",
  high: "var(--sev-high)",
  critical: "var(--sev-critical)",
};

export const PLATFORM_LABELS = {
  discord: "Discord",
  telegram: "Telegram",
  zalo: "Zalo",
  messenger: "Messenger",
  web: "Web",
  demo: "Demo",
};

export const STATUS_LABELS = {
  open: "Đang mở",
  monitoring: "Đang theo dõi",
  resolved: "Đã xử lý",
  snoozed: "Tạm hoãn",
};

// Deliberately a different hue family from SEVERITY_COLORS (red/amber/green
// heat scale): status is a workflow stage, not an urgency level, and sharing
// hues made a critical+open case render as three near-identical red badges.
export const STATUS_COLORS = {
  open: "var(--status-open)",
  monitoring: "var(--status-monitoring)",
  resolved: "var(--status-resolved)",
  snoozed: "var(--status-snoozed)",
};

/** event_type values written by OperationsStore.add_audit and the admin routes. */
export const AUDIT_EVENT_LABELS = {
  incident_created: "Mở trường hợp",
  message_grouped: "Gộp thêm tin nhắn",
  analysis_completed: "AI phân tích xong",
  incident_updated: "Admin cập nhật trường hợp",
  admin_platform_action: "Admin xử lý trên nền tảng",
  automatic_moderation_dm: "Tự động nhắn nhắc nhở",
  member_report_created: "Thành viên báo cáo",
  member_report_reviewed: "Admin xử lý báo cáo",
  admin_announcement: "Admin gửi thông báo",
  moderation_memory_updated: "Lưu trường hợp làm mẫu tham chiếu",
  duplicate_admin_notification_suppressed: "Bỏ qua thông báo trùng lặp",
  recent_duplicate_notification_suppressed: "Bỏ qua thông báo trùng lặp gần đây",
  incident_reputation_decision: "Admin/Mod duyệt vi phạm",
};

/** Discord/Telegram action values on an admin_platform_action audit entry. */
export const PLATFORM_ACTION_VERBS = {
  dm: "nhắn tin cảnh báo",
  delete_message: "xoá tin nhắn của",
  timeout: "timeout",
  kick: "kick",
  ban: "ban",
};

export const PLATFORM_ACTION_COLORS = {
  dm: "var(--accent-solid)",
  delete_message: "var(--sev-high)",
  timeout: "var(--sev-medium)",
  kick: "var(--sev-high)",
  ban: "var(--sev-critical)",
};

/**
 * Real actions taken on real incidents (Discord/Telegram), as opposed to the
 * system's own bookkeeping entries (incident_created, message_grouped, ...)
 * which are noise from an Admin's point of view. Shared by the moderation
 * log page and the Mod management page so "what counts as a mod action" is
 * defined once.
 */
export const ADMIN_ACTION_EVENT_TYPES = new Set([
  "admin_platform_action",
  "incident_updated",
  "member_report_reviewed",
  "admin_announcement",
  "moderation_memory_updated",
]);

export function describeAuditEntry(item) {
  const payload = item.payload || {};
  switch (item.event_type) {
    case "admin_platform_action": {
      const verb = PLATFORM_ACTION_VERBS[payload.action] || payload.action;
      const target = payload.target_user_id ? ` user ${payload.target_user_id}` : "";
      const duration = payload.duration_minutes ? ` (${payload.duration_minutes} phút)` : "";
      const failed = payload.completed === false ? " — thất bại" : "";
      return `đã ${verb}${target}${duration}${failed}`;
    }
    case "incident_updated": {
      const status = payload.status ? ` → ${statusLabel(payload.status)}` : "";
      const note = payload.note ? `: ${payload.note}` : "";
      return `cập nhật trường hợp${status}${note}`;
    }
    case "member_report_reviewed":
      return `đánh dấu báo cáo ${payload.report_id ?? ""} là ${payload.status === "reviewed" ? "đã xử lý" : "mở lại"}`;
    case "admin_announcement":
      return `gửi thông báo tới ${(payload.targets || []).join(", ") || "nền tảng"}`;
    case "moderation_memory_updated":
      return `lưu trường hợp làm mẫu tham chiếu (${moderationCategoryLabel(payload.category)})`;
    default:
      return auditEventLabel(item.event_type);
  }
}

export function auditToneFor(item) {
  if (item.event_type === "admin_platform_action") {
    return PLATFORM_ACTION_COLORS[item.payload?.action] || "var(--text-muted)";
  }
  return "var(--accent-solid)";
}

export function auditEventLabel(value) {
  return AUDIT_EVENT_LABELS[value] ?? value;
}

/** operations.py Decision enum: shared by incidents, policy actions and message decisions. */
export const DECISION_LABELS = {
  allow: "Cho phép",
  warn: "Cảnh báo",
  hide: "Ẩn",
  hold_for_review: "Chờ duyệt",
};

export const DECISION_COLORS = {
  allow: "var(--sev-low)",
  warn: "var(--sev-medium)",
  hide: "var(--sev-high)",
  hold_for_review: "var(--accent-solid)",
};

export function categoryLabel(category) {
  return CATEGORY_LABELS[category] ?? category;
}

export function severityLabel(severity) {
  return SEVERITY_LABELS[severity] ?? severity;
}

export function platformLabel(platform) {
  return PLATFORM_LABELS[platform] ?? platform;
}

export function statusLabel(value) {
  return STATUS_LABELS[value] ?? value;
}

export function decisionLabel(value) {
  return DECISION_LABELS[value] ?? value;
}

/**
 * backend/models/moderation.py uses a different, overlapping category enum than
 * operations.py (adds sexual/self_harm/ambiguous/other, drops disagreement/friendly_teasing).
 * Kept separate so a mislabeled ops category never silently falls back to the raw string.
 */
export const MODERATION_CATEGORY_LABELS = {
  safe: "An toàn",
  spam: "Spam / Lừa đảo",
  harassment: "Quấy rối",
  hate: "Ngôn từ thù ghét",
  violence: "Bạo lực / Đe doạ",
  sexual: "Nội dung nhạy cảm",
  self_harm: "Tự gây hại",
  ambiguous: "Chưa rõ ràng",
  other: "Khác",
};

export const MODERATION_ACTION_LABELS = {
  allow: "Cho phép",
  warn: "Cảnh báo",
  hide: "Ẩn nội dung",
  review: "Chờ Admin duyệt",
};

export const MODERATION_ACTION_COLORS = {
  allow: "var(--sev-low)",
  warn: "var(--sev-medium)",
  hide: "var(--sev-high)",
  review: "var(--accent-solid)",
};

/** agent_trace only ever contains these literal node-name labels (see moderation_graph.py). */
const AGENT_TRACE_LABELS = {
  "Context Agent": "Agent ngữ cảnh",
  "Policy Agent": "Agent chính sách",
  "Risk Agent": "Agent rủi ro",
  "Safety Gate": "Cổng an toàn",
  "Decision Agent": "Agent quyết định",
  "Agent Graph": "Đồ thị Agent",
  "Invalid Output Guardrail": "Cổng chặn kết quả không hợp lệ",
  "Mock Policy Agent": "Agent chính sách mô phỏng",
  "Deterministic Guardrail": "Cổng an toàn tất định",
};

const MODERATION_REASON_FALLBACKS = {
  safe: "Không phát hiện dấu hiệu vi phạm rõ ràng.",
  spam: "Nội dung có dấu hiệu spam hoặc lừa đảo và cần được kiểm tra.",
  harassment: "Nội dung có dấu hiệu quấy rối hoặc công kích cá nhân.",
  hate: "Nội dung có dấu hiệu ngôn từ thù ghét.",
  violence: "Nội dung có dấu hiệu đe dọa hoặc cổ súy bạo lực.",
  sexual: "Nội dung có dấu hiệu nhạy cảm và cần được kiểm tra.",
  self_harm: "Nội dung liên quan đến tự gây hại và cần Admin/Mod xem xét.",
  ambiguous: "Ngữ cảnh chưa đủ rõ để hệ thống tự động đưa ra kết luận.",
  benign_activity: "Đây là hoạt động thông thường, chưa thấy ý định gây hại.",
  friendly_teasing: "Ngữ cảnh cho thấy đây có thể là lời đùa thân thiện.",
  quoted_or_educational: "Nội dung đang được trích dẫn hoặc dùng để giải thích, chưa thấy ý định gây hại.",
  other: "Nội dung cần được kiểm tra thêm trước khi đưa ra kết luận.",
};

const ENGLISH_REASON_WORDS = new Set([
  "agents", "ambiguous", "appears", "attack", "because", "clear", "contains", "content", "context",
  "detected", "evidence", "exceeded", "found", "harmful", "harassment", "intent", "language", "message",
  "personal", "policy", "quota", "requires", "risk", "safe", "specialist", "threat", "user", "violation",
]);

function looksLikeEnglishReason(value) {
  const text = String(value || "").trim().toLowerCase();
  if (!text) return false;
  if (/^(allow|allowed|ambiguous|hide|no violation|review|safe|warn)[.! ]*$/.test(text)) return true;
  if (/^(spam|harassment|hate|violence|sexual|self_harm|ambiguous|safe)\s+từ\s+/i.test(text)) return true;
  const words = text.match(/[a-z]+/g) || [];
  return words.filter((word) => ENGLISH_REASON_WORDS.has(word)).length >= 2;
}

export function moderationCategoryLabel(category) {
  return MODERATION_CATEGORY_LABELS[category] ?? category;
}

export function moderationActionLabel(action) {
  return MODERATION_ACTION_LABELS[action] ?? action;
}

export function agentStepLabel(step) {
  return AGENT_TRACE_LABELS[step] ?? "Bước xử lý bổ sung";
}

export function vietnameseModerationText(value, category = "other", fallback = "") {
  const text = String(value || "").trim();
  if (text && !looksLikeEnglishReason(text)) return text;
  return fallback || MODERATION_REASON_FALLBACKS[category] || MODERATION_REASON_FALLBACKS.other;
}
