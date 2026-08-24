import { useState } from "react";
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
  "/bang-exp": "Bảng EXP",
  "/nguoi-ban": "Độ tin cậy người bán",
  "/thong-bao": "Thông báo",
  "/quan-ly-noi-dung": "Quản lý nội dung",
  "/lenh-bot": "Nội dung lệnh bot",
};

export default function AppLayout() {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const location = useLocation();
  const pageTitle = PAGE_TITLES[location.pathname] ?? "Tổng quan";

  return (
    <div className={`app-shell ${sidebarOpen ? "app-shell--sidebar-open" : ""}`}>
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
          onMenuClick={() => setSidebarOpen((open) => !open)}
        />
        <main className="app-shell__content">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
