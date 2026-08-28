import { useCallback, useEffect, useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  FloppyDisk,
  WarningCircle,
  CheckCircle,
  Plus,
  Trash,
  Sparkle,
  Eye,
  PencilSimple,
  Code,
  ShieldCheck,
  Megaphone,
  BookOpen,
  WarningOctagon,
  MagnifyingGlass,
  ArrowRight,
  ChatsCircle,
  Table,
  SlidersHorizontal,
  PaperPlaneTilt,
  CircleNotch,
  ArrowLeft,
} from "@phosphor-icons/react";
import { SkeletonBlock } from "./Skeleton.jsx";
import { ErrorState } from "./StatePanels.jsx";
import Modal from "./Modal.jsx";
import ThoMascot from "./ThoMascot.jsx";
import { ops } from "../api/client.js";
import { queryKeys } from "../lib/queryClient.js";
import { relativeTime } from "../lib/format.js";
import { useTablist } from "../lib/useTablist.js";

// Built-ins the backend always seeds; Admin can rewrite but never delete them.
const CORE_COMMANDS = new Set(["event", "daily", "weekly", "resources", "admin"]);
const RESERVED_NAMES = new Set(["start", "help", "rule", "rules", "faq", "report", "settings"]);
const COMMAND_NAME_PATTERN = /^[a-z0-9_]{2,32}$/;

const PLATFORM_OPTIONS = [
  { value: "telegram", label: "Telegram", color: "#229ed9" },
  { value: "discord", label: "Discord", color: "#5865f2" },
];

/** The seeded defaults all open this way. Close enough to detect reliably. */
const isPlaceholder = (body) => /^chưa có/i.test((body || "").trim());

/**
 * Rich library of command presets and templates for Admins to quickly deploy
 */
const COMMAND_PRESETS = [
  {
    id: "event",
    category: "events",
    categoryLabel: "Sự kiện & Hoạt động",
    icon: Megaphone,
    command: "event",
    description: "Thông báo giải đấu, sự kiện hoặc minigame tuần này",
    platforms: ["telegram", "discord"],
    body: `📢 **THÔNG BÁO SỰ KIỆN CỘNG ĐỒNG TUẦN NÀY**

🎯 **Hoạt động:** Mini-game & Thảo luận chuyên đề cùng Ban Quản Trị
⏰ **Thời gian:** 20:00 Thứ 7 tuần này
🎁 **Phần thưởng:** 500 EXP + Role Danh dự đặc biệt trên server
👉 **Cách tham gia:** Điền form đăng ký tại kênh #dang-ky hoặc react tin nhắn này!

*Chúc {user} và mọi người có những phút giây gắn kết vui vẻ!*`,
  },
  {
    id: "daily",
    category: "events",
    categoryLabel: "Sự kiện & Hoạt động",
    icon: Sparkle,
    command: "daily",
    description: "Nhận điểm danh, EXP và quà tặng hàng ngày",
    platforms: ["telegram", "discord"],
    body: `✨ **ĐIỂM DANH HÀNG NGÀY - NHẬN THƯỞNG**

Chào {user}! Bạn đã điểm danh hôm nay chưa?
🎁 **Phần thưởng:** +25 EXP và tăng chuỗi hoạt động (Streak).
🏆 Tích lũy đủ 7 ngày liên tiếp để nhận huy hiệu "Thành viên Chăm chỉ".

👉 *Tương tác tích cực tại các kênh chat để tự động tích lũy thêm điểm thưởng nhé!*`,
  },
  {
    id: "weekly",
    category: "events",
    categoryLabel: "Sự kiện & Hoạt động",
    icon: Sparkle,
    command: "weekly",
    description: "Bảng tổng kết tuần và vinh danh top thành viên",
    platforms: ["telegram", "discord"],
    body: `🏆 **TỔNG KẾT HOẠT ĐỘNG TUẦN & KẾ HOẠCH MỚI**

Cảm ơn tất cả thành viên đã đóng góp tích cực cho cộng đồng {server_name}!
🌟 **Top 3 cống hiến tuần:** Xem tại bảng xếp hạng /bang-exp
📌 **Lịch tuần tới:** Workshop chia sẻ kinh nghiệm vào tối Chủ Nhật.

*Hãy cùng nhau giữ gìn không gian trao đổi văn minh và lành mạnh!*`,
  },
  {
    id: "admin",
    category: "support",
    categoryLabel: "Hỗ trợ & Quản trị",
    icon: ShieldCheck,
    command: "admin",
    description: "Hướng dẫn liên hệ Ban Quản Trị và mở Ticket hỗ trợ",
    platforms: ["telegram", "discord"],
    body: `🛡️ **HỖ TRỢ TỪ BAN QUẢN TRỊ (ADMIN / MOD)**

Nếu bạn cần giải quyết khiếu nại, tranh chấp hoặc báo cáo vi phạm:
1. 📩 Mở Ticket tại kênh #ho-tro-ticket
2. ⚠️ Gõ lệnh \`/report\` kèm hình ảnh/bằng chứng vi phạm
3. ⏳ Đội ngũ Mod trực 24/7 sẽ phản hồi trong vòng 15-30 phút.

⛔ *Lưu ý: Ban Quản Trị không bao giờ chủ động nhắn tin riêng đòi mật khẩu hay mã OTP của bạn!*`,
  },
  {
    id: "scam_alert",
    category: "safety",
    categoryLabel: "An toàn & Chống lừa đảo",
    icon: WarningOctagon,
    command: "canh_bao",
    description: "Cảnh báo thủ đoạn lừa đảo và quy tắc an toàn giao dịch",
    platforms: ["telegram", "discord"],
    body: `⚠️ **CẢNH BÁO AN TOÀN & PHÒNG TRÁNH LỪA ĐẢO**

Thành viên {user} lưu ý các dấu hiệu lừa đảo phổ biến:
❌ Giả mạo Admin/Mod nhắn tin riêng yêu cầu chuyển tiền hoặc gửi OTP
❌ Gửi link lạ nhận quà miễn phí, file cài đặt (.exe, .scr)
❌ Yêu cầu giao dịch ngoài kênh bảo đảm hoặc không chịu check uy tín

👉 *Tra cứu người bán đáng tin cậy tại danh mục /nguoi-ban trước khi thực hiện giao dịch!*`,
  },
  {
    id: "market_rules",
    category: "safety",
    categoryLabel: "An toàn & Chống lừa đảo",
    icon: BookOpen,
    command: "cho_rules",
    description: "Quy định mua bán, đăng bài và xác thực người bán",
    platforms: ["telegram", "discord"],
    body: `🛒 **QUY ĐỊNH MUA BÁN & GIAO DỊCH TRONG CỘNG ĐỒNG**

1. Chỉ được đăng tin mua bán tại kênh #cho-giao-dich
2. Bắt buộc có ảnh thật sản phẩm, thông tin mô tả rõ ràng và giá bán công khai
3. Khuyến khích sử dụng tính năng xác nhận giao dịch qua Bot để tích lũy uy tín
4. Mọi hành vi gian lận, bùng cọc hoặc bán hàng giả sẽ bị BAN vĩnh viễn khỏi {server_name}.`,
  },
  {
    id: "resources",
    category: "resources",
    categoryLabel: "Tài nguyên & Hướng dẫn",
    icon: BookOpen,
    command: "resources",
    description: "Kho tài liệu, liên kết hữu ích và hướng dẫn tân thủ",
    platforms: ["telegram", "discord"],
    body: `📚 **KHO TÀI NGUYÊN & LIÊN KẾT HỮU ÍCH**

Tổng hợp các tài liệu quan trọng cho thành viên mới:
🔹 **Nội quy máy chủ:** Xem tại /rules hoặc kênh #noi-quy
🔹 **Kho tài liệu / Template:** https://drive.google.com/drive/folders/community-resources
🔹 **Hỏi đáp tự động:** Gõ /faq để được AI hỗ trợ giải đáp 24/7!`,
  },
  {
    id: "social",
    category: "resources",
    categoryLabel: "Tài nguyên & Hướng dẫn",
    icon: ChatsCircle,
    command: "social",
    description: "Tổng hợp các kênh mạng xã hội và nhóm chính thức",
    platforms: ["telegram", "discord"],
    body: `🌐 **CÁC KÊNH KẾT NỐI CHÍNH THỨC CỦA {server_name}**

Gia nhập hệ sinh thái cộng đồng của chúng tôi tại:
💬 **Server Discord:** https://discord.gg/vinuni-community
✈️ **Nhóm Telegram:** https://t.me/vinuni_community_official
🌐 **Cổng Web Portal:** http://localhost:5173/

*Hãy mời thêm bạn bè cùng tham gia để nhận thêm quà tặng nhé!*`,
  },
];

