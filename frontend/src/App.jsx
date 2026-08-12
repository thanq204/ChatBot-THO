import { Navigate, Route, Routes } from "react-router-dom";
import AppLayout from "./layouts/AppLayout.jsx";
import OverviewPage from "./pages/OverviewPage.jsx";
import AiSandboxPage from "./pages/AiSandboxPage.jsx";
import CommunityPage from "./pages/CommunityPage.jsx";
import PolicyPage from "./pages/PolicyPage.jsx";
import ModerationLogPage from "./pages/ModerationLogPage.jsx";
import UserManagementPage from "./pages/UserManagementPage.jsx";
import SettingsPage from "./pages/SettingsPage.jsx";

export default function App() {
  return (
    <Routes>
      <Route element={<AppLayout />}>
        <Route path="/" element={<OverviewPage />} />
        <Route path="/cong-dong" element={<CommunityPage />} />
        <Route path="/quy-tac-ai" element={<PolicyPage />} />
        <Route path="/nhat-ky" element={<ModerationLogPage />} />
        <Route path="/khu-thu-nghiem-ai" element={<AiSandboxPage />} />
        <Route path="/nguoi-dung" element={<UserManagementPage />} />
        <Route path="/cai-dat" element={<SettingsPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
