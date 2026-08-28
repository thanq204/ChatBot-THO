import { useMemo, useState } from "react";

/**
 * Violations over time, with total scanned as context.
 * Smooth cubic bezier curves with gradient area fill and glassmorphism tooltip.
 */

const W = 720;
const H = 210;
const PAD = { top: 14, right: 12, bottom: 26, left: 34 };

const PLOT_W = W - PAD.left - PAD.right;
const PLOT_H = H - PAD.top - PAD.bottom;

function niceCeil(value) {
  if (value <= 5) return 5;
  const magnitude = 10 ** Math.floor(Math.log10(value));
  return Math.ceil(value / magnitude) * magnitude;
}

function hourLabel(iso) {
  const date = new Date(iso);
  return `${String(date.getHours()).padStart(2, "0")}h`;
}

function dayHourLabel(iso) {
  const date = new Date(iso);
  return `${date.getDate()}/${date.getMonth() + 1} lúc ${String(date.getHours()).padStart(2, "0")}:${String(date.getMinutes()).padStart(2, "0")}`;
}

/**
 * Build smooth cubic bezier spline SVG path for a series of (x, y) coordinates
 */
function buildSplinePath(points) {
  if (!points || points.length === 0) return "";
  if (points.length === 1) return `M ${points[0].x} ${points[0].y}`;
  if (points.length === 2) return `M ${points[0].x} ${points[0].y} L ${points[1].x} ${points[1].y}`;

  let d = `M ${points[0].x.toFixed(1)} ${points[0].y.toFixed(1)}`;
  for (let i = 0; i < points.length - 1; i++) {
    const p0 = points[Math.max(i - 1, 0)];
    const p1 = points[i];
    const p2 = points[i + 1];
    const p3 = points[Math.min(i + 2, points.length - 1)];

    const cp1x = p1.x + (p2.x - p0.x) / 5.5;
    const cp1y = p1.y + (p2.y - p0.y) / 5.5;
    const cp2x = p2.x - (p3.x - p1.x) / 5.5;
    const cp2y = p2.y - (p3.y - p1.y) / 5.5;

    d += ` C ${cp1x.toFixed(1)} ${cp1y.toFixed(1)}, ${cp2x.toFixed(1)} ${cp2y.toFixed(1)}, ${p2.x.toFixed(1)} ${p2.y.toFixed(1)}`;
  }
  return d;
}

export default function TrendChart({ buckets }) {
  const [hover, setHover] = useState(null);

  const model = useMemo(() => {
    if (!buckets || buckets.length === 0) return null;
    const peak = Math.max(...buckets.map((b) => b.scanned), 1);
    const top = niceCeil(peak);
    const step = buckets.length > 1 ? PLOT_W / (buckets.length - 1) : 0;

    const x = (i) => PAD.left + i * step;
    const y = (value) => PAD.top + PLOT_H - (value / top) * PLOT_H;

    const scannedPoints = buckets.map((b, i) => ({ x: x(i), y: y(b.scanned) }));
    const violationPoints = buckets.map((b, i) => ({ x: x(i), y: y(b.violations) }));

    const scannedPath = buildSplinePath(scannedPoints);
    const violationPath = buildSplinePath(violationPoints);

    const bottomY = PAD.top + PLOT_H;
    const area = `${violationPath} L ${x(buckets.length - 1)} ${bottomY} L ${x(0)} ${bottomY} Z`;

    // Roughly six labels, always including the newest bucket.
    const labelEvery = Math.max(1, Math.round(buckets.length / 6));

    return { top, x, y, scannedPath, violationPath, area, labelEvery, step };
  }, [buckets]);

  if (!model) return null;

  const active = hover === null ? null : buckets[hover];

  return (
    <div className="trend">
      <div className="trend__legend">
        <span className="trend__key trend__key--violations">Vi phạm phát hiện</span>
        <span className="trend__key trend__key--scanned">Tổng tin đã quét</span>
      </div>

      <div className="trend__plot">
        <svg viewBox={`0 0 ${W} ${H}`} className="trend__svg" role="img" aria-label="Biểu đồ vi phạm theo giờ">
          <defs>
            <linearGradient id="trend-area-grad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="var(--accent-solid)" stopOpacity="0.32" />
              <stop offset="65%" stopColor="var(--accent-solid)" stopOpacity="0.06" />
              <stop offset="100%" stopColor="var(--accent-solid)" stopOpacity="0" />
            </linearGradient>
          </defs>

          {[0, 0.5, 1].map((ratio) => {
            const value = Math.round(model.top * (1 - ratio));
            const yPos = PAD.top + PLOT_H * ratio;
            return (
              <g key={ratio}>
                <line x1={PAD.left} y1={yPos} x2={W - PAD.right} y2={yPos} className="trend__grid" />
                <text x={PAD.left - 7} y={yPos + 3.5} className="trend__tick" textAnchor="end">
                  {value}
                </text>
              </g>
            );
          })}

          {buckets.map((bucket, i) =>
            i % model.labelEvery === 0 ? (
              <text
                key={bucket.start}
                x={model.x(i)}
                y={H - 8}
                className="trend__tick"
                textAnchor={i === 0 ? "start" : "middle"}
              >
                {hourLabel(bucket.start)}
              </text>
            ) : null,
          )}

          <path d={model.area} className="trend__area" />
          <path d={model.scannedPath} className="trend__line trend__line--scanned" vectorEffect="non-scaling-stroke" />
          <path
            d={model.violationPath}
            className="trend__line trend__line--violations"
            vectorEffect="non-scaling-stroke"
          />

          {active && (
            <>
              <line
                x1={model.x(hover)}
                y1={PAD.top}
                x2={model.x(hover)}
                y2={PAD.top + PLOT_H}
                className="trend__crosshair"
                vectorEffect="non-scaling-stroke"
              />
              <circle cx={model.x(hover)} cy={model.y(active.violations)} r="6" className="trend__dot" />
            </>
          )}

          {/* Hit targets are wider than the marks so hovering is forgiving. */}
          {buckets.map((bucket, i) => (
            <rect
              key={bucket.start}
              x={model.x(i) - model.step / 2}
              y={PAD.top}
              width={Math.max(model.step, 6)}
              height={PLOT_H}
              fill="transparent"
              onMouseEnter={() => setHover(i)}
              onMouseLeave={() => setHover(null)}
            />
          ))}
        </svg>

        {active && (
          <div
            className="trend__tip"
            style={{
              left: `${((model.x(hover) - PAD.left) / PLOT_W) * 100}%`,
            }}
          >
            <span className="trend__tip-time">{dayHourLabel(active.start)}</span>
            <span className="trend__tip-row">
              <em className="trend__swatch trend__swatch--violations" />
              <strong>{active.violations}</strong> vi phạm
            </span>
            <span className="trend__tip-row">
              <em className="trend__swatch trend__swatch--scanned" />
              <span>{active.scanned}</span> đã quét
            </span>
          </div>
        )}
      </div>
    </div>
  );
}
