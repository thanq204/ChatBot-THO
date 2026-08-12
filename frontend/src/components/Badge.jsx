export default function Badge({ tone = "var(--text-muted)", children }) {
  return (
    <span className="badge" style={{ color: tone, background: `color-mix(in srgb, ${tone} 14%, transparent)` }}>
      {children}
    </span>
  );
}
