import "./components.css";

export function Skeleton({ lines = 1, height = 16 }: { lines?: number; height?: number }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      {Array.from({ length: lines }).map((_, i) => (
        <div key={i} className="skeleton" style={{ height, width: "100%" }} />
      ))}
    </div>
  );
}
