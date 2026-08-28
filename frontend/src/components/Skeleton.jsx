import ThoMascot from "./ThoMascot.jsx";

export function SkeletonLine({ width = "100%", height = 14 }) {
  return <span className="skeleton-line" style={{ width, height }} />;
}

export function SkeletonBlock({ height = 180, message = "Đang nạp dữ liệu từ hệ thống...", compact = false }) {
  return (
    <div className={`mascot-loader ${compact ? "mascot-loader--compact" : ""}`} style={{ minHeight: height }}>
      <div className="mascot-loader__scene">
        <div className="mascot-loader__scooter-wrap">
          <ThoMascot height={compact ? 50 : 68} label="Đang tải dữ liệu" />
          <span className="mascot-loader__exhaust" />
        </div>
        <div className="mascot-loader__track" />
      </div>
      <div className="mascot-loader__status">
        <span className="mascot-loader__spin-dot" />
        <span className="mascot-loader__text">{message}</span>
      </div>
    </div>
  );
}

export function MascotLoader({ message = "Đang tải dữ liệu...", height = 240, fullScreen = false }) {
  return (
    <div className={`mascot-loader ${fullScreen ? "mascot-loader--fullscreen" : ""}`} style={{ minHeight: height }}>
      <div className="mascot-loader__scene">
        <div className="mascot-loader__scooter-wrap">
          <ThoMascot height={78} label="Đang tải dữ liệu" />
          <span className="mascot-loader__exhaust" />
        </div>
        <div className="mascot-loader__track" />
      </div>
      <div className="mascot-loader__status">
        <span className="mascot-loader__spin-dot" />
        <span className="mascot-loader__text">{message}</span>
      </div>
    </div>
  );
}
