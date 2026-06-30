# Analyzer v2 — Phase 2: Bundle Exporter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **Sketched plan — Phase 1 must ship first.** Revised 2026-06-26 with the real CodeGraph 1.1.1 schema names — tables are `nodes` / `edges` / `files` / `unresolved_refs`, NOT the placeholder `symbols` / `relations` from the earlier draft. Column shapes and DDL are frozen in `runs/feasibility_v2_analyzer/codegraph_schema.md` and reproduced in `skills/benchmark-repo-analyzer/references/codegraph_schema.md` at Task 1.
>
> Fields marked **PH1** read from the Phase 1 acceptance report (any extractor-list adjustments + the D5 resolution decision). Do not start Task 1 until both Phase 0 § 6 GO and Phase 1 acceptance § "Phase 2 GO" are filled.

**Goal:** Read CodeGraph's SQLite database and write the four canonical bundle artifacts (`source_inventory.jsonl`, `entity_index.jsonl`, `relation_graph.jsonl`, plus `project_manifest.json` and `analyzer_report.md`) into `runs/<project>_context_bundle/`, in a shape that the existing prepare/M2-M9/lint pipeline consumes without modification.

**Architecture:** A single Python script `skills/benchmark-repo-analyzer/scripts/codegraph_to_bundle.py` runs after `codegraph index` and reads only the CodeGraph SQLite file — never re-parses source. The script is deterministic: same DB in → same JSONL out, sorted by `source_id` / `entity_id` / `relation_id`. The v1 schema stays in place; one schema (relation-graph) bumps to v1.1 to add new predicate names. Comparison output (`--diff-against`) is human-readable only and never written into the canonical bundle path.

**Tech Stack:** Python 3 standard library (`sqlite3`, `json`, `hashlib`, `argparse`, `pathlib`), existing `uv run` invocation pattern, existing `schemas/*.schema.json` plus a v1.1 bump for relation-graph.

## Global Constraints

- The v1 bundle is the canonical comparison baseline. Do not delete or overwrite `runs/{vortex,nvdla}_context_bundle/` until Phase 5 promotion; write the v2 output to a sibling path `runs/{vortex,nvdla}_context_bundle_v2/` during Phases 2–4.
- All new relation predicate names land in `schemas/relation-graph.schema.json` v1.1 (additive enum entries). Do not break v1 — predicate names `defines`, `imports_or_includes`, `doc_mentions_entity` are kept; `contains` is dropped per D6 only after Phase 5 promotion. In Phase 2 the exporter omits `contains` but the schema still permits it.
- Output JSONL is sorted deterministically; re-running the exporter with the same DB must produce a byte-identical output.
- AST-derived signals get `confidence: 0.95`; regex / heuristic fallback stays at `0.7`. Per-source confidence is set by the extractor field on each record.
- The exporter never touches `repo_sources/` and never invokes `codegraph index` itself — indexing is a separate step. Document this in the script's docstring.

---

## File Structure

Create:

