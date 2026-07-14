import "./components.css";

export function StatTile({
  label,
  value,
  sublabel,
}: {
  label: string;
  value: string;
  sublabel?: string;
}) {
  return (
    <div className="stat-tile">
      <span className="stat-tile__value numeric">{value}</span>
      <span className="stat-tile__label">{label}</span>
      {sublabel && <span className="stat-tile__label">{sublabel}</span>}
    </div>
  );
}
