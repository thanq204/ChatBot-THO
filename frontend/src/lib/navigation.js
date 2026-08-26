import {
  SquaresFour,
  UsersThree,
  ClipboardText,
  Flask,
  ShieldStar,
  Megaphone,
  Books,
  Robot,
  ChatCircleDots,
  Trophy,
  Storefront,
} from "@phosphor-icons/react";

/**
 * The single source of truth for the dashboard's destinations.
 *
 * The sidebar renders it as navigation, the topbar search matches against it,
 * and AppLayout reads the labels for the breadcrumb. It used to be duplicated
 * across those three, with a comment asking future editors to keep them in
 * sync by hand.
 *
 * `keywords` exists so search finds a page by what it does, not only by its
 * label — someone hunting for "ban" should land on the case queue.
 */
export const NAV_ITEMS = [
  { to: "/tong-quan", label: "Tổng quan", icon: SquaresFour, end: true, keywords: "dashboard kpi thống kê biểu đồ" },
  { to: "/cong-dong", label: "Cộng đồng", icon: UsersThree, keywords: "case sự cố hàng đợi báo cáo ban kick vi phạm" },
  { to: "/nhat-ky", label: "Nhật ký kiểm duyệt", icon: ClipboardText, adminOnly: true, keywords: "audit log lịch sử hành động" },
  { to: "/khu-thu-nghiem-ai", label: "Khu thử nghiệm AI", icon: Flask, keywords: "sandbox test thử model phân loại" },
  { to: "/quan-ly-mod", label: "Quản lý Mod", icon: ShieldStar, adminOnly: true, keywords: "tài khoản user mời invite phân quyền" },
  { to: "/quan-ly-faq", label: "Quản lý FAQ", icon: ChatCircleDots, adminOnly: true, keywords: "câu hỏi thường gặp chủ đề" },
  { to: "/bang-exp", label: "Bảng EXP", icon: Trophy, adminOnly: true, keywords: "điểm level thành viên xếp hạng uy tín" },
  { to: "/nguoi-ban", label: "Người bán", icon: Storefront, keywords: "seller giao dịch uy tín scam trade" },
  { to: "/thong-bao", label: "Thông báo", icon: Megaphone, adminOnly: true, keywords: "announcement gửi broadcast telegram discord" },
  { to: "/quan-ly-noi-dung", label: "Quản lý nội dung", icon: Books, adminOnly: true, keywords: "tài liệu rag knowledge tri thức import" },
  { to: "/lenh-bot", label: "Nội dung lệnh bot", icon: Robot, adminOnly: true, keywords: "command lệnh bot nội dung" },
];

/** Admin-only destinations are filtered out entirely rather than shown disabled. */
export function navItemsFor(role) {
  return NAV_ITEMS.filter((item) => !item.adminOnly || role === "admin");
}

export const PAGE_TITLES = Object.fromEntries(NAV_ITEMS.map((item) => [item.to, item.label]));

export function searchNav(query, role) {
  const needle = query.trim().toLowerCase();
  if (!needle) return [];
  return navItemsFor(role).filter((item) =>
    `${item.label} ${item.keywords ?? ""} ${item.to}`.toLowerCase().includes(needle),
  );
}
