import "./components.css";

const LABELS: Record<string, string> = { P0: "P0", P1: "P1", P2: "P2" };
const CLASSES: Record<string, string> = { P0: "badge-p0", P1: "badge-p1", P2: "badge-p2" };

export function SeverityBadge({ severity }: { severity: string }) {
  const cls = CLASSES[severity] ?? "badge-none";
  return <span className={`badge ${cls}`}>{LABELS[severity] ?? severity}</span>;
}
