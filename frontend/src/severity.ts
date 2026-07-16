const SEVERITY_ORDER = ["P0", "P1", "P2"];

export function severityRank(severity: string): number {
  const i = SEVERITY_ORDER.indexOf(severity);
  return i === -1 ? SEVERITY_ORDER.length : i;
}

export function severityColorVar(severity: string): string {
  if (severity === "P0") return "var(--severity-p0)";
  if (severity === "P1") return "var(--severity-p1)";
  if (severity === "P2") return "var(--severity-p2)";
  return "var(--severity-none)";
}
