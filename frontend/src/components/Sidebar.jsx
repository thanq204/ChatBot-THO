import { NavLink } from "react-router-dom";
import { useAuth } from "../auth/AuthProvider.jsx";
import { navItemsFor } from "../lib/navigation.js";
import { BRAND } from "../lib/brand.js";

export default function Sidebar({ open, hidden, onNavigate }) {
  const { user } = useAuth();
  return (
    <aside
      className={`sidebar ${open ? "sidebar--open" : ""}`}
      // `inert` takes the clipped-but-still-focusable links out of the tab
      // order and off the accessibility tree while the sidebar is hidden.
      inert={hidden ? "" : undefined}
      aria-hidden={hidden ? "true" : undefined}
    >
      <div className="sidebar__brand">
        <span className="sidebar__logo">{BRAND.name}</span>
        <span className="sidebar__subtitle">{BRAND.dashboardSubtitle}</span>
      </div>

      <nav className="sidebar__nav" aria-label="Điều hướng chính">
        {navItemsFor(user?.role).map(({ to, label, icon: Icon, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            onClick={onNavigate}
            className={({ isActive }) => `sidebar__link ${isActive ? "sidebar__link--active" : ""}`}
          >
            <Icon size={19} weight="regular" />
            <span>{label}</span>
          </NavLink>
        ))}
      </nav>
    </aside>
  );
}
