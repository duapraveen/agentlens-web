import type { Role } from "./context/RoleContext";

export const PAGES_BY_ROLE: Record<Role, string[]> = {
  Engineer: ["Overview", "Conversations", "Clusters", "Fix Workbench", "Jobs"],
  Reviewer: ["Overview", "Conversations", "Review Queue"],
  Lead: ["Overview", "Conversations", "Clusters"],
};

export const NAV_ROUTES: Record<string, string> = {
  Overview: "/overview",
  Conversations: "/conversations",
  Clusters: "/clusters",
  "Review Queue": "/review-queue",
  "Fix Workbench": "/fix-workbench",
  Jobs: "/jobs",
};

export const DEFAULT_ROUTE_BY_ROLE: Record<Role, string> = {
  Engineer: "/overview",
  Reviewer: "/review-queue",
  Lead: "/overview",
};

export const DIMENSION_ORDER = [
  "task_completion",
  "factual_accuracy",
  "safety_compliance",
  "communication_quality",
];
