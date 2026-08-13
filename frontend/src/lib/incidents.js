import { categoryLabel } from "./taxonomy.js";

/**
 * OperationsStore builds incident titles as "<Category> từ <author name | author id>".
 * A raw platform snowflake makes every row unreadable, so the UI shows the author
 * name when there is one and a short recognisable tail otherwise.
 */
export function actorFromTitle(title = "") {
  const actor = title.replace(/^\S+\s+(?:từ|in)\s+/i, "").trim();
  if (!actor || actor === title.trim()) return "";
  const tail = actor.split("/").pop();
  return /^\d{6,}$/.test(tail) ? `ID …${tail.slice(-4)}` : actor;
}

export function primaryCategory(incident) {
  return incident.categories?.[0] ?? "safe";
}

/** Human-readable case name: "Bạo lực / Đe doạ · Nghĩa". */
export function caseHeadline(incident) {
  const actor = actorFromTitle(incident.title);
  const category = categoryLabel(primaryCategory(incident));
  return actor ? `${category} · ${actor}` : category;
}
