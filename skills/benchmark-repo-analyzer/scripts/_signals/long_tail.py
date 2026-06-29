"""long_tail: entities with inbound-edge count <= tau (default 3).

Axis 2. Computed from the v2 bundle alone (no source re-parse).
Confidence: 0.95 — inbound counts are exact from the relation graph.
"""
from __future__ import annotations

from typing import Iterable

from ._common import Bundle, make_signal

EXTRACTOR = "bundle_inbound_count_v2"
DEFAULT_TAU = 3


def emit(bundle: Bundle, *, repo_sources_root=None, tau: int = DEFAULT_TAU) -> Iterable[dict]:
    for e in bundle.entities:
        eid = e["entity_id"]
        n = bundle.inbound_counts.get(eid, 0)
        if n > tau:
            continue
        anchor = {
            "kind": "entity",
            "entity_id": eid,
            "source_id": e.get("source_id"),
            "path": e.get("path"),
            "lines": str(e.get("line_start", 1)),
        }
        evidence = {
            "name": e["name"],
            "kind": e["kind"],
            "inbound_edge_count": n,
            "tau": tau,
        }
        yield make_signal(
            bundle.project, "long_tail", 2, anchor, evidence,
            confidence=0.95, extractor=EXTRACTOR,
        )
