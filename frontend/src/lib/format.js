const numberFormatter = new Intl.NumberFormat("vi-VN");

export function formatNumber(value) {
  return numberFormatter.format(Math.round(value));
}

/** "5 phút trước" style relative time, Vietnamese. Coarse on purpose (dashboard, not a clock). */
export function relativeTime(isoString) {
  const then = new Date(isoString).getTime();
  if (Number.isNaN(then)) return "";
  const diffSeconds = Math.max(0, Math.round((Date.now() - then) / 1000));

  if (diffSeconds < 45) return "vừa xong";
  const diffMinutes = Math.round(diffSeconds / 60);
  if (diffMinutes < 60) return `${diffMinutes} phút trước`;
  const diffHours = Math.round(diffMinutes / 60);
  if (diffHours < 24) return `${diffHours} giờ trước`;
  const diffDays = Math.round(diffHours / 24);
  if (diffDays < 7) return `${diffDays} ngày trước`;
  return new Date(isoString).toLocaleDateString("vi-VN");
}
