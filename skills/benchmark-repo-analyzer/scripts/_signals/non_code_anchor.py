"""non_code_anchor: entities anchored in non-code source modalities
(script | config | build).

Axis 2. Computed from source_inventory's modality field.
"""
from __future__ import annotations

from typing import Iterable

from ._common import Bundle, make_signal

EXTRACTOR = "bundle_modality_filter_v2"
NON_CODE_MODALITIES = frozenset({"script", "config", "build"})


def emit(bundle: Bundle, *, repo_sources_root=None) -> Iterable[dict]:
    for e in bundle.entities:
        src = bundle.source_by_id.get(e.get("source_id"))
        if not src:
            continue
        modality = src.get("modality")
        if modality not in NON_CODE_MODALITIES:
            continue
        anchor = {
            "kind": "entity",
            "entity_id": e["entity_id"],
            "source_id": src["source_id"],
            "path": e.get("path"),
            "lines": str(e.get("line_start", 1)),
        }
        evidence = {
            "modality": modality,
            "source_type": src.get("source_type"),
            "language": src.get("language"),
            "entity_kind": e["kind"],
        }
        yield make_signal(
            bundle.project, "non_code_anchor", 2, anchor, evidence,
            confidence=0.95, extractor=EXTRACTOR,
        )
