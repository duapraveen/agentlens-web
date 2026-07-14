import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { fetchReviewQueue, submitReview } from "../api/client";
import { Card } from "../components/Card";
import { StatTile } from "../components/StatTile";
import { Skeleton } from "../components/Skeleton";

export function ReviewQueue() {
  const queryClient = useQueryClient();
  const [verdict, setVerdict] = useState<"agree" | "disagree" | null>(null);
  const [note, setNote] = useState("");
  const [showTranscript, setShowTranscript] = useState(false);

  const { data, isLoading } = useQuery({ queryKey: ["review-queue"], queryFn: fetchReviewQueue });

  const mutation = useMutation({
    mutationFn: (vars: { id: number; verdict: "agree" | "disagree"; note?: string }) =>
      submitReview(vars.id, vars.verdict, vars.note),
    onSuccess: (result) => {
      queryClient.setQueryData(["review-queue"], result);
      setVerdict(null);
      setNote("");
      setShowTranscript(false);
    },
  });

  if (isLoading || !data) {
    return (
      <Card>
        <Skeleton lines={6} />
      </Card>
    );
  }

  const { stats, current } = data;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <h2>Review Queue</h2>
      <Card>
        <div style={{ display: "flex", gap: 32 }}>
          <StatTile label="Agreement" value={stats.n_reviews ? `${Math.round(stats.agreement * 100)}%` : "—"} />
          <StatTile label="Reviews" value={String(stats.n_reviews)} />
          <StatTile label="Pending" value={String(data.pending_count)} />
        </div>
        {Object.keys(stats.per_dimension).length > 0 && (
          <p className="text-dense">
            {Object.entries(stats.per_dimension)
              .sort(([a], [b]) => a.localeCompare(b))
              .map(([dim, rate]) => `${dim}: ${Math.round(rate * 100)}% (${stats.per_dimension_counts[dim]})`)
              .join(" · ")}
          </p>
        )}
      </Card>

      {!current ? (
        <Card>
          <p>Queue clear — every flagged finding has a verdict.</p>
        </Card>
      ) : (
        <>
          <Card>
            <h3>
              {current.call_id} · {current.scenario}
            </h3>
            <p>
              <strong>{current.dimension}</strong> · score {current.score} · {current.severity}
            </p>
            <p className="text-dense">{current.failure_description ?? "(no description)"}</p>
            <p className="text-dense">
              {current.checks.length
                ? current.checks
                    .map((c) => (c.triggered ? `⚠ ${c.check_name.toUpperCase()}` : `✓ ${c.check_name}`))
                    .join(" · ")
                : "✓ No deterministic flags"}
            </p>
            <button className="btn btn-secondary" onClick={() => setShowTranscript((v) => !v)}>
              {showTranscript ? "Hide" : "View"} full transcript
            </button>
            {showTranscript && (
              <div className="text-dense" style={{ marginTop: 8 }}>
                {current.transcript.map((turn, i) => (
                  <p key={i}>
                    <strong>{(turn.speaker ?? "").toString().replace(/^\w/, (c) => c.toUpperCase())}:</strong>{" "}
                    {turn.text}
                  </p>
                ))}
              </div>
            )}
          </Card>

          <Card>
            <div style={{ display: "flex", gap: 8, marginBottom: 8 }}>
              <button
                className={verdict === "agree" ? "btn btn-primary" : "btn btn-secondary"}
                onClick={() => setVerdict("agree")}
              >
                ✓ Agree
              </button>
              <button
                className={verdict === "disagree" ? "btn btn-primary" : "btn btn-secondary"}
                onClick={() => setVerdict("disagree")}
              >
                ✗ Disagree
              </button>
            </div>
            <textarea
              className="text-dense"
              placeholder="Note (optional)"
              value={note}
              onChange={(e) => setNote(e.target.value)}
              style={{ width: "100%", minHeight: 60 }}
            />
            <button
              className="btn btn-primary"
              disabled={verdict === null || mutation.isPending}
              onClick={() => verdict && mutation.mutate({ id: current.eval_record_id, verdict, note: note || undefined })}
              style={{ marginTop: 8 }}
            >
              Submit & Next
            </button>
          </Card>
        </>
      )}
    </div>
  );
}
