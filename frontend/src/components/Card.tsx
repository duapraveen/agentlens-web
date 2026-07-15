import type { ReactNode } from "react";
import "./components.css";
import { severityColorVar } from "../severity";

export function Card({
  children,
  clickable = false,
  onClick,
  tint = "default",
  severity,
}: {
  children: ReactNode;
  clickable?: boolean;
  onClick?: () => void;
  tint?: "default" | "strong";
  severity?: string;
}) {
  const cls = ["card", clickable && "card--clickable", tint === "strong" && "card--strong"]
    .filter(Boolean)
    .join(" ");
  const style = severity ? { borderLeft: `4px solid ${severityColorVar(severity)}` } : undefined;
  return (
    <div className={cls} style={style} onClick={onClick}>
      {children}
    </div>
  );
}
