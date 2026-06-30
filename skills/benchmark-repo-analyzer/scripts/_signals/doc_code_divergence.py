"""doc_code_divergence: doc-source rows that mention a code entity.

Axis 3. NOT real content-level divergence — that work is deferred.
Phase 3 emits with `signal_class: "mention_only"` so downstream
consumers don't mistake the signal for what it isn't.

Confidence: 0.7 (heuristic; one step below the AST-derived signals).
"""
from __future__ import annotations

from typing import Iterable

from ._common import Bundle, make_signal

EXTRACTOR = "bundle_doc_mention_v2"


def emit(bundle: Bundle, *, repo_sources_root=None) -> Iterable[dict]:
    for r in bundle.relations:
        if r.get("predicate") != "doc_mentions_entity":
            continue
        subj = r.get("subject") or {}
        obj = r.get("object") or {}
        src = bundle.source_by_id.get(subj.get("id"))
        ent = bundle.entity_by_id.get(obj.get("id"))
        if not (src and ent):
            continue
        ev_anchors = r.get("evidence") or [{}]
        for ev in ev_anchors:
            anchor = {
                "kind": "source",
                "source_id": src["source_id"],
                "path": src.get("path"),
                "lines": ev.get("lines") or "1",
            }
            evidence = {
                "signal_class": "mention_only",
                "mentioned_entity_id": ent["entity_id"],
                "mentioned_entity_name": ent["name"],
                "doc_source_id": src["source_id"],
            }
            yield make_signal(
                bundle.project, "doc_code_divergence", 3, anchor, evidence,
                confidence=0.7, extractor=EXTRACTOR,
            )
