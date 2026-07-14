const BASE = "/api";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!response.ok) {
    const body = await response.text();
    throw new Error(`${init?.method ?? "GET"} ${path} failed (${response.status}): ${body}`);
  }
  return response.json() as Promise<T>;
}

export interface StatusSummary {
  last_eval_at: string | null;
  n_calls: number;
  n_golden: number;
}

export interface ConversationRow {
  call_id: string;
  scenario: string;
  failed_dimensions: string[];
  has_p0: boolean;
  avg_score: number;
  est_cost_cents: number;
  created_at: string;
}

export interface ClusterLabel {
  id: number;
  label: string;
}

export interface ConversationsList {
  rows: ConversationRow[];
  total: number;
  clusters: ClusterLabel[];
}

export interface EvalRecordDetail {
  id: number;
  dimension: string;
  score: number;
  severity: string;
  passed: boolean;
  failure_description: string | null;
  judge_reasoning: string;
  pipeline_stage: string | null;
  judge_model: string;
  prompt_version: string;
  rubric_version: string;
  input_hash: string;
}

export interface CheckResult {
  check_name: string;
  triggered: boolean;
  detail: string | null;
}

export interface CallDetail {
  call_id: string;
  scenario: string;
  transcript: { speaker?: string; text?: string }[];
  records: EvalRecordDetail[];
  checks: CheckResult[];
  cluster: { id: number; label: string } | null;
  ground_truth: { failure_mode: string; pipeline_stage: string; severity: string } | null;
}

export interface ClusterCard {
  cluster_id: number;
  label: string;
  description: string;
  routing: string;
  severity: string;
  size: number;
  is_p0: boolean;
}

export interface ClustersList {
  cards: ClusterCard[];
  n_failures: number;
  last_clustered_at: string | null;
}

export interface DimensionQuality {
  pass_rate: number;
  delta: number | null;
}

export interface Overview {
  quality: Record<string, DimensionQuality>;
  severities: Record<string, number>;
  precision: number | null;
  recall: number | null;
  agreement: number | null;
  n_reviews: number;
  top_clusters: ClusterCard[];
  total_eval_cents: number;
  avg_per_call_cents: number;
}

export interface AgreementStats {
  n_reviews: number;
  n_agree: number;
  agreement: number;
  per_dimension: Record<string, number>;
  per_dimension_counts: Record<string, number>;
}

export interface Finding {
  eval_record_id: number;
  call_id: string;
  scenario: string;
  dimension: string;
  score: number;
  severity: string;
  failure_description: string | null;
  checks: CheckResult[];
  transcript: { speaker?: string; text?: string }[];
}

export interface ReviewQueueState {
  stats: AgreementStats;
  pending_count: number;
  current: Finding | null;
}

export interface FixProposal {
  id: number;
  cluster_id: number;
  fix_type: string;
  rationale: string;
  patch: string;
  status: string;
}

export interface RegressionRun {
  id: number;
  fix_proposal_id: number;
  batch_id: string;
  n_before: number;
  n_after: number;
  before_pass_rates: Record<string, number>;
  after_pass_rates: Record<string, number>;
  target_dimension: string;
  regressed_dimensions: string[];
}

export interface FixWorkbenchState {
  cluster: ClusterCard;
  fix: FixProposal | null;
  regression: RegressionRun | null;
}

export interface JobSummary {
  finished_at: string | null;
  summary: Record<string, unknown>;
}

export interface JobsStatus {
  corpus: JobSummary;
  evals: JobSummary;
  cluster: JobSummary;
  log_lines: string[];
}

export const fetchStatus = () => request<StatusSummary>("/status");

export const fetchOverview = () => request<Overview>("/overview");

export function fetchConversations(params: {
  severity?: string;
  dimension?: string;
  clusterId?: number;
  outcome?: "pass" | "fail";
  page?: number;
}): Promise<ConversationsList> {
  const q = new URLSearchParams();
  if (params.severity) q.set("severity", params.severity);
  if (params.dimension) q.set("dimension", params.dimension);
  if (params.clusterId != null) q.set("cluster_id", String(params.clusterId));
  if (params.outcome) q.set("outcome", params.outcome);
  q.set("page", String(params.page ?? 0));
  return request<ConversationsList>(`/conversations?${q.toString()}`);
}

export const fetchConversationDetail = (callId: string) =>
  request<CallDetail>(`/conversations/${encodeURIComponent(callId)}`);

export function fetchClusters(params: {
  routing?: string;
  severity?: string;
  focusId?: number;
}): Promise<ClustersList> {
  const q = new URLSearchParams();
  if (params.routing) q.set("routing", params.routing);
  if (params.severity) q.set("severity", params.severity);
  if (params.focusId != null) q.set("focus_id", String(params.focusId));
  return request<ClustersList>(`/clusters?${q.toString()}`);
}

export const fetchReviewQueue = () => request<ReviewQueueState>("/review-queue");

export const submitReview = (evalRecordId: number, verdict: "agree" | "disagree", note?: string) =>
  request<ReviewQueueState>(`/review-queue/${evalRecordId}`, {
    method: "POST",
    body: JSON.stringify({ verdict, note: note ?? null }),
  });

export const fetchFixWorkbenchClusters = () => request<ClusterLabel[]>("/fix-workbench/clusters");

export const fetchFixWorkbench = (clusterId: number) =>
  request<FixWorkbenchState>(`/fix-workbench/${clusterId}`);

export const generateFix = (clusterId: number) =>
  request<FixProposal>(`/fix-workbench/${clusterId}/generate`, { method: "POST" });

export const applyRegression = (clusterId: number) =>
  request<RegressionRun>(`/fix-workbench/${clusterId}/apply-regression`, { method: "POST" });

export const fetchJobsStatus = () => request<JobsStatus>("/jobs/status");

export const fetchEvalEstimate = (scope: string, model: string) =>
  request<{ n_calls: number; estimate_cents: number }>(
    `/jobs/eval-estimate?scope=${scope}&model=${model}`
  );

export const launchCorpusJob = (count: number, failureRate: number) =>
  request<{ status: string }>("/jobs/corpus", {
    method: "POST",
    body: JSON.stringify({ count, failure_rate: failureRate }),
  });

export const launchEvalsJob = (scope: string, model: string) =>
  request<{ status: string }>("/jobs/evals", {
    method: "POST",
    body: JSON.stringify({ scope, model }),
  });

export const launchReclusterJob = () =>
  request<{ status: string }>("/jobs/recluster", { method: "POST" });
