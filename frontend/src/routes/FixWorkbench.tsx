import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import {
  applyRegression,
  fetchFixWorkbench,
  fetchFixWorkbenchClusters,
  generateFix,
} from "../api/client";
import { Card } from "../components/Card";
import { Skeleton } from "../components/Skeleton";

export function FixWorkbench() {
  const [params] = useSearchParams();
  const queryClient = useQueryClient();
  const presetId = params.get("cluster_id") ? Number(params.get("cluster_id")) : null;
  const [clusterId, setClusterId] = useState<number | null>(presetId);
  const [error, setError] = useState<string | null>(null);

  const { data: selectable } = useQuery({
    queryKey: ["fix-workbench-clusters"],
    queryFn: fetchFixWorkbenchClusters,
  });

  useEffect(() => {
    if (!selectable || selectable.length === 0) return;
    const isValid = clusterId != null && selectable.some((c) => c.id === clusterId);
    if (!isValid) {
      setClusterId(selectable[0].id);
    }
  }, [selectable, clusterId]);

  const { data: workbench, isLoading } = useQuery({
    queryKey: ["fix-workbench", clusterId],
    queryFn: () => fetchFixWorkbench(clusterId!),
    enabled: clusterId != null,
  });

  const generateMutation = useMutation({
    mutationFn: () => generateFix(clusterId!),
    onSuccess: () => {
      setError(null);
      queryClient.invalidateQueries({ queryKey: ["fix-workbench", clusterId] });
    },
    onError: (e: Error) => setError(e.message),
  });

  const regressionMutation = useMutation({
    mutationFn: () => applyRegression(clusterId!),
    onSuccess: () => {
      setError(null);
      queryClient.invalidateQueries({ queryKey: ["fix-workbench", clusterId] });
    },
    onError: (e: Error) => setError(e.message),
  });

  if (!selectable || selectable.length === 0) {
    return (
      <Card>
        <p>No non-P0 clusters available — run clustering from the Jobs page.</p>
      </Card>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <h2>Fix Workbench</h2>
      <select
        className="select"
        value={clusterId ?? ""}
        onChange={(e) => setClusterId(Number(e.target.value))}
      >
        {selectable.map((c) => (
          <option key={c.id} value={c.id}>
            {c.label}
          </option>
        ))}
      </select>

      {isLoading || !workbench ? (
        <Skeleton lines={6} />
      ) : (
        <>
          <Card>
            <h3>Proposed Fix</h3>
            <button
              className="btn btn-primary"
              disabled={generateMutation.isPending}
              onClick={() => generateMutation.mutate()}
            >
              Generate Fix
            </button>
            {error && <p style={{ color: "var(--severity-p0)" }}>{error}</p>}
            {!workbench.fix ? (
              <p className="text-dense">No fix proposed yet.</p>
            ) : (
              <>
                <p>
                  <strong>Type:</strong> {workbench.fix.fix_type} · <strong>Status:</strong> {workbench.fix.status}
                </p>
                <p className="text-dense">{workbench.fix.rationale}</p>
                <pre className="text-dense" style={{ background: "var(--color-panel-tint)", padding: 12 }}>
                  {workbench.fix.patch}
                </pre>
                <button
                  className="btn btn-primary"
                  disabled={workbench.cluster.is_p0 || regressionMutation.isPending}
                  title={
                    workbench.cluster.is_p0
                      ? "P0 findings require human acknowledgment before regression can run"
                      : undefined
                  }
                  onClick={() => regressionMutation.mutate()}
                >
                  Apply & Run Regression
                </button>
              </>
            )}
          </Card>

          {workbench.regression && (
            <Card>
              <h3>Regression Results</h3>
              <table className="al-table">
                <thead>
                  <tr>
                    <th>Dimension</th>
                    <th>Before</th>
                    <th>After</th>
                    <th>Delta</th>
                  </tr>
                </thead>
                <tbody>
                  {Array.from(
                    new Set([
                      ...Object.keys(workbench.regression.before_pass_rates),
                      ...Object.keys(workbench.regression.after_pass_rates),
                    ])
                  ).map((dim) => {
                    const before = workbench.regression!.before_pass_rates[dim];
                    const after = workbench.regression!.after_pass_rates[dim];
                    const delta = before != null && after != null ? after - before : null;
                    return (
                      <tr key={dim}>
                        <td>{dim}</td>
                        <td className="numeric">{before != null ? `${Math.round(before * 100)}%` : "—"}</td>
                        <td className="numeric">{after != null ? `${Math.round(after * 100)}%` : "—"}</td>
                        <td className="numeric">
                          {delta == null ? "—" : delta > 0 ? `▲ ${Math.round(delta * 100)}%` : delta < 0 ? `▼ ${Math.round(delta * 100)}%` : "—"}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
              <p className="text-dense">
                target: {workbench.regression.target_dimension} · regenerated batch: {workbench.regression.batch_id} ·
                n_before {workbench.regression.n_before} · n_after {workbench.regression.n_after}
              </p>
            </Card>
          )}
        </>
      )}
    </div>
  );
}
