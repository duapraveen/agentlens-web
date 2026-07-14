import { createContext, useContext, useState, type ReactNode } from "react";

export type Role = "Engineer" | "Reviewer" | "Lead";

const ROLE_KEY = "agentlens.role";

interface RoleContextValue {
  role: Role;
  setRole: (role: Role) => void;
}

const RoleContext = createContext<RoleContextValue | null>(null);

export function RoleProvider({ children }: { children: ReactNode }) {
  const [role, setRoleState] = useState<Role>(() => {
    const stored = sessionStorage.getItem(ROLE_KEY);
    return stored === "Engineer" || stored === "Reviewer" || stored === "Lead"
      ? stored
      : "Engineer";
  });

  const setRole = (next: Role) => {
    sessionStorage.setItem(ROLE_KEY, next);
    setRoleState(next);
  };

  return <RoleContext.Provider value={{ role, setRole }}>{children}</RoleContext.Provider>;
}

export function useRole(): RoleContextValue {
  const ctx = useContext(RoleContext);
  if (!ctx) throw new Error("useRole must be used within a RoleProvider");
  return ctx;
}
