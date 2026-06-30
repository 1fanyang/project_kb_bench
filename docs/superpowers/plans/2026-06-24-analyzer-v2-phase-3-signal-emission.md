# Analyzer v2 — Phase 3: Signal Emission Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **Sketched plan — Phase 2 must ship first.** Revised 2026-06-26 with the Phase 0 node-kind corrections: control-flow AST kinds are `conditional_statement` (NOT `if_statement`), `case_statement`, and `always_construct`. Lines marked **PH2** must still be reconciled against the actual record shape Phase 2 emits.

**Goal:** Compute the axis-2 / axis-3 attribute signals (`signal_index.jsonl`) from the v2 bundle so that downstream consumers (`prepare_module_inputs.py`, M5/M9) get cleaner anchors — especially `conditional_behavior` must never anchor at license / file-header lines (the v1 regression that motivated the entire v2 migration).

**Architecture:** A standalone Python script `skills/benchmark-repo-analyzer/scripts/signal_emitter.py` reads `source_inventory.jsonl`, `entity_index.jsonl`, and `relation_graph.jsonl` from a v2 bundle directory and writes `signal_index.jsonl` into the same directory. Each signal is computed by an isolated function (one per attribute) so signals can be added/removed without cross-contamination. Confidence is set per signal: `0.95` when the underlying evidence is AST-derived (the bundle exporter set the relation's `confidence` accordingly), `0.7` otherwise.

**Tech Stack:** Python 3 standard library; reuses `schemas/signal-index.schema.json`; existing `uv run pytest` runner; tests at `tests/test_signal_emitter.py`.

## Global Constraints

- The signal shape must match `schemas/signal-index.schema.json` exactly. Do not add new top-level fields without bumping the schema.
- For `distracting_info`: the `evidence.collision_sources` + `collision_source_count` + `total_entities_with_name` keys must be preserved — `prepare_module_inputs.py` and downstream M5/M9 currently consume them (see source plan § 2.1 finding A4 + § 6 acceptance for Phase 3).
- For `conditional_behavior`: zero anchors in the first 10 lines of any file (the v1 regression). Verify via a dedicated assertion in Task 4 acceptance.
- Signals are *pipeline-specific*, not CodeGraph-native. This layer is a Python script in the analyzer skill; it does not live inside CodeGraph.
- Per-signal `confidence`: `0.95` if every contributing relation's `confidence ≥ 0.95` (AST-derived in the v2 bundle), else `0.7`. No third level.
- Signals not implemented in Phase 3 (`version_fork_diff`, content-level `doc_code_divergence`) are explicitly marked TODO in the script's docstring; do not emit zero-value stubs.

---

## File Structure

Create:

- `skills/benchmark-repo-analyzer/scripts/signal_emitter.py` — entry point + dispatcher.
- `skills/benchmark-repo-analyzer/scripts/_signals/` — one module per attribute (`long_tail.py`, `distracting_info.py`, `non_code_anchor.py`, `conditional_behavior.py`, `doc_code_divergence.py`, `implicit_domain_knowledge.py`).
- `skills/benchmark-repo-analyzer/scripts/_signals/__init__.py` — exports `ALL_EMITTERS: list[Callable]`.
- `tests/test_signal_emitter.py` — per-signal unit tests using a fixture v2 bundle.
- `tests/fixtures/signal_emitter/v2_bundle/` — small hand-built v2 bundle: 4 sources, 6 entities, 8 relations covering each emitter's input shape.

Modify:

- `skills/benchmark-repo-analyzer/references/analyzer-contract.md` — note that v2 signal_index.jsonl carries `confidence ∈ {0.7, 0.95}`, and that `conditional_behavior` anchors are AST-anchored.
- `skills/benchmark-repo-analyzer/SKILL.md` — document the emitter invocation (right after `codegraph_to_bundle.py`).

Do not modify:

- `skills/benchmark-generator/scripts/prepare_module_inputs.py` — Phase 4 owns this. Phase 3 only proves the signals come out clean; Phase 4 wires the consumer.

---

### Task 1: Scaffold the emitter + `long_tail` signal

**Files:**
- Create: `skills/benchmark-repo-analyzer/scripts/signal_emitter.py`
- Create: `skills/benchmark-repo-analyzer/scripts/_signals/__init__.py`
- Create: `skills/benchmark-repo-analyzer/scripts/_signals/_common.py` — shared loaders + record builder.
- Create: `skills/benchmark-repo-analyzer/scripts/_signals/long_tail.py`
- Create: `tests/fixtures/signal_emitter/v2_bundle/` — minimal bundle.
- Create: `tests/test_signal_emitter.py`

**Interfaces:**
- Consumes: a v2 bundle directory (entity_index, relation_graph, source_inventory JSONL).
- Produces: `signal_index.jsonl` records. `long_tail` is the simplest signal — entities with inbound-edge count `≤ τ` (default 3). Later signals plug into the same dispatcher.

Reference v1 signal record shape (from `runs/vortex_context_bundle/signal_index.jsonl`):

```json
{"anchor": {"kind": "source", "lines": "4", "path": "...", "source_id": "..."},
 "attribute": "conditional_behavior", "axis": 3, "confidence": 0.7,
 "evidence": {...attribute-specific...},
 "extractor": "deterministic_signal_builder_v1",
 "project": "vortex",
 "signal_id": "sig:vortex:conditional_behavior:src-vortex-00002-a89e05187c07"}
```

In v2 the `extractor` becomes `"deterministic_signal_emitter_v2"`.

- [ ] **Step 1: Build the fixture bundle**

Author `tests/fixtures/signal_emitter/v2_bundle/`:

- `source_inventory.jsonl` — 4 source rows: one C++ code source, one YAML config, one Markdown doc, one Verilog RTL.
- `entity_index.jsonl` — 6 entities: `foo` (cpp function, src 1), `bar` (cpp function, src 1), `widget` (rst doc anchor, src 3), `clk_gate` (verilog module, src 4), `Adder` (verilog module, src 4), `Adder` (cpp class, src 1) — note the deliberate `Adder` name collision for distracting_info testing.
- `relation_graph.jsonl` — 8 relations: 2 `defines`, 3 `imports_or_includes`, 1 `doc_mentions_entity`, 1 `instantiates`, 1 `calls`. Inbound-edge counts engineered so `widget` has 0 inbound (long_tail), `foo` has 5 (not long_tail).

Commit these as hand-authored JSONL — no fixture generator. This keeps the test failing-mode honest: if a real bundle's shape diverges from this, the test catches it.

- [ ] **Step 2: Author `_signals/_common.py`**

```python
"""Shared helpers for signal emitters."""
from __future__ import annotations
import hashlib
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class Bundle:
    sources: list[dict]
    entities: list[dict]
    relations: list[dict]
    project: str


def load_bundle(bundle_dir: Path, project: str) -> Bundle:
    def _load(name):
        return [json.loads(l) for l in (bundle_dir / name).read_text().splitlines()]
    return Bundle(
        sources=_load("source_inventory.jsonl"),
        entities=_load("entity_index.jsonl"),
        relations=_load("relation_graph.jsonl"),
        project=project,
    )


def inbound_counts(b: Bundle) -> Counter:
    c = Counter()
    for r in b.relations:
        tgt = (r.get("object") or {}).get("id")
        if tgt:
            c[tgt] += 1
    return c


def signal_id(project: str, attribute: str, anchor: dict) -> str:
    h = hashlib.sha256(
        f"{anchor.get('source_id','')}:{anchor.get('lines','')}:{attribute}".encode()
    ).hexdigest()[:12]
    src = (anchor.get("source_id") or "anchor").replace("_", "-")
    return f"sig:{project}:{attribute}:{src}-{h}"


def build_record(project, attribute, axis, anchor, evidence, confidence) -> dict:
    return {
        "anchor": anchor,
        "attribute": attribute,
        "axis": axis,
        "confidence": confidence,
        "evidence": evidence,
        "extractor": "deterministic_signal_emitter_v2",
        "project": project,
        "signal_id": signal_id(project, attribute, anchor),
    }
```

- [ ] **Step 3: Author `_signals/long_tail.py`**

```python
"""long_tail: entities with inbound-edge count <= tau (default 3)."""
from __future__ import annotations
from ._common import Bundle, build_record, inbound_counts

ATTRIBUTE = "long_tail"
AXIS = 2
DEFAULT_TAU = 3


def emit(b: Bundle, tau: int = DEFAULT_TAU):
    counts = inbound_counts(b)
    for e in b.entities:
        n = counts.get(e["entity_id"], 0)
        if n > tau:
            continue
        anchor = {
            "kind": "entity",
            "entity_id": e["entity_id"],
            "source_id": e.get("source_id"),
            "lines": str(e.get("start_line") or 1),
        }
        confidence = 0.95  # AST-derived inbound count from v2 relations
        yield build_record(
            b.project, ATTRIBUTE, AXIS, anchor,
            {"inbound_edge_count": n, "tau": tau},
            confidence,
        )
```

- [ ] **Step 4: Author `_signals/__init__.py`**

```python
from . import long_tail

ALL_EMITTERS = [long_tail]
```

- [ ] **Step 5: Author `signal_emitter.py`**

```python
#!/usr/bin/env python3
"""Emit signal_index.jsonl from a v2 bundle directory.

Usage:
  uv run python skills/benchmark-repo-analyzer/scripts/signal_emitter.py \
      --bundle runs/vortex_context_bundle_v2/ --project vortex
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path

from _signals import ALL_EMITTERS
from _signals._common import load_bundle


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bundle", required=True, type=Path)
    ap.add_argument("--project", required=True)
    args = ap.parse_args()

    b = load_bundle(args.bundle, args.project)
    out = args.bundle / "signal_index.jsonl"
    with out.open("w") as f:
        for emitter in ALL_EMITTERS:
            for rec in emitter.emit(b):
                f.write(json.dumps(rec) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 6: TDD on long_tail**

```python
# tests/test_signal_emitter.py
import json, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills/benchmark-repo-analyzer/scripts/signal_emitter.py"
FIX = ROOT / "tests/fixtures/signal_emitter/v2_bundle"


def _run(tmp_path):
    target = tmp_path / "bundle"
    import shutil; shutil.copytree(FIX, target)
    subprocess.check_call([sys.executable, str(SCRIPT),
                           "--bundle", str(target), "--project", "fixture"])
    return target / "signal_index.jsonl"


def test_long_tail_picks_zero_inbound_entities(tmp_path):
    out = _run(tmp_path)
    recs = [json.loads(l) for l in out.read_text().splitlines()
            if json.loads(l)["attribute"] == "long_tail"]
    names = {(r["anchor"]["entity_id"], r["evidence"]["inbound_edge_count"]) for r in recs}
    # `widget` had 0 inbound; `foo` had 5 — must include widget, must not include foo.
    assert any(eid.endswith("widget") for eid, _ in names)
    assert not any(eid.endswith("foo") for eid, _ in names)
```

Run, watch fail (since `widget`'s exact `entity_id` is computed deterministically — the test should hash-match the same way the fixture does; if not, write the test to assert by `attribute` count + min inbound only, not by exact id).

- [ ] **Step 7: Commit**

```bash
git add tests/fixtures/signal_emitter/ tests/test_signal_emitter.py \
        skills/benchmark-repo-analyzer/scripts/signal_emitter.py \
        skills/benchmark-repo-analyzer/scripts/_signals/
git commit -m "feat(analyzer-v2/phase-3): scaffold signal emitter + long_tail signal"
```

---

### Task 2: `distracting_info` signal (must preserve collision evidence shape)

**Files:**
- Create: `skills/benchmark-repo-analyzer/scripts/_signals/distracting_info.py`
- Modify: `_signals/__init__.py` to register.
- Modify: `tests/test_signal_emitter.py` — add distracting_info test that asserts the evidence shape downstream consumers depend on.

**Interfaces:**
- Consumes: `Bundle.entities` (group by `name`).
- Produces: signals whose `evidence` carries `collision_sources` (list of source_ids), `collision_source_count` (int), and `total_entities_with_name` (int). The shape is load-bearing for `prepare_module_inputs.py`'s `graph_walk_neighbors` and M9's prompt assembly — verify in Phase 4.

- [ ] **Step 1: Write the failing test first**

```python
def test_distracting_info_preserves_collision_evidence_shape(tmp_path):
    out = _run(tmp_path)
    recs = [json.loads(l) for l in out.read_text().splitlines()
            if json.loads(l)["attribute"] == "distracting_info"]
    assert recs, "no distracting_info signals emitted"
    for r in recs:
        ev = r["evidence"]
        assert "collision_sources" in ev and isinstance(ev["collision_sources"], list)
        assert "collision_source_count" in ev
        assert "total_entities_with_name" in ev
        assert ev["collision_source_count"] == len(ev["collision_sources"])
        assert ev["total_entities_with_name"] >= 2
```

Run, watch fail.

- [ ] **Step 2: Implement**

```python
"""distracting_info: entities whose `name` is shared by >= 2 distinct sources."""
from __future__ import annotations
from collections import defaultdict
from ._common import Bundle, build_record

ATTRIBUTE = "distracting_info"
AXIS = 2


def emit(b: Bundle):
    by_name = defaultdict(list)
    for e in b.entities:
        by_name[e["name"]].append(e)
    for name, entities in by_name.items():
        sources = sorted({e.get("source_id") for e in entities if e.get("source_id")})
        if len(sources) < 2:
            continue
        for e in entities:
            anchor = {
                "kind": "entity",
                "entity_id": e["entity_id"],
                "source_id": e.get("source_id"),
                "lines": str(e.get("start_line") or 1),
            }
            ev = {
                "collision_sources": sources,
                "collision_source_count": len(sources),
                "total_entities_with_name": len(entities),
                "name": name,
            }
            yield build_record(b.project, ATTRIBUTE, AXIS, anchor, ev, 0.95)
```

Register in `__init__.py`.

- [ ] **Step 3: Run + commit**

```bash
uv run pytest tests/test_signal_emitter.py -v
git add … && git commit -m "feat(analyzer-v2/phase-3): distracting_info preserves collision shape"
```

---

### Task 3: `non_code_anchor` signal

**Files:**
- Create: `skills/benchmark-repo-analyzer/scripts/_signals/non_code_anchor.py`
- Modify: `_signals/__init__.py`
- Modify: `tests/test_signal_emitter.py`

**Interfaces:**
- Consumes: `Bundle.sources` (filter by modality ∈ {`script`, `config`, `build`}); references entities anchored to those sources.
- Produces: signals on each anchor whose source is non-code (axis 2). This is the simplest signal in the set.

- [ ] **Step 1: Test**

```python
def test_non_code_anchor_picks_config_source(tmp_path):
    out = _run(tmp_path)
    recs = [json.loads(l) for l in out.read_text().splitlines()
            if json.loads(l)["attribute"] == "non_code_anchor"]
    modalities = {r["evidence"]["modality"] for r in recs}
    assert "config" in modalities  # fixture's YAML source
```

- [ ] **Step 2: Implement**

```python
"""non_code_anchor: anchors whose source modality is script | config | build."""
from __future__ import annotations
from ._common import Bundle, build_record

ATTRIBUTE = "non_code_anchor"
AXIS = 2
NON_CODE = {"script", "config", "build"}


def emit(b: Bundle):
    by_src = {s["source_id"]: s for s in b.sources}
    for e in b.entities:
        s = by_src.get(e.get("source_id"))
        if not s or s.get("modality") not in NON_CODE:
            continue
        anchor = {"kind": "entity", "entity_id": e["entity_id"],
                  "source_id": s["source_id"],
                  "lines": str(e.get("start_line") or 1)}
        yield build_record(b.project, ATTRIBUTE, AXIS, anchor,
                           {"modality": s["modality"], "source_type": s.get("source_type")},
                           0.95)
```

- [ ] **Step 3: Run + commit**

---

### Task 4: `conditional_behavior` signal (the bug-fix signal)

**Files:**
- Create: `skills/benchmark-repo-analyzer/scripts/_signals/conditional_behavior.py`
- Modify: `tests/fixtures/signal_emitter/v2_bundle/relation_graph.jsonl` — add relations whose `evidence` carries an `ast_kind` field for `conditional_statement`, `case_statement`, `always_construct` (PH1/PH2 — confirm this is how Phase 2 propagated the AST kind; if Phase 1 went down the `conditions.scm` route instead, the signal reads `Bundle.entities` filtered by `kind.startswith("condition.")`).
- Modify: `_signals/__init__.py`
- Modify: `tests/test_signal_emitter.py` — assert the zero-first-10-lines invariant.

**Interfaces:**
- Consumes: relations or entities tagged with one of three AST node kinds: `conditional_statement`, `case_statement`, `always_construct`. Phase 2's exporter is responsible for surfacing the AST kind — verify the exact field name before implementing.
- Produces: signals whose `anchor.lines` is the real AST node start line, never a license-block line.

This is the signal whose v1 misbehaviour motivated the entire v2 migration. **The acceptance test is the load-bearing assertion of this whole phase.**

- [ ] **Step 1: Test the load-bearing assertion**

```python
def test_conditional_behavior_never_anchors_in_first_10_lines(tmp_path):
    out = _run(tmp_path)
    recs = [json.loads(l) for l in out.read_text().splitlines()
            if json.loads(l)["attribute"] == "conditional_behavior"]
    assert recs, "no conditional_behavior signals emitted (fixture or emitter broken)"
    for r in recs:
        line = int((r["anchor"]["lines"] or "1").split("-")[0])
        assert line > 10, f"conditional_behavior anchored at line {line} (file header zone)"
```

Run, watch fail.

- [ ] **Step 2: Implement (relation-evidence variant)**

```python
"""conditional_behavior: AST-anchored if/case/always sites in code modalities.

Reads from `relation_graph.jsonl` where `evidence[*].ast_kind` is one of the
three control-flow node kinds. If the exporter chose the conditions.scm route
instead, switch this to read from `Bundle.entities` filtered by
kind.startswith("condition.").
"""
from __future__ import annotations
from ._common import Bundle, build_record

ATTRIBUTE = "conditional_behavior"
AXIS = 3
TARGET_AST_KINDS = {"conditional_statement", "case_statement", "always_construct"}


def emit(b: Bundle):
    by_src = {s["source_id"]: s for s in b.sources}
    for r in b.relations:
        for ev in (r.get("evidence") or []):
            if ev.get("ast_kind") not in TARGET_AST_KINDS:
                continue
            src_id = ev.get("source_id")
            src = by_src.get(src_id)
            if not src:
                continue
            anchor = {"kind": "source", "source_id": src_id,
                      "path": src.get("path"),
                      "lines": ev.get("lines") or str(ev.get("start_line") or 1)}
            confidence = 0.95 if r.get("confidence", 0) >= 0.95 else 0.7
            yield build_record(b.project, ATTRIBUTE, AXIS, anchor,
                               {"ast_kind": ev["ast_kind"], "language": src.get("language"),
                                "modality": src.get("modality")},
                               confidence)
```

- [ ] **Step 3: Run + commit**

```bash
uv run pytest tests/test_signal_emitter.py -v -k conditional_behavior
git add … && git commit -m "feat(analyzer-v2/phase-3): conditional_behavior anchored at AST"
```

---

### Task 5: `doc_code_divergence` signal (honest re-emission)

**Files:**
- Create: `skills/benchmark-repo-analyzer/scripts/_signals/doc_code_divergence.py`
- Modify: `_signals/__init__.py`
- Modify: `tests/test_signal_emitter.py`

**Interfaces:**
- Consumes: `relations` filtered to `predicate == "doc_mentions_entity"` (subject is a doc source, object is a code entity).
- Produces: signals that label the relationship honestly — `evidence.signal_class: "mention_only"` — so downstream consumers know this isn't real content-level divergence. The source plan explicitly defers true divergence detection to a follow-on.

- [ ] **Step 1: Test**

```python
def test_doc_code_divergence_emits_mention_only_label(tmp_path):
    out = _run(tmp_path)
    recs = [json.loads(l) for l in out.read_text().splitlines()
            if json.loads(l)["attribute"] == "doc_code_divergence"]
    assert recs, "no doc_code_divergence signals emitted"
    assert all(r["evidence"]["signal_class"] == "mention_only" for r in recs)
```

- [ ] **Step 2: Implement**

```python
"""doc_code_divergence: doc sources that mention code entities.

This is NOT content-level divergence detection — that work is deferred.
Phase 3 emits with `signal_class: "mention_only"` so downstream consumers
don't mistake the signal for what it isn't. Confidence is 0.7 (heuristic).
"""
from __future__ import annotations
from ._common import Bundle, build_record

ATTRIBUTE = "doc_code_divergence"
AXIS = 3


def emit(b: Bundle):
    by_src = {s["source_id"]: s for s in b.sources}
    by_ent = {e["entity_id"]: e for e in b.entities}
    for r in b.relations:
        if r["predicate"] != "doc_mentions_entity":
            continue
        subj = r.get("subject") or {}
        obj = r.get("object") or {}
        src = by_src.get(subj.get("id"))
        ent = by_ent.get(obj.get("id"))
        if not (src and ent):
            continue
        for ev in (r.get("evidence") or [{}]):
            anchor = {"kind": "source", "source_id": src["source_id"],
                      "path": src.get("path"),
                      "lines": ev.get("lines") or "1"}
            yield build_record(b.project, ATTRIBUTE, AXIS, anchor,
                               {"signal_class": "mention_only",
                                "mentioned_entity_id": ent["entity_id"],
                                "mentioned_entity_name": ent["name"]},
                               0.7)
```

- [ ] **Step 3: Run + commit**

---

### Task 6: `implicit_domain_knowledge` signal (light heuristic) or explicit skip

**Files:**
- Create: `skills/benchmark-repo-analyzer/scripts/_signals/implicit_domain_knowledge.py` **or** add a one-paragraph note in `_signals/__init__.py` documenting the skip.
- Modify: `tests/test_signal_emitter.py` — assertion either way (presence if implemented; absence if skipped).

**Interfaces:**
- Consumes: `Bundle.sources` filtered to language ∈ {`verilog`, `systemverilog`, …HLS langs…}.
- Produces: a signal per RTL source, OR nothing (with the skip documented).

The source plan says "defer to a simple heuristic (RTL/HLS code files) or skip. Documented either way." Pick *one* before starting; document the choice in the task commit.

- [ ] **Step 1: Decide**

Default recommendation: implement as RTL-source heuristic with confidence `0.7`. The signal is cheap; downstream M5/M9 already filter low-confidence signals out if they're noisy. If the implementer reading this plan disagrees, ship the skip-with-docs variant — but commit one of the two paths, not both.

- [ ] **Step 2: Implement (RTL-source heuristic path)**

```python
"""implicit_domain_knowledge: heuristic — RTL/HLS source modality requires
familiarity with the domain to interpret. Confidence 0.7 (heuristic, not AST)."""
from __future__ import annotations
from ._common import Bundle, build_record

ATTRIBUTE = "implicit_domain_knowledge"
AXIS = 3
RTL_LANGS = {"verilog", "systemverilog"}
HLS_LANGS = {"chisel", "scala_chisel", "amaranth"}


def emit(b: Bundle):
    for s in b.sources:
        lang = (s.get("language") or "").lower()
        if lang not in RTL_LANGS | HLS_LANGS:
            continue
        anchor = {"kind": "source", "source_id": s["source_id"],
                  "path": s.get("path"), "lines": "1"}
        yield build_record(b.project, ATTRIBUTE, AXIS, anchor,
                           {"language": lang,
                            "heuristic": "rtl_or_hls_source_modality"},
                           0.7)
```

- [ ] **Step 3: Run + commit**

---

### Task 7: Real-data acceptance on Vortex

**Files:**
- Create (by running): `runs/vortex_context_bundle_v2/signal_index.jsonl`.
- Create: `runs/feasibility_v2_analyzer/phase3_acceptance.md`.
- Modify: `analyzer_v2_codegraph_treesitter_plan.md` § 9 — Phase 3 row to `complete`.

**Interfaces:**
- Consumes: Vortex v2 bundle from Phase 2.
- Produces: `signal_index.jsonl` with the three source-plan acceptance properties: zero license-zone `conditional_behavior` anchors, distracting_info evidence shape preserved, signal count comparable to v1.

- [ ] **Step 1: Run on Vortex**

```bash
uv run python skills/benchmark-repo-analyzer/scripts/signal_emitter.py \
    --bundle runs/vortex_context_bundle_v2/ --project vortex
```

- [ ] **Step 2: License-zone check (the load-bearing assertion of Phase 3)**

```bash
jq -c 'select(.attribute=="conditional_behavior") |
       select((.anchor.lines | split("-")[0] | tonumber) <= 10)' \
   runs/vortex_context_bundle_v2/signal_index.jsonl | wc -l
# Expected: 0
```

If non-zero, the emitter is anchoring on AST-spans that overlap the license block. Inspect the failing record's `anchor.path` + `anchor.lines` and debug before declaring acceptance.

- [ ] **Step 3: distracting_info shape check (load-bearing for prepare consumer)**

```bash
jq -c 'select(.attribute=="distracting_info") |
       select(.evidence.collision_sources == null
              or .evidence.collision_source_count == null
              or .evidence.total_entities_with_name == null)' \
   runs/vortex_context_bundle_v2/signal_index.jsonl | wc -l
# Expected: 0
```

- [ ] **Step 4: Signal-count parity check**

```bash
echo "v1: $(wc -l < runs/vortex_context_bundle/signal_index.jsonl)"
echo "v2: $(wc -l < runs/vortex_context_bundle_v2/signal_index.jsonl)"
```

Expected: v2 count is within ±30% of v1 (numeric drift is fine if accompanied by quality improvement — see § 5 of Phase 3 acceptance report).

- [ ] **Step 5: Write acceptance report**

`runs/feasibility_v2_analyzer/phase3_acceptance.md` — mirror Phase 2 template, ticking off:

- [ ] zero conditional_behavior anchors in file-header zone (lines 1–10)
- [ ] distracting_info evidence shape preserved
- [ ] signal count parity (state the numbers)
- [ ] Phase 4 GO / NO-GO line filled

- [ ] **Step 6: Tracker update + commit**

```bash
git add analyzer_v2_codegraph_treesitter_plan.md \
        runs/feasibility_v2_analyzer/phase3_acceptance.md
git commit -m "docs(analyzer-v2/phase-3): acceptance; phase-4 GO"
```

---

## Acceptance for "Phase 3 is done"

1. `tests/test_signal_emitter.py` passes; each implemented signal has at least one assertion.
2. Vortex v2 `signal_index.jsonl` has zero `conditional_behavior` records anchored at file lines ≤ 10.
3. Every `distracting_info` record's `evidence` carries `collision_sources`, `collision_source_count`, `total_entities_with_name`.
4. v2 signal count is within ±30% of the v1 baseline (or the deviation is justified in `phase3_acceptance.md`).
5. `runs/feasibility_v2_analyzer/phase3_acceptance.md` ends with `Phase 4 GO`.
6. `_signals/implicit_domain_knowledge.py` exists *or* the skip is documented in `_signals/__init__.py` — pick one.
