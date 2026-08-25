import { useEffect, useState } from "react";

/**
 * Progressive reveal for chronological feeds — logs, history, anything where
 * the newest entries matter most and older ones are context you opt into.
 *
 * Numbered pages are the wrong shape for these: nobody wants "page 4 of the
 * audit log", they want the recent slice and a way to keep reading. A table you
 * scan or audit gets <Pagination> instead.
 */
export function useLoadMore(items, step, resetKey = "") {
  const [visibleCount, setVisibleCount] = useState(step);
  const list = items ?? [];

  useEffect(() => { setVisibleCount(step); }, [resetKey, step]);

  const visible = list.slice(0, visibleCount);
  const remaining = Math.max(0, list.length - visibleCount);

  return {
    visible,
    remaining,
    total: list.length,
    showMore: () => setVisibleCount((count) => count + step),
    // Only worth offering once enough has been revealed that scrolling back up
    // is a real cost.
    canCollapse: visibleCount > step,
    collapse: () => setVisibleCount(step),
  };
}

export default function LoadMore({ remaining, step, onMore, unit = "mục", canCollapse, onCollapse }) {
  if (remaining === 0 && !canCollapse) return null;

  return (
    <div className="load-more-bar">
      {remaining > 0 && (
        <button type="button" className="load-more" onClick={onMore}>
          Xem thêm {Math.min(step, remaining)} {unit}
          <span className="load-more__hint">còn {remaining} {unit} chưa hiện</span>
        </button>
      )}
      {canCollapse && (
        <button type="button" className="load-more load-more--collapse" onClick={onCollapse}>
          Thu gọn
        </button>
      )}
    </div>
  );
}
