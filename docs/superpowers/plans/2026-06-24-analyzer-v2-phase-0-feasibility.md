# Analyzer v2 — Phase 0: Feasibility + Scoping Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Decide whether `tree-sitter-verilog` alone is enough RTL coverage for Vortex/NVDLA, and confirm CodeGraph indexes our non-RTL surface cleanly, before committing to the multi-week Phase 1 build.

**Architecture:** Two parallel measurement tracks — (a) parse every Vortex/NVDLA RTL file with `tree-sitter-verilog` and tally parse status + presence of expected AST node kinds; (b) install CodeGraph and run it on the non-RTL slice to confirm it builds a populated SQLite DB and resolves cross-file references. Outputs land in `runs/feasibility_v2_analyzer/` and a single `runs/feasibility_v2_analyzer.md` summary report that triggers a hard decision on Phase 1 / Phase 6 scope.

**Tech Stack:** Python 3 + `tree_sitter` + `tree-sitter-verilog`; Node.js + CodeGraph CLI; SQLite CLI; existing repo conventions (`uv` for Python deps, scripts under `scripts/` or skill-local).

## Global Constraints

- Source RTL paths: `repo_sources/vortex/**/*.{sv,v,svh,vh}` and `repo_sources/nvdla/**/*.{sv,v,svh,vh}`. Do not mutate `repo_sources/`.
- Feasibility outputs live under `runs/feasibility_v2_analyzer/`; never overwrite the existing v1 bundles at `runs/{vortex,nvdla}_context_bundle/`.
- Python deps go through `uv add`; do not edit `pyproject.toml` by hand.
- Node deps for CodeGraph are installed into a project-local `tools/codegraph/` checkout — do not install CodeGraph globally on the dev machine. CodeGraph upstream is `https://github.com/colbymchenry/codegraph`; the exact install command is discovered in Task 4, not assumed.
- All scripts are idempotent: re-running them overwrites the previous output rather than appending.
- This phase ships nothing into the production pipeline. The only mutating outputs are inside `runs/feasibility_v2_analyzer/` and a new `scripts/feasibility/` directory.

---

## File Structure

Create:

- `scripts/feasibility/measure_rtl_parse_coverage.py` — parses a directory of RTL files with tree-sitter-verilog, emits per-file JSON records (parse status + node-kind histogram) plus a summary.
- `scripts/feasibility/probe_codegraph_resolution.py` — runs five canned `codegraph` queries against the indexed DB and writes a transcript.
- `scripts/feasibility/dump_codegraph_schema.py` — opens the SQLite DB, dumps schema + row counts to JSON.
- `runs/feasibility_v2_analyzer/` — output directory (gitignored except for the report).
- `runs/feasibility_v2_analyzer.md` — final 2–3 page feasibility report. **This is the canonical Phase 0 deliverable.**
- `tools/codegraph/` — local checkout of the CodeGraph repo (gitignored).

Modify:

- `.gitignore` — add `tools/codegraph/` and `runs/feasibility_v2_analyzer/*.json` / `*.jsonl` (keep the `.md` report tracked).
- `analyzer_v2_codegraph_treesitter_plan.md` § 9 — update Phase 0 row to `complete | <date> | parse_rate=<x>%, fork pinned at <sha>` once Task 7 ships.

Do not modify:

- Any file under `repo_sources/`, `runs/vortex_context_bundle/`, `runs/nvdla_context_bundle/`, `skills/benchmark-repo-analyzer/`, `schemas/`.

---

### Task 1: Bootstrap tree-sitter-verilog Python environment

**Files:**
- Modify: `pyproject.toml` (via `uv add`, not by hand)
- Create: `scripts/feasibility/__init__.py` (empty marker)
- Create: `scripts/feasibility/_check_tsv_smoke.py` (throwaway, deleted at end of task)

**Interfaces:**
- Consumes: nothing.
- Produces: a Python interpreter where `import tree_sitter_verilog` and `import tree_sitter` both succeed, and `Parser(Language(tree_sitter_verilog.language()))` parses a one-module SV string into a non-error root node. Later tasks rely on these import paths.

- [ ] **Step 1: Add the two PyPI deps**

```bash
uv add tree-sitter tree-sitter-verilog
```

Expected: `pyproject.toml` gains `tree-sitter` and `tree-sitter-verilog` in `[project] dependencies`; `uv.lock` updates.

