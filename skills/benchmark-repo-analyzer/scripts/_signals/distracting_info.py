"""distracting_info: entities whose `name` is shared by >= 2 distinct sources.

Axis 2. Preserves the evidence shape downstream consumers
(prepare_module_inputs.py's graph_walk_neighbors + M9's prompt
assembler) currently read from v1 — collision_sources,
collision_source_count, total_entities_with_name.
"""
from __future__ import annotations

from typing import Iterable

from ._common import Bundle, make_signal

EXTRACTOR = "bundle_name_collision_v2"


def emit(bundle: Bundle, *, repo_sources_root=None) -> Iterable[dict]:
    for name, entities in bundle.entities_by_name.items():
        sources = sorted({e.get("source_id") for e in entities
                          if e.get("source_id")})
        if len(sources) < 2:
            continue
        # One signal per (entity, collision) pair so consumers can
        # ranged-filter by entity_id.
        for e in entities:
            anchor = {
                "kind": "entity",
                "entity_id": e["entity_id"],
                "source_id": e.get("source_id"),
                "path": e.get("path"),
                "lines": str(e.get("line_start", 1)),
            }
            evidence = {
                "name": name,
                "collision_sources": sources,
                "collision_source_count": len(sources),
                "total_entities_with_name": len(entities),
            }
            yield make_signal(
                bundle.project, "distracting_info", 2, anchor, evidence,
                confidence=0.95, extractor=EXTRACTOR,
            )
