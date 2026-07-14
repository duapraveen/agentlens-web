import { NavLink, Outlet } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { useRole } from "../context/RoleContext";
import { PAGES_BY_ROLE, NAV_ROUTES } from "../constants";
import { fetchStatus } from "../api/client";
import "./app-shell.css";

export function AppShell() {
  const { role, setRole } = useRole();
  const { data: status } = useQuery({ queryKey: ["status"], queryFn: fetchStatus });

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <h1 className="sidebar__title">AgentLens</h1>
        <select
          className="select"
          value={role}
          onChange={(e) => setRole(e.target.value as typeof role)}
        >
          <option value="Engineer">Engineer</option>
          <option value="Reviewer">Reviewer</option>
          <option value="Lead">Lead</option>
        </select>
        <hr />
        <nav>
          {PAGES_BY_ROLE[role].map((title) => (
            <NavLink
              key={title}
              to={NAV_ROUTES[title]}
              end={NAV_ROUTES[title] === "/"}
              className={({ isActive }) => `nav-link${isActive ? " nav-link--active" : ""}`}
            >
              {title}
            </NavLink>
          ))}
        </nav>
        <hr />
        {status && (
          <p className="sidebar__status text-dense">
            Last eval run: {status.last_eval_at ? new Date(status.last_eval_at).toLocaleString() : "never"}
            <br />
            Corpus calls: {status.n_calls}
            <br />
            Golden calls: {status.n_golden}
          </p>
        )}
      </aside>
      <main className="content">
        <Outlet />
      </main>
    </div>
  );
}
