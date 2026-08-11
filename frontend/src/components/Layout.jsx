import { ChatCircleTextIcon, ChartLineUpIcon, ShieldCheckIcon } from "@phosphor-icons/react";
import { NavLink } from "react-router-dom";

const LINKS = [
  { to: "/operations", label: "Operations", icon: ChartLineUpIcon },
  { to: "/review-queue", label: "Review queue", icon: ShieldCheckIcon },
  { to: "/member", label: "Member", icon: ChatCircleTextIcon },
];

export default function Layout({ children }) {
  return (
    <>
      <header className="topbar">
        <a className="brand" href="/operations">
          <span className="brand-mark">CO</span>
          <span>
            <span>Community operations</span>
            <strong>Operations Copilot</strong>
          </span>
        </a>
        <div className="topbar-right">
          <span className="status-chip">
            <i />
            Local workspace
          </span>
          <nav>
            {LINKS.map((link) => (
              <NavLink
                key={link.to}
                to={link.to}
                className={({ isActive }) => `icon-btn${isActive ? " active" : ""}`}
              >
                <link.icon size={15} weight="bold" />
                {link.label}
              </NavLink>
            ))}
          </nav>
        </div>
      </header>
      <main className="layout">{children}</main>
      <footer className="footer">
        <span>Community Operations Copilot</span>
        <span>Human judgment, assisted by AI.</span>
      </footer>
    </>
  );
}
