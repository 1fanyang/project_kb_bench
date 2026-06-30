#!/usr/bin/env python3
"""Prepare per-row candidate input for the v1.1 modular generator pipeline.

Stage 0 of the modular workflow (see modules/contracts.md). Reads the
deterministic plan from scripts/generate_v1_1_release_corpora.py and emits
drafts/<project>.candidates.jsonl: one line per planned row, holding the
anchor and 1-N candidate evidence spans the host LLM picks among in M2.

Deterministic; reuses existing select_signals + read_snippet helpers from
the legacy generator script.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
GENERATOR_PATH = ROOT / "scripts" / "generate_v1_1_release_corpora.py"

# Style budget for M5. Rotate deterministically so the corpus's per-row
# style assignment is reproducible. Real-world quotas can be tuned later;
# the M5 host LLM treats this as a hint, the validator audits it.
STYLE_ROTATION = (
    "colloquial",
    "contextual",
    "hypothesis-check",
    "follow-up",
)

# Diversity caps for M1. Counters are tracked corpus-wide while emitting
# candidates so we can warn early about reuse before paying for M2-M7 work.
PATH_LINES_REUSE_CAP = 3       # per-(path, lines) tuple across the corpus
ANCHOR_REUSE_CAP = 5            # per-source_id appearances as anchor

# Phase 6A: anchor-position rotation cap. Phase 5 smoke50 surfaced
# VX_cluster.sv:48-50 being picked as the row anchor 61 times — the
# `_edge_degree`-based sort always lifted the same hub-module candidate
# to position 0 because it had the highest outgoing-edge count.
# The cap here is a SOFT cap: in the anchor sort, candidates whose
# (path, lines) has already been picked >= ANCHOR_ROTATION_CAP times
# are pushed to a second tier behind unused candidates. If every
# candidate on a row is over-capped, the original highest-edge-degree
# wins — the row still gets a real anchor, never empty.
ANCHOR_ROTATION_CAP = PATH_LINES_REUSE_CAP  # matches the diversity-warning threshold


def diversity_report(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Summarize per-(path,lines) reuse and per-anchor reuse.

    Returned report has shape:
        {
          "path_lines_overuse": [{"key": "p:l", "count": n}, ...],
          "anchor_overuse":     [{"source_id": s, "count": n}, ...],
          "style_counts":       {"colloquial": n, ...}
        }
    The orchestrator (or a hand-run) decides whether to act on warnings.
    """
    pl_counts: Counter[tuple[str, str]] = Counter()
    anchor_counts: Counter[str] = Counter()
    style_counts: Counter[str] = Counter()
    for row in rows:
        plan = row.get("row_plan") or {}
        if isinstance(plan, dict):
            hint = plan.get("style_hint")
            if isinstance(hint, str):
                style_counts[hint] += 1
        for cand in row.get("candidates") or []:
            if not isinstance(cand, dict):
                continue
            path = str(cand.get("path", ""))
            lines = str(cand.get("lines", ""))
            sid = str(cand.get("source_id", ""))
            if path and lines:
                pl_counts[(path, lines)] += 1
            if sid:
                anchor_counts[sid] += 1
    return {
        "path_lines_overuse": [
            {"key": f"{p}:{l}", "count": c}
            for (p, l), c in pl_counts.most_common()
            if c > PATH_LINES_REUSE_CAP
        ],
        "anchor_overuse": [
            {"source_id": sid, "count": c}
            for sid, c in anchor_counts.most_common()
            if c > ANCHOR_REUSE_CAP
        ],
        "style_counts": dict(style_counts),
    }


