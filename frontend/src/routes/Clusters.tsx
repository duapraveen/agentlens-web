import { useQuery } from "@tanstack/react-query";
import { useNavigate, useSearchParams } from "react-router-dom";
import { fetchClusters } from "../api/client";
import { Card } from "../components/Card";
import { SeverityBadge } from "../components/SeverityBadge";
import { SeverityDot } from "../components/SeverityDot";
import { Skeleton } from "../components/Skeleton";

export function Clusters() {
  const [params, setParams] = useSearchParams();
  const navigate = useNavigate();

  const routing = params.get("routing") ?? undefined;
  const severity = params.get("severity") ?? undefined;
  const focusId = params.get("focus_id") ? Number(params.get("focus_id")) : undefined;

  const { data, isLoading } = useQuery({
    queryKey: ["clusters", routing, severity, focusId],
    queryFn: () => fetchClusters({ routing, severity, focusId }),
  });

  const setFilter = (key: string, value: string) => {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value);
    else next.delete(key);
    setParams(next);
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <h2>Clusters</h2>
      {focusId != null && (
        <button
          className="btn btn-secondary"
          style={{ alignSelf: "flex-start" }}
          onClick={() => {
            const next = new URLSearchParams(params);
            next.delete("focus_id");
            setParams(next);
          }}
        >
          Show all clusters
        </button>
      )}
      <div style={{ display: "flex", gap: 16 }}>
        <select className="select" value={routing ?? ""} onChange={(e) => setFilter("routing", e.target.value)}>
          <option value="">All routing</option>
          <option value="prompt_fix">prompt_fix</option>
          <option value="retrieval_data_fix">retrieval_data_fix</option>
          <option value="ops_process">ops_process</option>
          <option value="model_config">model_config</option>
        </select>
        <select className="select" value={severity ?? ""} onChange={(e) => setFilter("severity", e.target.value)}>
          <option value="">All severities</option>
          <option value="P0">P0</option>
          <option value="P1">P1</option>
          <option value="P2">P2</option>
        </select>
      </div>

      {isLoading || !data ? (
        <Skeleton lines={6} height={80} />
      ) : (
        <>
          <p className="text-dense">
            {data.cards.length} clusters · {data.n_failures} failures · last clustered{" "}
            {data.last_clustered_at ? new Date(data.last_clustered_at).toLocaleTimeString() : "never"}
          </p>
          {data.cards.map((card) => (
            <Card key={card.cluster_id} tint="strong" severity={card.severity}>
              <h3>
                <SeverityDot severity={card.severity} />
                <SeverityBadge severity={card.severity} /> {card.label} · {card.size} calls
              </h3>
              <p className="text-dense" style={{ color: "var(--color-text-secondary)" }}>
                routing: {card.routing} · dominant severity: {card.severity}
              </p>
              <p className="text-dense">{card.description}</p>
              <div style={{ display: "flex", gap: 8 }}>
                <button
                  className="btn btn-secondary"
                  onClick={() => navigate(`/conversations?cluster_id=${card.cluster_id}`)}
                >
                  View {card.size} calls
                </button>
                <button
                  className="btn btn-primary"
                  disabled={card.is_p0}
                  title={card.is_p0 ? "P0 findings require human resolution before a fix can be proposed" : undefined}
                  onClick={() => navigate(`/fix-workbench?cluster_id=${card.cluster_id}`)}
                >
                  Propose Fix
                </button>
              </div>
            </Card>
          ))}
        </>
      )}
    </div>
  );
}
