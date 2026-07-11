"""Golden-set cluster purity: does each injected failure mode land in one cluster? (AC-2.3)"""

from collections import Counter, defaultdict

from sqlalchemy.orm import Session

from agentlens.corpus.scenarios import FAILURE_MODE_INFO, FailureMode
from agentlens.models import Call, ClusterMember


def _member_cluster_ids(session: Session) -> dict[int, int]:
    return {m.eval_record_id: m.cluster_id for m in session.query(ClusterMember).all()}


def _representative_cluster(call: Call, mode: str, membership: dict[int, int]) -> int | None:
    """Cluster of the record matching the mode's expected dimension, else any failed record."""
    try:
        expected: str | None = FAILURE_MODE_INFO[FailureMode(mode)].dimension.value
    except ValueError:
        expected = None
    failed = [r for r in call.eval_records if not r.passed]
    for record in failed:
        if record.dimension == expected and record.id in membership:
            return membership[record.id]
    for record in failed:
        if record.id in membership:
            return membership[record.id]
    return None


def compute_mode_purity(session: Session) -> dict[str, float]:
    """Per ground-truth mode on golden calls: share of members in the dominant cluster.

    A golden failure call contributes its representative record's cluster;
    calls whose records were never clustered count against purity (0.0 when
    no member of a mode is clustered at all).
    """
    membership = _member_cluster_ids(session)
    by_mode: dict[str, list[int | None]] = defaultdict(list)
    golden_failures = session.query(Call).filter(Call.is_golden).join(Call.ground_truth).all()
    for call in golden_failures:
        assert call.ground_truth is not None  # join guarantees it
        mode = call.ground_truth.failure_mode
        by_mode[mode].append(_representative_cluster(call, mode, membership))

    purity: dict[str, float] = {}
    for mode, cluster_ids in by_mode.items():
        clustered = [c for c in cluster_ids if c is not None]
        if not clustered:
            purity[mode] = 0.0
            continue
        dominant = Counter(clustered).most_common(1)[0][1]
        purity[mode] = dominant / len(cluster_ids)
    return purity