def _load_generator():
    spec = importlib.util.spec_from_file_location("v1_1_generator", GENERATOR_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["v1_1_generator"] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def candidate_for_signal(signal: Any, source: Any, gen: Any, repo_root: Path) -> dict[str, Any]:
    lines = gen.line_window(source, signal.lines)
    raw_snippet = gen.read_snippet(repo_root, source.path, lines)
    return {
        "signal_id": signal.signal_id,
        "source_id": source.source_id,
        "path": source.path,
        "lines": lines,
        "raw_snippet": raw_snippet,
        "attribute": signal.attribute,
        "axis": signal.axis,
        "role_hint": "trigger_condition" if signal.attribute == "conditional_behavior" else "evidence_fact",
    }


def _candidate_signature(candidate: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        str(candidate.get("source_id", "")),
        str(candidate.get("path", "")),
        str(candidate.get("lines", "")),
        str(candidate.get("attribute", "")),
    )


def _candidate_from_signal_if_substantive(
    signal: Any,
    sources: dict[str, Any],
    gen: Any,
    repo_root: Path,
    stage0_audit: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Build a candidate, applying the same conditional-behavior rescue as
    the main selected-signal path. Returns None when the signal is not usable.
    """
    cand = candidate_for_signal(signal, sources[signal.source_id], gen, repo_root)
    if signal.attribute != "conditional_behavior":
        return cand

    ok, replacement_lines = conditional_behavior_substantive_span(
        cand["path"], cand["lines"], cand["raw_snippet"], repo_root,
    )
    if not ok:
        if stage0_audit is not None:
            stage0_audit.setdefault("conditional_behavior_dropped", []).append(
                f"{cand['path']}:{cand['lines']}"
            )
        return None
    if replacement_lines is not None:
        new_lines = gen.line_window(sources[signal.source_id], replacement_lines)
        new_snippet = gen.read_snippet(repo_root, cand["path"], new_lines)
        if stage0_audit is not None:
            stage0_audit.setdefault("conditional_behavior_rescued", []).append(
                f"{cand['path']}:{cand['lines']}→{new_lines}"
            )
        cand["lines"] = new_lines
        cand["raw_snippet"] = new_snippet
    return cand


# Code-language file suffixes where `if`/`case`/etc. tokens are semantically
# load-bearing. Documentation/config files are excluded from
# conditional_behavior consideration entirely — a `if` token in YAML or RST
# is either workflow gating or natural-language usage ("if applicable").
_CODE_SUFFIXES = (
    ".sv", ".v", ".vh", ".sva", ".c", ".cc", ".cpp", ".cxx",
    ".h", ".hh", ".hpp", ".hxx", ".py", ".go", ".rs", ".java", ".scala", ".swift",
)

# Guard-token regex (raw_snippet substring). Mirrors the validator side so
# Stage 0 rejection and Stage 5 lint agree on what counts as a real guard.
_GUARD_TOKEN_RE = re.compile(
    r"\bif\s*\(|\belse\b|\bcase\b|\bwhen\b|\bassert\b|"
    r"\bposedge\b|\bnegedge\b|@\s*\(|\brequire\b|\bassume\b|\bwait\b"
)

# License-text fingerprints that the analyzer's regex_fallback mis-classifies
# as conditional_behavior (because of the word "if" inside license prose).
_LICENSE_FINGERPRINTS = (
    "Unless required by applicable law",
    "WARRANTIES OF MERCHANTABILITY",
    "this distribution for more information",
    "Redistribution and use in source",
    "Apache License",
    "Permission is hereby granted",
)


def _strip_comment_prefix(line: str) -> str:
    """Return the part of a line that is NOT a single-line comment.

    Handles `//`, `#`, `--`, and leading-`*` (block-comment continuation).
    Block comments `/* ... */` are left in place; the caller is expected
    to fall back to the file-wide substantive check.
    """
    stripped = line.lstrip()
    for marker in ("//", "#", "--"):
        if stripped.startswith(marker):
            return ""
    if stripped.startswith("*"):  # likely inside a block comment
        return ""
    for marker in ("//", "#"):
        idx = line.find(marker)
        if idx >= 0:
            line = line[:idx]
    return line


def _is_include_guard_line(line: str) -> bool:
    """True for include-guard scaffolding (`ifndef X`, bare `define X` with
    no body, `endif`). A `define` with a value (e.g. `define FOO 42`) is a
    real macro definition and NOT a guard."""
    s = line.strip()
    if not s:
        return False
    if s.startswith("`ifndef") or s.startswith("`endif"):
        return True
    if s.startswith("#ifndef") or s.startswith("#endif"):
        return True
    # `define X` (1 token after the directive) is a guard sentinel; a real
    # macro has at least one more token (`define X Y` or `define X(args)`).
    for prefix in ("`define", "#define"):
        if s.startswith(prefix):
            rest = s.split(None, 2)
            if len(rest) <= 2:
                return True
            break
    return False


def _scan_for_guard_line(
    file_lines: list[str], start_after: int = 0
) -> tuple[int, str] | None:
    """Return (1-based line number, line content) of the first non-comment,
    non-guard line in `file_lines[start_after:]` that contains a real guard
    token. None if no such line exists."""
    for idx in range(start_after, len(file_lines)):
        raw = file_lines[idx]
        if _is_include_guard_line(raw):
            continue
        code_part = _strip_comment_prefix(raw)
        if code_part and _GUARD_TOKEN_RE.search(code_part):
            return idx + 1, raw
    return None


def conditional_behavior_substantive_span(
    path: str,
    lines: str,
    raw_snippet: str,
    repo_root: Path,
) -> tuple[bool, str | None]:
    """Return (is_substantive, replacement_lines).

    `is_substantive` is True iff a real control-flow guard exists in the
    file's code body. When True and the analyzer-reported span itself
    contains a guard, `replacement_lines` is None (keep original).
    When True but the original span was a header/license, `replacement_lines`
    is `"<start>-<end>"` pointing at the first real guard in the file
    (3-line window). When False, the candidate should be dropped.
    """
    lower_path = path.lower()
    if not any(lower_path.endswith(s) for s in _CODE_SUFFIXES):
        return False, None
    if any(fp in raw_snippet for fp in _LICENSE_FINGERPRINTS):
        # Still allow rescue: if the analyzer pointed at the license block
        # but the file ALSO has real conditionals below, point at those.
        pass

    full = repo_root / path
    if not full.exists():
        return False, None
    try:
        file_lines = full.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return False, None

    m = re.match(r"^(\d+)(?:-(\d+))?$", str(lines).strip())
    if not m:
        return False, None
    start = max(1, int(m.group(1)))
    end = int(m.group(2) or m.group(1))
    lo = max(1, start - 2)
    hi = min(len(file_lines), end + 2)

    # First pass: is the original span itself substantive?
    original_has_guard = False
    for raw in file_lines[lo - 1 : hi]:
        if _is_include_guard_line(raw):
            continue
        code_part = _strip_comment_prefix(raw)
        if code_part and _GUARD_TOKEN_RE.search(code_part):
            original_has_guard = True
            break
    if original_has_guard and not any(fp in raw_snippet for fp in _LICENSE_FINGERPRINTS):
        return True, None

    # Rescue path: scan the whole file from the top for the first real
    # guard. If found, rewrite the candidate to point there.
    found = _scan_for_guard_line(file_lines, start_after=0)
    if found is None:
        return False, None
    guard_line, _ = found
    end_line = min(len(file_lines), guard_line + 2)
    return True, f"{guard_line}-{end_line}"


def _find_first_substantive_line(path: Path) -> int | None:
    """For an included header, return the 1-based line number of its first
    substantive (non-comment, non-guard, non-blank) line. None if none."""
    if not path.exists():
        return None
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return None
    in_block_comment = False
    for index, raw in enumerate(lines, 1):
        stripped = raw.strip()
        if not stripped:
            continue
        if in_block_comment:
            if "*/" in stripped:
                in_block_comment = False
            continue
        if stripped.startswith("/*"):
            if "*/" not in stripped:
                in_block_comment = True
            continue
        if any(stripped.startswith(marker) for marker in ("//", "#", "--", "*")):
            continue
        if _is_include_guard_line(raw):
            continue
        if stripped.startswith("`include") or stripped.startswith("#include"):
            # An include statement is allowed but not very substantive on
            # its own; keep scanning for the first real declaration.
            continue
        return index
    return None


def _read_relation_graph(bundle: Path) -> list[dict[str, Any]]:
    """Lazy reader for relation_graph.jsonl. Empty list if the file is absent."""
    path = bundle / "relation_graph.jsonl"
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        if raw.strip():
            try:
                rows.append(json.loads(raw))
            except json.JSONDecodeError:
                continue
    return rows


def _index_relations(
    relations: list[dict[str, Any]],
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, list[dict[str, Any]]]]:
    """Build subject→edges and object→edges indexes for graph walk."""
    by_subject: dict[str, list[dict[str, Any]]] = {}
    by_object: dict[str, list[dict[str, Any]]] = {}
    for rel in relations:
        subj = (rel.get("subject") or {}).get("id")
        obj = (rel.get("object") or {}).get("id")
        if isinstance(subj, str):
            by_subject.setdefault(subj, []).append(rel)
        if isinstance(obj, str):
            by_object.setdefault(obj, []).append(rel)
    return by_subject, by_object


# Predicates worth following when expanding from an anchor source. We skip
# `contains` (top-level repo→file noise) and keep semantically-load-bearing
# edges: source `defines` entity, entity is `doc_mentions_entity`'d, source
# `imports_or_includes` another source.
_WALK_PREDICATES = {"defines", "doc_mentions_entity", "imports_or_includes"}
# Cap how many neighbor candidates a single anchor contributes — keeps the
# candidate list small enough for the host LLM to reason over.
NEIGHBOR_LIMIT = 3


def _build_source_name_index(sources: dict[str, Any]) -> dict[str, str]:
    """Map basename (e.g. 'VX_define.vh') → first matching source_id.

    Some relation-graph edges (`imports_or_includes`) reference includes by
    bare filename rather than source_id. This index lets the walk resolve
    those edges back to a real candidate source.
    """
    name_to_source: dict[str, str] = {}
    for sid, source in sources.items():
        name = Path(source.path).name
        # First-write-wins is fine; bare basenames may collide, but the walk
        # already de-duplicates by source_id at the consumer.
        name_to_source.setdefault(name, sid)
    return name_to_source


def graph_walk_neighbors(
    anchor_source_id: str,
    sources: dict[str, Any],
    by_subject: dict[str, list[dict[str, Any]]],
    by_object: dict[str, list[dict[str, Any]]],
    excluded_source_ids: set[str],
    gen: Any,
    repo_root: Path,
    limit: int = NEIGHBOR_LIMIT,
    name_index: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    """Return up to `limit` neighbor candidates reachable in 1-2 hops from the anchor.

    Hop 1: relations whose subject is the anchor source (gives entities the
    anchor defines / sources it imports).
    Hop 2: for each entity surfaced in hop 1, find other relations that
    reference that entity (gives other sources defining or doc-mentioning
    the same entity).

    Neighbors are filtered to distinct sources that exist in the source
    inventory and that aren't already in `excluded_source_ids` (the row's
    own anchor + previously-added neighbors).
    """
    if anchor_source_id not in by_subject and anchor_source_id not in by_object:
        return []

    neighbors: list[dict[str, Any]] = []
    seen_sources: set[str] = set(excluded_source_ids)

    def _emit_candidate(rel: dict[str, Any], target_source_id: str) -> None:
        if target_source_id in seen_sources or target_source_id not in sources:
            return
        predicate = rel.get("predicate")
        # Pull evidence lines from the relation; fall back to "1" if unset.
        evidence_entries = rel.get("evidence") or []
        lines: str | None = None
        for entry in evidence_entries:
            if isinstance(entry, dict) and entry.get("source_id") == target_source_id:
                raw_lines = entry.get("lines")
                if isinstance(raw_lines, str) and raw_lines:
                    lines = raw_lines
                    break
        if lines is None:
            for entry in evidence_entries:
                if isinstance(entry, dict):
                    raw_lines = entry.get("lines")
                    if isinstance(raw_lines, str) and raw_lines:
                        lines = raw_lines
                        break
        source = sources[target_source_id]

        # For `imports_or_includes` edges, the relation's evidence lines
        # point at the include statement in the includer — useless for the
        # included file. Re-locate to its first substantive line so the
        # candidate snippet shows real content rather than the file's
        # `ifndef X / `define X header.
        if predicate == "imports_or_includes":
            first = _find_first_substantive_line(repo_root / source.path)
            if first is not None:
                lines = f"{first}-{first + 2}"
        if lines is None:
            lines = "1"
        lines = gen.line_window(source, lines)
        raw_snippet = gen.read_snippet(repo_root, source.path, lines)
        neighbors.append(
            {
                "source_id": target_source_id,
                "path": source.path,
                "lines": lines,
                "raw_snippet": raw_snippet,
                "attribute": "graph_neighbor",
                "axis": None,
                "role_hint": "evidence_fact",
                "neighbor_relation": predicate,
            }
        )
        seen_sources.add(target_source_id)

    # Hop 1: relations directly touching the anchor as subject or object.
    hop1_entities: list[str] = []
    for rel in by_subject.get(anchor_source_id, []):
        predicate = rel.get("predicate")
        if predicate not in _WALK_PREDICATES:
            continue
        obj = rel.get("object") or {}
        obj_type = obj.get("type")
        obj_id = obj.get("id")
        if obj_type == "source" and isinstance(obj_id, str):
            _emit_candidate(rel, obj_id)
            if len(neighbors) >= limit:
                return neighbors
        elif obj_type == "include" and name_index:
            # `imports_or_includes` edges carry a bare basename rather than
            # a resolvable source_id. Look it up by name.
            basename = obj.get("name")
            if isinstance(basename, str):
                resolved = name_index.get(basename)
                if resolved:
                    _emit_candidate(rel, resolved)
                    if len(neighbors) >= limit:
                        return neighbors
        elif obj_type == "entity" and isinstance(obj_id, str):
            hop1_entities.append(obj_id)

    # Hop 2: other sources that reference each entity surfaced in hop 1.
    # We sweep this twice: first preferring `doc_mentions_entity` edges
    # (which pair the anchor code source with a documentation source — a
    # cleaner L3 third hop than yet another code defines edge), then
    # `defines` and `imports_or_includes` for fallback.
    def _hop2_for(predicates: set[str]) -> None:
        for entity_id in hop1_entities:
            if len(neighbors) >= limit:
                return
            for rel in by_object.get(entity_id, []):
                if rel.get("predicate") not in predicates:
                    continue
                subj = rel.get("subject") or {}
                subj_id = subj.get("id")
                if not isinstance(subj_id, str):
                    continue
                if subj.get("type") == "source" and subj_id != anchor_source_id:
                    _emit_candidate(rel, subj_id)
                    if len(neighbors) >= limit:
                        return

    _hop2_for({"doc_mentions_entity"})
    if len(neighbors) < limit:
        _hop2_for(_WALK_PREDICATES - {"doc_mentions_entity"})

    # Hop 1 reverse: other sources whose include-by-name targets the anchor.
    anchor_basename = Path(sources[anchor_source_id].path).name if anchor_source_id in sources else None
    if anchor_basename and len(neighbors) < limit:
        for rel in by_object.get(anchor_source_id, []):
            if rel.get("predicate") not in _WALK_PREDICATES:
                continue
            subj = rel.get("subject") or {}
            subj_id = subj.get("id")
            if subj.get("type") == "source" and isinstance(subj_id, str) and subj_id != anchor_source_id:
                _emit_candidate(rel, subj_id)
                if len(neighbors) >= limit:
                    return neighbors

    return neighbors


def backfill_signal_candidates(
    raw_candidates: list[dict[str, Any]],
    signals_by_attribute: dict[str, list[Any]],
    sources: dict[str, Any],
    gen: Any,
    repo_root: Path,
    layer: str,
    index: int,
    stage0_audit: dict[str, Any],
) -> None:
    """Ensure Stage 0 still offers M2 enough analyzer-backed candidates.

    Regex fallback often points conditional_behavior at license/config lines.
    When those are dropped, some L2/L3 rows lose their second difficulty axis
    or even their second source. Repeating the same deterministic selection
    cannot recover that, so Stage 0 backfills from the same signal_index using
    deterministic ordering. This keeps the row signal-driven while avoiding
    silent under-production.
    """
    if not raw_candidates:
        return

    seen = {_candidate_signature(c) for c in raw_candidates}

    def _current_axes() -> tuple[set[str], set[str]]:
        axis2 = {
            str(c.get("attribute"))
            for c in raw_candidates
            if c.get("axis") == 2 and isinstance(c.get("attribute"), str)
        }
        axis3 = {
            str(c.get("attribute"))
            for c in raw_candidates
            if c.get("axis") == 3 and isinstance(c.get("attribute"), str)
        }
        return axis2, axis3

    def _ordered_signals(axis: int, preferred: tuple[str, ...] = ()) -> list[Any]:
        attributes = [
            attr
            for attr, signals in signals_by_attribute.items()
            if signals and signals[0].axis == axis
        ]
        rank = {attr: pos for pos, attr in enumerate(preferred)}
        attributes.sort(key=lambda attr: (rank.get(attr, 999), attr))
        out: list[Any] = []
        for attr in attributes:
            signals = list(signals_by_attribute.get(attr) or [])
            if not signals:
                continue
            if signals:
                # Rotate deterministically by row index so backfills do not
                # collapse onto the same first source across the whole corpus.
                offset = index % len(signals)
                signals = signals[offset:] + signals[:offset]
            out.extend(signals)
        return out

    def _add_signal(signal: Any, prefer_new_source: bool = False) -> bool:
        if signal.source_id not in sources:
            return False
        if prefer_new_source and signal.source_id in {str(c.get("source_id", "")) for c in raw_candidates}:
            return False
        cand = _candidate_from_signal_if_substantive(signal, sources, gen, repo_root, stage0_audit)
        if cand is None:
            return False
        sig = _candidate_signature(cand)
        if sig in seen:
            return False
        raw_candidates.append(cand)
        seen.add(sig)
        stage0_audit.setdefault("signal_backfills", []).append(
            {
                "attribute": signal.attribute,
                "axis": signal.axis,
                "source_id": signal.source_id,
            }
        )
        return True

    axis2, axis3 = _current_axes()
    if not axis2:
        for signal in _ordered_signals(2, ("long_tail", "distracting_info", "non_code_anchor")):
            if _add_signal(signal, prefer_new_source=layer in {"L2", "L3"}):
                break
    if not axis3:
        for signal in _ordered_signals(3, ("implicit_domain_knowledge", "conditional_behavior", "doc_code_divergence")):
            if _add_signal(signal, prefer_new_source=layer in {"L2", "L3"}):
                break

    if layer in {"L2", "L3"} and len({str(c.get("source_id", "")) for c in raw_candidates}) < 2:
        # Keep the existing difficulty axes intact by preferring another
        # source for an already-claimed attribute before falling back to any
        # usable signal.
        axis2, axis3 = _current_axes()
        preferred_attrs = tuple(sorted(axis2 | axis3))
        ordered: list[Any] = []
        for attr in preferred_attrs:
            ordered.extend(signals_by_attribute.get(attr) or [])
        if not ordered:
            ordered = _ordered_signals(3) + _ordered_signals(2)
        for signal in ordered:
            if _add_signal(signal, prefer_new_source=True):
                break


def prepare_project(
    project: str,
    bundle: Path,
    profile: Path,
    repo_root: Path,
    output_dir: Path,
    gen: Any,
) -> list[dict[str, Any]]:
    gen.validate_profile(project, profile)
    sources = gen.load_sources(bundle, project, repo_root)
    # Phase 4: thread a drop counter so the Stage-0 audit records which
    # unknown axis attributes were dropped (signal_dataflow under "ignore
    # and ship"). The dict is mutated in load_signals.
    dropped_unknown: dict[str, int] = {}
    signals_by_attribute = gen.load_signals(
        bundle, project, sources,
        dropped_unknown_attributes=dropped_unknown,
    )
    if dropped_unknown:
        msg = ", ".join(f"{k}={v}" for k, v in sorted(dropped_unknown.items()))
        print(
            f"{project}: prepare dropped signal records for unknown axis "
            f"attributes (Phase 4 ignore-and-ship): {msg}",
            flush=True,
        )
    relations = _read_relation_graph(bundle)
    by_subject, by_object = _index_relations(relations)
    name_index = _build_source_name_index(sources)
    rows: list[dict[str, Any]] = []
    # Phase 6A — track per-(path, lines) anchor reuse across the row
    # loop. The anchor sort below demotes candidates whose tally hits
    # the cap, so popular hub modules (e.g. VX_cluster.sv:48-50) stop
    # winning every row.
    anchor_pl_tally: Counter[tuple[str, str]] = Counter()
    for index, (layer, answerability) in enumerate(zip(gen.LAYER_PLAN, gen.ANSWERABILITY_PLAN), 1):
        case_id = f"{project}-v1_1-{layer}-{index:03d}"
        cap = gen.capability(index - 1, project)
        atype = gen.answer_type(answerability, index - 1)
        row_plan: dict[str, Any] = {
            "layer": layer,
            "answerability": answerability,
            "axis2_retrieval": [],
            "axis3_reasoning": [],
            "capability": cap,
            "answer_type": atype,
            "style_hint": STYLE_ROTATION[(index - 1) % len(STYLE_ROTATION)],
        }
        anchor: dict[str, Any] | None = None
        candidates: list[dict[str, Any]] = []

        if answerability != "unanswerable_missing_evidence":
            selected = gen.select_signals(index, layer, project, signals_by_attribute, answerability)
            # Build raw candidates from each selected signal, but drop any
            # conditional_behavior candidate whose span is actually a license
            # header, include guard, or non-code-language file. The validator
            # already FAILs these at lint time (Ship 4 #5); rejecting them at
            # Stage 0 saves M2-M9 host-LLM tokens on dead candidates.
            raw_candidates: list[dict[str, Any]] = []
            dropped_conditional: list[str] = []
            rescued_conditional: list[str] = []
            stage0_audit: dict[str, Any] = {}
            for signal in selected:
                before_drop_count = len(stage0_audit.get("conditional_behavior_dropped", []))
                before_rescue_count = len(stage0_audit.get("conditional_behavior_rescued", []))
                cand = _candidate_from_signal_if_substantive(signal, sources, gen, repo_root, stage0_audit)
                if cand is None:
                    if len(stage0_audit.get("conditional_behavior_dropped", [])) == before_drop_count:
                        dropped_conditional.append(f"{signal.path}:{signal.lines}")
                    continue
                if len(stage0_audit.get("conditional_behavior_rescued", [])) > before_rescue_count:
                    rescued_conditional.append(stage0_audit["conditional_behavior_rescued"][-1])
                raw_candidates.append(cand)

            backfill_signal_candidates(
                raw_candidates=raw_candidates,
                signals_by_attribute=signals_by_attribute,
                sources=sources,
                gen=gen,
                repo_root=repo_root,
                layer=layer,
                index=index,
                stage0_audit=stage0_audit,
            )

            # Order so the anchor is the candidate with the most outgoing
            # graph edges (defines + doc_mentions_entity + imports_or_includes).
            # This makes graph_walk_neighbors start from the most-productive
            # spot and gives downstream stages a more truthful "anchor."
            def _edge_degree(source_id: str) -> int:
                outgoing = by_subject.get(source_id, []) or []
                return sum(
                    1
                    for rel in outgoing
                    if rel.get("predicate") in _WALK_PREDICATES
                )

            def _over_cap(cand: dict[str, Any]) -> int:
                """Phase 6A soft cap: 1 if this (path, lines) has been
                picked as anchor >= ANCHOR_ROTATION_CAP times; else 0.
                A capped candidate sorts BEHIND uncapped ones but
                otherwise preserves edge-degree ordering, so a row whose
                only candidates are over the cap still gets a real
                anchor (graceful fallback to the original
                highest-degree pick)."""
                key = (cand["path"], cand["lines"])
                return 1 if anchor_pl_tally.get(key, 0) >= ANCHOR_ROTATION_CAP else 0

            raw_candidates.sort(
                # Three-tier key:
                # 1. _over_cap=0 (uncapped) before _over_cap=1 (capped)
                # 2. Highest edge-degree first
                # 3. Deterministic tiebreak on path:lines for reproducibility
                key=lambda c: (
                    _over_cap(c),
                    -_edge_degree(c["source_id"]),
                    c["path"],
                    c["lines"],
                ),
            )
            for ordinal, cand in enumerate(raw_candidates, 1):
                cand["candidate_id"] = f"C{ordinal}"
                candidates.append(cand)

            # Refresh axis claims to match what survived the substantive
            # filter; if a conditional_behavior signal was dropped, its axis
            # claim is dropped too rather than left advertising an attribute
            # the row no longer has.
            kept_attrs = {(c.get("attribute"), c.get("axis")) for c in candidates}
            row_plan["axis2_retrieval"] = sorted({a for (a, ax) in kept_attrs if ax == 2 and isinstance(a, str)})
            row_plan["axis3_reasoning"] = sorted({a for (a, ax) in kept_attrs if ax == 3 and isinstance(a, str)})
            if dropped_conditional:
                stage0_audit["conditional_behavior_dropped"] = dropped_conditional
            if rescued_conditional:
                stage0_audit["conditional_behavior_rescued"] = rescued_conditional
            if stage0_audit:
                row_plan["_dropped_at_prepare"] = stage0_audit

            if candidates:
                first = candidates[0]
                # Phase 6A — record this (path, lines) usage so the next
                # row's anchor sort can demote it once the cap is reached.
                anchor_pl_tally[(first["path"], first["lines"])] += 1
                anchor = {
                    "source_id": first["source_id"],
                    "path": first["path"],
                    "lines": first["lines"],
                    "raw_snippet": first["raw_snippet"],
                }
                # Hop out of the anchor via the relation graph to surface up
                # to NEIGHBOR_LIMIT additional candidates with distinct
                # source_ids. M2 uses these to satisfy L2/L3 layer
                # constraints honestly when the analyzer's per-signal
                # selection paired the anchor with boilerplate.
                anchor_source_ids = {c["source_id"] for c in candidates}
                neighbors = graph_walk_neighbors(
                    anchor_source_id=first["source_id"],
                    sources=sources,
                    by_subject=by_subject,
                    by_object=by_object,
                    excluded_source_ids=anchor_source_ids,
                    gen=gen,
                    repo_root=repo_root,
                    name_index=name_index,
                )
                next_ordinal = len(candidates) + 1
                for offset, neighbor in enumerate(neighbors):
                    neighbor["candidate_id"] = f"C{next_ordinal + offset}"
                    candidates.append(neighbor)
        else:
            # Missing-evidence rows still claim a single axis — `negative_evidence`
            # — so the M9 adversarial gate can run a closed_book_llm baseline
            # on them and confirm the gap is real (i.e., the LLM can't answer
            # from prior knowledge either). Without this, the missing-evidence
            # bucket sails through the gate vacuously.
            row_plan["axis3_reasoning"] = ["negative_evidence"]

        rows.append(
            {
                "case_id": case_id,
                "project": project,
                "row_plan": row_plan,
                "anchor": anchor,
                "candidates": candidates,
            }
        )

    out_path = output_dir / f"{project}.candidates.jsonl"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")

    report = diversity_report(rows)
    report_path = output_dir / f"{project}.diversity_report.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print(f"{project}: wrote {len(rows)} candidate rows to {out_path}")
    overuse_pl = len(report["path_lines_overuse"])
    overuse_anchor = len(report["anchor_overuse"])
    if overuse_pl or overuse_anchor:
        print(
            f"{project}: diversity warnings — {overuse_pl} path:lines exceed cap "
            f"{PATH_LINES_REUSE_CAP}, {overuse_anchor} anchors exceed cap {ANCHOR_REUSE_CAP} "
            f"(details in {report_path})"
        )
    # Phase 6A audit: show the top concentrations of anchor (path, lines)
    # reuse — the values the new rotation cap is supposed to keep flat.
    # The cap is soft (over-cap candidates are demoted, not excluded), so
    # any count > ANCHOR_ROTATION_CAP here means a row had no uncapped
    # alternative — worth flagging if it keeps growing.
    top_anchors = anchor_pl_tally.most_common(5)
    if top_anchors:
        anchors_summary = ", ".join(
            f"{p}:{l}={n}" for ((p, l), n) in top_anchors
        )
        print(
            f"{project}: top anchor (path,lines) reuse (cap {ANCHOR_ROTATION_CAP}): "
            f"{anchors_summary}"
        )
    return rows


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--output-dir", type=Path, default=Path("drafts"))
    parser.add_argument("--project", choices=["nvdla", "vortex", "all"], default="all")
    parser.add_argument(
        "--bundle-path",
        type=Path,
        default=None,
        help=(
            "Directory holding source_inventory.jsonl / entity_index.jsonl "
            "/ relation_graph.jsonl / signal_index.jsonl. Defaults to "
            "`runs/<project>_context_bundle/` (the v1 path). Pass "
            "`runs/<project>_context_bundle_v2/` to opt into the v2 "
            "analyzer-produced bundle."
        ),
    )
    parser.add_argument(
        "--strict-diversity",
        action="store_true",
        help=(
            "Exit non-zero if any (path, lines) is reused more than "
            f"{PATH_LINES_REUSE_CAP} times or any source_id appears as anchor "
            f"more than {ANCHOR_REUSE_CAP} times across the corpus. Use in "
            "release builds to refuse spending host-LLM tokens on candidates "
            "with structural reuse bias."
        ),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    gen = _load_generator()
    projects = ["nvdla", "vortex"] if args.project == "all" else [args.project]
    strict_failures: list[str] = []
    for project in projects:
        if args.bundle_path is not None:
            # Single explicit bundle path; only valid when one project is
            # selected (mixing projects + a single bundle is ambiguous).
            if args.project == "all":
                print(
                    "ERROR: --bundle-path requires a specific --project "
                    "(not 'all'); the bundle path is project-specific.",
                    flush=True,
                )
                return 2
            bundle = args.bundle_path
        else:
            bundle = Path("runs") / f"{project}_context_bundle"
        profile = Path("runs") / f"{project}_generation_profile_v1_1.yaml"
        rows = prepare_project(project, bundle, profile, args.repo_root, args.output_dir, gen)
        if args.strict_diversity:
            report = diversity_report(rows)
            pl = len(report["path_lines_overuse"])
            an = len(report["anchor_overuse"])
            if pl or an:
                strict_failures.append(
                    f"{project}: {pl} (path,lines) over cap={PATH_LINES_REUSE_CAP}; "
                    f"{an} anchors over cap={ANCHOR_REUSE_CAP}"
                )
    if strict_failures:
        print(
            "ERROR: --strict-diversity refuses to release; signal sampling is too "
            "concentrated. See drafts/<project>.diversity_report.json for details:"
        )
        for msg in strict_failures:
            print(f"  - {msg}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
