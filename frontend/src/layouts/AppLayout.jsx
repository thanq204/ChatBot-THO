import { useEffect, useState } from "react";
import { Link, Outlet, useLocation } from "react-router-dom";
import Sidebar from "../components/Sidebar.jsx";
import Topbar from "../components/Topbar.jsx";

// Must stay in sync with NAV_ITEMS in components/Sidebar.jsx.
const PAGE_TITLES = {
  "/tong-quan": "Tổng quan",
  "/cong-dong": "Cộng đồng",
  "/nhat-ky": "Nhật ký kiểm duyệt",
  "/khu-thu-nghiem-ai": "Khu thử nghiệm AI",
  "/quan-ly-mod": "Quản lý Mod",
  "/quan-ly-faq": "Quản lý FAQ",
  "/bang-uy-tin": "Bảng uy tín",
  "/thong-bao": "Thông báo",
  "/quan-ly-noi-dung": "Quản lý nội dung",
  "/lenh-bot": "Nội dung lệnh bot",
};

const SIDEBAR_COLLAPSED_KEY = "acm-sidebar-collapsed";
// Below this, .sidebar switches to a fixed off-canvas drawer (see styles.css),
// so the same button must drive a different piece of state there.
const MOBILE_BREAKPOINT = 768;

export default function AppLayout() {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(() => {
    try { return window.localStorage.getItem(SIDEBAR_COLLAPSED_KEY) === "1"; } catch { return false; }
  });
  const location = useLocation();
  const pageTitle = PAGE_TITLES[location.pathname] ?? "Tổng quan";

  useEffect(() => {
    try { window.localStorage.setItem(SIDEBAR_COLLAPSED_KEY, sidebarCollapsed ? "1" : "0"); } catch { /* ignore */ }
  }, [sidebarCollapsed]);

  const toggleSidebar = () => {
    if (window.innerWidth <= MOBILE_BREAKPOINT) setSidebarOpen((open) => !open);
    else setSidebarCollapsed((collapsed) => !collapsed);
  };

  return (
    <div className={["app-shell", sidebarOpen && "app-shell--sidebar-open", sidebarCollapsed && "app-shell--sidebar-collapsed"].filter(Boolean).join(" ")}>
      <Sidebar open={sidebarOpen} onNavigate={() => setSidebarOpen(false)} />
      {sidebarOpen && (
        <button
          type="button"
          className="app-shell__scrim"
          aria-label="Đóng menu"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      <div className="app-shell__main">
        <Topbar
          breadcrumb={
            <span>
              <Link to="/" className="breadcrumb__home">Trang chủ</Link>{" "}
              <span className="breadcrumb__sep">/</span> <strong>{pageTitle}</strong>
            </span>
          }
          onMenuClick={toggleSidebar}
          menuLabel={sidebarCollapsed ? "Mở rộng menu" : "Thu gọn menu"}
        />
        <main className="app-shell__content">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
