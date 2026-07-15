import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { fetchOverview } from "../api/client";
import { Card } from "../components/Card";
import { Skeleton } from "../components/Skeleton";
import { StatTile } from "../components/StatTile";
import { SeverityDot } from "../components/SeverityDot";
import { severityRank } from "../severity";

export function Overview() {
  const navigate = useNavigate();
  const { data, isLoading } = useQuery({ queryKey: ["overview"], queryFn: fetchOverview });

  if (isLoading || !data) {
    return (
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 24 }}>
        {Array.from({ length: 4 }).map((_, i) => (
          <Card key={i}>
            <Skeleton lines={4} />
          </Card>
        ))}
      </div>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
      <h2>Overview</h2>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 24 }}>
        <Card>
          <h3>Quality</h3>
          {Object.entries(data.quality).map(([dim, q]) => {
            const arrow =
              q.delta == null ? "" : q.delta >= 0 ? ` ▲ ${Math.round(q.delta * 100)}%` : ` ▼ ${Math.round(q.delta * 100)}%`;
            return (
              <div key={dim} style={{ marginBottom: 8 }}>
                <div className="text-dense">
                  {dim}: {Math.round(q.pass_rate * 100)}%{arrow}
                </div>
                <progress value={q.pass_rate} max={1} style={{ width: "100%" }} />
              </div>
            );
          })}
        </Card>

        <Card>
          <h3>Severity</h3>
          {Object.entries(data.severities)
            .sort(([a], [b]) => severityRank(a) - severityRank(b))
            .map(([sev, count]) => (
              <button
                key={sev}
                className="btn btn-secondary"
                style={{ display: "block", marginBottom: 8, width: "100%", textAlign: "left" }}
                onClick={() => navigate(`/conversations?severity=${sev}`)}
              >
                <SeverityDot severity={sev} />
                {sev}: {count} findings
              </button>
            ))}
        </Card>

        <Card>
          <h3>Judge Accuracy</h3>
          <StatTile label="Precision (golden)" value={data.precision != null ? data.precision.toFixed(2) : "—"} />
          <StatTile label="Recall (golden)" value={data.recall != null ? data.recall.toFixed(2) : "—"} />
          <StatTile
            label="Human agreement"
            value={data.agreement != null ? `${Math.round(data.agreement * 100)}% (${data.n_reviews})` : "—"}
          />
        </Card>

        <Card>
          <h3>Top Clusters</h3>
          {data.top_clusters.length === 0 && (
            <p className="text-dense">No clusters yet — run clustering from the Jobs page.</p>
          )}
          {data.top_clusters.map((c) => (
            <button
              key={c.cluster_id}
              className="btn btn-secondary"
              style={{ display: "block", marginBottom: 8, width: "100%", textAlign: "left" }}
              onClick={() => navigate(`/clusters?focus_id=${c.cluster_id}`)}
            >
              <SeverityDot severity={c.severity} />
              {c.label} · {c.size} · {c.severity} · {c.routing}
            </button>
          ))}
        </Card>
      </div>

      <Card>
        <p className="text-dense">
          Total eval cost to date: {(data.total_eval_cents / 100).toFixed(2)} USD · avg{" "}
          {data.avg_per_call_cents.toFixed(2)}¢ per call
        </p>
      </Card>
    </div>
  );
}
