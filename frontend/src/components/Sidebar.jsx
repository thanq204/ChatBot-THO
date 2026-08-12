import { NavLink } from "react-router-dom";
import {
  SquaresFour,
  UsersThree,
  ShieldCheck,
  ClipboardText,
  Flask,
  IdentificationBadge,
  Megaphone,
  GearSix,
} from "@phosphor-icons/react";

const NAV_ITEMS = [
  { to: "/tong-quan", label: "Tổng quan", icon: SquaresFour, end: true },
  { to: "/cong-dong", label: "Cộng đồng", icon: UsersThree },
  { to: "/quy-tac-ai", label: "Quy tắc AI", icon: ShieldCheck },
  { to: "/nhat-ky", label: "Nhật ký kiểm duyệt", icon: ClipboardText },
  { to: "/khu-thu-nghiem-ai", label: "Khu thử nghiệm AI", icon: Flask },
  { to: "/nguoi-dung", label: "Quản lý người dùng", icon: IdentificationBadge },
  { to: "/thong-bao", label: "Thông báo", icon: Megaphone },
  { to: "/cai-dat", label: "Cài đặt", icon: GearSix },
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
