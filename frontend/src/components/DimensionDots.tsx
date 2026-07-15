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
  return (
    <span className="dimension-dots-wrap">
      <span className="dimension-dots">{dots}</span>
      <div className="dimension-tooltip">
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
      </div>
    </span>
  );
}