- `skills/benchmark-repo-analyzer/scripts/codegraph_to_bundle.py` — single entry point.
- `skills/benchmark-repo-analyzer/scripts/_codegraph_queries.py` — module of SQL query strings; isolated so the schema-pinning lives in one file.
- `skills/benchmark-repo-analyzer/scripts/_bundle_writer.py` — JSONL serializer with deterministic field ordering + a `_diff.py` helper for `--diff-against`.
- `skills/benchmark-repo-analyzer/references/codegraph_schema.md` — copy of the Phase 0 schema dump, frozen as the contract this exporter is written against (lives in the skill so future readers don't need to chase the runs directory).
- `tests/test_codegraph_to_bundle.py` — end-to-end test against a tiny seeded SQLite fixture.
- `tests/fixtures/codegraph_to_bundle/` — directory with a hand-crafted SQLite DB and the expected JSONL outputs.

Modify:

- `schemas/relation-graph.schema.json` — bump version to `v1.1`; add `instantiates`, `calls`, `imports` to the predicate enum; add `evidence.included_first_substantive_line` as an optional field on `imports_or_includes` records.
- `skills/benchmark-repo-analyzer/SKILL.md` — document the v2 exporter invocation.
- `skills/benchmark-repo-analyzer/references/analyzer-contract.md` — note that v2 output uses `analyzer_version: benchmark-repo-analyzer/v2-tree-sitter-codegraph` and `analysis_backends.code.used_primary: true`.

Do not modify:

- `runs/{vortex,nvdla}_context_bundle/` (v1 bundles — preserved as comparison baseline until Phase 5).
- Any consumer downstream of the bundle (`prepare_module_inputs.py`, M2-M9, lint) — Phase 4 owns wiring.

---

### Task 1: Freeze the CodeGraph schema as a skill-local contract

**Files:**
- Create: `skills/benchmark-repo-analyzer/references/codegraph_schema.md`
- Create: `skills/benchmark-repo-analyzer/scripts/_codegraph_queries.py`

**Interfaces:**
- Consumes: `runs/feasibility_v2_analyzer/codegraph_schema.md` from Phase 0 Task 6.
- Produces: an in-skill copy of the schema (the contract this Phase is implemented against) and a single Python module of SQL strings. Tasks 2–5 import from `_codegraph_queries`; later tasks never write raw SQL.

- [ ] **Step 1: Copy the schema dump into the skill**

```bash
cp runs/feasibility_v2_analyzer/codegraph_schema.md \
   skills/benchmark-repo-analyzer/references/codegraph_schema.md
```

Then prepend a header:

```markdown
# CodeGraph SQLite schema — frozen contract for v2 exporter

This file is the contract the v2 bundle exporter is written against. The
upstream CodeGraph schema may evolve; when it does, do not silently update
this file — re-pin the CodeGraph commit, re-dump the schema (Phase 0 Task 6),
diff against this file, and ship an exporter update in the same PR.

CodeGraph commit pinned to: <sha from runs/feasibility_v2_analyzer/_codegraph_commit.txt>
```

- [ ] **Step 2: Author `_codegraph_queries.py`**

```python
"""SQL query strings against CodeGraph's SQLite schema (PH0-frozen).

Every query is a constant; the only Python-side templating is on table/column
names if the schema dump revealed multiple tables (e.g. `symbols` and
`symbol_aliases`). Do not concatenate user input into these strings.
"""
from __future__ import annotations

# Schema confirmed via Phase 0 dump (runs/feasibility_v2_analyzer/codegraph_schema.md).
# Tables: nodes, edges, files, unresolved_refs (NOT symbols / relations).

FILES_QUERY = """
SELECT path, content_hash, language, size, modified_at,
       indexed_at, node_count, errors
FROM files
ORDER BY path
"""

ENTITIES_QUERY = """
SELECT id, kind, name, qualified_name, file_path, language,
       start_line, end_line, start_column, end_column,
       docstring, signature, visibility, is_exported,
       is_async, is_static, is_abstract,
       decorators, type_parameters, return_type, updated_at
FROM nodes
ORDER BY id
"""

# edges.source / edges.target are text node ids (e.g. "class:abc...");
# resolution to file paths uses a join via nodes.id.
RELATIONS_QUERY = """
SELECT id, kind, source, target, metadata, line, col, provenance
FROM edges
ORDER BY id
"""
```

- [ ] **Step 3: Commit**

```bash
git add skills/benchmark-repo-analyzer/references/codegraph_schema.md \
        skills/benchmark-repo-analyzer/scripts/_codegraph_queries.py
git commit -m "feat(analyzer-v2/phase-2): freeze codegraph schema as exporter contract"
```

---

### Task 2: Emit `source_inventory.jsonl`

**Files:**
- Create: `skills/benchmark-repo-analyzer/scripts/_bundle_writer.py` (initial: source-inventory serializer + helpers).
- Create: `skills/benchmark-repo-analyzer/scripts/codegraph_to_bundle.py` (initial: arg parsing + invokes the source-inventory writer).
- Create: `tests/fixtures/codegraph_to_bundle/tiny.db` — hand-built SQLite with 3 files spanning C++, Python, RST.
- Create: `tests/fixtures/codegraph_to_bundle/expected/source_inventory.jsonl`.
- Create: `tests/test_codegraph_to_bundle.py` (initial: source-inventory case).

**Interfaces:**
- Consumes: `_codegraph_queries.FILES_QUERY` (Task 1).
- Produces: a `source_inventory.jsonl` with the same field set as the v1 bundle (sample shown in source plan § 2). `source_id` is derived as `src_<project>_<5-digit-zero-padded-ordinal>` for determinism; later tasks key off this id.

Reference v1 record shape (one line; do not depart from this without bumping the schema):

```json
{"authority": "primary_source", "language": "yaml", "line_count": 294,
 "modality": "config", "parse_status": "parsed", "path": "...", "project": "vortex",
 "relative_path": "...", "repo_name": "vortex/vortex", "sha256": "sha256:...",
 "size_bytes": 8977, "source_id": "src_vortex_00002",
 "source_set_id": "vortex_main", "source_type": "config.source"}
```

- [ ] **Step 1: Write the test fixture DB**

`tests/fixtures/codegraph_to_bundle/_build_tiny_db.py` (script committed alongside the fixture so the fixture is reproducible):

```python
"""Build the tiny.db fixture deterministically.

Re-run after schema changes; commit both the script and the resulting tiny.db.
"""
import sqlite3, hashlib
from pathlib import Path

DB = Path(__file__).parent / "tiny.db"
DB.unlink(missing_ok=True)
conn = sqlite3.connect(DB)
# Schema below mirrors the real CodeGraph 1.1.1 DDL — see
# runs/feasibility_v2_analyzer/codegraph_schema.md and
# tools/codegraph/src/db/schema.sql for the source of truth.
conn.executescript('''
  CREATE TABLE files(path TEXT PRIMARY KEY, content_hash TEXT NOT NULL,
                     language TEXT NOT NULL, size INTEGER NOT NULL,
                     modified_at INTEGER NOT NULL, indexed_at INTEGER NOT NULL,
                     node_count INTEGER DEFAULT 0, errors TEXT);
  CREATE TABLE nodes(id TEXT PRIMARY KEY, kind TEXT NOT NULL, name TEXT NOT NULL,
                     qualified_name TEXT NOT NULL, file_path TEXT NOT NULL,
                     language TEXT NOT NULL, start_line INTEGER NOT NULL,
                     end_line INTEGER NOT NULL, start_column INTEGER NOT NULL,
                     end_column INTEGER NOT NULL, docstring TEXT, signature TEXT,
                     visibility TEXT, is_exported INTEGER DEFAULT 0,
                     is_async INTEGER DEFAULT 0, is_static INTEGER DEFAULT 0,
                     is_abstract INTEGER DEFAULT 0, decorators TEXT,
                     type_parameters TEXT, return_type TEXT,
                     updated_at INTEGER NOT NULL);
  CREATE TABLE edges(id INTEGER PRIMARY KEY AUTOINCREMENT, source TEXT NOT NULL,
                     target TEXT NOT NULL, kind TEXT NOT NULL, metadata TEXT,
                     line INTEGER, col INTEGER, provenance TEXT,
                     FOREIGN KEY (source) REFERENCES nodes(id) ON DELETE CASCADE,
                     FOREIGN KEY (target) REFERENCES nodes(id) ON DELETE CASCADE);
''')
files = [
  ("repo_sources/tiny/main.cpp",   "sha256:aaa...", "cpp",    200, 0, 0, 2, None),
  ("repo_sources/tiny/helper.py",  "sha256:bbb...", "python",  80, 0, 0, 1, None),
  ("repo_sources/tiny/README.rst", "sha256:ccc...", "rst",    120, 0, 0, 0, None),
]
conn.executemany(
    "INSERT INTO files VALUES (?,?,?,?,?,?,?,?)", files,
)
conn.commit()
```

Run it once to materialise `tiny.db`:

```bash
uv run python tests/fixtures/codegraph_to_bundle/_build_tiny_db.py
```

- [ ] **Step 2: Write the test (failing)**

`tests/test_codegraph_to_bundle.py`:

```python
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DB = ROOT / "tests/fixtures/codegraph_to_bundle/tiny.db"
EXPECTED = ROOT / "tests/fixtures/codegraph_to_bundle/expected/source_inventory.jsonl"
SCRIPT = ROOT / "skills/benchmark-repo-analyzer/scripts/codegraph_to_bundle.py"


def test_source_inventory_matches_expected(tmp_path):
    out = tmp_path / "context_bundle_v2"
    subprocess.check_call([
        sys.executable, str(SCRIPT),
        "--db", str(FIXTURE_DB),
        "--project", "tiny",
        "--source-set-id", "tiny_main",
        "--repo-name", "tiny/tiny",
        "--out", str(out),
    ])
    got = (out / "source_inventory.jsonl").read_text().splitlines()
    expected = EXPECTED.read_text().splitlines()
    assert got == expected
```

Author the expected fixture by hand (3 lines matching the v1 record shape).

- [ ] **Step 3: Confirm the test fails**

```bash
uv run pytest tests/test_codegraph_to_bundle.py -v
```

Expected: `FileNotFoundError` (script doesn't exist yet) or `AssertionError`.

- [ ] **Step 4: Implement the minimum to make it pass**

`skills/benchmark-repo-analyzer/scripts/_bundle_writer.py`:

```python
from __future__ import annotations
import json
from pathlib import Path
from typing import Iterable, Mapping

CANONICAL_SOURCE_FIELDS = [
    "authority", "language", "line_count", "modality", "parse_status",
    "path", "project", "relative_path", "repo_name", "sha256", "size_bytes",
    "source_id", "source_set_id", "source_type",
]


def write_jsonl(path: Path, records: Iterable[Mapping], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        for rec in records:
            ordered = {k: rec[k] for k in fields if k in rec}
            f.write(json.dumps(ordered, sort_keys=False) + "\n")


def derive_modality(language: str) -> str:
    # Minimal mapping; extend as Phase 2 acceptance reveals gaps.
    return {
        "cpp": "code", "c": "code", "python": "code", "verilog": "code",
        "yaml": "config", "json": "config", "make": "build",
        "shell": "script", "rst": "doc", "markdown": "doc",
    }.get(language or "", "unknown")


def derive_source_type(modality: str) -> str:
    return {
        "code": "code.source", "config": "config.source",
        "doc": "doc.source", "build": "build.source", "script": "script.source",
    }.get(modality, "unknown")
```

`skills/benchmark-repo-analyzer/scripts/codegraph_to_bundle.py`:

```python
#!/usr/bin/env python3
"""Export a CodeGraph SQLite DB into the canonical bundle JSONL layout.

Usage:
  uv run python skills/benchmark-repo-analyzer/scripts/codegraph_to_bundle.py \
      --db <codegraph.db> --project vortex --source-set-id vortex_main \
      --repo-name vortex/vortex --out runs/vortex_context_bundle_v2/
"""
from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

from _bundle_writer import (
    CANONICAL_SOURCE_FIELDS, derive_modality, derive_source_type, write_jsonl,
)
from _codegraph_queries import FILES_QUERY


def emit_source_inventory(conn, args, out_dir: Path) -> dict[int, str]:
    """Returns a map file_id -> source_id for downstream emitters."""
    records = []
    file_to_source = {}
    for ordinal, row in enumerate(conn.execute(FILES_QUERY), start=1):
        file_id, path, language, byte_size, line_count, sha256 = row
        source_id = f"src_{args.project}_{ordinal:05d}"
        file_to_source[file_id] = source_id
        modality = derive_modality(language)
        records.append({
            "authority": "primary_source",
            "language": language or "unknown",
            "line_count": line_count or 0,
            "modality": modality,
            "parse_status": "parsed",  # CodeGraph indexed it; per-file errors live elsewhere
            "path": path,
            "project": args.project,
            "relative_path": path.split(f"repo_sources/{args.project}/", 1)[-1],
            "repo_name": args.repo_name,
            "sha256": sha256,
            "size_bytes": byte_size or 0,
            "source_id": source_id,
            "source_set_id": args.source_set_id,
            "source_type": derive_source_type(modality),
        })
    write_jsonl(out_dir / "source_inventory.jsonl", records, CANONICAL_SOURCE_FIELDS)
    return file_to_source


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--project", required=True)
    ap.add_argument("--source-set-id", required=True)
    ap.add_argument("--repo-name", required=True)
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()

    conn = sqlite3.connect(args.db)
    emit_source_inventory(conn, args, args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 5: Run the test (pass)**

```bash
uv run pytest tests/test_codegraph_to_bundle.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add tests/fixtures/codegraph_to_bundle/_build_tiny_db.py \
        tests/fixtures/codegraph_to_bundle/tiny.db \
        tests/fixtures/codegraph_to_bundle/expected/source_inventory.jsonl \
        tests/test_codegraph_to_bundle.py \
        skills/benchmark-repo-analyzer/scripts/codegraph_to_bundle.py \
        skills/benchmark-repo-analyzer/scripts/_bundle_writer.py
git commit -m "feat(analyzer-v2/phase-2): emit source_inventory.jsonl from codegraph"
```

---

### Task 3: Emit `entity_index.jsonl`

**Files:**
- Modify: `skills/benchmark-repo-analyzer/scripts/codegraph_to_bundle.py` — add `emit_entity_index`.
- Modify: `skills/benchmark-repo-analyzer/scripts/_bundle_writer.py` — add `CANONICAL_ENTITY_FIELDS`.
- Modify: `tests/fixtures/codegraph_to_bundle/_build_tiny_db.py` — add 3 entities to the fixture.
- Create: `tests/fixtures/codegraph_to_bundle/expected/entity_index.jsonl`.
- Modify: `tests/test_codegraph_to_bundle.py` — add entity-index test.

**Interfaces:**
- Consumes: the `file_id -> source_id` map returned from Task 2; `_codegraph_queries.ENTITIES_QUERY`.
- Produces: `entity_index.jsonl` records keyed by `entity_id` (`ent_<project>_<12-hex>`). Phase 3's signal emitter and the relation-graph emitter (Task 4) both key off these ids.

Source-plan note: CodeGraph kinds map to existing v1 entity kinds (`function`, `class`, `variable`, `module`, `parameter`, `package`, `interface`, `macro`, `task`). The mapping is in Step 1.

- [ ] **Step 1: Define the kind mapping**

In `_bundle_writer.py`:

```python
CANONICAL_ENTITY_FIELDS = [
    "entity_id", "project", "name", "kind", "language", "source_id",
    "start_line", "end_line", "extractor",
]

# PH1 — kind strings on the right are emitted by CodeGraph's Verilog
# language module from Phase 1. Confirm against actual `symbols.kind` values.
CODEGRAPH_KIND_TO_V1 = {
    "module": "module", "parameter": "parameter", "function": "function",
    "task": "task", "interface": "interface", "package": "package",
    "macro": "macro", "class": "class",
    # built-in CodeGraph kinds (C/C++/Python/...):
    "method": "function", "variable": "variable", "constant": "constant",
}
```

- [ ] **Step 2: Extend fixture + expected**

Add three symbols to `_build_tiny_db.py` (e.g., one C++ function in `main.cpp`, one Python function in `helper.py`, one RST heading — or skip if RST has no symbols). Re-run the build script. Hand-author the matching `expected/entity_index.jsonl`.

- [ ] **Step 3: Write the failing test**

In `tests/test_codegraph_to_bundle.py`:

```python
def test_entity_index_matches_expected(tmp_path):
    out = _run_export(tmp_path)
    got = (out / "entity_index.jsonl").read_text().splitlines()
    expected = (ROOT / "tests/fixtures/codegraph_to_bundle/expected/entity_index.jsonl"
               ).read_text().splitlines()
    assert got == expected
```

Refactor the subprocess call into a `_run_export(tmp_path) -> Path` helper.

- [ ] **Step 4: Implement `emit_entity_index`**

```python
def emit_entity_index(conn, args, out_dir, file_to_source):
    import hashlib
    records = []
    for row in conn.execute(ENTITIES_QUERY):
        symbol_id, name, cg_kind, file_id, start_line, end_line, _, _ = row
        v1_kind = CODEGRAPH_KIND_TO_V1.get(cg_kind, cg_kind or "unknown")
        # Deterministic id: stable across re-runs, hash of (project, source, name, kind, line).
        h = hashlib.sha256(
            f"{args.project}|{file_to_source.get(file_id, '')}|{name}|{v1_kind}|{start_line}"
            .encode()
        ).hexdigest()[:12]
        records.append({
            "entity_id": f"ent_{args.project}_{h}",
            "project": args.project,
            "name": name,
            "kind": v1_kind,
            "language": None,  # filled from a join in a follow-up; not required by consumers
            "source_id": file_to_source.get(file_id),
            "start_line": start_line,
            "end_line": end_line,
            "extractor": "codegraph_tree_sitter_v2",
        })
    write_jsonl(out_dir / "entity_index.jsonl", records, CANONICAL_ENTITY_FIELDS)
    return {row[0]: rec["entity_id"]  # symbol_id -> entity_id
            for row, rec in zip(conn.execute(ENTITIES_QUERY), records)}
```

Wire it into `main()` after `emit_source_inventory`.

- [ ] **Step 5: Run + commit (same pattern as Task 2)**

```bash
uv run pytest tests/test_codegraph_to_bundle.py -v
git add … && git commit -m "feat(analyzer-v2/phase-2): emit entity_index.jsonl from codegraph"
```

---

### Task 4: Emit `relation_graph.jsonl` with resolved `object.id` and `included_first_substantive_line`

**Files:**
- Modify: `schemas/relation-graph.schema.json` — bump to v1.1; add predicates + new evidence field.
- Modify: `skills/benchmark-repo-analyzer/scripts/codegraph_to_bundle.py` — add `emit_relation_graph`.
- Modify: `skills/benchmark-repo-analyzer/scripts/_bundle_writer.py` — add `CANONICAL_RELATION_FIELDS` + first-substantive-line helper.
- Modify: `tests/fixtures/codegraph_to_bundle/_build_tiny_db.py` — add 4 relations (defines, instantiates, imports, calls).
- Create: `tests/fixtures/codegraph_to_bundle/expected/relation_graph.jsonl`.
- Modify: `tests/test_codegraph_to_bundle.py` — add relation-graph + schema-validation tests.

**Interfaces:**
- Consumes: the `symbol_id -> entity_id` map from Task 3; `_codegraph_queries.RELATIONS_QUERY`; for `imports_or_includes`, the included file's text (read from `repo_sources/`) to compute `included_first_substantive_line`.
- Produces: a relation-graph that (a) carries resolved `object.id` on `imports_or_includes`, (b) emits `instantiates` / `calls` / `imports` (new predicates), (c) drops `contains` edges (D6), (d) sets `confidence: 0.95` on AST-derived rows. Phase 3's signal emitter and Phase 4's prepare integration depend on all four.

Reference v1 relation shape:

```json
{"confidence": 0.62, "evidence": [{"lines": "1", "path": "...", "source_id": "...",
 "summary": "... defines config_key `name`."}], "extractor": "config_key_regex_fallback",
 "object": {"id": "ent_vortex_5595509218e4", "name": "name", "type": "entity"},
 "predicate": "defines", "project": "vortex", "relation_id": "rel_vortex_0000001",
 "subject": {"id": "src_vortex_00002", "name": "...", "type": "source"}}
```

v2 additions for `imports_or_includes`:

```json
{ ..., "evidence": [{"lines": "12", "path": "<includer>", "source_id": "<includer_src>",
 "summary": "<includer> includes <basename>.", "included_first_substantive_line": 17}]}
```

- [ ] **Step 1: Schema bump**

Edit `schemas/relation-graph.schema.json`:
- Add the version annotation `"$comment": "v1.1 — adds instantiates/calls/imports predicates and included_first_substantive_line"`.
- Add `instantiates`, `calls`, `imports` to the `predicate` enum.
- Add `included_first_substantive_line` (integer, ≥ 1) to the evidence item schema as optional.

Run the existing validator tests to confirm v1 records still pass:

```bash
uv run pytest tests/test_validate_benchmark_v1_1.py -v
uv run pytest tests/ -k 'context_bundle' -v
```

Expected: all pass; no v1 record fails under the bumped schema.

- [ ] **Step 2: First-substantive-line helper**

In `_bundle_writer.py`:

```python
# Reuses the same heuristic as
# skills/benchmark-generator/scripts/prepare_module_inputs.py:_find_first_substantive_line
# Once that helper is shared (a follow-on cleanup), import from one place.

import re
_NONSUBSTANTIVE = re.compile(
    r"^\s*(//.*|/\*.*|\*.*|#.*|`(ifndef|ifdef|define|endif|include).*|$)"
)


def first_substantive_line(path: Path) -> int:
    try:
        for i, line in enumerate(path.read_text(errors="replace").splitlines(), start=1):
            if not _NONSUBSTANTIVE.match(line):
                return i
    except OSError:
        pass
    return 1
```

- [ ] **Step 3: Implement `emit_relation_graph`**

```python
def emit_relation_graph(conn, args, out_dir, file_to_source, symbol_to_entity):
    records = []
    for ordinal, row in enumerate(conn.execute(RELATIONS_QUERY), start=1):
        (rel_id, pred, src_sym, src_file, tgt_sym, tgt_file, tgt_name,
         start_line, end_line, metadata_json) = row
        if pred == "contains":
            continue  # D6: dropped in v2
        rec = {
            "confidence": 0.95,
            "evidence": [],
            "extractor": "codegraph_tree_sitter_v2",
            "object": {
                "id": symbol_to_entity.get(tgt_sym) or file_to_source.get(tgt_file) or "",
                "name": tgt_name or "",
                "type": "entity" if symbol_to_entity.get(tgt_sym) else "source",
            },
            "predicate": pred,
            "project": args.project,
            "relation_id": f"rel_{args.project}_{ordinal:07d}",
            "subject": {
                "id": symbol_to_entity.get(src_sym) or file_to_source.get(src_file) or "",
                "name": "",  # filled in a follow-up; not required by consumers
                "type": "entity" if symbol_to_entity.get(src_sym) else "source",
            },
        }
        if pred == "imports_or_includes" or pred == "imports":
            target_file = _lookup_target_file_path(conn, tgt_file)
            if target_file:
                rec["evidence"].append({
                    "lines": str(start_line) if start_line else "1",
                    "path": _includer_path(conn, src_file),
                    "source_id": file_to_source.get(src_file, ""),
                    "summary": f"includes {Path(target_file).name}",
                    "included_first_substantive_line":
                        first_substantive_line(Path(target_file)),
                })
        records.append(rec)
    write_jsonl(out_dir / "relation_graph.jsonl", records, CANONICAL_RELATION_FIELDS)
```

The helpers `_lookup_target_file_path` and `_includer_path` are 3-line wrappers around the `files` table; implement inline.

- [ ] **Step 4: Fixture + test**

Extend the fixture with 4 relations (one of each predicate the exporter emits). Hand-author the expected output. Add the assertion in `tests/test_codegraph_to_bundle.py`. Also add a schema-validation assertion:

```python
def test_relation_graph_validates_against_schema_v1_1(tmp_path):
    import jsonschema, json
    out = _run_export(tmp_path)
    schema = json.loads((ROOT / "schemas/relation-graph.schema.json").read_text())
    for line in (out / "relation_graph.jsonl").read_text().splitlines():
        jsonschema.validate(json.loads(line), schema)
```

- [ ] **Step 5: Run + commit**

```bash
uv run pytest tests/test_codegraph_to_bundle.py -v
git add schemas/relation-graph.schema.json \
        skills/benchmark-repo-analyzer/scripts/codegraph_to_bundle.py \
        skills/benchmark-repo-analyzer/scripts/_bundle_writer.py \
        tests/fixtures/codegraph_to_bundle/ \
        tests/test_codegraph_to_bundle.py
git commit -m "feat(analyzer-v2/phase-2): emit relation_graph v1.1 with resolved targets"
```

---

### Task 5: Emit `project_manifest.json` and `analyzer_report.md`

**Files:**
- Modify: `skills/benchmark-repo-analyzer/scripts/codegraph_to_bundle.py` — add `emit_project_manifest` and `emit_analyzer_report`.
- Create: `tests/fixtures/codegraph_to_bundle/expected/project_manifest.json`.
- Modify: `tests/test_codegraph_to_bundle.py` — add manifest assertion (allow timestamp wildcarding).

**Interfaces:**
- Consumes: counts collected during emits in Tasks 2–4; CodeGraph commit pin from `runs/feasibility_v2_analyzer/_codegraph_commit.txt`.
- Produces: a manifest whose `analyzer_version` and `analysis_backends.code.used_primary` are the canonical marker of v2 vs v1 (Phase 5 grep) and a short markdown report (counts + top-five most-referenced entities) for human review.

Acceptance bullet from source plan: `analyzer_version: benchmark-repo-analyzer/v2-tree-sitter-codegraph` and `analysis_backends.code.used_primary: true`.

- [ ] **Step 1: Implement manifest emitter**

```python
def emit_project_manifest(args, out_dir, counts: dict, cg_pin: str):
    import datetime, json
    manifest = {
        "analyzer_version": "benchmark-repo-analyzer/v2-tree-sitter-codegraph",
        "analyzer_pin": {"codegraph_commit": cg_pin},
        "analysis_backends": {
            "code": {"requested_primary": "code_graph", "used_primary": True},
        },
        "counts": counts,
        "generated_at": datetime.datetime.utcnow().isoformat() + "Z",
        "project": args.project,
        "source_set_id": args.source_set_id,
    }
    (out_dir / "project_manifest.json").write_text(json.dumps(manifest, indent=2))
```

- [ ] **Step 2: Implement report emitter**

```python
def emit_analyzer_report(args, out_dir, counts: dict, top_entities: list[tuple[str, int]]):
    lines = [
        f"# Analyzer report — {args.project}",
        "",
        f"- analyzer: `benchmark-repo-analyzer/v2-tree-sitter-codegraph`",
        f"- sources: {counts['sources']}",
        f"- entities: {counts['entities']}",
        f"- relations: {counts['relations']} (dropped `contains`: {counts['contains_dropped']})",
        "",
        "## Top inbound-edge entities",
        ""
    ] + [f"- {name}: {n}" for name, n in top_entities[:5]]
    (out_dir / "analyzer_report.md").write_text("\n".join(lines) + "\n")
```

Plumb `counts` through `main()` (each emitter returns its count).

- [ ] **Step 3: Test**

```python
def test_manifest_marks_v2_primary(tmp_path):
    import json
    out = _run_export(tmp_path)
    m = json.loads((out / "project_manifest.json").read_text())
    assert m["analyzer_version"] == "benchmark-repo-analyzer/v2-tree-sitter-codegraph"
    assert m["analysis_backends"]["code"]["used_primary"] is True
```

- [ ] **Step 4: Run + commit**

```bash
uv run pytest tests/test_codegraph_to_bundle.py -v
git add … && git commit -m "feat(analyzer-v2/phase-2): emit project_manifest + analyzer_report"
```

---

### Task 6: Add `--diff-against <v1-bundle-dir>` flag

**Files:**
- Create: `skills/benchmark-repo-analyzer/scripts/_diff.py`
- Modify: `skills/benchmark-repo-analyzer/scripts/codegraph_to_bundle.py` — wire the flag.
- Modify: `tests/test_codegraph_to_bundle.py` — diff-output smoke.

**Interfaces:**
- Consumes: a path to a v1 bundle directory; the v2 output the exporter just produced.
- Produces: a human-readable `<out>/_diff_vs_v1.md` showing entity-count delta, predicate-distribution delta, and a per-source-set delta of resolved-target coverage. Never modifies the canonical artifacts.

The diff is for humans only. Do not embed it in the manifest. Phase 5's parity sweep is its only consumer.

- [ ] **Step 1: Implement the diff helper**

```python
"""Compare a v2 bundle dir against a v1 bundle dir and write a markdown report."""
from __future__ import annotations
import json
from collections import Counter
from pathlib import Path


def _load_jsonl(p: Path) -> list[dict]:
    return [json.loads(l) for l in p.read_text().splitlines()] if p.exists() else []


def diff(v2_dir: Path, v1_dir: Path) -> str:
    v1_rels = _load_jsonl(v1_dir / "relation_graph.jsonl")
    v2_rels = _load_jsonl(v2_dir / "relation_graph.jsonl")
    v1_ents = _load_jsonl(v1_dir / "entity_index.jsonl")
    v2_ents = _load_jsonl(v2_dir / "entity_index.jsonl")

    v1_pred = Counter(r["predicate"] for r in v1_rels)
    v2_pred = Counter(r["predicate"] for r in v2_rels)
    v1_ent_kinds = Counter(e["kind"] for e in v1_ents)
    v2_ent_kinds = Counter(e["kind"] for e in v2_ents)

    out = ["# v2 vs v1 bundle diff\n",
           f"\n- entities: v1={len(v1_ents)} v2={len(v2_ents)}",
           f"\n- relations: v1={len(v1_rels)} v2={len(v2_rels)}",
           "\n\n## Predicate distribution\n",
           "| predicate | v1 | v2 |\n|---|---|---|"]
    for k in sorted(set(v1_pred) | set(v2_pred)):
        out.append(f"\n| {k} | {v1_pred[k]} | {v2_pred[k]} |")
    out.append("\n\n## Entity kind distribution\n")
    out.append("| kind | v1 | v2 |\n|---|---|---|")
    for k in sorted(set(v1_ent_kinds) | set(v2_ent_kinds)):
        out.append(f"\n| {k} | {v1_ent_kinds[k]} | {v2_ent_kinds[k]} |")
    return "".join(out) + "\n"
```

- [ ] **Step 2: Wire the flag**

```python
ap.add_argument("--diff-against", type=Path,
                help="If set, write _diff_vs_v1.md comparing the v2 output to this v1 bundle dir.")
# ... after emits:
if args.diff_against:
    from _diff import diff as _diff_fn
    (args.out / "_diff_vs_v1.md").write_text(_diff_fn(args.out, args.diff_against))
```

- [ ] **Step 3: Smoke test**

Add to `tests/test_codegraph_to_bundle.py`:

```python
def test_diff_against_v1_writes_markdown(tmp_path):
    out = _run_export(tmp_path, extra_args=["--diff-against", str(FIXTURE_V1_DIR)])
    diff_md = (out / "_diff_vs_v1.md").read_text()
    assert "Predicate distribution" in diff_md
```

`FIXTURE_V1_DIR` should be a minimal hand-built v1 bundle dir under `tests/fixtures/codegraph_to_bundle/v1_baseline/`.

- [ ] **Step 4: Run + commit**

```bash
uv run pytest tests/test_codegraph_to_bundle.py -v
git add … && git commit -m "feat(analyzer-v2/phase-2): --diff-against flag for v1/v2 comparison"
```

---

### Task 7: Real-data acceptance on Vortex

**Files:**
- Create (by running): `runs/vortex_context_bundle_v2/` (entire bundle).
- Create (by running): `runs/vortex_context_bundle_v2/_diff_vs_v1.md`.
- Create: `runs/feasibility_v2_analyzer/phase2_acceptance.md`.
- Modify: `analyzer_v2_codegraph_treesitter_plan.md` § 9 — Phase 2 row to `complete`.

**Interfaces:**
- Consumes: the Vortex CodeGraph DB indexed by the Phase 1 fork (Phase 1 acceptance step 2).
- Produces: a v2 bundle directory + a diff report that proves the four Phase 2 acceptance checks from the source plan. Phase 3 reads this.

- [ ] **Step 1: Run the exporter**

```bash
source <(grep '^CG_' runs/feasibility_v2_analyzer/_codegraph_paths.md | sed 's/^/export /')
uv run python skills/benchmark-repo-analyzer/scripts/codegraph_to_bundle.py \
    --db "$CG_DB" --project vortex --source-set-id vortex_main \
    --repo-name vortex/vortex \
    --out runs/vortex_context_bundle_v2/ \
    --diff-against runs/vortex_context_bundle/
```

Expected: the directory contains all five files (`source_inventory`, `entity_index`, `relation_graph`, `project_manifest`, `analyzer_report`) plus `_diff_vs_v1.md`.

- [ ] **Step 2: Run the bundle validator on the v2 dir**

```bash
uv run python skills/benchmark-repo-analyzer/scripts/validate_context_bundle.py \
    --bundle runs/vortex_context_bundle_v2/
```

Expected: all jsonl files pass v1 schemas plus the bumped v1.1 relation-graph schema.

- [ ] **Step 3: Acceptance assertions (manual + scripted)**

```bash
# Entity-count parity check
jq -s 'length' runs/vortex_context_bundle/entity_index.jsonl
jq -s 'length' runs/vortex_context_bundle_v2/entity_index.jsonl

# All imports_or_includes carry resolved object.id?
jq -c 'select(.predicate=="imports_or_includes" or .predicate=="imports")
        | select(.object.id == "" or .object.id == null)' \
    runs/vortex_context_bundle_v2/relation_graph.jsonl | wc -l
# Expected: 0
```

- [ ] **Step 4: Write the acceptance report**

`runs/feasibility_v2_analyzer/phase2_acceptance.md` — mirror the Phase 1 acceptance template, ticking off the four source-plan acceptance bullets and noting any deltas in entity counts vs v1.

- [ ] **Step 5: Commit + tracker update**

```bash
# Flip § 9 Phase 2 row to complete.
git add analyzer_v2_codegraph_treesitter_plan.md \
        runs/feasibility_v2_analyzer/phase2_acceptance.md
git commit -m "docs(analyzer-v2/phase-2): acceptance on vortex; phase-3 GO"
```

---

## Acceptance for "Phase 2 is done"

1. `tests/test_codegraph_to_bundle.py` passes (covers source/entity/relation/manifest/diff against the tiny fixture).
2. `schemas/relation-graph.schema.json` is bumped to v1.1 and the existing v1 bundle still validates.
3. `runs/vortex_context_bundle_v2/` exists with all five canonical files.
4. Zero `imports_or_includes` edges in the v2 Vortex bundle have an empty `object.id`.
5. `project_manifest.json` reports `analyzer_version: benchmark-repo-analyzer/v2-tree-sitter-codegraph` and `analysis_backends.code.used_primary: true`.
6. `runs/vortex_context_bundle_v2/_diff_vs_v1.md` shows non-zero counts for at least one new predicate (`instantiates` or `imports`).
7. `runs/feasibility_v2_analyzer/phase2_acceptance.md` ends with `Phase 3 GO`.
