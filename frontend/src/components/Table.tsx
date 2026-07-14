import "./components.css";

export interface Column<Row> {
  key: string;
  header: string;
  render: (row: Row) => React.ReactNode;
  numeric?: boolean;
}

export function Table<Row>({
  columns,
  rows,
  rowKey,
  onRowClick,
}: {
  columns: Column<Row>[];
  rows: Row[];
  rowKey: (row: Row) => string;
  onRowClick?: (row: Row) => void;
}) {
  return (
    <div style={{ overflowX: "auto" }}>
      <table className="al-table">
        <thead>
          <tr>
            {columns.map((col) => (
              <th key={col.key}>{col.header}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr
              key={rowKey(row)}
              data-clickable={Boolean(onRowClick)}
              onClick={() => onRowClick?.(row)}
            >
              {columns.map((col) => (
                <td key={col.key} className={col.numeric ? "numeric" : undefined}>
                  {col.render(row)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