If `uv add tree-sitter-verilog` fails because the wheel is unavailable on this platform, fall back to:

```bash
uv add tree-sitter tree-sitter-languages
```

…and substitute `from tree_sitter_languages import get_language; lang = get_language("verilog")` for the import shown in Step 3. Record which path was taken in Task 7's report.

- [ ] **Step 2: Write a 10-line smoke parser**

Create `scripts/feasibility/_check_tsv_smoke.py`:

```python
"""Throwaway smoke test that tree-sitter-verilog is wired up correctly.

Deleted at the end of Phase 0 Task 1; do not import from this file.
"""
from tree_sitter import Language, Parser
import tree_sitter_verilog as tsv

SRC = b"""
module foo #(parameter int W = 8) (input logic clk, output logic [W-1:0] q);
  always_ff @(posedge clk) q <= q + 1;
endmodule
"""

parser = Parser(Language(tsv.language()))
tree = parser.parse(SRC)
root = tree.root_node
print(f"root.type={root.type} has_error={root.has_error} child_count={root.child_count}")
for child in root.children:
    print(f"  {child.type} [{child.start_byte}:{child.end_byte}]")
```

- [ ] **Step 3: Run the smoke and verify**

```bash
uv run python scripts/feasibility/_check_tsv_smoke.py
```

Expected (exact node names may differ slightly between tree-sitter-verilog versions; the *shape* is what matters):

```
root.type=source_file has_error=False child_count=1
  module_declaration [...]
```

Fail conditions: `has_error=True`, `child_count=0`, or any traceback. If the import fails, fall through to the `tree-sitter-languages` path from Step 1.

**Record the exact root child type name** (`module_declaration` vs `module_header` vs another) — Task 2 reuses it as an expected-kind. Write it into a one-line note: `runs/feasibility_v2_analyzer/_observed_node_kinds.md`.

- [ ] **Step 4: Delete the smoke and commit**

```bash
rm scripts/feasibility/_check_tsv_smoke.py
git add pyproject.toml uv.lock scripts/feasibility/__init__.py runs/feasibility_v2_analyzer/_observed_node_kinds.md
git commit -m "feat(analyzer-v2): add tree-sitter + tree-sitter-verilog python deps"
```

---

### Task 2: Measure tree-sitter-verilog parse coverage on Vortex RTL

**Files:**
- Create: `scripts/feasibility/measure_rtl_parse_coverage.py`
- Create (by running): `runs/feasibility_v2_analyzer/vortex_rtl_coverage.jsonl` (per-file records) and `runs/feasibility_v2_analyzer/vortex_rtl_coverage.summary.json` (aggregates).
- Test: this is a measurement task; the "test" is asserting the output shape via a small `--self-check` flag, not pytest.

**Interfaces:**
- Consumes: the `tree_sitter_verilog.language()` import path validated in Task 1; the observed root node kind from `_observed_node_kinds.md`.
- Produces: a per-file JSONL where each record is `{"path": str, "parse_status": "clean" | "partial" | "error", "node_kind_counts": dict, "error_count": int, "size_bytes": int}` and a summary JSON `{"total_files": int, "clean": int, "partial": int, "error": int, "files_with_kind": dict, "parse_rate_pct": float}`. Task 7 reads both.

- [ ] **Step 1: Write the measurement script**

Create `scripts/feasibility/measure_rtl_parse_coverage.py`:

