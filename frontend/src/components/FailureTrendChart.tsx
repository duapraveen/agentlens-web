import { useMemo, useState } from "react";
import type { FailureTrendPoint } from "../api/client";
import { Table, type Column } from "./Table";
import "./failure-trend-chart.css";

const WIDTH = 640;
const HEIGHT = 260;
const MARGIN = { top: 16, right: 16, bottom: 32, left: 44 };
const PLOT_WIDTH = WIDTH - MARGIN.left - MARGIN.right;
const PLOT_HEIGHT = HEIGHT - MARGIN.top - MARGIN.bottom;

const SERIES: { key: keyof FailureTrendPoint; label: string; color: string }[] = [
  { key: "overall_rate", label: "Overall", color: "var(--chart-overall)" },
  { key: "p0_rate", label: "P0", color: "var(--severity-p0)" },
  { key: "p1_rate", label: "P1", color: "var(--severity-p1)" },
  { key: "p2_rate", label: "P2", color: "var(--severity-p2)" },
];

function niceMax(actualMax: number): number {
  if (actualMax <= 0) return 0.1;
  const rounded = Math.ceil(actualMax * 10) / 10;
  return Math.min(1, Math.max(0.1, rounded));
}

function formatDate(iso: string): string {
  const [, month, day] = iso.split("-");
  return `${month}/${day}`;
}

export function FailureTrendChart({ points }: { points: FailureTrendPoint[] }) {
  const [hoverIndex, setHoverIndex] = useState<number | null>(null);
  const [showTable, setShowTable] = useState(false);

  const yMax = useMemo(
    () => niceMax(Math.max(0, ...points.map((p) => p.overall_rate))),
    [points]
  );

  if (points.length === 0) {
    return <p className="text-dense">No eval data yet — run evals from the Jobs page.</p>;
  }

  const xFor = (i: number) =>
    points.length > 1 ? (i / (points.length - 1)) * PLOT_WIDTH : PLOT_WIDTH / 2;
  const yFor = (rate: number) => PLOT_HEIGHT - (rate / yMax) * PLOT_HEIGHT;

  const linePath = (key: keyof FailureTrendPoint) =>
    points
      .map((p, i) => `${i === 0 ? "M" : "L"} ${xFor(i).toFixed(2)} ${yFor(p[key] as number).toFixed(2)}`)
      .join(" ");

  const gridTicks = [0, 0.25, 0.5, 0.75, 1].map((f) => f * yMax);

  const handleMove = (e: React.MouseEvent<SVGRectElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const relX = e.clientX - rect.left;
    const idx = Math.round((relX / PLOT_WIDTH) * (points.length - 1));
    setHoverIndex(Math.max(0, Math.min(points.length - 1, idx)));
  };

  const hovered = hoverIndex != null ? points[hoverIndex] : null;

  const tableColumns: Column<FailureTrendPoint>[] = [
    { key: "date", header: "Date", render: (p) => p.date },
    {
      key: "overall_rate",
      header: "Overall",
      numeric: true,
      render: (p) => `${Math.round(p.overall_rate * 100)}%`,
    },
    { key: "p0_rate", header: "P0", numeric: true, render: (p) => `${Math.round(p.p0_rate * 100)}%` },
    { key: "p1_rate", header: "P1", numeric: true, render: (p) => `${Math.round(p.p1_rate * 100)}%` },
    { key: "p2_rate", header: "P2", numeric: true, render: (p) => `${Math.round(p.p2_rate * 100)}%` },
  ];

  return (
    <div className="failure-trend-chart">
      <div className="failure-trend-chart__plot-wrap">
        <svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} className="failure-trend-chart__svg">
          <g transform={`translate(${MARGIN.left}, ${MARGIN.top})`}>
            {gridTicks.map((tick) => (
              <g key={tick}>
                <line
                  x1={0}
                  x2={PLOT_WIDTH}
                  y1={yFor(tick)}
                  y2={yFor(tick)}
                  className="failure-trend-chart__gridline"
                />
                <text x={-8} y={yFor(tick)} className="failure-trend-chart__tick" textAnchor="end" dy="0.32em">
                  {Math.round(tick * 100)}%
                </text>
              </g>
            ))}

            {points.map((p, i) => {
              const showLabel =
                points.length <= 7 || i === 0 || i === points.length - 1 || i % Math.ceil(points.length / 6) === 0;
              return showLabel ? (
                <text
                  key={p.date}
                  x={xFor(i)}
                  y={PLOT_HEIGHT + 20}
                  className="failure-trend-chart__tick"
                  textAnchor="middle"
                >
                  {formatDate(p.date)}
                </text>
              ) : null;
            })}

            {SERIES.map((s) => (
              <path key={s.key} d={linePath(s.key)} stroke={s.color} className="failure-trend-chart__line" fill="none" />
            ))}

            {SERIES.map((s) =>
              points.map((p, i) => (
                <circle
                  key={`${s.key}-${p.date}`}
                  cx={xFor(i)}
                  cy={yFor(p[s.key] as number)}
                  r={4}
                  fill={s.color}
                  className="failure-trend-chart__dot"
                />
              ))
            )}

            {hoverIndex != null && (
              <line
                x1={xFor(hoverIndex)}
                x2={xFor(hoverIndex)}
                y1={0}
                y2={PLOT_HEIGHT}
                className="failure-trend-chart__crosshair"
              />
            )}

            <rect
              x={0}
              y={0}
              width={PLOT_WIDTH}
              height={PLOT_HEIGHT}
              fill="transparent"
              onMouseMove={handleMove}
              onMouseLeave={() => setHoverIndex(null)}
            />
          </g>
        </svg>

        {hovered && (
          <div
            className="failure-trend-chart__tooltip"
            style={{
              left: `${(MARGIN.left + xFor(hoverIndex!)) / WIDTH * 100}%`,
            }}
          >
            <div className="failure-trend-chart__tooltip-date">{hovered.date}</div>
            {SERIES.map((s) => (
              <div key={s.key} className="failure-trend-chart__tooltip-row">
                <span className="failure-trend-chart__tooltip-key" style={{ background: s.color }} />
                <span className="text-dense">{s.label}</span>
                <strong className="failure-trend-chart__tooltip-value">
                  {Math.round((hovered[s.key] as number) * 100)}%
                </strong>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="failure-trend-chart__legend">
        {SERIES.map((s) => (
          <span key={s.key} className="failure-trend-chart__legend-item">
            <span className="failure-trend-chart__legend-swatch" style={{ background: s.color }} />
            {s.label}
          </span>
        ))}
      </div>

      <button className="btn btn-secondary" onClick={() => setShowTable((v) => !v)} style={{ marginTop: 8 }}>
        {showTable ? "Hide" : "View"} as table
      </button>
      {showTable && (
        <div style={{ marginTop: 8 }}>
          <Table columns={tableColumns} rows={points} rowKey={(p) => p.date} />
        </div>
      )}
    </div>
  );
}
