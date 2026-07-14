import type { ReactNode } from "react";
import "./components.css";

export function Card({
  children,
  clickable = false,
  onClick,
}: {
  children: ReactNode;
  clickable?: boolean;
  onClick?: () => void;
}) {
  return (
    <div className={`card${clickable ? " card--clickable" : ""}`} onClick={onClick}>
      {children}
    </div>
  );
}
