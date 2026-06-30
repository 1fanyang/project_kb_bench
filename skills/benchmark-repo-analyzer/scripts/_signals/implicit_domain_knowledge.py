"""implicit_domain_knowledge: heuristic — RTL/HLS source languages need
domain familiarity to interpret.

Axis 3. Confidence 0.7 (heuristic, not AST-derived).
"""
from __future__ import annotations

from typing import Iterable

from ._common import Bundle, make_signal

EXTRACTOR = "rtl_or_hls_language_heuristic_v2"
RTL_LANGS = frozenset({"verilog", "systemverilog"})
HLS_LANGS = frozenset({"chisel", "scala_chisel", "amaranth"})


def emit(bundle: Bundle, *, repo_sources_root=None) -> Iterable[dict]:
    for s in bundle.sources:
        lang = (s.get("language") or "").lower()
        if lang not in RTL_LANGS | HLS_LANGS:
            continue
        anchor = {
            "kind": "source",
            "source_id": s["source_id"],
            "path": s.get("path"),
            "lines": "1",
        }
        evidence = {
            "language": lang,
            "heuristic": "rtl_or_hls_source_modality",
        }
        yield make_signal(
            bundle.project, "implicit_domain_knowledge", 3, anchor, evidence,
            confidence=0.7, extractor=EXTRACTOR,
        )
