import "./components.css";
import { severityColorVar } from "../severity";

export function SeverityDot({ severity }: { severity: string }) {
  return (
    <span
      className="severity-dot"
      style={{ backgroundColor: severityColorVar(severity) }}
      aria-hidden="true"
    />
  );
}
