import { Navigate, Route, Routes } from "react-router-dom";
import AppLayout from "./layouts/AppLayout.jsx";
import RequireAuth from "./auth/RequireAuth.jsx";
import LandingPage from "./pages/LandingPage.jsx";
import LoginPage from "./pages/LoginPage.jsx";
import OverviewPage from "./pages/OverviewPage.jsx";
import AiSandboxPage from "./pages/AiSandboxPage.jsx";
import CommunityPage from "./pages/CommunityPage.jsx";
import PolicyPage from "./pages/PolicyPage.jsx";
import ModerationLogPage from "./pages/ModerationLogPage.jsx";
import ModManagementPage from "./pages/ModManagementPage.jsx";
import NotificationPage from "./pages/NotificationPage.jsx";
import SettingsPage from "./pages/SettingsPage.jsx";
import BotCommandsPage from "./pages/BotCommandsPage.jsx";

export default function App() {
  return (
    <Routes>
      {/* Public surface: no sidebar, no topbar. */}
      <Route path="/" element={<LandingPage />} />
      <Route path="/login" element={<LoginPage />} />

      {/* Dashboard sits behind the mock session and off "/" so the landing
          page can own the root. */}
      <Route element={<RequireAuth />}>
        <Route element={<AppLayout />}>
          <Route path="/tong-quan" element={<OverviewPage />} />
          <Route path="/cong-dong" element={<CommunityPage />} />
          <Route path="/quy-tac-ai" element={<PolicyPage />} />
          <Route path="/nhat-ky" element={<ModerationLogPage />} />
          <Route path="/khu-thu-nghiem-ai" element={<AiSandboxPage />} />
          <Route path="/quan-ly-mod" element={<ModManagementPage />} />
          <Route path="/thong-bao" element={<NotificationPage />} />
          <Route path="/quan-ly-noi-dung" element={<SettingsPage />} />
          <Route path="/lenh-bot" element={<BotCommandsPage />} />
        </Route>
      </Route>

      {/* Unknown paths land on the marketing page, never on the login gate. */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