```python
#!/usr/bin/env python3
"""Walk an RTL directory, parse each .sv/.v/.svh/.vh file with
tree-sitter-verilog, and emit per-file + summary JSON.

Usage:
  uv run python scripts/feasibility/measure_rtl_parse_coverage.py \
      --root repo_sources/vortex \
      --out-jsonl runs/feasibility_v2_analyzer/vortex_rtl_coverage.jsonl \
      --out-summary runs/feasibility_v2_analyzer/vortex_rtl_coverage.summary.json

Exits 0 on success regardless of parse outcomes (this is measurement, not gating).
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

from tree_sitter import Language, Parser
import tree_sitter_verilog as tsv

RTL_SUFFIXES = {".sv", ".v", ".svh", ".vh"}

EXPECTED_KINDS = {
    "module_declaration",
    "parameter_declaration",
    "always_construct",  # tree-sitter-verilog typically uses always_construct, not always_block
    "if_statement",
    "case_statement",
    "module_instantiation",
}


def classify(root) -> str:
    if not root.has_error:
        return "clean"
    # any ERROR node in tree => at least partial
    err_count = sum(1 for n in walk(root) if n.type == "ERROR" or n.is_missing)
    total = sum(1 for _ in walk(root))
    if err_count == 0:
        return "clean"
    if err_count / max(total, 1) < 0.05:
        return "partial"
    return "error"


def walk(node):
    yield node
    for c in node.children:
        yield from walk(c)


def kind_counts(root) -> Counter:
    return Counter(n.type for n in walk(root))


def collect_files(root: Path) -> list[Path]:
    return sorted(p for p in root.rglob("*") if p.suffix in RTL_SUFFIXES and p.is_file())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True, type=Path)
    ap.add_argument("--out-jsonl", required=True, type=Path)
    ap.add_argument("--out-summary", required=True, type=Path)
    ap.add_argument("--self-check", action="store_true",
                    help="Only validate output schema by writing one synthetic record.")
    args = ap.parse_args()

    args.out_jsonl.parent.mkdir(parents=True, exist_ok=True)
    parser = Parser(Language(tsv.language()))

    if args.self_check:
        sample = {"path": "synthetic", "parse_status": "clean",
                  "node_kind_counts": {"module_declaration": 1},
                  "error_count": 0, "size_bytes": 0}
        args.out_jsonl.write_text(json.dumps(sample) + "\n")
        args.out_summary.write_text(json.dumps({
            "total_files": 1, "clean": 1, "partial": 0, "error": 0,
            "files_with_kind": {"module_declaration": 1},
            "parse_rate_pct": 100.0,
        }, indent=2))
        return 0

    files = collect_files(args.root)
    by_status = Counter()
    files_with_kind = Counter()
    with args.out_jsonl.open("w") as out:
        for p in files:
            data = p.read_bytes()
            tree = parser.parse(data)
            status = classify(tree.root_node)
            by_status[status] += 1
            counts = kind_counts(tree.root_node)
            for k in EXPECTED_KINDS:
                if counts.get(k, 0) > 0:
                    files_with_kind[k] += 1
            rec = {
                "path": str(p.relative_to(args.root)),
                "parse_status": status,
                "node_kind_counts": {k: counts[k] for k in EXPECTED_KINDS},
                "error_count": sum(1 for n in walk(tree.root_node)
                                   if n.type == "ERROR" or n.is_missing),
                "size_bytes": len(data),
            }
            out.write(json.dumps(rec) + "\n")

    total = len(files)
    summary = {
        "total_files": total,
        "clean": by_status["clean"],
        "partial": by_status["partial"],
        "error": by_status["error"],
        "files_with_kind": dict(files_with_kind),
        "parse_rate_pct": round(100.0 * by_status["clean"] / max(total, 1), 2),
    }
    args.out_summary.write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Self-check the script's I/O shape**

```bash
mkdir -p runs/feasibility_v2_analyzer
uv run python scripts/feasibility/measure_rtl_parse_coverage.py \
    --root repo_sources/vortex \
    --out-jsonl /tmp/_selfcheck.jsonl \
    --out-summary /tmp/_selfcheck.summary.json \
    --self-check
test -s /tmp/_selfcheck.jsonl && cat /tmp/_selfcheck.summary.json
```

Expected: a one-line JSONL and a summary JSON with `total_files: 1, parse_rate_pct: 100.0`. If the schema fields don't match what's in the script above, fix the script before continuing.

- [ ] **Step 3: Run against Vortex**

```bash
uv run python scripts/feasibility/measure_rtl_parse_coverage.py \
    --root repo_sources/vortex \
    --out-jsonl runs/feasibility_v2_analyzer/vortex_rtl_coverage.jsonl \
    --out-summary runs/feasibility_v2_analyzer/vortex_rtl_coverage.summary.json