const DYNAMIC_VARIABLES = [
  { tag: "{user}", label: "Tên thành viên", sample: "@HoangAnh" },
  { tag: "{server_name}", label: "Tên cộng đồng", sample: "THO Community" },
  { tag: "{current_date}", label: "Ngày hiện tại", sample: "28/08/2026" },
  { tag: "{rules_channel}", label: "Kênh nội quy", sample: "#noi-quy" },
  { tag: "{support_channel}", label: "Kênh hỗ trợ", sample: "#ho-tro-ticket" },
];

function sortCommands(list) {
  const order = ["event", "daily", "weekly", "resources", "admin"];
  return [...list].sort((a, b) => {
    const ai = order.indexOf(a.command);
    const bi = order.indexOf(b.command);
    if (ai !== -1 || bi !== -1) return (ai === -1 ? 999 : ai) - (bi === -1 ? 999 : bi);
    return a.command.localeCompare(b.command);
  });
}

function samePlatforms(a, b) {
  const left = [...(a || [])].sort();
  const right = [...(b || [])].sort();
  return left.length === right.length && left.every((value, index) => value === right[index]);
}

function PlatformCheckboxes({ value, onToggle }) {
  return (
    <div className="chip-row">
      {PLATFORM_OPTIONS.map((option) => (
        <label key={option.value} className="platform-check">
          <input type="checkbox" checked={value.includes(option.value)} onChange={() => onToggle(option.value)} />
          <span style={{ display: "inline-flex", alignItems: "center", gap: 5 }}>
            {option.value === "discord" ? <ChatsCircle size={14} weight="fill" color="#5865f2" /> : <PaperPlaneTilt size={14} weight="fill" color="#229ed9" />}
            {option.label}
          </span>
        </label>
      ))}
    </div>
  );
}

