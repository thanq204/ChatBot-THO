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

export const STATUS_COLORS = {
  open: "var(--sev-high)",
  monitoring: "var(--accent-solid)",
  resolved: "var(--sev-low)",
  snoozed: "var(--text-muted)",
};

/** event_type values written by OperationsStore.add_audit and the admin routes. */
export const AUDIT_EVENT_LABELS = {
  incident_created: "Mở case",
  message_grouped: "Gộp thêm message",
  analysis_completed: "AI phân tích xong",
  incident_updated: "Admin cập nhật case",
  admin_platform_action: "Admin xử lý trên nền tảng",
  automatic_moderation_dm: "Tự động nhắn nhắc nhở",
  member_report_created: "Thành viên báo cáo",
  member_report_reviewed: "Admin xử lý báo cáo",
  admin_announcement: "Admin gửi thông báo",
  moderation_memory_updated: "Lưu case làm mẫu tham chiếu",
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
      return `cập nhật case${status}${note}`;
    }
    case "member_report_reviewed":
      return `đánh dấu báo cáo ${payload.report_id ?? ""} là ${payload.status === "reviewed" ? "đã xử lý" : "mở lại"}`;
    case "admin_announcement":
      return `gửi thông báo tới ${(payload.targets || []).join(", ") || "nền tảng"}`;
    case "moderation_memory_updated":
      return `lưu case làm mẫu tham chiếu (${moderationCategoryLabel(payload.category)})`;
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
  hold_for_review: "Chờ review",
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
  "Invalid Output Guardrail": "Chặn output không hợp lệ",
  "Mock Policy Agent": "Agent chính sách (mock)",
  "Deterministic Guardrail": "Guardrail tất định",
};

export function moderationCategoryLabel(category) {
  return MODERATION_CATEGORY_LABELS[category] ?? category;
}

export function moderationActionLabel(action) {
  return MODERATION_ACTION_LABELS[action] ?? action;
}

export function agentStepLabel(step) {
  return AGENT_TRACE_LABELS[step] ?? step;
}
