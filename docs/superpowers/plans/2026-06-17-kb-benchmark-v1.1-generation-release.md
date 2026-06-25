# kb_benchmark v1.1 Generation and Release Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Use the v1.1 infrastructure to stamp the v1.0 corpus, generate v1.1 smoke corpora, then produce release-grade NVDLA and Vortex v1.1 benchmark artifacts.

**Architecture:** This plan starts only after `2026-06-17-kb-benchmark-v1.1-infra.md` is complete. Generation remains artifact-based: profiles and analyzer bundles guide agentic benchmark generation, validators admit or reject rows, and release reports summarize structural/adversarial gates plus baselines. Existing v1 artifacts are never overwritten.

**Tech Stack:** Python 3 standard library, `unittest`, existing benchmark-generator skill, existing `scripts/run_codex_baselines.py`, existing `scripts/evaluate_methods.py`, v1.1 validator CLI from the infrastructure plan.

---

## Preconditions

All items from the infrastructure plan must be true before starting:

- `uv run pytest` passes.
- `runs/nvdla_context_bundle/signal_index.jsonl` exists and validates.
- `runs/vortex_context_bundle/signal_index.jsonl` exists and validates.
- `skills/benchmark-validator/scripts/validate_benchmark.py lint --schema-version v1.1` exists.
- `--structural-gate-json` writes reason-coded records.
- `skills/benchmark-validator/scripts/adversarial_gate.py --dry-run` writes row x claim records.

## File Structure

Create:

- `runs/nvdla_generation_profile_v1_1.yaml`: v1.1 NVDLA release profile.
- `runs/vortex_generation_profile_v1_1.yaml`: v1.1 Vortex release profile.
- `tests/test_stamp_v1_1_difficulty.py`: tests for v1.0 migration stamping.
- `scripts/stamp_v1_1_difficulty.py`: sidecar migrator from v1 rows to v1.1 candidate rows.
- `runs/nvdla_benchmark_v1_1_migrated.jsonl`: stamped NVDLA v1 corpus.
- `runs/vortex_benchmark_v1_1_migrated.jsonl`: stamped Vortex v1 corpus.
- `runs/nvdla_benchmark_v1_1_smoke.jsonl`: 20-row NVDLA smoke benchmark.
- `runs/vortex_benchmark_v1_1_smoke.jsonl`: 20-row Vortex smoke benchmark.
- `runs/nvdla_benchmark_v1_1.jsonl`: 200-row NVDLA release benchmark.
- `runs/vortex_benchmark_v1_1.jsonl`: 200-row Vortex release benchmark.

Modify:

- `skills/benchmark-generator/SKILL.md`: add v1.1 generation discipline and smoke/release prompts.
- `README.md`: add v1.1 release artifact commands after artifacts exist.

Do not modify:

- `runs/nvdla_benchmark_v1.jsonl`
- `runs/vortex_benchmark_v1.jsonl`
- v1 lint reports, except when creating separate v1.1 reports.

### Task 1: Add v1.1 Generation Profiles

**Files:**
- Create: `runs/nvdla_generation_profile_v1_1.yaml`
- Create: `runs/vortex_generation_profile_v1_1.yaml`
- Test: profile grep and schema smoke via existing JSON/YAML text checks

- [ ] **Step 1: Create the NVDLA v1.1 profile**

Create `runs/nvdla_generation_profile_v1_1.yaml`:

```yaml
schema_version: generation-profile/v1
benchmark:
  id: nvdla_benchmark_v1_1
  output_name: runs/nvdla_benchmark_v1_1.jsonl
  target_count: 200
  case_id_pattern: "{project}-v1_1-{layer}-{seq:03d}"
input:
  context_bundle: runs/nvdla_context_bundle
  signal_index: runs/nvdla_context_bundle/signal_index.jsonl
projects:
  - id: nvdla
    target_count: 200
layers:
  - code: L1
    zh: 单源检索
    target_count: 50
  - code: L2
    zh: 跨源核对
    target_count: 90
  - code: L3
    zh: 多跳机制
    target_count: 60
attribute_quotas:
  rule: every_case_has_at_least_two_signals_across_axes_combined
  per_attribute_minimum:
    long_tail: 0.30
    distracting_info: 0.20
    version_fork: 0.10
    non_code_anchor: 0.15
    false_premise: 0.08
    doc_code_divergence: 0.15
    conditional_behavior: 0.20
    negative_evidence: 0.10
    implicit_domain_knowledge: 0.15
    quantitative_aggregation: 0.08
answerability_mix:
  answerable: 0.70
  unanswerable_missing_evidence: 0.15
  unanswerable_false_premise: 0.10
  unanswerable_ambiguous: 0.05
adversarial_gate:
  enabled: true
  dry_run_allowed: true
  judge:
    provider: deepseek
    model: deepseek-v4-pro
    api_key_env: DEEPSEEK_API_KEY
    threshold: 0.7
  baselines:
    closed_book_llm:
      model: deepseek-v4-flash
    top_1_dense_only:
      top_k: 1
capability_seeds:
  - code: repo_structure_location
    zh: 项目结构定位
  - code: rtl_symbol_location
    zh: RTL 符号定位
  - code: software_stack_path
    zh: 软件栈路径
  - code: doc_code_cross_check
    zh: 文档代码核对
  - code: build_sim_verif_flow
    zh: 构建仿真验证流程
  - code: mechanism_trace
    zh: 机制链路解释
sampling:
  query_style_mix:
    colloquial: 0.34
    contextual: 0.28
    fact_check: 0.18
    followup: 0.10
    evidence_request: 0.10
answer_policy:
  require_direct_answer_first: true
  citation_format: "`path:line-range`"
  query_rewrite_policy: visible-query-semantics-only
known_limits:
  - CodeGraph was unavailable in the v1 analyzer bundle, so call/callee-heavy signals depend on deterministic sidecar extraction.
  - v1.1 release generation must preserve v1 source snapshots and never overwrite runs/nvdla_benchmark_v1.jsonl.
```