function renderMessagePreview(rawText) {
  if (!rawText) return "Chưa có nội dung xem trước...";
  return rawText
    .replace(/\{user\}/g, "@ThànhViên")
    .replace(/\{server_name\}/g, "THO Community")
    .replace(/\{current_date\}/g, new Date().toLocaleDateString("vi-VN"))
    .replace(/\{rules_channel\}/g, "#noi-quy")
    .replace(/\{support_channel\}/g, "#ho-tro-ticket");
}

export default function CommandContentEditor() {
  const cmdTabs = useTablist();
  const queryClient = useQueryClient();
  const [active, setActive] = useState(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [platformFilter, setPlatformFilter] = useState("all"); // 'all' | 'discord' | 'telegram'
  const [viewMode, setViewMode] = useState("matrix"); // 'matrix' (default) | 'editor'
  const [previewPlatform, setPreviewPlatform] = useState("discord"); // 'discord' | 'telegram'

  const [draft, setDraft] = useState("");
  const [draftDescription, setDraftDescription] = useState("");
  const [draftPlatforms, setDraftPlatforms] = useState(["telegram", "discord"]);
  const [actionError, setActionError] = useState("");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [togglingKeys, setTogglingKeys] = useState({});

  const [creating, setCreating] = useState(false);
  const [newKey, setNewKey] = useState("");
  const [newDescription, setNewDescription] = useState("");
  const [newBody, setNewBody] = useState("");
  const [newPlatforms, setNewPlatforms] = useState(["telegram", "discord"]);
  const [createError, setCreateError] = useState("");
  const [createBusy, setCreateBusy] = useState(false);
  const [selectedTemplateCat, setSelectedTemplateCat] = useState("all");

  const commandsQuery = useQuery({
    queryKey: queryKeys.commandContents,
    queryFn: ops.commandContents,
    select: sortCommands,
  });

  const commands = commandsQuery.data ?? null;
  const loading = commandsQuery.isPending;
  const error = actionError || commandsQuery.error?.message || "";

  const patchCommands = useCallback(
    (updater) =>
      queryClient.setQueryData(queryKeys.commandContents, (list) => updater(list ?? [])),
    [queryClient],
  );

  const load = useCallback(() => {
    setActionError("");
    queryClient.invalidateQueries({ queryKey: queryKeys.commandContents });
  }, [queryClient]);

  useEffect(() => {
    if (!commands) return;
    setActive((current) =>
      current && commands.some((item) => item.command === current) ? current : commands[0]?.command ?? null,
    );
  }, [commands]);

  useEffect(() => {
    const item = commands?.find((command) => command.command === active);
    setDraft(item?.body ?? "");
    setDraftDescription(item?.description ?? "");
    setDraftPlatforms(item?.platforms?.length ? item.platforms : ["telegram", "discord"]);
    setSaved(false);
  }, [active]); // eslint-disable-line react-hooks/exhaustive-deps

  function toggleDraftPlatform(value) {
    setDraftPlatforms((prev) => (prev.includes(value) ? prev.filter((item) => item !== value) : [...prev, value]));
    setSaved(false);
  }

  function insertVariable(tag) {
    setDraft((prev) => `${prev} ${tag} `);
    setSaved(false);
  }

  function applyPresetToDraft(preset) {
    setDraft(preset.body);
    if (!draftDescription || draftDescription.trim().length === 0) {
      setDraftDescription(preset.description);
    }
    setDraftPlatforms(preset.platforms);
    setSaved(false);
  }

  async function save() {
    if (!draft.trim() || !active || draftPlatforms.length === 0) return;
    setSaving(true);
    setActionError("");
    try {
      const updated = await ops.saveCommandContent(active, {
        body: draft,
        description: draftDescription.trim(),
        platforms: draftPlatforms,
      });
      patchCommands((list) => list.map((item) => (item.command === active ? updated : item)));
      setDraft(updated.body);
      setDraftDescription(updated.description);
      setDraftPlatforms(updated.platforms);
      setSaved(true);
    } catch (err) {
      setActionError(err.message);
    } finally {
      setSaving(false);
    }
  }

  async function toggleCommandPlatformFast(commandName, platformToToggle) {
    const key = `${commandName}-${platformToToggle}`;
    if (togglingKeys[key]) return; // prevent spam clicks

    const target = commands?.find((c) => c.command === commandName);
    if (!target) return;
    const currentPlatforms = target.platforms || [];
    const newPlatforms = currentPlatforms.includes(platformToToggle)
      ? currentPlatforms.filter((p) => p !== platformToToggle)
      : [...currentPlatforms, platformToToggle];

    if (newPlatforms.length === 0) {
      alert("Mỗi lệnh phải hoạt động trên ít nhất một nền tảng.");
      return;
    }

    setTogglingKeys((prev) => ({ ...prev, [key]: true }));
    try {
      const updated = await ops.saveCommandContent(commandName, {
        body: target.body,
        description: target.description || "",
        platforms: newPlatforms,
      });
      patchCommands((list) => list.map((item) => (item.command === commandName ? updated : item)));
      if (active === commandName) {
        setDraftPlatforms(newPlatforms);
      }
    } catch (err) {
      setActionError(err.message);
    } finally {
      setTogglingKeys((prev) => {
        const next = { ...prev };
        delete next[key];
        return next;
      });
    }
  }

  async function removeActive() {
    if (!active || CORE_COMMANDS.has(active)) return;
    if (!window.confirm(`Xoá lệnh /${active}? Thành viên sẽ không dùng được lệnh này nữa.`)) return;
    setDeleting(true);
    setActionError("");
    try {
      await ops.deleteCommandContent(active);
      patchCommands((list) => list.filter((item) => item.command !== active));
    } catch (err) {
      setActionError(err.message);
    } finally {
      setDeleting(false);
    }
  }

  function openCreate() {
    setNewKey("");
    setNewDescription("");
    setNewBody("");
    const initialPlatforms =
      platformFilter === "discord"
        ? ["discord"]
        : platformFilter === "telegram"
        ? ["telegram"]
        : ["telegram", "discord"];
    setNewPlatforms(initialPlatforms);
    setCreateError("");
    setSelectedTemplateCat("all");
    setCreating(true);
  }

  function handleSetPlatformFilter(filter) {
    setPlatformFilter(filter);
    if (filter === "discord") {
      setPreviewPlatform("discord");
    } else if (filter === "telegram") {
      setPreviewPlatform("telegram");
    }
  }

  function applyPresetToCreate(preset) {
    setNewKey(preset.command);
    setNewDescription(preset.description);
    setNewBody(preset.body);
    const initialPlatforms =
      platformFilter === "discord"
        ? ["discord"]
        : platformFilter === "telegram"
        ? ["telegram"]
        : preset.platforms || ["telegram", "discord"];
    setNewPlatforms(initialPlatforms);
    setCreateError("");
  }

  const closeCreate = useCallback(() => setCreating(false), []);

  async function submitCreate(event) {
    event.preventDefault();
    const key = newKey.trim().toLowerCase();
    if (!COMMAND_NAME_PATTERN.test(key)) {
      setCreateError("Tên lệnh chỉ gồm chữ thường, số và dấu gạch dưới, dài 2-32 ký tự.");
      return;
    }
    if (RESERVED_NAMES.has(key)) {
      setCreateError("Tên lệnh này đã được hệ thống dùng cho chức năng khác, hãy chọn tên khác.");
      return;
    }
    if (commands?.some((item) => item.command === key)) {
      setCreateError("Lệnh này đã tồn tại trong danh sách.");
      return;
    }
    if (!newBody.trim()) {
      setCreateError("Nhập nội dung bot sẽ trả lời cho lệnh này.");
      return;
    }
    if (newPlatforms.length === 0) {
      setCreateError("Chọn ít nhất một nền tảng để lệnh hoạt động.");
      return;
    }
    setCreateBusy(true);
    setCreateError("");
    try {
      const created = await ops.saveCommandContent(key, {
        body: newBody,
        description: newDescription.trim(),
        platforms: newPlatforms,
      });
      patchCommands((list) => [...list, created]);
      setActive(created.command);
      setCreating(false);
    } catch (err) {
      setCreateError(err.message);
    } finally {
      setCreateBusy(false);
    }
  }

  const stats = useMemo(() => {
    if (!commands) return { total: 0, configured: 0, pending: 0, discord: 0, telegram: 0 };
    const pending = commands.filter((c) => isPlaceholder(c.body)).length;
    const discord = commands.filter((c) => (c.platforms || []).includes("discord")).length;
    const telegram = commands.filter((c) => (c.platforms || []).includes("telegram")).length;
    return {
      total: commands.length,
      configured: commands.length - pending,
      pending,
      discord,
      telegram,
    };
  }, [commands]);

  const filteredCommands = useMemo(() => {
    if (!commands) return [];
    return commands.filter((cmd) => {
      // Platform filter
      if (platformFilter === "discord" && !(cmd.platforms || []).includes("discord")) {
        return false;
      }
      if (platformFilter === "telegram" && !(cmd.platforms || []).includes("telegram")) {
        return false;
      }
      // Search filter
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase().trim();
        const match =
          cmd.command.toLowerCase().includes(q) ||
          (cmd.description && cmd.description.toLowerCase().includes(q)) ||
          (cmd.body && cmd.body.toLowerCase().includes(q));
        if (!match) return false;
      }
      return true;
    });
  }, [commands, searchQuery, platformFilter]);

  const activeItem = commands?.find((item) => item.command === active) ?? null;
  const empty = isPlaceholder(draft);
  const dirty =
    activeItem !== null &&
    (draft !== activeItem.body ||
      draftDescription !== (activeItem.description || "") ||
      !samePlatforms(draftPlatforms, activeItem.platforms));
  const isCore = active !== null && CORE_COMMANDS.has(active);

  const filteredPresets = useMemo(() => {
    if (selectedTemplateCat === "all") return COMMAND_PRESETS;
    return COMMAND_PRESETS.filter((p) => p.category === selectedTemplateCat);
  }, [selectedTemplateCat]);

  return (
    <div className="cmd">
      {/* Top Overview & Mode Switcher */}
      <div className="cmd__top-bar">
        {/* Platform Tabs & View Switcher */}
        <div className="cmd__platform-filter-row">
          <div className="cmd__platform-pills" role="tablist" aria-label="Lọc theo nền tảng">
            <button
              type="button"
              className={`cmd__platform-pill ${platformFilter === "all" ? "is-active" : ""}`}
              onClick={() => handleSetPlatformFilter("all")}
            >
              🌐 Tất cả ({stats.total})
            </button>
            <button
              type="button"
              className={`cmd__platform-pill cmd__platform-pill--discord ${platformFilter === "discord" ? "is-active" : ""}`}
              onClick={() => handleSetPlatformFilter("discord")}
            >
              <ChatsCircle size={15} weight="fill" color="#5865f2" /> Discord ({stats.discord})
            </button>
            <button
              type="button"
              className={`cmd__platform-pill cmd__platform-pill--telegram ${platformFilter === "telegram" ? "is-active" : ""}`}
              onClick={() => handleSetPlatformFilter("telegram")}
            >
              <PaperPlaneTilt size={15} weight="fill" color="#229ed9" /> Telegram ({stats.telegram})
            </button>
          </div>

          {/* Switch between Single Editor and Matrix Table */}
          <div className="cmd__view-toggle">
            <button
              type="button"
              className={`cmd__view-btn ${viewMode === "editor" ? "is-active" : ""}`}
              onClick={() => setViewMode("editor")}
              title="Chế độ soạn thảo chi tiết"
            >
              <PencilSimple size={14} /> Soạn thảo
            </button>
            <button
              type="button"
              className={`cmd__view-btn ${viewMode === "matrix" ? "is-active" : ""}`}
              onClick={() => setViewMode("matrix")}
              title="Bảng đối soát tất cả lệnh trên Discord & Telegram"
            >
              <Table size={14} /> Bảng đối soát nền tảng
            </button>
          </div>
        </div>

        {/* Search Bar */}
        <div className="cmd__search-box">
          <MagnifyingGlass size={15} />
          <input
            type="search"
            placeholder={
              platformFilter === "discord"
                ? "Tìm lệnh đang có trên Discord..."
                : platformFilter === "telegram"
                ? "Tìm lệnh đang có trên Telegram..."
                : "Tìm kiếm lệnh theo tên hoặc nội dung..."
            }
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
        </div>
      </div>

      {loading && <SkeletonBlock height={220} message="Đang nạp danh sách lệnh bot..." />}
      {!loading && error && <ErrorState message={error} onRetry={load} />}

      {/* VIEW 1: MATRIX TABLE (Xem toàn bộ lệnh trên Telegram & Discord) */}
      {!loading && !error && viewMode === "matrix" && (
        <div className="cmd__matrix-card">
          <div className="cmd__matrix-header">
            <div>
              <h3 style={{ margin: "0 0 4px 0", fontSize: 15, fontWeight: 700 }}>
                Bảng đối soát Lệnh Bot trên Discord & Telegram
              </h3>
              <p className="muted small" style={{ margin: 0 }}>
                Xem danh sách tất cả các lệnh đang kích hoạt trên từng nền tảng và bật/tắt nhanh 1 chạm.
              </p>
            </div>
            <button type="button" className="btn btn--primary btn--sm" onClick={openCreate}>
              <Plus size={14} weight="bold" /> Thêm lệnh mới
            </button>
          </div>

          <div className="cmd__matrix-table-wrap">
            <table className="cmd__matrix-table">
              <thead>
                <tr>
                  <th>Lệnh</th>
                  <th>Mô tả chức năng</th>
                  <th style={{ textAlign: "center", width: 140 }}>
                    <span style={{ display: "inline-flex", alignItems: "center", gap: 5, color: "#5865f2" }}>
                      <ChatsCircle size={15} weight="fill" /> Discord
                    </span>
                  </th>
                  <th style={{ textAlign: "center", width: 140 }}>
                    <span style={{ display: "inline-flex", alignItems: "center", gap: 5, color: "#229ed9" }}>
                      <PaperPlaneTilt size={15} weight="fill" /> Telegram
                    </span>
                  </th>
                  <th style={{ textAlign: "center", width: 130 }}>Nội dung</th>
                  <th style={{ textAlign: "right", width: 100 }}>Thao tác</th>
                </tr>
              </thead>
              <tbody>
                {filteredCommands.length === 0 ? (
                  <tr>
                    <td colSpan={6} style={{ textAlign: "center", padding: "32px 16px" }} className="muted">
                      Không có lệnh nào phù hợp với bộ lọc hiện tại.
                    </td>
                  </tr>
                ) : (
                  filteredCommands.map((item) => {
                    const hasDiscord = (item.platforms || []).includes("discord");
                    const hasTelegram = (item.platforms || []).includes("telegram");
                    const isPending = isPlaceholder(item.body);
                    const isCoreItem = CORE_COMMANDS.has(item.command);
                    const isTogglingDiscord = Boolean(togglingKeys[`${item.command}-discord`]);
                    const isTogglingTelegram = Boolean(togglingKeys[`${item.command}-telegram`]);

                    return (
                      <tr key={item.command} className={active === item.command ? "cmd__matrix-row--active" : ""}>
                        <td>
                          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                            <code style={{ fontWeight: 700, fontSize: 13 }}>/{item.command}</code>
                            {isCoreItem && <span className="cmd__badge-core">Hệ thống</span>}
                          </div>
                        </td>
                        <td>
                          <span className="cmd__matrix-desc">{item.description || "Chưa có mô tả"}</span>
                        </td>
                        <td style={{ textAlign: "center" }}>
                          <button
                            type="button"
                            className={`cmd__platform-toggle ${hasDiscord ? "is-on" : "is-off"} ${isTogglingDiscord ? "is-busy" : ""}`}
                            onClick={() => toggleCommandPlatformFast(item.command, "discord")}
                            disabled={isTogglingDiscord}
                            title={
                              isTogglingDiscord
                                ? "Đang cập nhật..."
                                : hasDiscord
                                ? "Bấm để tắt trên Discord"
                                : "Bấm để bật trên Discord"
                            }
                          >
                            {isTogglingDiscord ? (
                              <CircleNotch size={14} className="spin" />
                            ) : (
                              <ChatsCircle size={14} weight="fill" />
                            )}
                            {isTogglingDiscord ? "Đang xử lý..." : hasDiscord ? "Đang bật" : "Tắt"}
                          </button>
                        </td>
                        <td style={{ textAlign: "center" }}>
                          <button
                            type="button"
                            className={`cmd__platform-toggle ${hasTelegram ? "is-on" : "is-off"} ${isTogglingTelegram ? "is-busy" : ""}`}
                            onClick={() => toggleCommandPlatformFast(item.command, "telegram")}
                            disabled={isTogglingTelegram}
                            title={
                              isTogglingTelegram
                                ? "Đang cập nhật..."
                                : hasTelegram
                                ? "Bấm để tắt trên Telegram"
                                : "Bấm để bật trên Telegram"
                            }
                          >
                            {isTogglingTelegram ? (
                              <CircleNotch size={14} className="spin" />
                            ) : (
                              <PaperPlaneTilt size={14} weight="fill" />
                            )}
                            {isTogglingTelegram ? "Đang xử lý..." : hasTelegram ? "Đang bật" : "Tắt"}
                          </button>
                        </td>
                        <td style={{ textAlign: "center" }}>
                          {isPending ? (
                            <span className="cmd__matrix-status-pill cmd__matrix-status-pill--warn" title="Đang dùng câu báo mặc định">
                              Chưa soạn
                            </span>
                          ) : (
                            <span className="cmd__matrix-status-pill cmd__matrix-status-pill--ok" title="Đã có nội dung thật">
                              Đã có ({item.body.length} ký tự)
                            </span>
                          )}
                        </td>
                        <td style={{ textAlign: "right" }}>
                          <button
                            type="button"
                            className="btn btn--ghost btn--sm"
                            onClick={() => {
                              setActive(item.command);
                              setViewMode("editor");
                            }}
                          >
                            <PencilSimple size={13} /> Sửa
                          </button>
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* VIEW 2: DETAILED EDITOR (Màn hình Soạn thảo chi tiết) */}
      {!loading && !error && viewMode === "editor" && (
        <>
          {/* Command Tabs (Clean & Minimal) */}
          <div className="cmd__tabs" role="tablist" aria-label="Chọn lệnh" ref={cmdTabs.ref} onKeyDown={cmdTabs.onKeyDown}>
            {filteredCommands.map((command) => (
              <button
                key={command.command}
                type="button"
                role="tab"
                aria-selected={active === command.command}
                className={`cmd__tab${active === command.command ? " is-active" : ""}`}
                onClick={() => setActive(command.command)}
              >
                <span>/{command.command}</span>
                {isPlaceholder(command.body) && <span className="cmd__dot" title="Chưa có nội dung thật" />}
              </button>
            ))}
            <button type="button" className="cmd__tab cmd__tab--add" onClick={openCreate}>
              <Plus size={13} weight="bold" /> Thêm lệnh mới
            </button>
          </div>

          {activeItem && (
            <div className="cmd__layout">
              {/* Left Column: Command Editor Form */}
              <div className="cmd__editor-pane">
                <div className="cmd__header-meta">
                  <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
                      <h3 className="cmd__title" style={{ margin: 0 }}>
                        Lệnh <code>/{active}</code>
                        {isCore && <span className="cmd__badge-core">Hệ thống</span>}
                      </h3>

                      {/* Compact Platform Selector Dropdown */}
                      <div className="cmd__platform-dropdown-wrap">
                        <select
                          className="cmd__platform-select"
                          value={
                            draftPlatforms.length === 2
                              ? "both"
                              : draftPlatforms.includes("discord")
                              ? "discord"
                              : "telegram"
                          }
                          onChange={(e) => {
                            const val = e.target.value;
                            if (val === "both") setDraftPlatforms(["telegram", "discord"]);
                            else if (val === "discord") setDraftPlatforms(["discord"]);
                            else setDraftPlatforms(["telegram"]);
                            setSaved(false);
                          }}
                          aria-label="Chọn nền tảng hoạt động"
                        >
                          <option value="both">🌐 Cả Discord & Telegram</option>
                          <option value="discord">💬 Chỉ Discord</option>
                          <option value="telegram">✈️ Chỉ Telegram</option>
                        </select>
                      </div>
                    </div>

                    <p className="muted small" style={{ margin: 0 }}>
                      Khi thành viên gõ <code>/{active}</code>, Bot sẽ tự động phản hồi nội dung này.
                    </p>
                  </div>

                  {/* Action buttons: Back to Matrix Table & Template Picker */}
                  <div className="cmd__quick-template-dropdown" style={{ display: "flex", alignItems: "center", gap: 6 }}>
                    <button
                      type="button"
                      className="btn btn--ghost btn--sm"
                      onClick={() => setViewMode("matrix")}
                      title="Quay lại Bảng đối soát nền tảng"
                    >
                      <ArrowLeft size={14} /> Quay lại bảng
                    </button>
                    <button
                      type="button"
                      className="btn btn--ghost btn--sm"
                      onClick={() => {
                        const match = COMMAND_PRESETS.find((p) => p.command === active) || COMMAND_PRESETS[0];
                        applyPresetToDraft(match);
                      }}
                      title="Nạp nhanh mẫu văn bản chuẩn cho lệnh này"
                    >
                      <Sparkle size={14} weight="fill" color="var(--accent-solid)" /> Dùng mẫu gợi ý
                    </button>
                  </div>
                </div>

                {empty && (
                  <p className="cmd__flag">
                    <WarningCircle size={16} weight="fill" />
                    Lệnh này đang dùng văn bản mặc định ("chưa có thông báo mới"). Hãy điền nội dung thật hoặc chọn một mẫu gợi ý phía trên.
                  </p>
                )}

                <label className="field">
                  <span>Mô tả ngắn (hiển thị trong danh mục <code>/help</code> cho thành viên)</span>
                  <input
                    value={draftDescription}
                    onChange={(event) => {
                      setDraftDescription(event.target.value);
                      setSaved(false);
                    }}
                    placeholder="Ví dụ: Xem thông báo sự kiện cộng đồng tuần này"
                    maxLength={300}
                  />
                </label>

                <div className="field">
                  <div className="cmd__label-row">
                    <span>Nội dung phản hồi của Bot</span>
                    <span className="muted small">{draft.length} / 5000 ký tự</span>
                  </div>

                  {/* Quick Variable Insertion Bar */}
                  <div className="cmd__var-toolbar">
                    <span className="muted small" style={{ fontSize: 11 }}>Chèn biến nhanh:</span>
                    {DYNAMIC_VARIABLES.map((v) => (
                      <button
                        key={v.tag}
                        type="button"
                        className="cmd__var-chip"
                        onClick={() => insertVariable(v.tag)}
                        title={`Chèn biến ${v.tag} (${v.label})`}
                      >
                        <code>{v.tag}</code>
                      </button>
                    ))}
                  </div>

                  <textarea
                    rows={8}
                    maxLength={5000}
                    value={draft}
                    placeholder="Nhập nội dung tin nhắn bot sẽ gửi lại. Hỗ trợ định dạng Markdown (**đậm**, *nghiêng*, emoji)..."
                    onChange={(event) => {
                      setDraft(event.target.value);
                      setSaved(false);
                    }}
                  />
                </div>

                <div className="form-actions">
                  <button
                    type="button"
                    className="btn btn--primary"
                    onClick={save}
                    disabled={saving || !dirty || !draft.trim() || draftPlatforms.length === 0}
                  >
                    <FloppyDisk size={15} weight="bold" /> {saving ? "Đang lưu..." : "Lưu thay đổi"}
                  </button>
                  {!isCore && (
                    <button type="button" className="btn btn--ghost" onClick={removeActive} disabled={deleting}>
                      <Trash size={14} /> {deleting ? "Đang xoá..." : "Xoá lệnh"}
                    </button>
                  )}
                  <span className="muted small">
                    {saved && !dirty ? (
                      <span style={{ color: "var(--sev-low)", display: "inline-flex", alignItems: "center", gap: 4 }}>
                        <CheckCircle size={14} weight="fill" /> Đã lưu thành công
                      </span>
                    ) : (
                      `Cập nhật lần cuối: ${relativeTime(activeItem.updated_at)}`
                    )}
                  </span>
                </div>
              </div>

              {/* Right Column: Live Chat Simulation Preview (Auto-synced) */}
              {(() => {
                const autoPlatform =
                  platformFilter === "telegram"
                    ? "telegram"
                    : platformFilter === "discord"
                    ? "discord"
                    : draftPlatforms.includes("discord")
                    ? "discord"
                    : "telegram";

                return (
                  <div className="cmd__preview-pane">
                    <div className="cmd__preview-header">
                      <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                        <Eye size={16} weight="bold" color="var(--accent-solid)" />
                        <strong>Mô phỏng tin nhắn Bot</strong>
                      </div>
                      <span className="cmd__preview-badge-pill">
                        {autoPlatform === "discord" ? "💬 Discord" : "✈️ Telegram"}
                      </span>
                    </div>

                    <div className={`cmd__chat-mock cmd__chat-mock--${autoPlatform}`}>
                      {/* User Trigger Message */}
                      <div className="cmd__chat-user-msg">
                        <div className="cmd__chat-user-avatar">
                          {autoPlatform === "discord" ? "U" : "Tg"}
                        </div>
                        <div className="cmd__chat-user-content">
                          <span className="cmd__chat-user-name">
                            {autoPlatform === "discord" ? "Thành viên Discord" : "Thành viên Telegram"}
                          </span>
                          <p className="cmd__chat-user-text">/{active}</p>
                        </div>
                      </div>

                      {/* Bot Response Message */}
                      <div className="cmd__chat-bot-msg">
                        <div className="cmd__chat-bot-avatar">
                          <ThoMascot height={28} />
                        </div>
                        <div className="cmd__chat-bot-content">
                          <div className="cmd__chat-bot-meta">
                            <span className="cmd__chat-bot-name">THO Assistant</span>
                            <span className={`cmd__chat-bot-tag cmd__chat-bot-tag--${autoPlatform}`}>
                              {autoPlatform === "discord" ? "BOT [AI]" : "bot"}
                            </span>
                            <span className="cmd__chat-bot-time">
                              Hôm nay lúc {new Date().toLocaleTimeString("vi-VN", { hour: "2-digit", minute: "2-digit" })}
                            </span>
                          </div>
                          <div className={`cmd__chat-bot-body cmd__chat-bot-body--${autoPlatform}`}>
                            {renderMessagePreview(draft)}
                          </div>
                        </div>
                      </div>
                    </div>

                    <div className="cmd__preview-hint">
                      <Sparkle size={13} weight="fill" />
                      <span>
                        Đang mô phỏng giao diện <strong>{autoPlatform === "discord" ? "Discord" : "Telegram"}</strong>. Các biến <code>&#123;user&#125;</code> sẽ được Bot tự động giải mã.
                      </span>
                    </div>
                  </div>
                );
              })()}
            </div>
          )}
        </>
      )}

      {/* Modal: Create New Command with Suggestion Templates */}
      <Modal open={creating} title="Tạo lệnh Bot mới cho cộng đồng" onClose={closeCreate}>
        <form className="stack" onSubmit={submitCreate}>
          <p className="muted small">
            Chọn một trong các mẫu có sẵn dưới đây để điền nhanh hoặc tự soạn nội dung theo nhu cầu của máy chủ:
          </p>

          {/* Preset Templates Selector in Modal */}
          <div className="cmd__templates-section">
            <div className="cmd__templates-head">
              <span style={{ fontSize: 13, fontWeight: 600 }}>Gợi ý mẫu lệnh tạo nhanh (1 chạm):</span>
              <div className="cmd__cat-pills">
                <button
                  type="button"
                  className={`cmd__cat-pill ${selectedTemplateCat === "all" ? "is-active" : ""}`}
                  onClick={() => setSelectedTemplateCat("all")}
                >
                  Tất cả
                </button>
                <button
                  type="button"
                  className={`cmd__cat-pill ${selectedTemplateCat === "events" ? "is-active" : ""}`}
                  onClick={() => setSelectedTemplateCat("events")}
                >
                  Sự kiện
                </button>
                <button
                  type="button"
                  className={`cmd__cat-pill ${selectedTemplateCat === "safety" ? "is-active" : ""}`}
                  onClick={() => setSelectedTemplateCat("safety")}
                >
                  An toàn
                </button>
                <button
                  type="button"
                  className={`cmd__cat-pill ${selectedTemplateCat === "support" ? "is-active" : ""}`}
                  onClick={() => setSelectedTemplateCat("support")}
                >
                  Hỗ trợ
                </button>
                <button
                  type="button"
                  className={`cmd__cat-pill ${selectedTemplateCat === "resources" ? "is-active" : ""}`}
                  onClick={() => setSelectedTemplateCat("resources")}
                >
                  Tài nguyên
                </button>
              </div>
            </div>

            <div className="cmd__templates-grid">
              {filteredPresets.map((preset) => {
                const IconComponent = preset.icon || Sparkle;
                return (
                  <button
                    key={preset.id}
                    type="button"
                    className="cmd__template-card"
                    onClick={() => applyPresetToCreate(preset)}
                  >
                    <div className="cmd__template-card-top">
                      <span className="cmd__template-card-icon">
                        <IconComponent size={16} weight="fill" />
                      </span>
                      <code>/{preset.command}</code>
                    </div>
                    <span className="cmd__template-card-desc">{preset.description}</span>
                  </button>
                );
              })}
            </div>
          </div>

          <label className="field">
            <span>Nền tảng hoạt động</span>
            <select
              value={
                newPlatforms.length === 2
                  ? "both"
                  : newPlatforms.includes("discord")
                  ? "discord"
                  : "telegram"
              }
              onChange={(e) => {
                const val = e.target.value;
                if (val === "both") setNewPlatforms(["telegram", "discord"]);
                else if (val === "discord") setNewPlatforms(["discord"]);
                else setNewPlatforms(["telegram"]);
              }}
            >
              <option value="both">🌐 Cả 2 nền tảng (Discord & Telegram)</option>
              <option value="discord">💬 Chỉ Discord</option>
              <option value="telegram">✈️ Chỉ Telegram</option>
            </select>
          </label>

          <label className="field">
            <span>Tên lệnh (không bao gồm dấu gạch chéo <code>/</code>)</span>
            <input
              value={newKey}
              onChange={(event) => setNewKey(event.target.value)}
              placeholder="vi_du_lenh"
              maxLength={32}
              required
            />
          </label>

          <label className="field">
            <span>Mô tả ngắn (hiển thị trong danh mục <code>/help</code> cho thành viên)</span>
            <input
              value={newDescription}
              onChange={(event) => setNewDescription(event.target.value)}
              placeholder="Mô tả công dụng của lệnh cho thành viên"
              maxLength={300}
            />
          </label>

          <label className="field">
            <span>Nội dung phản hồi của Bot</span>
            <textarea
              rows={5}
              maxLength={5000}
              value={newBody}
              onChange={(event) => setNewBody(event.target.value)}
              placeholder="Nội dung bot sẽ gửi lại khi thành viên gõ lệnh này"
              required
            />
          </label>

          {createError && <p style={{ color: "var(--sev-critical)", fontSize: 13 }}>{createError}</p>}

          <div className="form-actions" style={{ marginTop: 8 }}>
            <button type="submit" className="btn btn--primary" disabled={createBusy}>
              <Plus size={15} weight="bold" /> {createBusy ? "Đang tạo lệnh..." : "Tạo lệnh Bot"}
            </button>
            <button type="button" className="btn btn--ghost" onClick={closeCreate}>
              Hủy
            </button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
