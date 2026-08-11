import { Navigate, Route, Routes } from "react-router-dom";
import Layout from "./components/Layout.jsx";
import OperationsPage from "./pages/OperationsPage.jsx";
import MemberPage from "./pages/MemberPage.jsx";
import ReviewQueuePage from "./pages/ReviewQueuePage.jsx";

export default function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Navigate to="/operations" replace />} />
        <Route path="/operations" element={<OperationsPage />} />
        <Route path="/member" element={<MemberPage />} />
        <Route path="/review-queue" element={<ReviewQueuePage />} />
        {/* Legacy paths from the server-rendered build. */}
        <Route path="/admin" element={<Navigate to="/operations" replace />} />
        <Route path="/moderation-admin" element={<Navigate to="/review-queue" replace />} />
        <Route path="*" element={<Navigate to="/operations" replace />} />
      </Routes>
    </Layout>
  );
}
