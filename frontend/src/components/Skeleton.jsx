export function SkeletonLine({ width = "100%", height = 14 }) {
  return <span className="skeleton-line" style={{ width, height }} />;
}

export function SkeletonBlock({ height = 120 }) {
  return <div className="skeleton-block" style={{ height }} />;
}
