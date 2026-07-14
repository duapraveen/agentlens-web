import { useQuery } from "@tanstack/react-query";
import { useNavigate, useSearchParams } from "react-router-dom";
import { fetchConversations } from "../api/client";
import type { ConversationRow } from "../api/client";
import { Table, type Column } from "../components/Table";
import { Pagination } from "../components/Pagination";
import { DimensionDots } from "../components/DimensionDots";
import { Skeleton } from "../components/Skeleton";
import { DIMENSION_ORDER } from "../constants";

const PAGE_SIZE = 25;

export function Conversations() {
  const [params, setParams] = useSearchParams();
  const navigate = useNavigate();

  const severity = params.get("severity") ?? undefined;
  const dimension = params.get("dimension") ?? undefined;
  const clusterId = params.get("cluster_id") ? Number(params.get("cluster_id")) : undefined;
  const outcome = (params.get("outcome") as "pass" | "fail" | null) ?? undefined;
  const page = Number(params.get("page") ?? "0");

  const { data, isLoading } = useQuery({
    queryKey: ["conversations", severity, dimension, clusterId, outcome, page],
    queryFn: () => fetchConversations({ severity, dimension, clusterId, outcome, page }),
  });

  const setFilter = (key: string, value: string) => {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value);
    else next.delete(key);
    next.set("page", "0");
    setParams(next);
  };

  const columns: Column<ConversationRow>[] = [
    { key: "id", header: "ID", render: (r) => r.call_id },
    { key: "scenario", header: "Scenario", render: (r) => r.scenario },
    {
      key: "fails",
      header: "Fails",
      render: (r) => <DimensionDots order={DIMENSION_ORDER} failed={r.failed_dimensions} />,
    },
    { key: "p0", header: "P0", render: (r) => (r.has_p0 ? "⚠" : "") },
    { key: "score", header: "Avg Score", render: (r) => r.avg_score.toFixed(1), numeric: true },
    { key: "cost", header: "Cost (est ¢)", render: (r) => r.est_cost_cents.toFixed(2), numeric: true },
    { key: "date", header: "Date", render: (r) => new Date(r.created_at).toLocaleString() },
  ];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <h2>Conversations</h2>
      <div style={{ display: "flex", gap: 16 }}>
        <select className="select" value={severity ?? ""} onChange={(e) => setFilter("severity", e.target.value)}>
          <option value="">All severities</option>
          <option value="P0">P0</option>
          <option value="P1">P1</option>
          <option value="P2">P2</option>
        </select>
        <select className="select" value={dimension ?? ""} onChange={(e) => setFilter("dimension", e.target.value)}>
          <option value="">All dimensions</option>
          {DIMENSION_ORDER.map((d) => (
            <option key={d} value={d}>
              {d}
            </option>
          ))}
        </select>
        <select
          className="select"
          value={clusterId ?? ""}
          onChange={(e) => setFilter("cluster_id", e.target.value)}
        >
          <option value="">All clusters</option>
          {data?.clusters.map((c) => (
            <option key={c.id} value={c.id}>
              {c.label}
            </option>
          ))}
        </select>
        <select className="select" value={outcome ?? ""} onChange={(e) => setFilter("outcome", e.target.value)}>
          <option value="">All outcomes</option>
          <option value="pass">Pass only</option>
          <option value="fail">Fail only</option>
        </select>
      </div>

      {isLoading || !data ? (
        <Skeleton lines={8} height={32} />
      ) : (
        <>
          <p className="text-dense">
            {data.total} calls · {data.rows.filter((r) => r.failed_dimensions.length).length} with failures ·{" "}
            {data.rows.filter((r) => r.has_p0).length} P0
          </p>
          <Table
            columns={columns}
            rows={data.rows}
            rowKey={(r) => r.call_id}
            onRowClick={(r) => navigate(`/calls/${r.call_id}?from=conversations`)}
          />
          <Pagination
            page={page}
            pageSize={PAGE_SIZE}
            total={data.total}
            onPageChange={(next) => {
              const p = new URLSearchParams(params);
              p.set("page", String(next));
              setParams(p);
            }}
          />
        </>
      )}
    </div>
  );
}
