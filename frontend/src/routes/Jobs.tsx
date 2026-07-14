import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  fetchEvalEstimate,
  fetchJobsStatus,
  launchCorpusJob,
  launchEvalsJob,
  launchReclusterJob,
} from "../api/client";
import { Card } from "../components/Card";
import { Skeleton } from "../components/Skeleton";

function summaryLine(finishedAt: string | null, summary: Record<string, unknown>, fields: string[]): string {
  if (!finishedAt) return "No completed runs yet.";
  const parts = [`Last run ${new Date(finishedAt).toLocaleString()}`];
  parts.push(...fields.map((f) => `${f}: ${summary[f] ?? "—"}`));
  return parts.join(" · ");
}

export function Jobs() {
  const queryClient = useQueryClient();
  const [count, setCount] = useState(60);
  const [failureRate, setFailureRate] = useState(30);
  const [scope, setScope] = useState<"unevaluated" | "full">("unevaluated");
  const [model, setModel] = useState("claude-haiku-4-5");
  const [message, setMessage] = useState<string | null>(null);
  const [messageIsError, setMessageIsError] = useState(false);

  const { data: status, isLoading } = useQuery({ queryKey: ["jobs-status"], queryFn: fetchJobsStatus });
  const { data: estimate } = useQuery({
    queryKey: ["eval-estimate", scope, model],
    queryFn: () => fetchEvalEstimate(scope, model),
  });

  const corpusMutation = useMutation({
    mutationFn: () => launchCorpusJob(count, failureRate / 100),
    onSuccess: () => {
      setMessageIsError(false);
      setMessage("Started generate_corpus — follow progress in the job log below.");
      queryClient.invalidateQueries({ queryKey: ["jobs-status"] });
    },
    onError: (e: Error) => {
      setMessageIsError(true);
      setMessage(e.message);
    },
  });

  const evalsMutation = useMutation({
    mutationFn: () => launchEvalsJob(scope, model),
    onSuccess: () => {
      setMessageIsError(false);
      setMessage("Started run_evals — follow progress in the job log below.");
      queryClient.invalidateQueries({ queryKey: ["jobs-status"] });
    },
    onError: (e: Error) => {
      setMessageIsError(true);
      setMessage(e.message);
    },
  });

  const reclusterMutation = useMutation({
    mutationFn: () => launchReclusterJob(),
    onSuccess: () => {
      setMessageIsError(false);
      setMessage("Started recluster — follow progress in the job log below.");
      queryClient.invalidateQueries({ queryKey: ["jobs-status"] });
    },
    onError: (e: Error) => {
      setMessageIsError(true);
      setMessage(e.message);
    },
  });

  if (isLoading || !status) {
    return (
      <Card>
        <Skeleton lines={8} />
      </Card>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <h2>Jobs</h2>
      {message && (
        <p className="text-dense" style={messageIsError ? { color: "var(--severity-p0)" } : undefined}>
          {message}
        </p>
      )}

      <Card>
        <h3>Corpus Generation</h3>
        <label className="text-dense">
          Call count
          <input
            type="number"
            min={1}
            max={500}
            value={count}
            onChange={(e) => setCount(Number(e.target.value))}
            style={{ marginLeft: 8 }}
          />
        </label>
        <br />
        <label className="text-dense">
          Failure injection rate: {failureRate}%
          <input
            type="range"
            min={0}
            max={100}
            value={failureRate}
            onChange={(e) => setFailureRate(Number(e.target.value))}
            style={{ display: "block", width: "100%" }}
          />
        </label>
        <button className="btn btn-primary" onClick={() => corpusMutation.mutate()}>
          Generate Corpus
        </button>
        <p className="text-dense">
          {summaryLine(status.corpus.finished_at, status.corpus.summary, ["generated", "failed", "duration_ms"])}
        </p>
      </Card>

      <Card>
        <h3>Eval Run</h3>
        <div>
          <label className="text-dense">
            <input
              type="radio"
              checked={scope === "unevaluated"}
              onChange={() => setScope("unevaluated")}
            />{" "}
            Unevaluated only
          </label>{" "}
          <label className="text-dense">
            <input type="radio" checked={scope === "full"} onChange={() => setScope("full")} /> Full corpus
          </label>
        </div>
        <select className="select" value={model} onChange={(e) => setModel(e.target.value)}>
          <option value="claude-haiku-4-5">claude-haiku-4-5</option>
          <option value="claude-sonnet-5">claude-sonnet-5</option>
        </select>
        {estimate && (
          <p className="text-dense">
            Estimated: {estimate.n_calls} calls ≈ {(estimate.estimate_cents / 100).toFixed(2)} USD
          </p>
        )}
        <button className="btn btn-primary" onClick={() => evalsMutation.mutate()}>
          Run Evals
        </button>
        <p className="text-dense">
          {summaryLine(status.evals.finished_at, status.evals.summary, ["evaluated", "cost_cents", "duration_ms"])}
        </p>
      </Card>

      <Card>
        <h3>Clustering</h3>
        <button className="btn btn-primary" onClick={() => reclusterMutation.mutate()}>
          Re-cluster Failures
        </button>
        <p className="text-dense">
          {summaryLine(status.cluster.finished_at, status.cluster.summary, ["clusters", "failures", "cost_cents"])}
        </p>
      </Card>

      <Card>
        <h3>Job log</h3>
        <div style={{ maxHeight: 200, overflowY: "auto" }} className="text-dense">
          {status.log_lines.length ? status.log_lines.map((line, i) => <div key={i}>{line}</div>) : "No job log yet."}
        </div>
      </Card>
    </div>
  );
}
