import { useEffect, useRef } from "react";
import { Navigate, Outlet, useLocation } from "react-router-dom";
import { useAuth } from "./AuthProvider.jsx";
import { useToast } from "../components/ToastProvider.jsx";
import { PAGE_TITLES } from "../lib/navigation.js";

/**
 * Route gate for admin-only pages.
 *
 * The redirect used to be silent: a Mod who followed a bookmark or a shared
 * link simply appeared on the overview page with no explanation, which reads as
 * the app losing the navigation rather than refusing it. It now says why.
 */
export default function RequireRole({ role, roles }) {
  const { user } = useAuth();
  const location = useLocation();
  const toast = useToast();
  const acceptedRoles = roles ?? [role];
  const allowed = acceptedRoles.includes(user?.role);
  // StrictMode double-invokes effects in development; without this the same
  // refusal would raise two identical toasts.
  const announced = useRef(false);

  useEffect(() => {
    if (allowed || announced.current) return;
    announced.current = true;
    const page = PAGE_TITLES[location.pathname];
    toast.info(
      page
        ? `Bạn không có quyền mở trang “${page}”. Đã đưa bạn về Tổng quan.`
        : "Bạn không có quyền mở trang này. Đã đưa bạn về Tổng quan.",
    );
  }, [allowed, location.pathname, toast]);

  return allowed ? <Outlet /> : <Navigate to="/tong-quan" replace />;
}
