import { Suspense, lazy } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import AppLayout from "./layouts/AppLayout.jsx";
import RequireAuth from "./auth/RequireAuth.jsx";
import RequireRole from "./auth/RequireRole.jsx";
import { SkeletonBlock } from "./components/Skeleton.jsx";

/**
 * Every route is split out of the entry bundle.
 *
 * Loading them statically meant a visitor to the dashboard also downloaded and
 * parsed the marketing page along with its sakura field and agent-flow
 * animation, and vice versa. Each route now arrives as its own chunk, fetched
 * the first time it is opened and cached by the browser after that.
 */
const LandingPage = lazy(() => import("./pages/LandingPage.jsx"));
const LoginPage = lazy(() => import("./pages/LoginPage.jsx"));
const OverviewPage = lazy(() => import("./pages/OverviewPage.jsx"));
const AiSandboxPage = lazy(() => import("./pages/AiSandboxPage.jsx"));
const CommunityPage = lazy(() => import("./pages/CommunityPage.jsx"));
const ModerationLogPage = lazy(() => import("./pages/ModerationLogPage.jsx"));
const ModManagementPage = lazy(() => import("./pages/ModManagementPage.jsx"));
const NotificationPage = lazy(() => import("./pages/NotificationPage.jsx"));
const SettingsPage = lazy(() => import("./pages/SettingsPage.jsx"));
const BotCommandsPage = lazy(() => import("./pages/BotCommandsPage.jsx"));
const FaqManagementPage = lazy(() => import("./pages/FaqManagementPage.jsx"));
const ReputationPage = lazy(() => import("./pages/ReputationPage.jsx"));

/** Shown only while a route's chunk is in flight, which is once per route. */
function RouteFallback() {
  return (
    <div className="page-grid">
      <SkeletonBlock height={220} />
    </div>
  );
}

export default function App() {
  return (
    <Suspense fallback={<RouteFallback />}>
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
            <Route element={<RequireRole role="admin" />}>
              <Route path="/nhat-ky" element={<ModerationLogPage />} />
              <Route path="/quan-ly-mod" element={<ModManagementPage />} />
              <Route path="/quan-ly-faq" element={<FaqManagementPage />} />
              <Route path="/bang-uy-tin" element={<ReputationPage />} />
            </Route>
            <Route path="/khu-thu-nghiem-ai" element={<AiSandboxPage />} />
            <Route path="/thong-bao" element={<NotificationPage />} />
            <Route path="/quan-ly-noi-dung" element={<SettingsPage />} />
            <Route path="/lenh-bot" element={<BotCommandsPage />} />
          </Route>
        </Route>

        {/* Unknown paths land on the marketing page, never on the login gate. */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Suspense>
  );
}
