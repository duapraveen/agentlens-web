import "./components.css";

export function Tabs({
  tabs,
  active,
  onChange,
}: {
  tabs: string[];
  active: string;
  onChange: (tab: string) => void;
}) {
  return (
    <div className="tabs">
      {tabs.map((tab) => (
        <button key={tab} data-active={tab === active} onClick={() => onChange(tab)}>
          {tab}
        </button>
      ))}
    </div>
  );
}
