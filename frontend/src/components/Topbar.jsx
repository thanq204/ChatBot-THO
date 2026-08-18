import { useNavigate } from "react-router-dom";
import {
  List,
  MagnifyingGlass,
  ChatCircleDots,
  Bell,
  Moon,
  SignOut,
  Sun,
  UserCircle,
} from "@phosphor-icons/react";
import { useAuth } from "../auth/AuthProvider.jsx";
import { useTheme } from "../theme/ThemeProvider.jsx";

export default function Topbar({ breadcrumb, onMenuClick }) {
  const { theme, toggleTheme } = useTheme();
  const { user, signOut } = useAuth();
  const navigate = useNavigate();

  const handleSignOut = () => {
    signOut();
    navigate("/", { replace: true });
  };

  return (
    <header className="topbar">
      <div className="topbar__left">
        <button type="button" className="icon-btn topbar__menu" onClick={onMenuClick} aria-label="Mở menu">
          <List size={20} weight="bold" />
        </button>

        <label className="search">
          <MagnifyingGlass size={17} />
          <input type="search" placeholder="Tìm kiếm..." aria-label="Tìm kiếm" />
        </label>
      </div>

      <div className="topbar__right">
        {breadcrumb && <nav className="breadcrumb" aria-label="Đường dẫn">{breadcrumb}</nav>}

        <button
          type="button"
          className="icon-btn"
          onClick={toggleTheme}
          aria-label={theme === "dark" ? "Chuyển sang giao diện sáng" : "Chuyển sang giao diện tối"}
          title={theme === "dark" ? "Giao diện sáng" : "Giao diện tối"}
        >
          {theme === "dark" ? <Sun size={19} weight="bold" /> : <Moon size={19} weight="bold" />}
        </button>

        <button type="button" className="icon-btn" aria-label="Tin nhắn">
          <ChatCircleDots size={19} />
        </button>
        <button type="button" className="icon-btn" aria-label="Thông báo">
          <Bell size={19} />
        </button>

        <div className="account">
          <UserCircle size={26} weight="fill" />
          <span className="account__meta">
            <span className="account__name">{user?.display_name ?? "Khách"}</span>
            <span className="account__role">{user?.role === "admin" ? "Quản trị viên" : user?.role === "mod" ? "Kiểm duyệt viên" : "Chưa đăng nhập"}</span>
          </span>
          <button type="button" className="icon-btn" onClick={handleSignOut} aria-label="Đăng xuất" title="Đăng xuất">
            <SignOut size={18} />
          </button>
        </div>
      </div>
    </header>
  );
}