- [ ] **Step 2: Create the Vortex v1.1 profile**

Create `runs/vortex_generation_profile_v1_1.yaml`:

```yaml
schema_version: generation-profile/v1
benchmark:
  id: vortex_benchmark_v1_1
  output_name: runs/vortex_benchmark_v1_1.jsonl
  target_count: 200
  case_id_pattern: "{project}-v1_1-{layer}-{seq:03d}"
input:
  context_bundle: runs/vortex_context_bundle
  signal_index: runs/vortex_context_bundle/signal_index.jsonl
projects:
  - id: vortex
    target_count: 200
layers:
  - code: L1
    zh: 单源检索
    target_count: 50
  - code: L2
    zh: 跨源核对
    target_count: 90
  - code: L3
    zh: 多跳机制
    target_count: 60
attribute_quotas:
  rule: every_case_has_at_least_two_signals_across_axes_combined
  per_attribute_minimum:
    long_tail: 0.30
    distracting_info: 0.20
    version_fork: 0.00
    non_code_anchor: 0.15
    false_premise: 0.08
    doc_code_divergence: 0.15
    conditional_behavior: 0.20
    negative_evidence: 0.10
    implicit_domain_knowledge: 0.15
    quantitative_aggregation: 0.08
answerability_mix:
  answerable: 0.70
  unanswerable_missing_evidence: 0.15
  unanswerable_false_premise: 0.10
  unanswerable_ambiguous: 0.05
adversarial_gate:
  enabled: true
  dry_run_allowed: true
  judge:
    provider: deepseek
    model: deepseek-v4-pro
    api_key_env: DEEPSEEK_API_KEY
    threshold: 0.7
  baselines:
    closed_book_llm:
      model: deepseek-v4-flash
    top_1_dense_only:
      top_k: 1
capability_seeds:
  - code: doc_code_cross_check
    zh: 文档代码交叉核查
  - code: mechanism_trace
    zh: 机制链路追踪
  - code: build_simulation_flow
    zh: 构建与仿真流程
  - code: tests_debug_evidence
    zh: 测试与调试证据
  - code: negative_insufficient_evidence
    zh: 负面与证据不足
  - code: rtl_hierarchy_trace
    zh: RTL层级关系
  - code: runtime_api_trace
    zh: Runtime API链路
  - code: cache_and_perf
    zh: 缓存与性能计数
sampling:
  query_style_mix:
    colloquial: 0.34
    contextual: 0.30
    fact_check: 0.18
    followup: 0.08
    evidence_request: 0.10
answer_policy:
  require_direct_answer_first: true
  citation_format: "`path:line-range`"
  query_rewrite_policy: visible-query-semantics-only
known_limits:
  - Vortex has no configured version-fork source set in this benchmark snapshot; version_fork quota is fixed at 0.00.
  - v1.1 release generation must preserve v1 source snapshots and never overwrite runs/vortex_benchmark_v1.jsonl.
```

- [ ] **Step 3: Verify profile fields**

Run:

```bash
rg -n "attribute_quotas|answerability_mix|adversarial_gate|signal_index|version_fork" runs/nvdla_generation_profile_v1_1.yaml runs/vortex_generation_profile_v1_1.yaml
```

Expected: output includes all five terms for both files, and Vortex shows `version_fork: 0.00`.

- [ ] **Step 4: Commit profiles**

```bash
git add runs/nvdla_generation_profile_v1_1.yaml runs/vortex_generation_profile_v1_1.yaml
git commit -m "Define v1.1 generation profiles for NVDLA and Vortex" \
  -m "The new profiles separate v1.1 release generation from existing v1 artifacts and encode answerability mix, difficulty quotas, and gate configuration." \
  -m "Constraint: v1 benchmark profiles and JSONL outputs must remain unchanged." \
  -m "Rejected: Reuse v1 profile filenames | separate files avoid accidental v1 corpus churn." \
  -m "Confidence: high" \
  -m "Scope-risk: narrow" \
  -m "Tested: rg profile scan for v1.1 fields"
```

### Task 2: Add v1.1 Migration Stamping Script

**Files:**
- Create: `tests/test_stamp_v1_1_difficulty.py`
- Create: `scripts/stamp_v1_1_difficulty.py`
- Test: `tests/test_stamp_v1_1_difficulty.py`

- [ ] **Step 1: Write migration stamping tests**

