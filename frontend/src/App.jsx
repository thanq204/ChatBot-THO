import { Navigate, Route, Routes } from "react-router-dom";
import AppLayout from "./layouts/AppLayout.jsx";
import OverviewPage from "./pages/OverviewPage.jsx";
import AiSandboxPage from "./pages/AiSandboxPage.jsx";
import ComingSoonPage from "./pages/ComingSoonPage.jsx";

export default function App() {
  return (
    <Routes>
      <Route element={<AppLayout />}>
        <Route path="/" element={<OverviewPage />} />
        <Route path="/cong-dong" element={<ComingSoonPage title="Cộng đồng" />} />
        <Route path="/quy-tac-ai" element={<ComingSoonPage title="Quy tắc AI" />} />
        <Route path="/nhat-ky" element={<ComingSoonPage title="Nhật ký kiểm duyệt" />} />
        <Route path="/khu-thu-nghiem-ai" element={<AiSandboxPage />} />
        <Route path="/nguoi-dung" element={<ComingSoonPage title="Quản lý người dùng" />} />
        <Route path="/cai-dat" element={<ComingSoonPage title="Cài đặt" />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
