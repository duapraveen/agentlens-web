import { Navigate } from "react-router-dom";
import { useRole } from "../context/RoleContext";
import { DEFAULT_ROUTE_BY_ROLE } from "../constants";

export function DefaultLanding() {
  const { role } = useRole();
  return <Navigate to={DEFAULT_ROUTE_BY_ROLE[role]} replace />;
}
