"""Shared utilities for the Phase 3 signal emitters.

The Bundle dataclass loads a v2 bundle directory (the four JSONLs +
manifest) and provides O(1) lookups the emitters need: sources by id,
entities by id, relations by predicate, and a name-collision index.
"""
from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable


@dataclass
class Bundle:
    bundle_dir: Path
    project: str
    sources: list[dict]
    entities: list[dict]
    relations: list[dict]

    # Derived lookups (populated in __post_init__ via classmethod load).
    source_by_id: dict[str, dict] = field(default_factory=dict)
    source_by_path: dict[str, dict] = field(default_factory=dict)
    entity_by_id: dict[str, dict] = field(default_factory=dict)
    entities_by_name: dict[str, list[dict]] = field(default_factory=dict)
    inbound_counts: dict[str, int] = field(default_factory=dict)

    @classmethod
    def load(cls, bundle_dir: Path, project: str) -> "Bundle":
        def jl(name: str) -> list[dict]:
            p = bundle_dir / name
            if not p.exists():
                return []
            return [json.loads(line) for line in p.read_text().splitlines()
                    if line.strip()]

        sources = jl("source_inventory.jsonl")
        entities = jl("entity_index.jsonl")
        relations = jl("relation_graph.jsonl")

        source_by_id = {s["source_id"]: s for s in sources}
        source_by_path = {s["path"]: s for s in sources}
        entity_by_id = {e["entity_id"]: e for e in entities}

        entities_by_name: dict[str, list[dict]] = defaultdict(list)
        for e in entities:
            entities_by_name[e["name"]].append(e)

        inbound_counts: dict[str, int] = defaultdict(int)
        for r in relations:
            tgt = (r.get("object") or {}).get("id")
            if tgt:
                inbound_counts[tgt] += 1

        return cls(
            bundle_dir=bundle_dir,
            project=project,
            sources=sources,
            entities=entities,
            relations=relations,
            source_by_id=source_by_id,
            source_by_path=source_by_path,
            entity_by_id=entity_by_id,
            entities_by_name=dict(entities_by_name),
            inbound_counts=dict(inbound_counts),
        )


# ---------------------------------------------------------------------------
# Signal record builder
# ---------------------------------------------------------------------------

def signal_id(project: str, attribute: str, anchor: dict, salt: str = "") -> str:
    """Deterministic signal id.

    Re-running the emitter on the same bundle must produce the same ids
    (so consumers can diff). Includes salt for cases where one anchor
    spawns multiple signals (e.g. a case_statement with N arms each
    producing a write site).
    """
    src = anchor.get("source_id") or anchor.get("entity_id") or "anchor"
    lines = anchor.get("lines", "")
    h = hashlib.sha256(f"{src}|{lines}|{attribute}|{salt}".encode()).hexdigest()[:12]
    src_clean = src.replace("_", "-")
    return f"sig:{project}:{attribute}:{src_clean}-{h}"


def make_signal(
    project: str,
    attribute: str,
    axis: int,
    anchor: dict,
    evidence: dict,
    *,
    confidence: float,
    extractor: str,
    salt: str = "",
) -> dict:
    """Build a signal_index record matching the v1 row shape."""
    return {
        "signal_id": signal_id(project, attribute, anchor, salt),
        "project": project,
        "axis": axis,
        "attribute": attribute,
        "anchor": anchor,
        "evidence": evidence,
        "extractor": extractor,
        "confidence": confidence,
    }


# ---------------------------------------------------------------------------
# Dedup helper for signal_emitter.py
# ---------------------------------------------------------------------------

def dedupe(signals: Iterable[dict]) -> list[dict]:
    """Keep the first record per (project, attribute, anchor) triple.

    Multiple emitters can in principle produce overlapping anchors; we
    keep whichever fired first.
    """
    by_id: dict[str, dict] = {}
    for s in signals:
        sid = s["signal_id"]
        if sid not in by_id:
            by_id[sid] = s
    return list(by_id.values())
