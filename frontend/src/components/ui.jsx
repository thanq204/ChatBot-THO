export function Panel({ title, eyebrow, subtitle, actions, children, className = "" }) {
  const hasHead = title || actions || subtitle;
  return (
    <section className={`panel ${className}`.trim()}>
      {hasHead && (
        <div className="panel-head">
          <div>
            {eyebrow && <span className="meta">{eyebrow}</span>}
            {title && <h2>{title}</h2>}
            {subtitle && <p>{subtitle}</p>}
          </div>
          {actions && <div className="button-row">{actions}</div>}
        </div>
      )}
      {children}
    </section>
  );
}

export function Notice({ tone = "", children }) {
  if (!children) return null;
  return <p className={`notice ${tone}`.trim()}>{children}</p>;
}

export function Empty({ icon: Icon, children }) {
  return (
    <p className="empty">
      {Icon && <Icon size={22} weight="light" />}
      {children}
    </p>
  );
}

export function SkeletonRows({ count = 3 }) {
  return (
    <div className="stack" aria-busy="true" aria-label="Đang tải">
      {Array.from({ length: count }, (_, index) => (
        <div key={index} className="skeleton skeleton-row" />
      ))}
    </div>
  );
}

export function SkeletonText({ lines = 3 }) {
  return (
    <div aria-busy="true" aria-label="Đang tải">
      {Array.from({ length: lines }, (_, index) => (
        <div key={index} className="skeleton skeleton-line" style={{ width: index === lines - 1 ? "60%" : "100%" }} />
      ))}
    </div>
  );
}

export const percent = (value) => `${Math.round((value || 0) * 100)}%`;

export const dateText = (value) => (value ? new Date(value).toLocaleString("vi-VN") : "-");
