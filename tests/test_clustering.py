"""Tests for the silhouette-scanned KMeans assignment."""

from agentlens.clustering.cluster import assign_clusters
from agentlens.clustering.embed import embed_texts

_GROUPS = {
    "availability": [
        "Agent offered an appointment slot that was never established as available.",
        "Agent invented availability and presented a fabricated appointment slot.",
        "Agent confidently offered a slot with no basis for its availability.",
    ],
    "loop": [
        "Agent repeated the same clarifying question three times despite answers.",
        "Agent looped on the same menu question and never completed the task.",
        "Agent kept repeating an identical question, ending the call unresolved.",
    ],
    "escalation": [
        "Patient reported chest pain and the agent did not escalate to emergency care.",
        "Agent ignored a red-flag symptom and failed to escalate the call.",
        "Red-flag chest pain was not escalated; the agent continued routine booking.",
    ],
}


def test_assign_clusters_groups_similar_descriptions() -> None:
    texts = [t for group in _GROUPS.values() for t in group]
    labels = assign_clusters(embed_texts(texts))
    availability, loop, escalation = labels[0:3], labels[3:6], labels[6:9]
    assert len(set(availability)) == 1
    assert len(set(loop)) == 1
    assert len(set(escalation)) == 1
    assert len({availability[0], loop[0], escalation[0]}) == 3


def test_assign_clusters_deterministic() -> None:
    texts = [t for group in _GROUPS.values() for t in group]
    embeddings = embed_texts(texts)
    assert assign_clusters(embeddings) == assign_clusters(embeddings)


def test_tiny_input_single_cluster() -> None:
    assert assign_clusters(embed_texts(["only one description"])) == [0]
    assert assign_clusters(embed_texts(["first text here", "second text there"])) == [0, 0]
