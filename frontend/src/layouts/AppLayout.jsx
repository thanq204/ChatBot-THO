import { useEffect, useState } from "react";
import { Link, Outlet, useLocation } from "react-router-dom";
import Sidebar from "../components/Sidebar.jsx";
import Topbar from "../components/Topbar.jsx";
import { PAGE_TITLES } from "../lib/navigation.js";

const SIDEBAR_COLLAPSED_KEY = "acm-sidebar-collapsed";
// Below this, .sidebar switches to a fixed off-canvas drawer (see styles.css),
// so the same button must drive a different piece of state there.
const MOBILE_BREAKPOINT = 768;

export default function AppLayout() {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(() => {
    try { return window.localStorage.getItem(SIDEBAR_COLLAPSED_KEY) === "1"; } catch { return false; }
  });
  // Both hidden states only clip the sidebar visually — width:0 on desktop, an
  // off-canvas transform on mobile — so without `inert` its eleven links stay
  // in the tab order and a keyboard user walks through invisible controls.
  const [isMobile, setIsMobile] = useState(() => window.innerWidth <= MOBILE_BREAKPOINT);
  const location = useLocation();
  const pageTitle = PAGE_TITLES[location.pathname] ?? "Tổng quan";

  useEffect(() => {
    try { window.localStorage.setItem(SIDEBAR_COLLAPSED_KEY, sidebarCollapsed ? "1" : "0"); } catch { /* ignore */ }
  }, [sidebarCollapsed]);

  useEffect(() => {
    const media = window.matchMedia(`(max-width: ${MOBILE_BREAKPOINT}px)`);
    const onChange = (event) => setIsMobile(event.matches);
    setIsMobile(media.matches);
    media.addEventListener("change", onChange);
    return () => media.removeEventListener("change", onChange);
  }, []);

  const sidebarHidden = isMobile ? !sidebarOpen : sidebarCollapsed;

  const toggleSidebar = () => {
    if (isMobile) setSidebarOpen((open) => !open);
    else setSidebarCollapsed((collapsed) => !collapsed);
  };

  return (
    <div className={["app-shell", sidebarOpen && "app-shell--sidebar-open", sidebarCollapsed && "app-shell--sidebar-collapsed"].filter(Boolean).join(" ")}>
      <a className="skip-link" href="#noi-dung-chinh">Bỏ qua điều hướng, tới nội dung chính</a>
      <Sidebar open={sidebarOpen} hidden={sidebarHidden} onNavigate={() => setSidebarOpen(false)} />
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
        <main className="app-shell__content" id="noi-dung-chinh" tabIndex={-1}>
          <Outlet />
        </main>
      </div>
    </div>
  );
}