```

Expected: a printed summary with `total_files` around 201 (matches the source-doc count; if it differs by more than ±5%, investigate before proceeding — either the RTL set has changed or the suffix filter is wrong).

- [ ] **Step 4: Note the parse-rate bucket**

Open the printed summary and record the bucket in `runs/feasibility_v2_analyzer/_observed_node_kinds.md`:

- `parse_rate_pct >= 95.0` → Phase 6 skipped
- `80.0 <= parse_rate_pct < 95.0` → Phase 6 needed (Verible secondary)
- `parse_rate_pct < 80.0` → abort plan; reconsider RTL parser choice

This single number drives Task 7's recommendation.

- [ ] **Step 5: Commit**

```bash
git add scripts/feasibility/measure_rtl_parse_coverage.py \
        runs/feasibility_v2_analyzer/vortex_rtl_coverage.summary.json \
        runs/feasibility_v2_analyzer/_observed_node_kinds.md
# vortex_rtl_coverage.jsonl is gitignored (added in Task 7); skip it here.
git commit -m "feat(analyzer-v2/phase-0): measure tree-sitter-verilog coverage on vortex rtl"
```

---

### Task 3: Measure tree-sitter-verilog parse coverage on NVDLA RTL sample

**Files:**
- Modify: none (reuses Task 2's script)
- Create (by running): `runs/feasibility_v2_analyzer/nvdla_rtl_coverage.jsonl` and `runs/feasibility_v2_analyzer/nvdla_rtl_coverage.summary.json`.

**Interfaces:**
- Consumes: `scripts/feasibility/measure_rtl_parse_coverage.py` from Task 2; an NVDLA RTL root path.
- Produces: same shape as Task 2's output, scoped to NVDLA. Task 7 compares the Vortex and NVDLA parse-rate buckets — they may diverge.

- [ ] **Step 1: Locate the NVDLA RTL root**

```bash
find repo_sources/nvdla -type d -name 'vmod' -o -name 'rtl' 2>/dev/null | head
ls repo_sources/nvdla/ 2>/dev/null | head
```

Expected: a directory containing `.v` / `.sv` files, e.g. `repo_sources/nvdla/<repo>/vmod`. If the layout has multiple RTL roots, pick the one with the most files (`find <candidate> -name '*.v' -o -name '*.sv' | wc -l`). Record the chosen path in `runs/feasibility_v2_analyzer/_observed_node_kinds.md`.

If no NVDLA RTL is present in `repo_sources/`, skip Tasks 3 and proceed; document the skip in Task 7. Do not block on missing NVDLA — the Phase 1 trigger is the Vortex bucket.

- [ ] **Step 2: Run with the same script (no sub-sampling — measure everything; ~50 was the source-doc minimum, not a cap)**

```bash
uv run python scripts/feasibility/measure_rtl_parse_coverage.py \
    --root <nvdla-rtl-root-from-step-1> \
    --out-jsonl runs/feasibility_v2_analyzer/nvdla_rtl_coverage.jsonl \
    --out-summary runs/feasibility_v2_analyzer/nvdla_rtl_coverage.summary.json
```

Expected: same JSON shape as Vortex; `total_files` ≥ 50 (per source-doc minimum).

- [ ] **Step 3: Commit**

```bash
git add runs/feasibility_v2_analyzer/nvdla_rtl_coverage.summary.json \
        runs/feasibility_v2_analyzer/_observed_node_kinds.md