Create `tests/test_stamp_v1_1_difficulty.py`:

```python
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "stamp_v1_1_difficulty.py"


def load_module():
    spec = importlib.util.spec_from_file_location("stamp_v1_1_difficulty", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class StampV11DifficultyTest(unittest.TestCase):
    def test_stamp_row_adds_answerability_and_claim_sources(self):
        stamper = load_module()
        row = {
            "case_id": "demo-v1-L1-001",
            "project": "demo",
            "layer": {"code": "L1", "zh": "单源检索"},
            "evidence": [{"source_id": "src:a", "path": "repo/a.c"}],
        }
        signals = [
            {
                "signal_id": "sig:demo:long_tail:ent:a",
                "project": "demo",
                "axis": 2,
                "attribute": "long_tail",
                "anchor": {"source_id": "src:a", "path": "repo/a.c"},
                "evidence": {},
                "extractor": "test",
                "confidence": 0.9,
            },
            {
                "signal_id": "sig:demo:conditional_behavior:ent:a",
                "project": "demo",
                "axis": 3,
                "attribute": "conditional_behavior",
                "anchor": {"source_id": "src:a", "path": "repo/a.c"},
                "evidence": {},
                "extractor": "test",
                "confidence": 0.8,
            },
        ]

        stamped = stamper.stamp_row(row, signals)

        self.assertEqual(stamped["answerability"], "answerable")
        self.assertEqual(stamped["difficulty"]["axis1_layer"], "L1")
        self.assertEqual(stamped["difficulty"]["axis2_retrieval"], ["long_tail"])
        self.assertEqual(stamped["difficulty"]["axis3_reasoning"], ["conditional_behavior"])
        self.assertEqual(
            stamped["difficulty"]["claim_sources"]["long_tail"],
            ["sig:demo:long_tail:ent:a"],
        )

    def test_cli_writes_migrated_jsonl(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            bundle = tmpdir / "bundle"
            bundle.mkdir()
            benchmark = tmpdir / "benchmark.jsonl"
            output = tmpdir / "migrated.jsonl"
            benchmark.write_text(
                json.dumps(
                    {
                        "case_id": "demo-v1-L1-001",
                        "project": "demo",
                        "layer": {"code": "L1", "zh": "单源检索"},
                        "query": "q",
                        "query_rewrite": "q",
                        "answer_type": {"code": "fact_check", "zh": "事实核查"},
                        "references": [{"source_id": "src:a", "path": "repo/a.c"}],
                        "evidence": [{"evidence_id": "E1", "source_id": "src:a", "path": "repo/a.c", "role": "evidence_fact", "statement": "fact"}],
                        "expected_answer": "answer",
                        "answer_rubric": {"answer_goal": "goal", "required_atoms": [{"id": "A1", "role": "conclusion", "statement": "fact", "match_type": "semantic_fact", "evidence_ids": ["E1"], "weight": 1.0}]},
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
            (bundle / "signal_index.jsonl").write_text(
                json.dumps(
                    {
                        "signal_id": "sig:demo:long_tail:src:a",
                        "project": "demo",
                        "axis": 2,
                        "attribute": "long_tail",
                        "anchor": {"source_id": "src:a", "path": "repo/a.c"},
                        "evidence": {},
                        "extractor": "test",
                        "confidence": 0.9,
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    str(benchmark),
                    "--context-bundle",
                    str(bundle),
                    "--output",
                    str(output),
                ],
                cwd=ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            migrated = json.loads(output.read_text(encoding="utf-8").strip())
            self.assertEqual(migrated["answerability"], "answerable")
            self.assertEqual(migrated["difficulty"]["axis2_retrieval"], ["long_tail"])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify script is missing**

Run:

```bash
uv run pytest tests/test_stamp_v1_1_difficulty.py -q
```

Expected: FAIL because `scripts/stamp_v1_1_difficulty.py` does not exist.

- [ ] **Step 3: Add the stamping script**

Create `scripts/stamp_v1_1_difficulty.py`:

```python
#!/usr/bin/env python3
"""Stamp v1 benchmark rows with v1.1 answerability and difficulty candidates."""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Stamp v1 rows with v1.1 difficulty metadata.")
    parser.add_argument("benchmark", type=Path)
    parser.add_argument("--context-bundle", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            value = json.loads(line)
            if isinstance(value, dict):
                rows.append(value)
    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def row_source_ids(row: dict[str, Any]) -> set[str]:
    evidence = row.get("evidence", [])
    return {
        str(item.get("source_id"))
        for item in evidence
        if isinstance(item, dict) and item.get("source_id")
    } if isinstance(evidence, list) else set()


def row_paths(row: dict[str, Any]) -> set[str]:
    evidence = row.get("evidence", [])
    return {
        str(item.get("path"))
        for item in evidence
        if isinstance(item, dict) and item.get("path")
    } if isinstance(evidence, list) else set()


def matching_signals(row: dict[str, Any], signals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    source_ids = row_source_ids(row)
    paths = row_paths(row)
    matched: list[dict[str, Any]] = []
    for signal in signals:
        anchor = signal.get("anchor", {})
        if not isinstance(anchor, dict):
            continue
        if anchor.get("source_id") in source_ids or anchor.get("path") in paths:
            matched.append(signal)
    return matched


def stamp_row(row: dict[str, Any], signals: list[dict[str, Any]]) -> dict[str, Any]:
    stamped = copy.deepcopy(row)
    matched = matching_signals(row, signals)
    axis2 = sorted({str(signal["attribute"]) for signal in matched if signal.get("axis") == 2})
    axis3 = sorted({str(signal["attribute"]) for signal in matched if signal.get("axis") == 3})
    claim_sources: dict[str, list[str]] = {}
    for signal in matched:
        attribute = str(signal.get("attribute"))
        claim_sources.setdefault(attribute, []).append(str(signal.get("signal_id")))
    stamped["answerability"] = stamped.get("answerability", "answerable")
    stamped["difficulty"] = {
        "axis1_layer": stamped.get("layer", {}).get("code") if isinstance(stamped.get("layer"), dict) else "L1",
        "axis2_retrieval": axis2,
        "axis3_reasoning": axis3,
        "claim_sources": {key: sorted(values) for key, values in sorted(claim_sources.items())},
    }
    return stamped


def main() -> int:
    args = parse_args()
    rows = load_jsonl(args.benchmark)
    signals = load_jsonl(args.context_bundle / "signal_index.jsonl")
    stamped = [stamp_row(row, signals) for row in rows]
    write_jsonl(args.output, stamped)
    print(f"Wrote {len(stamped)} stamped rows to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run stamping tests**

Run:

```bash
uv run pytest tests/test_stamp_v1_1_difficulty.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit stamping script**

```bash
git add tests/test_stamp_v1_1_difficulty.py scripts/stamp_v1_1_difficulty.py
git commit -m "Add sidecar stamping for v1 to v1.1 migration" \
  -m "The migration script stamps answerability and signal-backed difficulty metadata without mutating existing v1 benchmark files." \
  -m "Constraint: v1 source JSONL files must remain immutable during migration." \
  -m "Confidence: medium" \
  -m "Scope-risk: narrow" \
  -m "Tested: uv run pytest tests/test_stamp_v1_1_difficulty.py -q"
```

### Task 3: Migrate and Audit Existing v1 Rows

**Files:**
- Create: `runs/nvdla_benchmark_v1_1_migrated.jsonl`
- Create: `runs/vortex_benchmark_v1_1_migrated.jsonl`
- Create: `runs/nvdla_benchmark_v1_1_migrated.structural_gate.json`
- Create: `runs/vortex_benchmark_v1_1_migrated.structural_gate.json`
- Test: v1.1 validator CLI

- [ ] **Step 1: Stamp existing v1 corpora**

Run:

```bash
uv run python scripts/stamp_v1_1_difficulty.py runs/nvdla_benchmark_v1.jsonl --context-bundle runs/nvdla_context_bundle --output runs/nvdla_benchmark_v1_1_migrated.jsonl
uv run python scripts/stamp_v1_1_difficulty.py runs/vortex_benchmark_v1.jsonl --context-bundle runs/vortex_context_bundle --output runs/vortex_benchmark_v1_1_migrated.jsonl
```

Expected:

```text
Wrote 50 stamped rows to runs/nvdla_benchmark_v1_1_migrated.jsonl
Wrote 50 stamped rows to runs/vortex_benchmark_v1_1_migrated.jsonl
```

- [ ] **Step 2: Run structural audit**

Run:

```bash
uv run python skills/benchmark-validator/scripts/validate_benchmark.py lint runs/nvdla_benchmark_v1_1_migrated.jsonl --context-bundle runs/nvdla_context_bundle --repo-root . --schema-version v1.1 --structural-gate-json runs/nvdla_benchmark_v1_1_migrated.structural_gate.json
uv run python skills/benchmark-validator/scripts/validate_benchmark.py lint runs/vortex_benchmark_v1_1_migrated.jsonl --context-bundle runs/vortex_context_bundle --repo-root . --schema-version v1.1 --structural-gate-json runs/vortex_benchmark_v1_1_migrated.structural_gate.json
```

Expected: commands may exit non-zero because migrated v1 rows are expected to expose structural weaknesses. The structural gate JSON files must still be written.

- [ ] **Step 3: Write migration notes into generation reports**

Append this section to `runs/nvdla_generation_report.md` and `runs/vortex_generation_report.md`:

```markdown
## v1.1 Migration Audit

The v1 benchmark rows were stamped into a sidecar v1.1 candidate file and
audited with `--schema-version v1.1`. The original v1 JSONL file was not
modified. Rows that fail the structural gate are inputs for rewrite, relabel,
or archive decisions during v1.1 corpus construction.
```

- [ ] **Step 4: Commit migration audit artifacts**

```bash
git add runs/nvdla_benchmark_v1_1_migrated.jsonl runs/vortex_benchmark_v1_1_migrated.jsonl runs/nvdla_benchmark_v1_1_migrated.structural_gate.json runs/vortex_benchmark_v1_1_migrated.structural_gate.json runs/nvdla_generation_report.md runs/vortex_generation_report.md
git commit -m "Audit v1 corpus against v1.1 structural rules" \
  -m "The migrated sidecars show which existing rows can survive v1.1 and which need relabeling, rewriting, or archival." \
  -m "Constraint: Existing v1 benchmark JSONL files stay unchanged." \
  -m "Confidence: medium" \
  -m "Scope-risk: narrow" \
  -m "Tested: stamp_v1_1_difficulty.py ran for NVDLA and Vortex" \
  -m "Tested: validate_benchmark.py lint --schema-version v1.1 wrote structural gate reports"
```

### Task 4: Update Generator Skill for v1.1 Smoke Generation

**Files:**
- Modify: `skills/benchmark-generator/SKILL.md`
- Test: documentation grep

- [ ] **Step 1: Add v1.1 generator instructions**

In `skills/benchmark-generator/SKILL.md`, add this section after the current required output list:

```markdown
## v1.1 generation mode

When the request names v1.1 or the profile contains `attribute_quotas`, use
attribute-first generation:

1. Read `signal_index.jsonl` from the configured context bundle.
2. Choose target difficulty attributes from quota deficits.
3. Select anchors whose signals satisfy the selected attributes.
4. Write `answerability` and `difficulty` into every row.
5. Run validator lint with `--schema-version v1.1`.
6. Write structural gate, adversarial dry-run, rejected rows, and generation report artifacts.

Do not overwrite v1 benchmark files. Use `_v1_1` or `_v1_1_smoke` output names.
```

- [ ] **Step 2: Verify skill text**

Run:

```bash
rg -n "v1.1 generation mode|attribute-first|signal_index|schema-version v1.1|_v1_1_smoke" skills/benchmark-generator/SKILL.md
```

Expected: every term appears in `skills/benchmark-generator/SKILL.md`.

- [ ] **Step 3: Commit generator skill update**

```bash
git add skills/benchmark-generator/SKILL.md
git commit -m "Teach benchmark generator skill the v1.1 attribute-first flow" \
  -m "The generator instructions now route v1.1 requests through signal-index sampling and explicit structural gate validation." \
  -m "Constraint: v1 generation behavior remains available for existing profiles." \
  -m "Confidence: high" \
  -m "Scope-risk: narrow" \
  -m "Tested: rg skill text for v1.1 generation terms"
```

### Task 5: Generate and Validate 20-Case Smoke Corpora

**Files:**
- Create: `runs/nvdla_benchmark_v1_1_smoke.jsonl`
- Create: `runs/vortex_benchmark_v1_1_smoke.jsonl`
- Create: smoke metadata/report/gate files under `runs/`
- Test: v1.1 validator and adversarial dry-run

- [ ] **Step 1: Generate NVDLA smoke corpus with benchmark-generator**

Send this exact skill request:

```text
$benchmark-generator
Use runs/nvdla_context_bundle as the analyzer bundle.
Use runs/nvdla_generation_profile_v1_1.yaml as the profile.
Generate a 20-case v1.1 smoke benchmark at runs/nvdla_benchmark_v1_1_smoke.jsonl.
Use runs/nvdla_context_bundle/signal_index.jsonl for attribute-first sampling.
Every row must include answerability and difficulty with claim_sources.
Target mix: 14 answerable, 3 unanswerable_missing_evidence, 2 unanswerable_false_premise, 1 unanswerable_ambiguous.
Run the validator with --schema-version v1.1 and write runs/nvdla_benchmark_v1_1_smoke.structural_gate.json.
Run adversarial_gate.py --dry-run and write runs/nvdla_benchmark_v1_1_smoke.adversarial_gate.jsonl.
Write metadata to runs/nvdla_benchmark_v1_1_smoke.metadata.json and report to runs/nvdla_generation_report_v1_1_smoke.md.
Do not overwrite runs/nvdla_benchmark_v1.jsonl.
```

- [ ] **Step 2: Generate Vortex smoke corpus with benchmark-generator**

Send this exact skill request:

```text
$benchmark-generator
Use runs/vortex_context_bundle as the analyzer bundle.
Use runs/vortex_generation_profile_v1_1.yaml as the profile.
Generate a 20-case v1.1 smoke benchmark at runs/vortex_benchmark_v1_1_smoke.jsonl.
Use runs/vortex_context_bundle/signal_index.jsonl for attribute-first sampling.
Every row must include answerability and difficulty with claim_sources.
Target mix: 14 answerable, 3 unanswerable_missing_evidence, 2 unanswerable_false_premise, 1 unanswerable_ambiguous.
Run the validator with --schema-version v1.1 and write runs/vortex_benchmark_v1_1_smoke.structural_gate.json.
Run adversarial_gate.py --dry-run and write runs/vortex_benchmark_v1_1_smoke.adversarial_gate.jsonl.
Write metadata to runs/vortex_benchmark_v1_1_smoke.metadata.json and report to runs/vortex_generation_report_v1_1_smoke.md.
Do not overwrite runs/vortex_benchmark_v1.jsonl.
```

- [ ] **Step 3: Validate smoke corpora**

Run:

```bash
uv run python skills/benchmark-validator/scripts/validate_benchmark.py lint runs/nvdla_benchmark_v1_1_smoke.jsonl --context-bundle runs/nvdla_context_bundle --repo-root . --schema-version v1.1 --structural-gate-json runs/nvdla_benchmark_v1_1_smoke.structural_gate.json
uv run python skills/benchmark-validator/scripts/validate_benchmark.py lint runs/vortex_benchmark_v1_1_smoke.jsonl --context-bundle runs/vortex_context_bundle --repo-root . --schema-version v1.1 --structural-gate-json runs/vortex_benchmark_v1_1_smoke.structural_gate.json
uv run python skills/benchmark-validator/scripts/adversarial_gate.py runs/nvdla_benchmark_v1_1_smoke.jsonl --dry-run --output-jsonl runs/nvdla_benchmark_v1_1_smoke.adversarial_gate.jsonl
uv run python skills/benchmark-validator/scripts/adversarial_gate.py runs/vortex_benchmark_v1_1_smoke.jsonl --dry-run --output-jsonl runs/vortex_benchmark_v1_1_smoke.adversarial_gate.jsonl
```

Expected: validator exits 0 for both smoke corpora and adversarial dry-run writes non-empty JSONL files.

- [ ] **Step 4: Commit smoke corpora**

```bash
git add runs/nvdla_benchmark_v1_1_smoke.jsonl runs/vortex_benchmark_v1_1_smoke.jsonl runs/nvdla_benchmark_v1_1_smoke.* runs/vortex_benchmark_v1_1_smoke.* runs/nvdla_generation_report_v1_1_smoke.md runs/vortex_generation_report_v1_1_smoke.md
git commit -m "Generate v1.1 smoke benchmarks from signal-index sampling" \
  -m "The smoke corpora prove the v1.1 profile, signal-index, structural gate, and adversarial dry-run path works before scaling to 200 cases per project." \
  -m "Constraint: Smoke generation must not mutate existing v1 benchmark outputs." \
  -m "Confidence: medium" \
  -m "Scope-risk: moderate" \
  -m "Tested: validate_benchmark.py lint --schema-version v1.1 for NVDLA and Vortex smoke corpora" \
  -m "Tested: adversarial_gate.py --dry-run for NVDLA and Vortex smoke corpora"
```

### Task 6: Generate Full v1.1 Release Corpora

**Files:**
- Create: `runs/nvdla_benchmark_v1_1.jsonl`
- Create: `runs/vortex_benchmark_v1_1.jsonl`
- Create: release metadata, reports, structural gate, adversarial gate, and rejected JSONL files under `runs/`
- Test: v1.1 validator and adversarial dry-run

- [ ] **Step 1: Generate NVDLA release corpus**

Send this exact skill request:

```text
$benchmark-generator
Use runs/nvdla_context_bundle as the analyzer bundle.
Use runs/nvdla_generation_profile_v1_1.yaml as the profile.
Generate a 200-case v1.1 release benchmark at runs/nvdla_benchmark_v1_1.jsonl.
Use runs/nvdla_context_bundle/signal_index.jsonl for attribute-first sampling.
Over-draft candidates when needed, then keep only rows passing --schema-version v1.1 structural gate.
Every row must include answerability and difficulty with claim_sources.
Target answerability counts: 140 answerable, 30 unanswerable_missing_evidence, 20 unanswerable_false_premise, 10 unanswerable_ambiguous.
Write rejected rows to runs/nvdla_benchmark_v1_1.rejected.jsonl.
Write structural gate to runs/nvdla_benchmark_v1_1.structural_gate.json.
Run adversarial_gate.py --dry-run and write runs/nvdla_benchmark_v1_1.adversarial_gate.jsonl.
Write metadata to runs/nvdla_benchmark_v1_1.metadata.json and report to runs/nvdla_generation_report_v1_1.md.
Do not overwrite any v1 file.
```

- [ ] **Step 2: Generate Vortex release corpus**

Send this exact skill request:

```text
$benchmark-generator
Use runs/vortex_context_bundle as the analyzer bundle.
Use runs/vortex_generation_profile_v1_1.yaml as the profile.
Generate a 200-case v1.1 release benchmark at runs/vortex_benchmark_v1_1.jsonl.
Use runs/vortex_context_bundle/signal_index.jsonl for attribute-first sampling.
Over-draft candidates when needed, then keep only rows passing --schema-version v1.1 structural gate.
Every row must include answerability and difficulty with claim_sources.
Target answerability counts: 140 answerable, 30 unanswerable_missing_evidence, 20 unanswerable_false_premise, 10 unanswerable_ambiguous.
Do not generate version_fork rows for Vortex.
Write rejected rows to runs/vortex_benchmark_v1_1.rejected.jsonl.
Write structural gate to runs/vortex_benchmark_v1_1.structural_gate.json.
Run adversarial_gate.py --dry-run and write runs/vortex_benchmark_v1_1.adversarial_gate.jsonl.
Write metadata to runs/vortex_benchmark_v1_1.metadata.json and report to runs/vortex_generation_report_v1_1.md.
Do not overwrite any v1 file.
```

- [ ] **Step 3: Validate release corpora**

Run:

```bash
uv run python skills/benchmark-validator/scripts/validate_benchmark.py lint runs/nvdla_benchmark_v1_1.jsonl --context-bundle runs/nvdla_context_bundle --repo-root . --schema-version v1.1 --json-report runs/nvdla_benchmark_v1_1.lint.json --markdown-report runs/nvdla_benchmark_v1_1.lint.md --structural-gate-json runs/nvdla_benchmark_v1_1.structural_gate.json
uv run python skills/benchmark-validator/scripts/validate_benchmark.py lint runs/vortex_benchmark_v1_1.jsonl --context-bundle runs/vortex_context_bundle --repo-root . --schema-version v1.1 --json-report runs/vortex_benchmark_v1_1.lint.json --markdown-report runs/vortex_benchmark_v1_1.lint.md --structural-gate-json runs/vortex_benchmark_v1_1.structural_gate.json
```

Expected: both commands exit 0.

- [ ] **Step 4: Commit release corpora**

```bash
git add runs/nvdla_benchmark_v1_1* runs/vortex_benchmark_v1_1* runs/nvdla_generation_report_v1_1.md runs/vortex_generation_report_v1_1.md
git commit -m "Generate release-grade v1.1 benchmarks" \
  -m "NVDLA and Vortex now have separate v1.1 release corpora with answerability, difficulty claims, structural gate reports, and adversarial dry-run records." \
  -m "Constraint: v1 release artifacts remain unchanged and available for comparison." \
  -m "Confidence: medium" \
  -m "Scope-risk: broad" \
  -m "Tested: validate_benchmark.py lint --schema-version v1.1 for NVDLA and Vortex release corpora" \
  -m "Not-tested: Provider-backed adversarial gate unless DEEPSEEK_API_KEY is configured"
```

### Task 7: Run Baselines and Release Evaluation

**Files:**
- Create: `predictions/nvdla_baseline_oracle_codex_predictions_v1_1.jsonl`
- Create: `predictions/nvdla_baseline_grep_agent_predictions_v1_1.jsonl`
- Create: `predictions/vortex_baseline_oracle_codex_predictions_v1_1.jsonl`
- Create: `predictions/vortex_baseline_grep_agent_predictions_v1_1.jsonl`
- Create: evaluation JSON/MD reports under `predictions/`
- Test: evaluator CLI

- [ ] **Step 1: Run oracle baselines**

Run:

```bash
uv run python scripts/run_codex_baselines.py oracle runs/nvdla_benchmark_v1_1.jsonl --repo-root . --output predictions/nvdla_baseline_oracle_codex_predictions_v1_1.jsonl --resume
uv run python scripts/run_codex_baselines.py oracle runs/vortex_benchmark_v1_1.jsonl --repo-root . --output predictions/vortex_baseline_oracle_codex_predictions_v1_1.jsonl --resume
```

Expected: each command writes or resumes predictions and prints progress lines beginning with `Wrote ` until complete.

- [ ] **Step 2: Run grep-agent baselines**

Run:

```bash
uv run python scripts/run_codex_baselines.py grep-agent runs/nvdla_benchmark_v1_1.jsonl --repo-root . --repo-path repo_sources/nvdla/hw --repo-path repo_sources/nvdla/sw --repo-path repo_sources/nvdla/doc --output predictions/nvdla_baseline_grep_agent_predictions_v1_1.jsonl --resume --allow-nl
uv run python scripts/run_codex_baselines.py grep-agent runs/vortex_benchmark_v1_1.jsonl --repo-root . --repo-path repo_sources/vortex/vortex --output predictions/vortex_baseline_grep_agent_predictions_v1_1.jsonl --resume --allow-nl
```

Expected: each command writes or resumes predictions and records token usage from Codex JSON events.

- [ ] **Step 3: Evaluate deterministic reports**

Run:

```bash
uv run python scripts/evaluate_methods.py runs/nvdla_benchmark_v1_1.jsonl predictions/nvdla_baseline_oracle_codex_predictions_v1_1.jsonl --top-k 10 --output-json predictions/nvdla_baseline_oracle_eval_v1_1.json --output-md predictions/nvdla_baseline_oracle_eval_v1_1.md
uv run python scripts/evaluate_methods.py runs/nvdla_benchmark_v1_1.jsonl predictions/nvdla_baseline_grep_agent_predictions_v1_1.jsonl --top-k 10 --output-json predictions/nvdla_baseline_grep_agent_eval_v1_1.json --output-md predictions/nvdla_baseline_grep_agent_eval_v1_1.md
uv run python scripts/evaluate_methods.py runs/vortex_benchmark_v1_1.jsonl predictions/vortex_baseline_oracle_codex_predictions_v1_1.jsonl --top-k 10 --output-json predictions/vortex_baseline_oracle_eval_v1_1.json --output-md predictions/vortex_baseline_oracle_eval_v1_1.md
uv run python scripts/evaluate_methods.py runs/vortex_benchmark_v1_1.jsonl predictions/vortex_baseline_grep_agent_predictions_v1_1.jsonl --top-k 10 --output-json predictions/vortex_baseline_grep_agent_eval_v1_1.json --output-md predictions/vortex_baseline_grep_agent_eval_v1_1.md
```

Expected: each command exits 0 and prints `Cases: 200`, evidence recall, citation pass, judge coverage, and token usage lines.

- [ ] **Step 4: Run provider-backed judge reports when the key exists**

Run:

```bash
uv run python scripts/evaluate_methods.py runs/nvdla_benchmark_v1_1.jsonl predictions/nvdla_baseline_grep_agent_predictions_v1_1.jsonl --top-k 10 --llm-judge-provider deepseek --llm-judge-model deepseek-v4-pro --llm-judge-api-key-env DEEPSEEK_API_KEY --require-llm-judge --output-json predictions/nvdla_baseline_grep_agent_eval_v1_1.deepseek.json --output-md predictions/nvdla_baseline_grep_agent_eval_v1_1.deepseek.md
uv run python scripts/evaluate_methods.py runs/vortex_benchmark_v1_1.jsonl predictions/vortex_baseline_grep_agent_predictions_v1_1.jsonl --top-k 10 --llm-judge-provider deepseek --llm-judge-model deepseek-v4-pro --llm-judge-api-key-env DEEPSEEK_API_KEY --require-llm-judge --output-json predictions/vortex_baseline_grep_agent_eval_v1_1.deepseek.json --output-md predictions/vortex_baseline_grep_agent_eval_v1_1.deepseek.md
```

Expected with `DEEPSEEK_API_KEY` configured: both commands exit 0 and report LLM judge coverage `1.000`.

Expected without `DEEPSEEK_API_KEY`: commands exit non-zero. Record this as `Not-tested` in the release commit instead of committing partial DeepSeek reports.

- [ ] **Step 5: Commit baseline reports**

```bash
git add predictions/*v1_1*.json predictions/*v1_1*.jsonl predictions/*v1_1*.md
git commit -m "Evaluate v1.1 benchmarks with oracle and grep baselines" \
  -m "The release includes deterministic retrieval, citation, and token-cost reports for NVDLA and Vortex v1.1 baselines." \
  -m "Constraint: Provider-backed judge reports are included only when complete and key-backed." \
  -m "Confidence: medium" \
  -m "Scope-risk: moderate" \
  -m "Tested: evaluate_methods.py deterministic reports for oracle and grep-agent baselines" \
  -m "Not-tested: DeepSeek judge reports when DEEPSEEK_API_KEY is unavailable"
```

### Task 8: Publish README Release Commands

**Files:**
- Modify: `README.md`
- Test: documentation grep

- [ ] **Step 1: Add v1.1 release usage to README**

Add this section to `README.md` after the current method-evaluation example:

```markdown
## v1.1 Release Artifacts

The v1.1 benchmarks are separate from v1:

```text
runs/nvdla_benchmark_v1_1.jsonl
runs/vortex_benchmark_v1_1.jsonl
```

Validate them with explicit v1.1 rules:

```bash
python3 skills/benchmark-validator/scripts/validate_benchmark.py lint \
  runs/nvdla_benchmark_v1_1.jsonl \
  --context-bundle runs/nvdla_context_bundle \
  --repo-root . \
  --schema-version v1.1 \
  --structural-gate-json runs/nvdla_benchmark_v1_1.structural_gate.json
```

Run deterministic baseline evaluation:

```bash
python3 scripts/evaluate_methods.py \
  runs/nvdla_benchmark_v1_1.jsonl \
  predictions/nvdla_baseline_grep_agent_predictions_v1_1.jsonl \
  --top-k 10 \
  --output-json predictions/nvdla_baseline_grep_agent_eval_v1_1.json \
  --output-md predictions/nvdla_baseline_grep_agent_eval_v1_1.md
```
```

- [ ] **Step 2: Verify README v1.1 terms**

Run:

```bash
rg -n "v1.1 Release Artifacts|nvdla_benchmark_v1_1|vortex_benchmark_v1_1|schema-version v1.1|baseline_grep_agent_eval_v1_1" README.md
```

Expected: all terms are present.

- [ ] **Step 3: Commit README update**

```bash
git add README.md
git commit -m "Publish v1.1 release artifact usage" \
  -m "The README now shows where v1.1 benchmarks live and how to validate and evaluate them without confusing them with v1 artifacts." \
  -m "Constraint: v1 usage examples stay available for compatibility." \
  -m "Confidence: high" \
  -m "Scope-risk: narrow" \
  -m "Tested: rg README scan for v1.1 release commands"
```

## Release Completion Checklist

- [ ] v1.1 infrastructure completion checklist is satisfied.
- [ ] `runs/nvdla_generation_profile_v1_1.yaml` exists.
- [ ] `runs/vortex_generation_profile_v1_1.yaml` exists.
- [ ] v1 migrated sidecars exist and original v1 JSONL files are unchanged.
- [ ] smoke corpora pass `--schema-version v1.1`.
- [ ] release corpora each contain 200 rows.
- [ ] release corpora pass `--schema-version v1.1`.
- [ ] adversarial gate dry-run JSONL exists for both release corpora.
- [ ] oracle and grep-agent prediction JSONL exists for both release corpora.
- [ ] deterministic evaluation JSON/MD exists for oracle and grep-agent baselines.
- [ ] DeepSeek reports are either complete or explicitly omitted with `Not-tested` trailer.
- [ ] README includes v1.1 validation and evaluation commands.
