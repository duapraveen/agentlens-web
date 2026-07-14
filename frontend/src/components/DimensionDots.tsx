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
  return <span className="dimension-dots">{dots}</span>;
}
