import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  List,
  MagnifyingGlass,
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
import { searchNav } from "../lib/navigation.js";
import ProfileModal from "./ProfileModal.jsx";

export default function Topbar({ breadcrumb, onMenuClick, menuLabel = "Mở menu" }) {
  const { theme, toggleTheme } = useTheme();
  const { user, signOut } = useAuth();
  const navigate = useNavigate();
  const [menuOpen, setMenuOpen] = useState(false);
  const [profileOpen, setProfileOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [highlight, setHighlight] = useState(0);
  const menuRef = useRef(null);
  const searchRef = useRef(null);

  const results = useMemo(() => searchNav(query, user?.role), [query, user?.role]);
  const searchOpen = query.trim().length > 0;

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

  useEffect(() => { setHighlight(0); }, [query]);

  useEffect(() => {
    if (!searchOpen) return undefined;
    const handleClick = (event) => { if (!searchRef.current?.contains(event.target)) setQuery(""); };
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [searchOpen]);

  // Ctrl/Cmd+K from anywhere. An operator on the case queue should not have to
  // reach for the mouse to jump to the audit log.
  useEffect(() => {
    const onKeyDown = (event) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        searchRef.current?.querySelector("input")?.focus();
      }
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, []);

  const go = useCallback((to) => {
    setQuery("");
    navigate(to);
  }, [navigate]);

  const onSearchKeyDown = (event) => {
    if (event.key === "Escape") { setQuery(""); event.currentTarget.blur(); return; }
    if (results.length === 0) return;
    if (event.key === "ArrowDown") { event.preventDefault(); setHighlight((i) => (i + 1) % results.length); }
    else if (event.key === "ArrowUp") { event.preventDefault(); setHighlight((i) => (i - 1 + results.length) % results.length); }
    else if (event.key === "Enter") { event.preventDefault(); go(results[highlight].to); }
  };

  const openProfile = useCallback(() => { setMenuOpen(false); setProfileOpen(true); }, []);

  return (
    <header className="topbar">
      <div className="topbar__left">
        <button type="button" className="icon-btn topbar__menu" onClick={onMenuClick} aria-label={menuLabel} title={menuLabel}>
          <List size={20} weight="bold" />
        </button>

        <div className="search" ref={searchRef}>
          <label className="search__field">
            <MagnifyingGlass size={17} />
            <input
              type="search"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              onKeyDown={onSearchKeyDown}
              placeholder="Tìm trang..."
              aria-label="Tìm trang"
              aria-expanded={searchOpen}
              aria-controls="topbar-search-results"
              role="combobox"
              aria-autocomplete="list"
            />
            <kbd className="search__hint" aria-hidden="true">Ctrl K</kbd>
          </label>

          {searchOpen && (
            <div className="search-results" id="topbar-search-results" role="listbox">
              {results.length === 0 ? (
                <p className="search-results__empty">Không có trang nào khớp “{query}”.</p>
              ) : (
                results.map((item, index) => {
                  const Icon = item.icon;
                  return (
                    <button
                      key={item.to}
                      type="button"
                      role="option"
                      aria-selected={index === highlight}
                      className={`search-results__item ${index === highlight ? "is-active" : ""}`.trim()}
                      onMouseEnter={() => setHighlight(index)}
                      onClick={() => go(item.to)}
                    >
                      <Icon size={16} />
                      {item.label}
                    </button>
                  );
                })
              )}
            </div>
          )}
        </div>
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

        <button
          type="button"
          className="icon-btn"
          onClick={() => navigate("/thong-bao")}
          aria-label="Thông báo"
          title="Thông báo"
        >
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
