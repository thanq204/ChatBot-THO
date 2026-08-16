import { NavLink } from "react-router-dom";
import {
  SquaresFour,
  UsersThree,
  ClipboardText,
  Flask,
  ShieldStar,
  Megaphone,
  Books,
  Robot,
} from "@phosphor-icons/react";

const NAV_ITEMS = [
  { to: "/tong-quan", label: "Tổng quan", icon: SquaresFour, end: true },
  { to: "/cong-dong", label: "Cộng đồng", icon: UsersThree },
  { to: "/nhat-ky", label: "Nhật ký kiểm duyệt", icon: ClipboardText },
  { to: "/khu-thu-nghiem-ai", label: "Khu thử nghiệm AI", icon: Flask },
  { to: "/quan-ly-mod", label: "Quản lý Mod", icon: ShieldStar },
  { to: "/thong-bao", label: "Thông báo", icon: Megaphone },
  { to: "/quan-ly-noi-dung", label: "Quản lý nội dung", icon: Books },
  { to: "/lenh-bot", label: "Nội dung lệnh bot", icon: Robot },
];

export default function Sidebar({ open, onNavigate }) {
  return (
    <aside className={`sidebar ${open ? "sidebar--open" : ""}`}>
      <div className="sidebar__brand">
        <span className="sidebar__logo">ModAI</span>
        <span className="sidebar__subtitle">Bảng điều khiển kiểm duyệt</span>
      </div>

      <nav className="sidebar__nav" aria-label="Điều hướng chính">
        {NAV_ITEMS.map(({ to, label, icon: Icon, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            onClick={onNavigate}
            className={({ isActive }) => `sidebar__link ${isActive ? "sidebar__link--active" : ""}`}
          >
            <Icon size={19} weight="regular" />
            <span>{label}</span>
          </NavLink>
        ))}
      </nav>
    </aside>
  );
}
