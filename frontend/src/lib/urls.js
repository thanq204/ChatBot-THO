/** Return only absolute HTTP(S) links that are safe to hand to an anchor. */
export function safeExternalUrl(value) {
  if (typeof value !== "string" || !value.trim()) return null;
  try {
    const parsed = new URL(value.trim());
    if (!(["http:", "https:"].includes(parsed.protocol)) || parsed.username || parsed.password) return null;
    return parsed.href;
  } catch {
    return null;
  }
}
