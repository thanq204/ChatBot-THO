import { Navigate, Outlet } from "react-router-dom";
import { useAuth } from "./AuthProvider.jsx";

export default function RequireRole({ role }) {
  const { user } = useAuth();
  return user?.role === role ? <Outlet /> : <Navigate to="/tong-quan" replace />;
}
