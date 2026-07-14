import "./components.css";

const LABELS: Record<string, string> = { P0: "P0", P1: "P1", P2: "P2" };

export function SeverityBadge({ severity }: { severity: string }) {
  const cls = severity === "P0" ? "badge-p0" : severity === "P1" ? "badge-p1" : "badge-p2";
  return <span className={`badge ${cls}`}>{LABELS[severity] ?? severity}</span>;
}
