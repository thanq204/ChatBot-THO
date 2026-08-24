import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  List,
  MagnifyingGlass,
  ChatCircleDots,
  Bell,
  CaretDown,
  Moon,
  PencilSimple,
  SignOut,
  Sun,
  UserCircle,
} from "@phosphor-icons/react";
import { useAuth } from "../auth/AuthProvider.jsx";
import { useTheme } from "../theme/ThemeProvider.jsx";
import ProfileModal from "./ProfileModal.jsx";

export default function Topbar({ breadcrumb, onMenuClick, menuLabel = "Mở menu" }) {
  const { theme, toggleTheme } = useTheme();
  const { user, signOut } = useAuth();
  const navigate = useNavigate();
  const [menuOpen, setMenuOpen] = useState(false);
  const [profileOpen, setProfileOpen] = useState(false);
  const menuRef = useRef(null);

  const handleSignOut = () => {
    signOut();
    navigate("/", { replace: true });
  };

  useEffect(() => {
    if (!menuOpen) return undefined;
    const handleClick = (event) => { if (!menuRef.current?.contains(event.target)) setMenuOpen(false); };
    const handleKeyDown = (event) => { if (event.key === "Escape") setMenuOpen(false); };
    document.addEventListener("mousedown", handleClick);
    document.addEventListener("keydown", handleKeyDown);
    return () => { document.removeEventListener("mousedown", handleClick); document.removeEventListener("keydown", handleKeyDown); };
  }, [menuOpen]);

  const openProfile = useCallback(() => { setMenuOpen(false); setProfileOpen(true); }, []);

  return (
    <header className="topbar">
      <div className="topbar__left">
        <button type="button" className="icon-btn topbar__menu" onClick={onMenuClick} aria-label={menuLabel} title={menuLabel}>
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

        <div className="account" ref={menuRef}>
          <button
            type="button"
            className="account__trigger"
            onClick={() => setMenuOpen((open) => !open)}
            aria-haspopup="menu"
            aria-expanded={menuOpen}
          >
            <UserCircle size={26} weight="fill" />
            <span className="account__meta">
              <span className="account__name">{user?.display_name ?? "Khách"}</span>
              <span className="account__role">{user?.role === "admin" ? "Quản trị viên" : user?.role === "mod" ? "Kiểm duyệt viên" : "Chưa đăng nhập"}</span>
            </span>
            <CaretDown size={13} weight="bold" className="account__caret" />
          </button>

          {menuOpen && (
            <div className="account-menu" role="menu">
              <div className="account-menu__header">
                <span className="account-menu__name">{user?.display_name ?? "Khách"}</span>
                <span className="muted small">{user?.email}</span>
              </div>
              <button type="button" className="account-menu__item" role="menuitem" onClick={openProfile}>
                <PencilSimple size={16} /> Chỉnh sửa hồ sơ
              </button>
              <button type="button" className="account-menu__item account-menu__item--danger" role="menuitem" onClick={handleSignOut}>
                <SignOut size={16} /> Đăng xuất
              </button>
            </div>
          )}
        </div>
      </div>

      <ProfileModal open={profileOpen} onClose={() => setProfileOpen(false)} />
    </header>
  );
}
