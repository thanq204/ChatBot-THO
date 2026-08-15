import { useMemo, useState } from "react";

/**
 * Violations over time, with total scanned as context.
 *
 * Form is "emphasis", not categorical: violations carry the accent, scanned is
 * de-emphasis gray. Plotting all four decisions would bury the signal, because
 * "allow" is ~87% of traffic and would flatten everything else against the axis.
 *
 * Drawn as inline SVG in a fixed coordinate space and scaled by CSS.
 * vector-effect keeps strokes at their true width at any container size.
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
  return `${date.getDate()}/${date.getMonth() + 1} ${String(date.getHours()).padStart(2, "0")}h`;
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

    const line = (key) => buckets.map((b, i) => `${i === 0 ? "M" : "L"}${x(i)} ${y(b[key])}`).join(" ");
    const area = `${line("violations")} L${x(buckets.length - 1)} ${PAD.top + PLOT_H} L${x(0)} ${
      PAD.top + PLOT_H
    } Z`;

    // Roughly six labels, always including the newest bucket.
    const labelEvery = Math.max(1, Math.round(buckets.length / 6));

    return { top, x, y, scannedPath: line("scanned"), violationPath: line("violations"), area, labelEvery, step };
  }, [buckets]);

  if (!model) return null;

  const active = hover === null ? null : buckets[hover];

  return (
    <div className="trend">
      <div className="trend__legend">
        <span className="trend__key trend__key--violations">Vi phạm</span>
        <span className="trend__key trend__key--scanned">Đã quét</span>
      </div>

      <div className="trend__plot">
        <svg viewBox={`0 0 ${W} ${H}`} className="trend__svg" role="img" aria-label="Biểu đồ vi phạm theo giờ">
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
              <circle cx={model.x(hover)} cy={model.y(active.violations)} r="5" className="trend__dot" />
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
              <em className="trend__swatch trend__swatch--violations" /> {active.violations} vi phạm
            </span>
            <span className="trend__tip-row">
              <em className="trend__swatch trend__swatch--scanned" /> {active.scanned} đã quét
            </span>
          </div>
        )}
      </div>
    </div>
  );
}
