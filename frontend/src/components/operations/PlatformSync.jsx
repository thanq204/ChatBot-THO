import { ArrowsClockwiseIcon, PlugsConnectedIcon } from "@phosphor-icons/react";
import { useState } from "react";
import { ops } from "../../api/client.js";
import { PlatformMark, hasPlatformMark, platformLabel } from "../PlatformIcon.jsx";
import { Notice, Panel } from "../ui.jsx";

const MODE_LABEL = {
  "live-read": "Đang đọc live",
  "not-configured": "Chưa cấu hình",
  planned: "Sắp ra mắt",
  local: "Local",
};

export default function PlatformSync({ platforms, onSynced }) {
  const [limit, setLimit] = useState("100");
  const [busy, setBusy] = useState("");
  const [result, setResult] = useState(null);

  async function sync(platform) {
    setBusy(platform);
    setResult({ tone: "", text: `Đang đọc dữ liệu thật từ ${platform}...` });
    try {
      // Only Discord paginates through history; Telegram polls a fixed window.
      const pulled = await ops.pullPlatform(platform, platform === "discord" ? limit : "50");
      setResult({
        tone: "success",
        text: `Đã nhận ${pulled.received} message và phân tích ${pulled.analyzed} message từ ${platform}.`,
      });
      await onSynced();
    } catch (error) {
      setResult({ tone: "error", text: error.message });
    } finally {
      setBusy("");
    }
  }

  return (
    <Panel
      title="Platform sync"
      subtitle="Khi có token, nút này đọc message thật rồi đưa qua 3 gates. Discord quét được nhiều trang lịch sử."
      actions={
        <>
          <select
            value={limit}
            onChange={(event) => setLimit(event.target.value)}
            aria-label="Số message mỗi lần quét"
          >
            <option value="50">50 messages</option>
            <option value="100">100 messages</option>
            <option value="500">500 messages</option>
          </select>
          <button className="secondary icon-btn" onClick={() => sync("discord")} disabled={Boolean(busy)}>
            <ArrowsClockwiseIcon size={14} className={busy === "discord" ? "spin-icon" : undefined} />
            {busy === "discord" ? "Đang quét..." : "Scan Discord"}
          </button>
          <button className="secondary icon-btn" onClick={() => sync("telegram")} disabled={Boolean(busy)}>
            <ArrowsClockwiseIcon size={14} className={busy === "telegram" ? "spin-icon" : undefined} />
            {busy === "telegram" ? "Đang quét..." : "Sync Telegram"}
          </button>
        </>
      }
    >
      <div className="platform-grid">
        {platforms.length === 0 && <span className="meta">Đang kiểm tra connector…</span>}
        {platforms.map((item) => (
          <div key={item.platform} className={`platform-badge ${item.mode === "live-read" ? "is-live" : ""}`.trim()}>
            <span className="platform-mark">
              {hasPlatformMark(item.platform) ? (
                <PlatformMark platform={item.platform} size={17} />
              ) : (
                <PlugsConnectedIcon size={17} weight="bold" color="var(--ink-faint)" />
              )}
            </span>
            <span>
              <strong>{platformLabel(item.platform)}</strong>
              <small>{MODE_LABEL[item.mode] || item.mode}</small>
            </span>
          </div>
        ))}
      </div>
      {result && (
        <div style={{ marginTop: 14 }}>
          <Notice tone={result.tone}>{result.text}</Notice>
        </div>
      )}
    </Panel>
  );
}
