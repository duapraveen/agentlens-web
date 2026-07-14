import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import { fetchConversationDetail } from "../api/client";
import { Card } from "../components/Card";
import { Skeleton } from "../components/Skeleton";
import { SeverityBadge } from "../components/SeverityBadge";
import { useRole } from "../context/RoleContext";

export function CallDetail() {
  const { callId } = useParams<{ callId: string }>();
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const { role } = useRole();
  const [showGroundTruth, setShowGroundTruth] = useState(false);

  const { data, isLoading } = useQuery({
    queryKey: ["call", callId],
    queryFn: () => fetchConversationDetail(callId!),
    enabled: Boolean(callId),
  });

  if (isLoading || !data) {
    return (
      <Card>
        <Skeleton lines={10} />
      </Card>
    );
  }

  const origin = params.get("from") === "review-queue" ? "/review-queue" : "/conversations";

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <div style={{ display: "flex", justifyContent: "space-between" }}>
        <button className="btn btn-secondary" onClick={() => navigate(origin)}>
          ← Back
        </button>
        {data.cluster && (
          <button className="btn btn-secondary" onClick={() => navigate(`/clusters?focus_id=${data.cluster!.id}`)}>
            View cluster → {data.cluster.label}
          </button>
        )}
      </div>

      <h2>
        Call {data.call_id} · {data.scenario}
      </h2>

      <Card>
        <h3>Transcript</h3>
        <div style={{ maxHeight: 300, overflowY: "auto" }} className="text-dense">
          {data.transcript.map((turn, i) => (
            <p key={i}>
              <strong>{(turn.speaker ?? "").toString().replace(/^\w/, (c) => c.toUpperCase())}:</strong>{" "}
              {turn.text}
            </p>
          ))}
        </div>
      </Card>

      <h3>Scores</h3>
      {data.records.map((record) => (
        <details key={record.id} style={{ marginBottom: 8 }}>
          <summary>
            {record.dimension} · {record.score} · <SeverityBadge severity={record.severity} /> ·{" "}
            {record.passed ? "pass" : "FAIL"} · stage: {record.pipeline_stage ?? "—"}
          </summary>
          <div className="text-dense" style={{ padding: 12 }}>
            <p>{record.judge_reasoning}</p>
            {record.failure_description && <p><strong>Finding:</strong> {record.failure_description}</p>}
            <p><strong>Deterministic checks:</strong></p>
            <p>
              {data.checks.length
                ? data.checks.map((c) => (c.triggered ? `⚠ ${c.check_name.toUpperCase()}` : `✓ ${c.check_name}`)).join(" · ")
                : "✓ No deterministic flags"}
            </p>
            <p style={{ color: "var(--color-text-secondary)" }}>
              Prompt v{record.prompt_version} · Model: {record.judge_model} · Rubric v{record.rubric_version} ·
              Input hash: {record.input_hash}
            </p>
          </div>
        </details>
      ))}

      {role === "Engineer" && (
        <label className="text-dense">
          <input type="checkbox" checked={showGroundTruth} onChange={(e) => setShowGroundTruth(e.target.checked)} />{" "}
          Show ground truth
        </label>
      )}
      {showGroundTruth && role === "Engineer" && (
        <Card>
          {data.ground_truth ? (
            <p>
              Injected: {data.ground_truth.failure_mode} · stage: {data.ground_truth.pipeline_stage} · severity:{" "}
              {data.ground_truth.severity}
            </p>
          ) : (
            <p>No injected failure — this is a clean call.</p>
          )}
        </Card>
      )}
    </div>
  );
}