git commit -m "feat(analyzer-v2/phase-0): measure tree-sitter-verilog coverage on nvdla rtl"
```

---

### Task 4: Install CodeGraph locally and index Vortex non-RTL

**Files:**
- Create: `tools/codegraph/` (cloned, gitignored).
- Modify: `.gitignore` — add `tools/codegraph/` and `runs/feasibility_v2_analyzer/*.jsonl`.
- Create (by running): `repo_sources/vortex/.codegraph/codegraph.db` or the path CodeGraph chooses for its SQLite DB. **Path is unknown until install — record the actual path** in `runs/feasibility_v2_analyzer/_codegraph_paths.md` once observed.

**Interfaces:**
- Consumes: Node.js >= 18 on `$PATH` (verify in Step 1); the Vortex non-RTL source tree at `repo_sources/vortex/`.
- Produces: a populated SQLite DB at a known path, and a recorded `codegraph` CLI binary path. Tasks 5 and 6 reuse both.

- [ ] **Step 1: Verify Node is installed**

```bash
node --version
npm --version
```

Expected: Node ≥ 18 (CodeGraph's likely floor; if the README disagrees, follow it). If absent, stop and ask the user to install Node before continuing — do not silently `brew install`.

- [ ] **Step 2: Clone CodeGraph into a project-local tools dir**

```bash
mkdir -p tools
git clone https://github.com/colbymchenry/codegraph tools/codegraph
cd tools/codegraph && git rev-parse HEAD > ../../runs/feasibility_v2_analyzer/_codegraph_commit.txt && cd -
```

Expected: a clone with `package.json` at `tools/codegraph/package.json`; the recorded HEAD sha goes into Task 7's report and becomes the pin candidate for Phase 1 D4.

- [ ] **Step 3: Install dependencies per the upstream README**

```bash
cd tools/codegraph
cat README.md | head -80          # discover the actual install command
# Most likely: npm install   (run whatever the README prescribes)
npm install
cd -
```

Expected: `node_modules/` populated under `tools/codegraph/`. **Do not** install globally (no `npm install -g`).

If the upstream README prescribes a different runtime (pnpm, yarn, bun), follow it and record the deviation in `_codegraph_paths.md`.

- [ ] **Step 4: Locate the CLI entry point**

```bash
ls tools/codegraph/bin/ 2>/dev/null
jq -r '.bin' tools/codegraph/package.json 2>/dev/null
```

Expected: an executable path, e.g. `tools/codegraph/bin/codegraph` or `tools/codegraph/dist/cli.js`. Record it as `CG_BIN=<path>` in `runs/feasibility_v2_analyzer/_codegraph_paths.md`. Tasks 5 and 6 reference this variable.

- [ ] **Step 5: Index Vortex non-RTL**

CodeGraph's invocation flags are not knowable from this plan — use the upstream README. The intent is: index `repo_sources/vortex/` while excluding `*.sv`, `*.v`, `*.svh`, `*.vh`. Concretely, something like:

```bash
"$CG_BIN" index repo_sources/vortex --exclude '**/*.sv' --exclude '**/*.v' \
                                    --exclude '**/*.svh' --exclude '**/*.vh' \
    2>&1 | tee runs/feasibility_v2_analyzer/codegraph_index_vortex.log
```

Expected: command exits 0; the log shows files being indexed (C, C++, Python, Markdown, YAML, …); the SQLite DB lands at whatever path the tool chose. Find it:

```bash
find . -name 'codegraph*.db' -newer runs/feasibility_v2_analyzer/_codegraph_commit.txt 2>/dev/null
```

Record the path as `CG_DB=<path>` in `_codegraph_paths.md`.

- [ ] **Step 6: Sanity-check DB population**

```bash
sqlite3 "$CG_DB" '.tables' | tee runs/feasibility_v2_analyzer/codegraph_tables.txt
sqlite3 "$CG_DB" 'SELECT name, sql FROM sqlite_master WHERE type="table" LIMIT 5;'
```

Expected: at least one table whose name suggests files/symbols/nodes; non-zero row counts in those tables. If the DB is empty, the index command in Step 5 silently failed — re-read the log before continuing.

- [ ] **Step 7: Update .gitignore and commit metadata**

Edit `.gitignore` to add:

```
tools/codegraph/
runs/feasibility_v2_analyzer/*.jsonl
runs/feasibility_v2_analyzer/*.log
```

Then:

```bash
git add .gitignore \
        runs/feasibility_v2_analyzer/_codegraph_commit.txt \
        runs/feasibility_v2_analyzer/_codegraph_paths.md \
        runs/feasibility_v2_analyzer/codegraph_tables.txt
git commit -m "feat(analyzer-v2/phase-0): install codegraph and index vortex non-rtl"
```

---

### Task 5: Verify CodeGraph cross-file resolution on sample queries

**Files:**
- Create: `scripts/feasibility/probe_codegraph_resolution.py`
- Create (by running): `runs/feasibility_v2_analyzer/codegraph_probe_transcript.md`

**Interfaces:**
- Consumes: `CG_BIN` and `CG_DB` from Task 4's `_codegraph_paths.md`.
- Produces: a markdown transcript with query → response pairs that demonstrate (or fail to demonstrate) cross-file resolution. Task 7 reads it.

- [ ] **Step 1: Write the probe script**

Create `scripts/feasibility/probe_codegraph_resolution.py`:

```python
#!/usr/bin/env python3
"""Run five canned codegraph CLI queries and write a markdown transcript.

The five probes target capabilities we depend on for Phase 1+:
  1. Symbol lookup by name (any-language).
  2. Cross-file include/import resolution (C++ #include).
  3. Function definition lookup (Python).
  4. Cross-file call resolution.
  5. Exact-text search via FTS5.

Treat any non-zero exit or empty payload as a failure; record both in the transcript.
"""
from __future__ import annotations

import argparse
import os
import shlex
import subprocess
import sys
from pathlib import Path

# Each probe is (label, argv suffix appended to [CG_BIN]). Adjust subcommand names
# to match the actual CodeGraph CLI surface discovered in Task 4 Step 4.
PROBES = [
    ("symbol-lookup-any",     "query --kind any --name vx_simx_init"),  # replace with a real Vortex symbol
    ("include-resolution",    "explore --file repo_sources/vortex/sim/simx/main.cpp --kind includes"),
    ("python-function-defn",  "query --kind function --name run_test"),
    ("cross-file-call",       "explore --symbol vx_simx_init --kind callers"),
    ("fts-text-search",       "search 'TODO(perf)'"),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cg-bin", required=True)
    ap.add_argument("--cg-db", required=True)
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()

    args.out.parent.mkdir(parents=True, exist_ok=True)
    lines = ["# CodeGraph resolution probe transcript\n"]
    env = {**os.environ, "CODEGRAPH_DB": args.cg_db}

    for label, suffix in PROBES:
        cmd = [args.cg_bin, *shlex.split(suffix)]
        lines.append(f"\n## {label}\n\n```\n$ {' '.join(shlex.quote(c) for c in cmd)}\n")
        try:
            r = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=30)
            lines.append(r.stdout or "(no stdout)\n")
            if r.stderr:
                lines.append(f"\n--- stderr ---\n{r.stderr}")
            lines.append(f"\nexit_code={r.returncode}\n```\n")
        except subprocess.TimeoutExpired:
            lines.append("TIMEOUT after 30s\n```\n")
        except FileNotFoundError as e:
            lines.append(f"FileNotFoundError: {e}\n```\n")
    args.out.write_text("".join(lines))
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Pick a real Vortex symbol for the probes**

```bash
grep -rho 'VX_[A-Za-z_]\+' repo_sources/vortex/sim/simx/ | sort -u | head
```

Pick one that appears in ≥ 2 files (use `grep -l` to confirm). Edit `scripts/feasibility/probe_codegraph_resolution.py` to substitute it for `vx_simx_init` in the `PROBES` list, and pick a real `.cpp` path for the include-resolution probe.

- [ ] **Step 3: Run the probe**

```bash
source <(grep '^CG_' runs/feasibility_v2_analyzer/_codegraph_paths.md | sed 's/^/export /')
uv run python scripts/feasibility/probe_codegraph_resolution.py \
    --cg-bin "$CG_BIN" --cg-db "$CG_DB" \
    --out runs/feasibility_v2_analyzer/codegraph_probe_transcript.md
```

Expected: a transcript where at least 3 of the 5 probes return non-empty results with `exit_code=0`. If the CodeGraph CLI subcommand names diverge from `query`/`explore`/`search`, adjust the script; the *capabilities* are what matter, not the verb names.

- [ ] **Step 4: Commit**

```bash
git add scripts/feasibility/probe_codegraph_resolution.py \
        runs/feasibility_v2_analyzer/codegraph_probe_transcript.md
git commit -m "feat(analyzer-v2/phase-0): probe codegraph cross-file resolution"
```

---

### Task 6: Dump CodeGraph's SQLite schema

**Files:**
- Create: `scripts/feasibility/dump_codegraph_schema.py`
- Create (by running): `runs/feasibility_v2_analyzer/codegraph_schema.json` and `runs/feasibility_v2_analyzer/codegraph_schema.md`.

**Interfaces:**
- Consumes: `CG_DB` from Task 4.
- Produces: a machine-readable schema dump (tables, columns, FKs, indexes, row counts) and a human-readable markdown table. Phase 2's bundle exporter (separate plan) reads the markdown directly when authoring SQL queries; not having this delays Phase 2 by ~1 day.

- [ ] **Step 1: Write the schema dumper**

Create `scripts/feasibility/dump_codegraph_schema.py`:

```python
#!/usr/bin/env python3
"""Dump CodeGraph's SQLite schema to JSON + markdown.

For each table, capture: column names/types, PK, FKs, indexes, and row count.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--out-json", required=True, type=Path)
    ap.add_argument("--out-md", required=True, type=Path)
    args = ap.parse_args()

    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(args.db)
    tables = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' "
        "AND name NOT LIKE 'sqlite_%' ORDER BY name"
    )]

    schema = []
    for t in tables:
        cols = list(conn.execute(f"PRAGMA table_info({t})"))
        fks = list(conn.execute(f"PRAGMA foreign_key_list({t})"))
        idx = list(conn.execute(f"PRAGMA index_list({t})"))
        try:
            count = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        except sqlite3.OperationalError:
            count = None  # virtual tables (FTS5) sometimes refuse COUNT
        schema.append({
            "table": t,
            "row_count": count,
            "columns": [{"name": c[1], "type": c[2], "notnull": bool(c[3]),
                         "default": c[4], "pk": bool(c[5])} for c in cols],
            "foreign_keys": [{"from": f[3], "to_table": f[2], "to": f[4]} for f in fks],
            "indexes": [{"name": i[1], "unique": bool(i[2])} for i in idx],
        })

    args.out_json.write_text(json.dumps(schema, indent=2))

    md = ["# CodeGraph SQLite schema\n"]
    for s in schema:
        md.append(f"\n## `{s['table']}`  ({s['row_count']} rows)\n")
        md.append("| col | type | pk | notnull | default |\n|---|---|---|---|---|\n")
        for c in s["columns"]:
            md.append(f"| {c['name']} | {c['type']} | {'Y' if c['pk'] else ''} | "
                      f"{'Y' if c['notnull'] else ''} | {c['default'] or ''} |\n")
        if s["foreign_keys"]:
            md.append("\nForeign keys:\n")
            for f in s["foreign_keys"]:
                md.append(f"- {f['from']} → {f['to_table']}.{f['to']}\n")
    args.out_md.write_text("".join(md))
    print(f"wrote {args.out_json} and {args.out_md}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Run it**

```bash
source <(grep '^CG_' runs/feasibility_v2_analyzer/_codegraph_paths.md | sed 's/^/export /')
uv run python scripts/feasibility/dump_codegraph_schema.py \
    --db "$CG_DB" \
    --out-json runs/feasibility_v2_analyzer/codegraph_schema.json \
    --out-md runs/feasibility_v2_analyzer/codegraph_schema.md
```

Expected: a markdown file listing > 3 tables. If fewer tables are present, suspect Step 5 of Task 4 didn't actually index — re-investigate before continuing.

- [ ] **Step 3: Commit**

```bash
git add scripts/feasibility/dump_codegraph_schema.py \
        runs/feasibility_v2_analyzer/codegraph_schema.json \
        runs/feasibility_v2_analyzer/codegraph_schema.md
git commit -m "feat(analyzer-v2/phase-0): dump codegraph sqlite schema"
```

---

### Task 7: Write the feasibility report and lock Phase 1 / Phase 6 scope

**Files:**
- Create: `runs/feasibility_v2_analyzer.md`
- Modify: `analyzer_v2_codegraph_treesitter_plan.md` § 9 — flip Phase 0 row to `complete`.

**Interfaces:**
- Consumes: every artifact produced in Tasks 1–6.
- Produces: a 2–3 page markdown report that resolves three decisions: (a) Phase 6 in/out (Vortex parse-rate bucket); (b) Phase 1 D4 fork pin (CodeGraph commit sha); (c) any observed node-kind name corrections that Phase 1's `entities.scm` queries must use. Every later phase reads this report.

- [ ] **Step 1: Draft the report from the canonical template**

Create `runs/feasibility_v2_analyzer.md`:

```markdown
# Analyzer v2 Phase 0 — Feasibility report

Date: <fill on commit>
Author: <fill on commit>
Plan reference: `analyzer_v2_codegraph_treesitter_plan.md` § 4 Phase 0.

## 1. Decision summary

- **Phase 6 (Verible secondary parser):** REQUIRED | SKIPPED | ABORT-AND-REPLAN
  - Driver: Vortex parse-rate = `<X>%` (bucket: `<≥95 / 80–95 / <80>`).
- **CodeGraph fork pin:** `colbymchenry/codegraph@<sha>` (recorded in `_codegraph_commit.txt`).
- **Observed RTL root node kind:** `<source_file | other>` — drives `queries/verilog/*.scm` authoring in Phase 1.
- **Observed always-block node kind:** `<always_construct | always_block | other>` — drives Phase 3 `conditional_behavior` emitter.

## 2. tree-sitter-verilog coverage

### Vortex
- Total RTL files measured: `<N>` (path: `repo_sources/vortex`).
- Parse status: clean=`<a>`, partial=`<b>`, error=`<c>`.
- Files containing expected node kinds (from `vortex_rtl_coverage.summary.json`):
  - `module_declaration`: `<n>`
  - `parameter_declaration`: `<n>`
  - `always_construct`: `<n>`
  - `if_statement`: `<n>`
  - `case_statement`: `<n>`
  - `module_instantiation`: `<n>`
- Top three error-rate files (path + error_count): `<…>`. These guide which constructs to harden in Phase 1.

### NVDLA
- Total RTL files measured: `<N>` (path: `<chosen-nvdla-rtl-root>`). If skipped, say why.
- Parse status + node-kind counts: same shape.

## 3. CodeGraph behaviour

- Install path: `<CG_BIN>`; DB path: `<CG_DB>` (also in `_codegraph_paths.md`).
- Indexing the Vortex non-RTL surface: `<seconds>` real time, `<MB>` DB size.
- Table count: `<n>` (full schema in `codegraph_schema.md`).
- Cross-file resolution probes: `<x>` of 5 returned non-empty payloads (see `codegraph_probe_transcript.md`). Notes on probes that failed: `<…>`.

## 4. Risks observed in Phase 0 (feed into Phase 1+ risk register)

- `<construct that errored repeatedly>`: occurs in `<n>` Vortex files. Mitigation: `<harden query / fall back to Verible / accept-and-document>`.
- `<any CLI surface area that diverged from upstream README>`: `<…>`.

## 5. Required adjustments to later phases

- Phase 1 `queries/verilog/entities.scm` must use these node kind names: `<list>`.
- Phase 2 SQL queries against the CodeGraph DB: see `codegraph_schema.md` tables `<X>`, `<Y>` for symbols, `<Z>` for relations.
- Phase 6 scope: `<REQUIRED|SKIPPED|REPLAN>` based on bucket above.

## 6. Sign-off

Phase 0 outputs reviewed by: `<reviewer>` on `<date>`.
Phase 1 GO / NO-GO: `<…>`.
```

Fill every `<…>` placeholder from the artifacts produced in Tasks 1–6. No `<…>` may remain on commit.

- [ ] **Step 2: Update the master plan's phase tracker**

In `analyzer_v2_codegraph_treesitter_plan.md` § 9, replace the Phase 0 row:

```
| 0 — Feasibility | not started | — | — |
```

with:

```
| 0 — Feasibility | complete | <YYYY-MM-DD> | parse_rate=<X>%, pin=<short-sha>, phase-6=<required|skipped> |
```

- [ ] **Step 3: Commit the report**

```bash
git add runs/feasibility_v2_analyzer.md analyzer_v2_codegraph_treesitter_plan.md
git commit -m "docs(analyzer-v2/phase-0): feasibility report; lock phase-1/phase-6 scope"
```

- [ ] **Step 4: Brief the user**

Post the report's § 1 Decision summary into the conversation (or to whomever picks up Phase 1). Phase 1 should not start until the GO/NO-GO line is filled.

---

## Acceptance for "Phase 0 is done"

All of the following must hold:

1. `runs/feasibility_v2_analyzer.md` exists, contains no `<…>` placeholders, and ends with a GO/NO-GO decision.
2. `runs/feasibility_v2_analyzer/vortex_rtl_coverage.summary.json` exists and reports a `parse_rate_pct` value used in the report.
3. `runs/feasibility_v2_analyzer/codegraph_schema.md` exists and lists ≥ 1 table with non-zero row count.
4. `tools/codegraph/` is cloned, dependencies installed, HEAD recorded in `_codegraph_commit.txt`.
5. `analyzer_v2_codegraph_treesitter_plan.md` § 9 Phase 0 row reads `complete | <date> | …`.
6. `existing pytest suite passes` (`uv run pytest -q`) — no Phase 0 task should have touched code under `skills/` or `schemas/`; this check just guards against accidental edits.
