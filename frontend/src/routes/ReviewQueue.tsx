import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { fetchReviewQueue, submitReview } from "../api/client";
import type { ScoredRecord } from "../api/client";
import { Card } from "../components/Card";
import { StatTile } from "../components/StatTile";
import { Skeleton } from "../components/Skeleton";
import { SeverityDot } from "../components/SeverityDot";
import { SeverityBadge } from "../components/SeverityBadge";
import { severityColorVar, severityRank } from "../severity";

function ScoreFoldout({
  record,
  onSubmitted,
}: {
  record: ScoredRecord;
  onSubmitted: (result: unknown) => void;
}) {
  const [verdict, setVerdict] = useState<"agree" | "disagree" | null>(
    (record.review?.verdict as "agree" | "disagree" | undefined) ?? null
  );
  const [note, setNote] = useState(record.review?.note ?? "");
  const [error, setError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: (vars: { verdict: "agree" | "disagree"; note?: string }) =>
      submitReview(record.id, vars.verdict, vars.note),
    onSuccess: (result) => {
      setError(null);
      onSubmitted(result);
    },
    onError: (e: Error) => setError(e.message),
  });

  return (
    <details
      style={{
        marginBottom: 8,
        borderLeft: `4px solid ${record.passed ? "transparent" : severityColorVar(record.severity)}`,
        paddingLeft: 8,
      }}
    >
      <summary>
        {!record.passed && <SeverityDot severity={record.severity} />}
        {record.dimension} · {record.score} · <SeverityBadge severity={record.severity} /> ·{" "}
        {record.passed ? "pass" : "FAIL"} · stage: {record.pipeline_stage ?? "—"}
        {record.review && (
          <span className="text-dense" style={{ marginLeft: 8, color: "var(--color-text-secondary)" }}>
            (reviewed: {record.review.verdict})
          </span>
        )}
      </summary>
      <div className="text-dense" style={{ padding: 12 }}>
        <p>{record.judge_reasoning}</p>
        {record.failure_description && (
          <p>
            <strong>Finding:</strong> {record.failure_description}
          </p>
        )}
        <p style={{ color: "var(--color-text-secondary)" }}>
          Prompt v{record.prompt_version} · Model: {record.judge_model} · Rubric v{record.rubric_version} ·
          Input hash: {record.input_hash}
        </p>

        <div style={{ display: "flex", gap: 8, marginTop: 8, marginBottom: 8 }}>
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
          placeholder="Note (why is the reasoning/evidence flawed?)"
          value={note}
          onChange={(e) => setNote(e.target.value)}
          style={{ width: "100%", minHeight: 50 }}
        />
        <button
          className="btn btn-primary"
          disabled={verdict === null || mutation.isPending}
          onClick={() => verdict && mutation.mutate({ verdict, note: note || undefined })}
          style={{ marginTop: 8 }}
        >
          {record.review ? "Update Review" : "Submit Review"}
        </button>
        {error && <p style={{ color: "var(--severity-p0)" }}>{error}</p>}
      </div>
    </details>
  );
}

export function ReviewQueue() {
  const queryClient = useQueryClient();
  const [showTranscript, setShowTranscript] = useState(false);

  const { data, isLoading } = useQuery({ queryKey: ["review-queue"], queryFn: fetchReviewQueue });

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

          <h3>Scores</h3>
          {[...current.records]
            .sort((a, b) => severityRank(a.severity) - severityRank(b.severity))
            .map((record) => (
              <ScoreFoldout
                key={record.id}
                record={record}
                onSubmitted={(result) => queryClient.setQueryData(["review-queue"], result)}
              />
            ))}
        </>
      )}
    </div>
  );
}
