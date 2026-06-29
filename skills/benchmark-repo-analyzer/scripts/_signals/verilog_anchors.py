"""Phase 3 signals derived from re-parsing Verilog source via tree-sitter.

Why re-parse: the Phase 1 verilogExtractor doesn't surface
conditional_statement / case_statement / always_construct as entities
(the framework has no control-flow slot), so the v2 bundle alone can't
tell us where conditional behavior anchors are. Per Phase 3 direction,
we don't extend the extractor framework yet — we re-parse Verilog
source via the Phase 0 Python tree-sitter binding instead.

Emits two attributes into signal_index.jsonl:

- `conditional_behavior` (axis 3) — one record per
  conditional_statement / case_statement / always_construct site,
  anchored on its real start line. Evidence carries the AST kind, the
  predicate text, and any signals written under the construct.

- `signal_dataflow` (axis 3) — one record per assignment site
  (continuous_assign, blocking, nonblocking), anchored on the
  assignment line. Evidence names the written signal and its RHS
  dependencies.

Both record families carry:
- `extractor: "verilog_tree_sitter_reparse_v2"` (the provenance tag)
- `evidence.provenance: "tree_sitter_verilog_reparse_v2"` (explicit
  field; the user asked for it to be marked)
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Iterable

# Resolve _verilog_reparse relative to the parent scripts dir.
_HERE = Path(__file__).parent.parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))
import _verilog_reparse as vr  # noqa: E402

from ._common import Bundle, make_signal


EXTRACTOR = "verilog_tree_sitter_reparse_v2"
PROVENANCE = "tree_sitter_verilog_reparse_v2"


def emit(bundle: Bundle, repo_sources_root: Path | None = None) -> Iterable[dict]:
    """Yield conditional_behavior + signal_dataflow records.

    `repo_sources_root` defaults to whatever sits at `repo_sources/` in
    the cwd at run time; pass an absolute path when the bundle was built
    against a checkout outside the worktree (typical for our setup).
    """
    if repo_sources_root is None:
        repo_sources_root = Path("repo_sources")

    for src in bundle.sources:
        if (src.get("language") or "").lower() != "verilog":
            continue
        src_id = src["source_id"]
        rel_path = src.get("relative_path") or src.get("path", "")
        # source.path is conventionally `repo_sources/<repo_name>/<relative>`;
        # strip the leading `repo_sources/` to compose with repo_sources_root.
        on_disk = _resolve_on_disk(src, repo_sources_root)
        if on_disk is None or not on_disk.exists():
            continue

        controls, dataflow = vr.reparse(on_disk)

        for c in controls:
            anchor = {
                "kind": "source",
                "source_id": src_id,
                "path": src.get("path", ""),
                "lines": _lines_str(c.start_line, c.end_line),
            }
            evidence = {
                "ast_kind": c.kind,
                "predicate_text": c.predicate_text,
                "contained_writes": list(c.contained_writes),
                "enclosing_construct": c.enclosing_construct,
                "language": "verilog",
                "modality": src.get("modality", "code"),
                "source_type": src.get("source_type", "code.source"),
                "provenance": PROVENANCE,
            }
            yield make_signal(
                bundle.project, "conditional_behavior", 3,
                anchor, evidence,
                confidence=0.95, extractor=EXTRACTOR,
                salt=f"{c.kind}:{c.start_line}:{c.end_line}",
            )

        for d in dataflow:
            anchor = {
                "kind": "source",
                "source_id": src_id,
                "path": src.get("path", ""),
                "lines": str(d.line),
            }
            evidence = {
                "op": d.op,
                "signal_name": d.signal_name,
                "rhs_signals": list(d.rhs_signals),
                "in_construct_type": d.in_construct_type,
                "assignment_kind": d.assignment_kind,
                "language": "verilog",
                "modality": src.get("modality", "code"),
                "source_type": src.get("source_type", "code.source"),
                "provenance": PROVENANCE,
            }
            yield make_signal(
                bundle.project, "signal_dataflow", 3,
                anchor, evidence,
                confidence=0.95, extractor=EXTRACTOR,
                salt=f"{d.assignment_kind}:{d.signal_name}:{d.line}",
            )


def _lines_str(start: int, end: int) -> str:
    return str(start) if start == end else f"{start}-{end}"


def _resolve_on_disk(src: dict, repo_sources_root: Path) -> Path | None:
    """Map a source row's `path` to an actual filesystem path.

    The exporter writes `path` as `repo_sources/<repo_name>/<relative>`.
    We strip the leading `repo_sources/` and join under our actual
    repo_sources_root, which may be elsewhere on disk (e.g. the
    main checkout while we work in a worktree).
    """
    bundle_path = src.get("path", "")
    rel = src.get("relative_path", "")
    repo_name = src.get("repo_name", "")
    if rel and repo_name:
        return repo_sources_root / repo_name / rel
    # Fallback: strip the bundle's leading "repo_sources/" if present.
    prefix = "repo_sources/"
    if bundle_path.startswith(prefix):
        return repo_sources_root / bundle_path[len(prefix):]
    return None
