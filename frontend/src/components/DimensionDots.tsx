import { useRef, useState } from "react";
import { createPortal } from "react-dom";
import "./components.css";

export function DimensionDots({
  order,
  failed,
}: {
  order: string[];
  failed: Set<string> | string[];
}) {
  const failedSet = failed instanceof Set ? failed : new Set(failed);
  const dots = order.map((dim) => (failedSet.has(dim) ? "●" : "○")).join("");
  const anchorRef = useRef<HTMLSpanElement>(null);
  const [pos, setPos] = useState<{ top: number; left: number } | null>(null);

  const show = () => {
    const rect = anchorRef.current?.getBoundingClientRect();
    if (rect) setPos({ top: rect.bottom + 4, left: rect.left });
  };
  const hide = () => setPos(null);

  return (
    <span
      ref={anchorRef}
      className="dimension-dots-wrap"
      onMouseEnter={show}
      onMouseLeave={hide}
    >
      <span className="dimension-dots">{dots}</span>
      {pos &&
        createPortal(
          <div
            className="dimension-tooltip dimension-tooltip--portal"
            style={{ top: pos.top, left: pos.left }}
          >
            {order.map((dim) => (
              <div key={dim} className="dimension-tooltip__row">
                <span>{dim}</span>
                <span
                  style={{
                    color: failedSet.has(dim) ? "var(--severity-p0)" : "var(--color-primary)",
                    fontWeight: 700,
                  }}
                >
                  {failedSet.has(dim) ? "FAIL" : "PASS"}
                </span>
              </div>
            ))}
          </div>,
          document.body
        )}
    </span>
  );
}
