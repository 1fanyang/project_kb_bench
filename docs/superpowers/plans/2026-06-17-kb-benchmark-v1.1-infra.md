# kb_benchmark v1.1 Infrastructure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add v1.1-compatible schemas, signal-index support, structural gating, and adversarial-gate dry-run infrastructure without breaking the existing v1.0 NVDLA/Vortex benchmarks.

**Architecture:** Keep the current artifact pipeline intact: analyzer bundle -> generator artifact -> validator/evaluator. v1.1 is additive: legacy rows stay valid by default, while `--schema-version v1.1` enables stricter answerability and structural-gate checks. `signal_index.jsonl` becomes the analyzer-to-generator difficulty contract and is optional for v1 bundles but validated when present.

**Tech Stack:** Python 3 standard library, `unittest`, JSON/JSONL scripts, existing `uv run pytest` test runner, existing JSON schemas under `schemas/`.

---

## Fixed API Decisions

- Validator strict mode flag: `--schema-version v1.1`.
- Validator default mode: `--schema-version v1`.
- Structural gate report flag: `--structural-gate-json /tmp/structural_gate.json`.
- Signal builder script: `skills/benchmark-repo-analyzer/scripts/build_signal_index.py`.
- Adversarial gate script: `skills/benchmark-validator/scripts/adversarial_gate.py`.
- Dry-run adversarial output status: `skipped_no_provider`.

## File Structure

Create:

- `schemas/signal-index.schema.json`: schema for analyzer-produced difficulty signals.
- `tests/test_validate_benchmark_v1_1.py`: validator v1/v1.1 compatibility, answerability, and structural-gate tests.
- `tests/test_signal_index.py`: signal-index validator and builder tests.
- `tests/test_adversarial_gate.py`: adversarial gate dry-run and secret-safety tests.
- `skills/benchmark-repo-analyzer/scripts/build_signal_index.py`: deterministic first-pass signal-index emitter.
- `skills/benchmark-validator/scripts/adversarial_gate.py`: dry-run/resumable adversarial gate shell.

Modify:

- `schemas/benchmark-row.schema.json`: additive `answerability` and `difficulty` fields.
- `schemas/generation-profile.schema.json`: additive v1.1 quota and gate config blocks.
- `skills/benchmark-validator/scripts/validate_benchmark.py`: `--schema-version`, answerability-aware evidence rules, structural-gate reason records.
- `skills/benchmark-generator/scripts/lint_benchmark_jsonl.py`: mirror the validator's v1.1 row checks for generator lint.
- `skills/benchmark-repo-analyzer/scripts/validate_context_bundle.py`: optional `signal_index.jsonl` validation and summary counts.
- `README.md`: v1.1 CLI examples and compatibility note.
- `skills/benchmark-repo-analyzer/references/analyzer-contract.md`: document `signal_index.jsonl`.
- `skills/benchmark-generator/references/generator-contract.md`: document attribute-first inputs.
- `skills/benchmark-validator/references/validator-contract.md`: document v1.1 structural gate and adversarial gate.

Do not modify:

- `runs/nvdla_benchmark_v1.jsonl`
- `runs/vortex_benchmark_v1.jsonl`
- current `predictions/` artifacts

### Task 1: Lock v1.0 Compatibility and Add v1.1 Fixture Tests

**Files:**
- Create: `tests/test_validate_benchmark_v1_1.py`
- Modify: none
- Test: `tests/test_validate_benchmark_v1_1.py`

- [ ] **Step 1: Write compatibility and answerability tests**

Create `tests/test_validate_benchmark_v1_1.py` with this content:

```python
import copy
import importlib.util
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills" / "benchmark-validator" / "scripts" / "validate_benchmark.py"


def load_module():
    spec = importlib.util.spec_from_file_location("validate_benchmark", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def answerable_row():
    return {
        "_file": "inline.jsonl",
        "_line": 1,
        "case_id": "case-answerable",
        "project": "demo",
        "layer": {"code": "L1", "zh": "单源检索"},
        "capability": {"code": "mechanism_trace", "zh": "机制链路解释"},
        "query": "这个 guard 会阻止 launch 吗？请给证据。",
        "query_rewrite": "判断 guard 是否阻止 launch",
        "answer_type": {"code": "yes_no", "zh": "是否判断"},
        "references": [{"source_id": "src:a", "path": "repo/a.c"}],
        "evidence": [
            {
                "evidence_id": "E1",
                "source_id": "src:a",
                "path": "repo/a.c",
                "lines": "10-12",
                "role": "guard",
                "statement": "The guard returns before launch when count is zero.",
            }
        ],
        "expected_answer": "会，guard 在 count 为 0 时提前返回，因此不会 launch。repo/a.c:10-12",
        "answer_rubric": {
            "answer_goal": "Answer whether the guard blocks launch.",
            "required_atoms": [
                {
                    "id": "A1",
                    "role": "conclusion",
                    "statement": "The guard blocks launch when count is zero.",
                    "match_type": "semantic_yes_no",
                    "evidence_ids": ["E1"],
                    "weight": 1.0,
                }
            ],
            "forbidden_atoms": [
                {
                    "id": "F1",
                    "statement": "The answer claims launch still happens.",
                    "match_type": "semantic_contradiction",
                    "severity": "fatal",
                }
            ],
            "citation_policy": {
                "required": "always",
                "required_evidence_ids": ["E1"],
                "acceptable_granularity": "path_line",
            },
        },
    }


def lint_fail_messages(validator, row, schema_version="v1", sources=None):
    findings = []
    rows = [copy.deepcopy(row)]
    validator.validate_benchmark_rows(
        rows,
        findings,
        ROOT,
        sources or {},
        schema_version=schema_version,
    )
    return [finding.message for finding in findings if finding.severity == "FAIL"]


class ValidateBenchmarkV11Test(unittest.TestCase):
    def test_current_nvdla_and_vortex_v1_benchmarks_still_lint(self):
        cases = [
            (
                ROOT / "runs" / "nvdla_benchmark_v1.jsonl",
                ROOT / "runs" / "nvdla_context_bundle",
            ),
            (
                ROOT / "runs" / "vortex_benchmark_v1.jsonl",
                ROOT / "runs" / "vortex_context_bundle",
            ),
        ]
        for benchmark, bundle in cases:
            if not benchmark.exists() or not bundle.exists():
                self.skipTest(f"missing local artifact: {benchmark} or {bundle}")
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "lint",
                    str(benchmark),
                    "--context-bundle",
                    str(bundle),
                    "--repo-root",
                    str(ROOT),
                ],
                cwd=ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_missing_answerability_is_legacy_answerable(self):
        validator = load_module()
        row = answerable_row()
        self.assertNotIn("answerability", row)

        messages = lint_fail_messages(validator, row, schema_version="v1")

        self.assertNotIn("`answerability` is required in v1.1 mode", messages)
        self.assertEqual(messages, [])

    def test_v1_1_allows_missing_evidence_for_missing_evidence_refusal(self):
        validator = load_module()
        row = answerable_row()
        row["case_id"] = "case-missing"
        row["answerability"] = "unanswerable_missing_evidence"
        row["references"] = []
        row["evidence"] = []
        row["expected_answer"] = "无法从当前快照确认这个行为；列出的源码中没有支持该说法的证据。"
        row["answer_rubric"]["required_atoms"][0] = {
            "id": "A1",
            "role": "conclusion",
            "statement": "The answer refuses because evidence is missing.",
            "match_type": "semantic_fact",
            "evidence_ids": [],
            "weight": 1.0,
        }
        row["answer_rubric"]["forbidden_atoms"] = [
            {
                "id": "F1",
                "statement": "The answer fabricates a concrete implementation detail.",
                "match_type": "semantic_contradiction",
                "severity": "fatal",
            }
        ]
        row["answer_rubric"]["citation_policy"] = {"required": "never"}

        messages = lint_fail_messages(validator, row, schema_version="v1.1")

        self.assertEqual(messages, [])

    def test_v1_1_rejects_answerable_row_with_empty_evidence(self):
        validator = load_module()
        row = answerable_row()
        row["answerability"] = "answerable"
        row["evidence"] = []

        messages = lint_fail_messages(validator, row, schema_version="v1.1")

        self.assertIn("`evidence` must be a non-empty list for answerable rows", messages)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the new tests to verify they fail for missing v1.1 API**

Run:

```bash
uv run pytest tests/test_validate_benchmark_v1_1.py -q
```

Expected: FAIL with a `TypeError` mentioning `schema_version`, because `validate_benchmark_rows()` does not accept that argument yet.

- [ ] **Step 3: Commit the failing test**

```bash
git add tests/test_validate_benchmark_v1_1.py
git commit -m "Define v1.1 validator compatibility expectations" \
  -m "The tests lock legacy v1 lint behavior before adding stricter v1.1 answerability rules." \
  -m "Constraint: Existing NVDLA and Vortex v1 benchmark JSONL files must remain valid by default." \
  -m "Confidence: high" \
  -m "Scope-risk: narrow" \
  -m "Tested: uv run pytest tests/test_validate_benchmark_v1_1.py -q fails with missing schema_version API" \
  -m "Not-tested: v1.1 implementation is not present yet"
```

### Task 2: Add v1.1 Schema Fields and Validator Mode

**Files:**
- Modify: `schemas/benchmark-row.schema.json`
- Modify: `schemas/generation-profile.schema.json`
- Modify: `skills/benchmark-validator/scripts/validate_benchmark.py`
- Test: `tests/test_validate_benchmark_v1_1.py`

- [ ] **Step 1: Extend `schemas/benchmark-row.schema.json`**

In `schemas/benchmark-row.schema.json`, add these properties inside the top-level `properties` object:

```json
"answerability": {
  "type": "string",
  "enum": [
    "answerable",
    "unanswerable_missing_evidence",
    "unanswerable_false_premise",
    "unanswerable_ambiguous"
  ]
},
"difficulty": {
  "type": "object",
  "properties": {
    "axis1_layer": {"type": "string", "enum": ["L1", "L2", "L3"]},
    "axis2_retrieval": {
      "type": "array",
      "items": {"type": "string"}
    },
    "axis3_reasoning": {
      "type": "array",
      "items": {"type": "string"}
    },
    "claim_sources": {
      "type": "object",
      "additionalProperties": {
        "type": "array",
        "items": {"type": "string"}
      }
    }
  },
  "additionalProperties": true
}
```

Then append this `allOf` block before top-level `"additionalProperties": true`:

```json
"allOf": [
  {
    "if": {
      "anyOf": [
        {"not": {"required": ["answerability"]}},
        {"properties": {"answerability": {"const": "answerable"}}}
      ]
    },
    "then": {
      "properties": {
        "references": {"minItems": 1},
        "evidence": {"minItems": 1}
      }
    }
  },
  {
    "if": {"properties": {"answerability": {"const": "unanswerable_missing_evidence"}}},
    "then": {
      "properties": {
        "references": {"minItems": 0},
        "evidence": {"minItems": 0}
      }
    }
  }
]
```

- [ ] **Step 2: Extend `schemas/generation-profile.schema.json`**

Add these top-level properties inside `properties`:

```json
"attribute_quotas": {
  "type": "object",
  "properties": {
    "rule": {"type": "string"},
    "per_attribute_minimum": {
      "type": "object",
      "additionalProperties": {"type": "number", "minimum": 0, "maximum": 1}
    }
  },
  "additionalProperties": true
},
"answerability_mix": {
  "type": "object",
  "additionalProperties": {"type": "number", "minimum": 0, "maximum": 1}
},
"adversarial_gate": {
  "type": "object",
  "properties": {
    "enabled": {"type": "boolean"},
    "judge": {"type": "object", "additionalProperties": true},
    "baselines": {"type": "object", "additionalProperties": true}
  },
  "additionalProperties": true
}
```

- [ ] **Step 3: Add validator constants and CLI flags**

In `skills/benchmark-validator/scripts/validate_benchmark.py`, add these constants near the existing `ANSWER_TYPES` block:

```python
SCHEMA_VERSIONS = {"v1", "v1.1"}
ANSWERABILITY_VALUES = {
    "answerable",
    "unanswerable_missing_evidence",
    "unanswerable_false_premise",
    "unanswerable_ambiguous",
}
ZERO_EVIDENCE_ANSWERABILITY = {
    "unanswerable_missing_evidence",
    "unanswerable_false_premise",
}
```

In `parse_args()`, add this option to both `lint` and `evaluate` subcommands:

```python
    lint.add_argument(
        "--schema-version",
        choices=sorted(SCHEMA_VERSIONS),
        default="v1",
        help="Validation rules to enforce. v1 keeps legacy compatibility; v1.1 enables answerability and structural rules.",
    )
```

For `evaluate`, use the same argument name and default:

```python
    evaluate.add_argument(
        "--schema-version",
        choices=sorted(SCHEMA_VERSIONS),
        default="v1",
        help="Validation rules to enforce before scoring run results.",
    )
```

- [ ] **Step 4: Make reference/evidence validation answerability-aware**

Change the signature of `validate_references_and_evidence()` to:

```python
def validate_references_and_evidence(
    row: dict[str, Any],
    findings: list[Finding],
    repo_root: Path,
    sources: dict[str, dict[str, Any]],
    schema_version: str = "v1",
) -> set[str]:
```

At the start of the function after `case_id`, add:

```python
    answerability = str(row.get("answerability", "answerable"))
    zero_evidence_allowed = (
        schema_version == "v1.1"
        and answerability in ZERO_EVIDENCE_ANSWERABILITY
    )
```

Replace the unconditional reference/evidence non-empty checks with:

```python
    if not isinstance(references, list):
        add(findings, "FAIL", row["_file"], row["_line"], case_id, "`references` must be a list")
    elif not references and not zero_evidence_allowed:
        add(findings, "FAIL", row["_file"], row["_line"], case_id, "`references` must be a non-empty list for answerable rows")
```

and:

```python
    if not isinstance(evidence, list):
        add(findings, "FAIL", row["_file"], row["_line"], case_id, "`evidence` must be a list")
        return evidence_ids
    if not evidence and not zero_evidence_allowed:
        add(findings, "FAIL", row["_file"], row["_line"], case_id, "`evidence` must be a non-empty list for answerable rows")
        return evidence_ids
```

- [ ] **Step 5: Thread `schema_version` through row validation**

Change `validate_benchmark_rows()` to:

```python
def validate_benchmark_rows(
    rows: list[dict[str, Any]],
    findings: list[Finding],
    repo_root: Path,
    sources: dict[str, dict[str, Any]],
    schema_version: str = "v1",
) -> list[dict[str, Any]]:
```

At the start of the function add:

```python
    structural_records: list[dict[str, Any]] = []
```

Inside the row loop before `validate_query_rewrite(row, findings)`, add:

```python
        if schema_version == "v1.1":
            answerability = row.get("answerability")
            if answerability not in ANSWERABILITY_VALUES:
                add(findings, "FAIL", row["_file"], row["_line"], case_id, "`answerability` is required in v1.1 mode")
```

Change the evidence validation call to:

```python
        evidence_ids = validate_references_and_evidence(
            row,
            findings,
            repo_root,
            sources,
            schema_version=schema_version,
        )
```

At the end of the function add:

```python
    return structural_records
```

In `run_lint()` and `run_evaluate()`, call:

```python
    structural_records = validate_benchmark_rows(
        rows,
        findings,
        args.repo_root,
        sources,
        schema_version=args.schema_version,
    )
```

For `run_evaluate()`, use `benchmark_rows` instead of `rows`.

- [ ] **Step 6: Run the v1.1 validator tests**

Run:

```bash
uv run pytest tests/test_validate_benchmark_v1_1.py -q
```

Expected: PASS.

- [ ] **Step 7: Run baseline compatibility lint**

Run:

```bash
uv run python skills/benchmark-validator/scripts/validate_benchmark.py lint runs/nvdla_benchmark_v1.jsonl --context-bundle runs/nvdla_context_bundle --repo-root .
uv run python skills/benchmark-validator/scripts/validate_benchmark.py lint runs/vortex_benchmark_v1.jsonl --context-bundle runs/vortex_context_bundle --repo-root .
```

Expected:

```text
Rows: 50
FAIL: 0  WARN: 0
```

for both commands.

- [ ] **Step 8: Commit schema and validator mode**

```bash
git add schemas/benchmark-row.schema.json schemas/generation-profile.schema.json skills/benchmark-validator/scripts/validate_benchmark.py tests/test_validate_benchmark_v1_1.py
git commit -m "Add compatibility-preserving v1.1 validation mode" \
  -m "The validator now defaults to legacy v1 behavior and enables answerability-specific checks only through --schema-version v1.1." \
  -m "Constraint: v1.0 NVDLA and Vortex benchmarks must lint unchanged." \
  -m "Rejected: Make v1.1 checks default immediately | this would fail legacy rows before migration." \
  -m "Confidence: high" \
  -m "Scope-risk: moderate" \
  -m "Tested: uv run pytest tests/test_validate_benchmark_v1_1.py -q" \
  -m "Tested: v1 lint commands for NVDLA and Vortex returned FAIL: 0 WARN: 0"
```

### Task 3: Add Structural Gate Rules

**Files:**
- Modify: `skills/benchmark-validator/scripts/validate_benchmark.py`
- Modify: `skills/benchmark-generator/scripts/lint_benchmark_jsonl.py`
- Modify: `tests/test_validate_benchmark_v1_1.py`
- Test: `tests/test_validate_benchmark_v1_1.py`

- [ ] **Step 1: Add structural-gate tests**

Append these tests to `ValidateBenchmarkV11Test` in `tests/test_validate_benchmark_v1_1.py`:

```python
    def test_v1_1_rejects_l2_single_source_evidence(self):
        validator = load_module()
        row = answerable_row()
        row["answerability"] = "answerable"
        row["layer"] = {"code": "L2", "zh": "跨源核对"}
        row["difficulty"] = {
            "axis1_layer": "L2",
            "axis2_retrieval": ["long_tail"],
            "axis3_reasoning": ["conditional_behavior"],
            "claim_sources": {"long_tail": ["sig:demo:a"], "conditional_behavior": ["sig:demo:b"]},
        }

        findings = []
        records = validator.validate_benchmark_rows(
            [row],
            findings,
            ROOT,
            {},
            schema_version="v1.1",
        )

        self.assertFalse(records[0]["pass"])
        self.assertIn("L2_SINGLE_SOURCE", records[0]["reason_codes"])

    def test_v1_1_accepts_l3_with_cross_source_chain(self):
        validator = load_module()
        row = answerable_row()
        row["answerability"] = "answerable"
        row["layer"] = {"code": "L3", "zh": "多跳机制"}
        row["difficulty"] = {
            "axis1_layer": "L3",
            "axis2_retrieval": ["long_tail"],
            "axis3_reasoning": ["conditional_behavior"],
            "claim_sources": {"long_tail": ["sig:demo:a"], "conditional_behavior": ["sig:demo:b"]},
        }
        row["references"].append({"source_id": "src:b", "path": "repo/b.c"})
        row["evidence"].append(
            {
                "evidence_id": "E2",
                "source_id": "src:b",
                "path": "repo/b.c",
                "lines": "20-21",
                "role": "state",
                "statement": "The state update happens after the guard.",
            }
        )
        row["answer_rubric"]["required_atoms"] = [
            {
                "id": "A1",
                "role": "evidence_fact",
                "statement": "The guard blocks launch when count is zero.",
                "match_type": "semantic_fact",
                "evidence_ids": ["E1"],
                "weight": 1.0,
            },
            {
                "id": "A2",
                "role": "conclusion",
                "statement": "The later state update therefore does not happen on that path.",
                "match_type": "semantic_reasoning",
                "evidence_ids": ["E2"],
                "depends_on": ["A1"],
                "weight": 1.0,
            },
        ]

        findings = []
        records = validator.validate_benchmark_rows(
            [row],
            findings,
            ROOT,
            {},
            schema_version="v1.1",
        )

        self.assertTrue(records[0]["pass"], records)

    def test_structural_gate_json_is_written_by_cli(self):
        import json
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            benchmark = tmpdir / "benchmark.jsonl"
            gate = tmpdir / "structural.json"
            row = answerable_row()
            row.pop("_file", None)
            row.pop("_line", None)
            row["answerability"] = "answerable"
            row["difficulty"] = {
                "axis1_layer": "L1",
                "axis2_retrieval": ["long_tail"],
                "axis3_reasoning": ["conditional_behavior"],
                "claim_sources": {"long_tail": ["sig:demo:a"], "conditional_behavior": ["sig:demo:b"]},
            }
            benchmark.write_text(json.dumps(row, ensure_ascii=False) + "\n", encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "lint",
                    str(benchmark),
                    "--schema-version",
                    "v1.1",
                    "--repo-root",
                    str(ROOT),
                    "--structural-gate-json",
                    str(gate),
                ],
                cwd=ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            records = json.loads(gate.read_text(encoding="utf-8"))
            self.assertEqual(records[0]["case_id"], "case-answerable")
            self.assertTrue(records[0]["pass"])
```

- [ ] **Step 2: Run tests to verify structural gate is missing**

Run:

```bash
uv run pytest tests/test_validate_benchmark_v1_1.py -q
```

Expected: FAIL because `validate_benchmark_rows()` returns an empty structural-record list and the CLI does not recognize `--structural-gate-json`.

- [ ] **Step 3: Add structural gate constants and helpers**

In `skills/benchmark-validator/scripts/validate_benchmark.py`, add these constants near `ANSWERABILITY_VALUES`:

```python
CONDITIONAL_EVIDENCE_ROLES = {"trigger_condition", "branch", "guard", "predicate", "state"}
STRUCTURAL_REASON_MESSAGES = {
    "MISSING_DIFFICULTY": "`difficulty` is required in v1.1 mode",
    "DIFFICULTY_LAYER_MISMATCH": "`difficulty.axis1_layer` must match `layer.code`",
    "INSUFFICIENT_DIFFICULTY_SIGNALS": "v1.1 rows need at least two difficulty signals across axes",
    "L2_SINGLE_SOURCE": "L2 rows need evidence from at least two source_id values",
    "L3_SINGLE_SOURCE": "L3 rows need evidence from at least two source_id values",
    "L3_NO_ATOM_CHAIN": "L3 rows need at least one required atom with depends_on",
    "CONDITIONAL_BEHAVIOR_WITHOUT_ROLE": "`conditional_behavior` needs guard/branch/predicate/state evidence",
    "FORBIDDEN_ATOMS_REQUIRED": "yes_no, fact_check, and false_premise rows need forbidden_atoms",
    "FILE_ANCHOR_LEAK": "query names an evidence file without file_anchor_required tag",
}
```

Add these helper functions after `label_code()`:

```python
def row_tags(row: dict[str, Any]) -> set[str]:
    tags = row.get("tags", [])
    return {str(item) for item in tags if isinstance(item, str)} if isinstance(tags, list) else set()


def difficulty_attributes(row: dict[str, Any]) -> list[str]:
    difficulty = row.get("difficulty")
    if not isinstance(difficulty, dict):
        return []
    attrs: list[str] = []
    for key in ("axis2_retrieval", "axis3_reasoning"):
        values = difficulty.get(key, [])
        if isinstance(values, list):
            attrs.extend(str(value) for value in values if isinstance(value, str))
    return attrs


def evidence_source_ids(row: dict[str, Any]) -> set[str]:
    evidence = row.get("evidence", [])
    if not isinstance(evidence, list):
        return set()
    return {
        str(item.get("source_id"))
        for item in evidence
        if isinstance(item, dict) and is_nonempty_string(item.get("source_id"))
    }


def has_atom_dependency(row: dict[str, Any]) -> bool:
    rubric = row.get("answer_rubric", {})
    atoms = rubric.get("required_atoms", []) if isinstance(rubric, dict) else []
    if not isinstance(atoms, list):
        return False
    for atom in atoms:
        if isinstance(atom, dict) and isinstance(atom.get("depends_on"), list) and atom["depends_on"]:
            return True
    return False


def has_conditional_evidence_role(row: dict[str, Any]) -> bool:
    evidence = row.get("evidence", [])
    if not isinstance(evidence, list):
        return False
    return any(
        isinstance(item, dict) and item.get("role") in CONDITIONAL_EVIDENCE_ROLES
        for item in evidence
    )


def query_mentions_evidence_file(row: dict[str, Any]) -> bool:
    query = str(row.get("query", ""))
    evidence = row.get("evidence", [])
    if not isinstance(evidence, list):
        return False
    for item in evidence:
        if not isinstance(item, dict):
            continue
        path = str(item.get("path", ""))
        if path and path in query:
            return True
        filename = Path(path).name
        if filename and "." in filename and filename in query:
            return True
    return False
```

- [ ] **Step 4: Add the structural gate record function**

Add this function before `validate_benchmark_rows()`:

```python
def structural_gate_record(row: dict[str, Any]) -> dict[str, Any]:
    case_id = str(row.get("case_id", "<missing>"))
    layer = label_code(row.get("layer"))
    answer_type = label_code(row.get("answer_type"))
    answerability = str(row.get("answerability", "answerable"))
    difficulty = row.get("difficulty")
    reason_codes: list[str] = []

    if not isinstance(difficulty, dict):
        reason_codes.append("MISSING_DIFFICULTY")
        attrs: list[str] = []
    else:
        attrs = difficulty_attributes(row)
        if difficulty.get("axis1_layer") != layer:
            reason_codes.append("DIFFICULTY_LAYER_MISMATCH")

    if len(set(attrs + ([layer] if layer == "L3" else []))) < 2:
        reason_codes.append("INSUFFICIENT_DIFFICULTY_SIGNALS")

    source_ids = evidence_source_ids(row)
    if layer == "L2" and len(source_ids) < 2:
        reason_codes.append("L2_SINGLE_SOURCE")
    if layer == "L3":
        if len(source_ids) < 2:
            reason_codes.append("L3_SINGLE_SOURCE")
        if not has_atom_dependency(row):
            reason_codes.append("L3_NO_ATOM_CHAIN")

    if "conditional_behavior" in attrs and not has_conditional_evidence_role(row):
        reason_codes.append("CONDITIONAL_BEHAVIOR_WITHOUT_ROLE")

    rubric = row.get("answer_rubric", {})
    forbidden_atoms = rubric.get("forbidden_atoms", []) if isinstance(rubric, dict) else []
    if (
        answer_type in {"yes_no", "fact_check"}
        or answerability == "unanswerable_false_premise"
        or "false_premise" in attrs
    ) and not forbidden_atoms:
        reason_codes.append("FORBIDDEN_ATOMS_REQUIRED")

    if "file_anchor_required" not in row_tags(row) and query_mentions_evidence_file(row):
        reason_codes.append("FILE_ANCHOR_LEAK")

    return {
        "case_id": case_id,
        "pass": not reason_codes,
        "reason_codes": reason_codes,
        "reasons": [STRUCTURAL_REASON_MESSAGES[code] for code in reason_codes],
        "layer": layer,
        "answerability": answerability,
        "attributes": attrs,
    }
```

- [ ] **Step 5: Wire structural records into validation**

Inside `validate_benchmark_rows()`, after `validate_rubric(row, findings, evidence_ids)`, add:

```python
        if schema_version == "v1.1":
            record = structural_gate_record(row)
            structural_records.append(record)
            for code in record["reason_codes"]:
                add(findings, "FAIL", row["_file"], row["_line"], case_id, STRUCTURAL_REASON_MESSAGES[code])
```

In `parse_args()`, add this to the lint subcommand:

```python
    lint.add_argument("--structural-gate-json", type=Path, help="Write v1.1 structural gate records to JSON")
```

In `run_lint()`, after the JSON report write block, add:

```python
    if args.structural_gate_json:
        args.structural_gate_json.parent.mkdir(parents=True, exist_ok=True)
        args.structural_gate_json.write_text(
            json.dumps(structural_records, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
```

- [ ] **Step 6: Mirror v1.1 checks in generator lint**

In `skills/benchmark-generator/scripts/lint_benchmark_jsonl.py`, add `--schema-version` with choices `v1` and `v1.1`, then copy the same helper functions and structural-gate call used by `validate_benchmark.py`.

Use the same reason code strings. Keep the default as `v1`.

- [ ] **Step 7: Run structural-gate tests**

Run:

```bash
uv run pytest tests/test_validate_benchmark_v1_1.py -q
```

Expected: PASS.

- [ ] **Step 8: Run compatibility lint again**

Run:

```bash
uv run python skills/benchmark-validator/scripts/validate_benchmark.py lint runs/nvdla_benchmark_v1.jsonl --context-bundle runs/nvdla_context_bundle --repo-root .
uv run python skills/benchmark-validator/scripts/validate_benchmark.py lint runs/vortex_benchmark_v1.jsonl --context-bundle runs/vortex_context_bundle --repo-root .
```

Expected: both commands print `FAIL: 0  WARN: 0`.

- [ ] **Step 9: Commit structural gate**

```bash
git add skills/benchmark-validator/scripts/validate_benchmark.py skills/benchmark-generator/scripts/lint_benchmark_jsonl.py tests/test_validate_benchmark_v1_1.py
git commit -m "Enforce v1.1 benchmark structural claims behind an explicit mode" \
  -m "The structural gate checks evidence breadth, chained atom structure, conditional evidence roles, forbidden atoms, and file-anchor leakage only when v1.1 mode is requested." \
  -m "Constraint: Legacy v1 lint remains the default for existing corpus artifacts." \
  -m "Rejected: Treat structural warnings as report-only | v1.1 difficulty claims need hard deterministic failures before model-backed gates." \
  -m "Confidence: high" \
  -m "Scope-risk: moderate" \
  -m "Tested: uv run pytest tests/test_validate_benchmark_v1_1.py -q" \
  -m "Tested: v1 lint commands for NVDLA and Vortex returned FAIL: 0 WARN: 0"
```

### Task 4: Add Signal Index Schema, Validation, and Builder

**Files:**
- Create: `schemas/signal-index.schema.json`
- Create: `tests/test_signal_index.py`
- Create: `skills/benchmark-repo-analyzer/scripts/build_signal_index.py`
- Modify: `skills/benchmark-repo-analyzer/scripts/validate_context_bundle.py`
- Test: `tests/test_signal_index.py`

- [ ] **Step 1: Add signal-index tests**

Create `tests/test_signal_index.py` with this content:

```python
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = ROOT / "skills" / "benchmark-repo-analyzer" / "scripts" / "validate_context_bundle.py"
BUILDER = ROOT / "skills" / "benchmark-repo-analyzer" / "scripts" / "build_signal_index.py"


def load_validator():
    spec = importlib.util.spec_from_file_location("validate_context_bundle", VALIDATOR)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class SignalIndexTest(unittest.TestCase):
    def test_signal_index_schema_file_exists_and_names_required_fields(self):
        schema_path = ROOT / "schemas" / "signal-index.schema.json"
        self.assertTrue(schema_path.exists())
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        self.assertEqual(schema["title"], "Analyzer Signal Index Row")
        self.assertEqual(
            set(schema["required"]),
            {"signal_id", "project", "axis", "attribute", "anchor", "evidence", "extractor", "confidence"},
        )

    def test_context_validator_accepts_valid_signal_index(self):
        validator = load_validator()
        rows = [
            {
                "_line": 1,
                "signal_id": "sig:demo:entity-a:long_tail",
                "project": "demo",
                "axis": 2,
                "attribute": "long_tail",
                "anchor": {"kind": "entity", "entity_id": "ent:a", "source_id": "src:a"},
                "evidence": {"reference_count": 1},
                "extractor": "test",
                "confidence": 0.9,
            }
        ]
        findings = []
        validator.validate_signals(
            rows,
            Path("signal_index.jsonl"),
            project_id="demo",
            sources={"src:a": {"source_id": "src:a"}},
            entities={"ent:a": {"entity_id": "ent:a"}},
            findings=findings,
        )

        self.assertEqual([f.message for f in findings if f.severity == "FAIL"], [])

    def test_signal_builder_emits_long_tail_and_non_code_signals(self):
        with tempfile.TemporaryDirectory() as tmp:
            bundle = Path(tmp) / "bundle"
            bundle.mkdir()
            (bundle / "source_inventory.jsonl").write_text(
                json.dumps(
                    {
                        "source_id": "src:make",
                        "project": "demo",
                        "source_set_id": "main",
                        "repo_name": "demo",
                        "path": "Makefile",
                        "relative_path": "Makefile",
                        "modality": "script",
                        "source_type": "build.make",
                        "authority": "primary_source",
                        "language": "make",
                        "line_count": 10,
                        "size_bytes": 10,
                        "sha256": "sha256:1",
                        "parse_status": "parsed",
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
            (bundle / "entity_index.jsonl").write_text(
                json.dumps(
                    {
                        "entity_id": "ent:target",
                        "project": "demo",
                        "source_id": "src:make",
                        "name": "run",
                        "kind": "make_target",
                        "path": "Makefile",
                        "line_start": 1,
                        "line_end": 1,
                        "extractor": "test",
                        "confidence": 0.9,
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
            (bundle / "relation_graph.jsonl").write_text("", encoding="utf-8")
            output = bundle / "signal_index.jsonl"

            result = subprocess.run(
                [sys.executable, str(BUILDER), str(bundle), "--output", str(output)],
                cwd=ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            signals = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
            self.assertTrue(any(item["attribute"] == "long_tail" for item in signals))
            self.assertTrue(any(item["attribute"] == "non_code_anchor" for item in signals))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run signal tests to verify they fail**

Run:

```bash
uv run pytest tests/test_signal_index.py -q
```

Expected: FAIL because `schemas/signal-index.schema.json`, `validate_signals()`, and `build_signal_index.py` do not exist yet.

- [ ] **Step 3: Add `schemas/signal-index.schema.json`**

Create `schemas/signal-index.schema.json`:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://example.local/kb-benchmark/signal-index.schema.json",
  "title": "Analyzer Signal Index Row",
  "type": "object",
  "required": [
    "signal_id",
    "project",
    "axis",
    "attribute",
    "anchor",
    "evidence",
    "extractor",
    "confidence"
  ],
  "properties": {
    "signal_id": {"type": "string", "minLength": 1},
    "project": {"type": "string", "minLength": 1},
    "axis": {"type": "integer", "enum": [2, 3]},
    "attribute": {"type": "string", "minLength": 1},
    "anchor": {
      "type": "object",
      "properties": {
        "kind": {"type": "string"},
        "entity_id": {"type": "string"},
        "source_id": {"type": "string"},
        "path": {"type": "string"},
        "lines": {"type": "string"}
      },
      "additionalProperties": true
    },
    "evidence": {"type": "object", "additionalProperties": true},
    "extractor": {"type": "string", "minLength": 1},
    "confidence": {"type": "number", "minimum": 0, "maximum": 1}
  },
  "additionalProperties": true
}
```

- [ ] **Step 4: Add signal validation to context bundle validator**

In `skills/benchmark-repo-analyzer/scripts/validate_context_bundle.py`, add this required-fields constant near `RELATION_REQUIRED`:

```python
SIGNAL_REQUIRED = {
    "signal_id",
    "project",
    "axis",
    "attribute",
    "anchor",
    "evidence",
    "extractor",
    "confidence",
}
```

Add this helper after `validate_relations()`:

```python
def validate_signals(
    rows: list[dict[str, Any]],
    path: Path,
    project_id: str | None,
    sources: dict[str, dict[str, Any]],
    entities: dict[str, dict[str, Any]],
    findings: list[Finding],
) -> dict[str, int]:
    by_id: set[str] = set()
    by_attribute: dict[str, int] = {}
    for row in rows:
        line = row.get("_line")
        signal_id = str(row.get("signal_id", "<missing>"))
        missing = sorted(SIGNAL_REQUIRED - set(row))
        if missing:
            add(findings, "FAIL", str(path), line, signal_id, f"signal missing fields: {', '.join(missing)}")
        if signal_id in by_id:
            add(findings, "FAIL", str(path), line, signal_id, "duplicate signal_id")
        elif signal_id != "<missing>":
            by_id.add(signal_id)
        if project_id and row.get("project") != project_id:
            add(findings, "FAIL", str(path), line, signal_id, "`project` does not match manifest project.id")
        if row.get("axis") not in {2, 3}:
            add(findings, "FAIL", str(path), line, signal_id, "`axis` must be 2 or 3")
        if not is_number_0_to_1(row.get("confidence")):
            add(findings, "FAIL", str(path), line, signal_id, "`confidence` must be a number from 0 to 1")
        anchor = row.get("anchor")
        if not isinstance(anchor, dict):
            add(findings, "FAIL", str(path), line, signal_id, "`anchor` must be an object")
            continue
        source_id = anchor.get("source_id")
        entity_id = anchor.get("entity_id")
        if source_id and source_id not in sources:
            add(findings, "FAIL", str(path), line, signal_id, "anchor.source_id not present in source inventory")
        if entity_id and entity_id not in entities:
            add(findings, "FAIL", str(path), line, signal_id, "anchor.entity_id not present in entity index")
        attribute = str(row.get("attribute", "<missing>"))
        by_attribute[attribute] = by_attribute.get(attribute, 0) + 1
    return by_attribute
```

In `main()`, derive `project_id` after manifest validation:

```python
    project_id = None
    if isinstance(manifest, dict) and isinstance(manifest.get("project"), dict):
        project_id = manifest["project"].get("id")
```

Then load and validate optional signals after relation validation:

```python
    signal_path = bundle / "signal_index.jsonl"
    signal_rows = load_jsonl(signal_path, findings) if signal_path.exists() else []
    signal_counts = (
        validate_signals(signal_rows, signal_path, project_id, sources, entities, findings)
        if signal_path.exists()
        else {}
    )
```

Add `signals` and `signal_counts` to the `summary` dict:

```python
        "signals": len(signal_rows),
        "signal_counts": dict(sorted(signal_counts.items())),
```

Print signal counts after the existing source/entity/relation line:

```python
    if signal_path.exists():
        print(f"Signals: {len(signal_rows)}  Attributes: {dict(sorted(signal_counts.items()))}")
```

- [ ] **Step 5: Add deterministic signal builder**

Create `skills/benchmark-repo-analyzer/scripts/build_signal_index.py`:

```python
#!/usr/bin/env python3
"""Build a deterministic v1.1 signal_index.jsonl from analyzer bundle artifacts."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


NON_CODE_MODALITIES = {"script", "config"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build signal_index.jsonl for a project context bundle.")
    parser.add_argument("bundle", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--long-tail-threshold", type=int, default=3)
    return parser.parse_args()


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
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


def relation_endpoint_ids(row: dict[str, Any]) -> list[str]:
    ids: list[str] = []
    for field in ("subject", "object"):
        endpoint = row.get(field)
        if isinstance(endpoint, dict) and isinstance(endpoint.get("id"), str):
            ids.append(endpoint["id"])
    return ids


def entity_anchor(entity: dict[str, Any]) -> dict[str, Any]:
    return {
        "kind": "entity",
        "entity_id": entity.get("entity_id"),
        "source_id": entity.get("source_id"),
        "path": entity.get("path"),
        "lines": f"{entity.get('line_start')}-{entity.get('line_end')}",
    }


def source_anchor(source: dict[str, Any]) -> dict[str, Any]:
    return {
        "kind": "source",
        "source_id": source.get("source_id"),
        "path": source.get("path"),
    }


def make_signal(
    project: str,
    attribute: str,
    axis: int,
    anchor: dict[str, Any],
    evidence: dict[str, Any],
    extractor: str,
    confidence: float,
) -> dict[str, Any]:
    anchor_id = anchor.get("entity_id") or anchor.get("source_id") or anchor.get("path")
    return {
        "signal_id": f"sig:{project}:{attribute}:{anchor_id}",
        "project": project,
        "axis": axis,
        "attribute": attribute,
        "anchor": anchor,
        "evidence": evidence,
        "extractor": extractor,
        "confidence": confidence,
    }


def build_signals(bundle: Path, long_tail_threshold: int) -> list[dict[str, Any]]:
    sources = load_jsonl(bundle / "source_inventory.jsonl")
    entities = load_jsonl(bundle / "entity_index.jsonl")
    relations = load_jsonl(bundle / "relation_graph.jsonl")
    project = ""
    if sources:
        project = str(sources[0].get("project", "project"))
    elif entities:
        project = str(entities[0].get("project", "project"))

    source_by_id = {str(row.get("source_id")): row for row in sources if row.get("source_id")}
    inbound = Counter()
    for relation in relations:
        for endpoint_id in relation_endpoint_ids(relation):
            inbound[endpoint_id] += 1

    signals: list[dict[str, Any]] = []

    for entity in entities:
        entity_id = str(entity.get("entity_id", ""))
        degree = inbound.get(entity_id, 0)
        if degree <= long_tail_threshold:
            signals.append(
                make_signal(
                    project,
                    "long_tail",
                    2,
                    entity_anchor(entity),
                    {"reference_count": degree, "threshold": long_tail_threshold},
                    "build_signal_index/relation_graph_indegree",
                    0.8,
                )
            )

    for source in sources:
        if source.get("modality") in NON_CODE_MODALITIES:
            signals.append(
                make_signal(
                    project,
                    "non_code_anchor",
                    2,
                    source_anchor(source),
                    {"modality": source.get("modality"), "source_type": source.get("source_type")},
                    "build_signal_index/source_modality",
                    0.9,
                )
            )

    by_name: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for entity in entities:
        name = str(entity.get("name", "")).strip().lower()
        if name:
            by_name[name].append(entity)
    for name, matching in by_name.items():
        source_ids = {item.get("source_id") for item in matching}
        if len(matching) > 1 and len(source_ids) > 1:
            for entity in matching:
                signals.append(
                    make_signal(
                        project,
                        "distracting_info",
                        2,
                        entity_anchor(entity),
                        {"collision_name": name, "collision_count": len(matching)},
                        "build_signal_index/name_collision",
                        0.75,
                    )
                )

    for relation in relations:
        predicate = str(relation.get("predicate", ""))
        if predicate in {"checks_condition", "reads", "writes"}:
            for endpoint_id in relation_endpoint_ids(relation):
                entity = next((item for item in entities if item.get("entity_id") == endpoint_id), None)
                if entity:
                    signals.append(
                        make_signal(
                            project,
                            "conditional_behavior",
                            3,
                            entity_anchor(entity),
                            {"predicate": predicate, "relation_id": relation.get("relation_id")},
                            "build_signal_index/relation_predicate",
                            0.7,
                        )
                    )

    return sorted(signals, key=lambda item: item["signal_id"])


def main() -> int:
    args = parse_args()
    signals = build_signals(args.bundle, args.long_tail_threshold)
    write_jsonl(args.output, signals)
    print(f"Wrote {len(signals)} signals to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 6: Run signal-index tests**

Run:

```bash
uv run pytest tests/test_signal_index.py -q
```

Expected: PASS.

- [ ] **Step 7: Build and validate local signal indexes**

Run:

```bash
uv run python skills/benchmark-repo-analyzer/scripts/build_signal_index.py runs/nvdla_context_bundle --output runs/nvdla_context_bundle/signal_index.jsonl
uv run python skills/benchmark-repo-analyzer/scripts/build_signal_index.py runs/vortex_context_bundle --output runs/vortex_context_bundle/signal_index.jsonl
uv run python skills/benchmark-repo-analyzer/scripts/validate_context_bundle.py runs/nvdla_context_bundle --repo-root .
uv run python skills/benchmark-repo-analyzer/scripts/validate_context_bundle.py runs/vortex_context_bundle --repo-root .
```

Expected: both validator runs exit 0 and print a `Signals:` line.

- [ ] **Step 8: Commit signal-index infrastructure**

```bash
git add schemas/signal-index.schema.json tests/test_signal_index.py skills/benchmark-repo-analyzer/scripts/validate_context_bundle.py skills/benchmark-repo-analyzer/scripts/build_signal_index.py runs/nvdla_context_bundle/signal_index.jsonl runs/vortex_context_bundle/signal_index.jsonl
git commit -m "Add deterministic signal index infrastructure for v1.1" \
  -m "The analyzer bundle can now carry optional signal_index.jsonl records, with a deterministic first-pass builder for long-tail, non-code, distracting-info, and conditional-behavior signals." \
  -m "Constraint: signal_index.jsonl must be optional for existing v1 bundles." \
  -m "Rejected: Require full analyzer regeneration before signal support | a deterministic sidecar builder lets the current corpus move forward." \
  -m "Confidence: medium" \
  -m "Scope-risk: moderate" \
  -m "Tested: uv run pytest tests/test_signal_index.py -q" \
  -m "Tested: validate_context_bundle.py runs on NVDLA and Vortex bundles"
```

### Task 5: Add Adversarial Gate Dry-Run

**Files:**
- Create: `tests/test_adversarial_gate.py`
- Create: `skills/benchmark-validator/scripts/adversarial_gate.py`
- Test: `tests/test_adversarial_gate.py`

- [ ] **Step 1: Add dry-run tests**

Create `tests/test_adversarial_gate.py`:

```python
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills" / "benchmark-validator" / "scripts" / "adversarial_gate.py"


class AdversarialGateTest(unittest.TestCase):
    def test_dry_run_writes_one_record_per_claim(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            benchmark = tmpdir / "benchmark.jsonl"
            output = tmpdir / "gate.jsonl"
            row = {
                "case_id": "case-1",
                "difficulty": {
                    "axis1_layer": "L2",
                    "axis2_retrieval": ["long_tail"],
                    "axis3_reasoning": ["conditional_behavior"],
                    "claim_sources": {
                        "long_tail": ["sig:demo:a"],
                        "conditional_behavior": ["sig:demo:b"],
                    },
                },
            }
            benchmark.write_text(json.dumps(row, ensure_ascii=False) + "\n", encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    str(benchmark),
                    "--dry-run",
                    "--output-jsonl",
                    str(output),
                ],
                cwd=ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            records = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
            self.assertEqual([record["attribute"] for record in records], ["long_tail", "conditional_behavior"])
            self.assertTrue(all(record["status"] == "skipped_no_provider" for record in records))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run dry-run tests to verify script is missing**

Run:

```bash
uv run pytest tests/test_adversarial_gate.py -q
```

Expected: FAIL because `skills/benchmark-validator/scripts/adversarial_gate.py` does not exist.

- [ ] **Step 3: Add adversarial gate dry-run script**

Create `skills/benchmark-validator/scripts/adversarial_gate.py`:

```python
#!/usr/bin/env python3
"""Run or dry-run matched adversarial gates for v1.1 benchmark claims."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ATTRIBUTE_BASELINES = {
    "long_tail": "closed_book_llm",
    "distracting_info": "top_1_dense_only",
    "version_fork": "single_source_set_retrieval",
    "non_code_anchor": "code_only_retrieval",
    "false_premise": "closed_book_llm",
    "doc_code_divergence": "doc_only_retrieval",
    "conditional_behavior": "top_1_dense_only",
    "negative_evidence": "closed_book_llm",
    "implicit_domain_knowledge": "oracle_evidence_no_reasoning_llm",
    "quantitative_aggregation": "top_1_dense_only",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate v1.1 adversarial gate claims.")
    parser.add_argument("benchmark", type=Path)
    parser.add_argument("--output-jsonl", type=Path, required=True)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--judge-provider", choices=["command", "deepseek"])
    parser.add_argument("--judge-model", default="deepseek-v4-pro")
    return parser.parse_args()


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            value = json.loads(line)
            if isinstance(value, dict):
                rows.append(value)
    return rows


def row_claims(row: dict[str, Any]) -> list[str]:
    difficulty = row.get("difficulty")
    if not isinstance(difficulty, dict):
        return []
    claims: list[str] = []
    for field in ("axis2_retrieval", "axis3_reasoning"):
        values = difficulty.get(field, [])
        if isinstance(values, list):
            claims.extend(str(value) for value in values if isinstance(value, str))
    return claims


def dry_run_record(row: dict[str, Any], attribute: str, judge_model: str) -> dict[str, Any]:
    baseline = ATTRIBUTE_BASELINES.get(attribute, "closed_book_llm")
    return {
        "case_id": row.get("case_id"),
        "attribute": attribute,
        "baseline": baseline,
        "status": "skipped_no_provider",
        "confirmed": None,
        "judge_provider": None,
        "judge_model": judge_model,
        "cache_key": f"{row.get('case_id')}:{attribute}:{baseline}:{judge_model}:dry-run-v1",
        "rationale": "Dry run only; no adversarial baseline or judge was invoked.",
    }


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def run(args: argparse.Namespace) -> int:
    benchmark_rows = load_jsonl(args.benchmark)
    records: list[dict[str, Any]] = []
    for row in benchmark_rows:
        for attribute in row_claims(row):
            records.append(dry_run_record(row, attribute, args.judge_model))
    write_jsonl(args.output_jsonl, records)
    print(f"Wrote {len(records)} adversarial gate records to {args.output_jsonl}")
    return 0


def main() -> int:
    args = parse_args()
    if not args.dry_run and not args.judge_provider:
        print("ERROR: non-dry-run mode requires --judge-provider", flush=True)
        return 2
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run dry-run tests**

Run:

```bash
uv run pytest tests/test_adversarial_gate.py -q
```

Expected: PASS.

- [ ] **Step 5: Run full test suite**

Run:

```bash
uv run pytest
```

Expected: PASS.

- [ ] **Step 6: Commit adversarial dry-run infrastructure**

```bash
git add tests/test_adversarial_gate.py skills/benchmark-validator/scripts/adversarial_gate.py
git commit -m "Add dry-run adversarial gate records for v1.1 claims" \
  -m "The dry-run gate establishes row x claim output shape and cache keys before paid model-backed baselines are wired in." \
  -m "Constraint: v1.1 generation must be able to proceed without a judge provider configured." \
  -m "Rejected: Block gate development on provider-backed baselines | dry-run records let downstream reporting stabilize first." \
  -m "Confidence: medium" \
  -m "Scope-risk: narrow" \
  -m "Tested: uv run pytest tests/test_adversarial_gate.py -q" \
  -m "Tested: uv run pytest"
```

### Task 6: Update Contracts and README

**Files:**
- Modify: `README.md`
- Modify: `skills/benchmark-repo-analyzer/references/analyzer-contract.md`
- Modify: `skills/benchmark-generator/references/generator-contract.md`
- Modify: `skills/benchmark-validator/references/validator-contract.md`
- Test: documentation grep

- [ ] **Step 1: Update analyzer contract**

In `skills/benchmark-repo-analyzer/references/analyzer-contract.md`, add this section after the output bundle file list:

```markdown
## v1.1 optional file: signal_index.jsonl

`signal_index.jsonl` is optional for v1 bundles and recommended for v1.1 generation.
Each row records one analyzer-derived difficulty signal. The generator must use
this artifact for attribute-first sampling instead of rediscovering difficulty
from source files.

Required fields:

| Field | Meaning |
|---|---|
| `signal_id` | Stable signal id, unique inside the bundle. |
| `project` | Project id from manifest. |
| `axis` | Difficulty axis, currently `2` retrieval difficulty or `3` reasoning difficulty. |
| `attribute` | Difficulty attribute such as `long_tail` or `conditional_behavior`. |
| `anchor` | Entity or source anchor the signal applies to. |
| `evidence` | Extractor-specific evidence payload. |
| `extractor` | Tool or heuristic that produced the signal. |
| `confidence` | Number from `0.0` to `1.0`. |
```

- [ ] **Step 2: Update generator contract**

In `skills/benchmark-generator/references/generator-contract.md`, add:

```markdown
## v1.1 Generation Inputs

For v1.1 generation, consume `signal_index.jsonl` when it is present. The
generator chooses target difficulty attributes first, then selects anchors from
matching signals. It should not scan the source repositories to infer difficulty
attributes that the analyzer did not expose.

Profile additions:

- `attribute_quotas.per_attribute_minimum`
- `answerability_mix`
- `adversarial_gate`

Every v1.1 row should include:

- `answerability`
- `difficulty.axis1_layer`
- `difficulty.axis2_retrieval`
- `difficulty.axis3_reasoning`
- `difficulty.claim_sources`
```

- [ ] **Step 3: Update validator contract**

In `skills/benchmark-validator/references/validator-contract.md`, add:

```markdown
## v1.1 Validation Mode

Use `--schema-version v1.1` to enable v1.1 checks. The default remains `v1`
so existing benchmarks continue to lint unchanged.

Structural gate reports are written with:

```bash
python3 skills/benchmark-validator/scripts/validate_benchmark.py lint benchmark.jsonl \
  --schema-version v1.1 \
  --structural-gate-json benchmark.structural_gate.json
```

Adversarial dry-run reports are written with:

```bash
python3 skills/benchmark-validator/scripts/adversarial_gate.py benchmark.jsonl \
  --dry-run \
  --output-jsonl benchmark.adversarial_gate.jsonl
```
```

- [ ] **Step 4: Update README**

Add a short `v1.1 development workflow` section to `README.md`:

```markdown
## v1.1 Development Workflow

v1.1 keeps v1 artifacts valid by default. Use explicit v1.1 mode for stricter
answerability and difficulty checks:

```bash
python3 skills/benchmark-validator/scripts/validate_benchmark.py lint \
  runs/nvdla_benchmark_v1_1.jsonl \
  --context-bundle runs/nvdla_context_bundle \
  --repo-root . \
  --schema-version v1.1 \
  --structural-gate-json runs/nvdla_benchmark_v1_1.structural_gate.json
```

Build analyzer signals before v1.1 generation:

```bash
python3 skills/benchmark-repo-analyzer/scripts/build_signal_index.py \
  runs/nvdla_context_bundle \
  --output runs/nvdla_context_bundle/signal_index.jsonl
```

Run the adversarial gate in dry-run mode when no judge provider is configured:

```bash
python3 skills/benchmark-validator/scripts/adversarial_gate.py \
  runs/nvdla_benchmark_v1_1.jsonl \
  --dry-run \
  --output-jsonl runs/nvdla_benchmark_v1_1.adversarial_gate.jsonl
```
```

- [ ] **Step 5: Verify docs mention all v1.1 artifacts**

Run:

```bash
rg -n "signal_index|answerability|difficulty|schema-version v1.1|structural-gate-json|adversarial_gate" README.md skills schemas tests
```

Expected: output contains matches in README, analyzer contract, generator contract, validator contract, schemas, and tests.

- [ ] **Step 6: Final verification**

Run:

```bash
uv run pytest
uv run python skills/benchmark-validator/scripts/validate_benchmark.py lint runs/nvdla_benchmark_v1.jsonl --context-bundle runs/nvdla_context_bundle --repo-root .
uv run python skills/benchmark-validator/scripts/validate_benchmark.py lint runs/vortex_benchmark_v1.jsonl --context-bundle runs/vortex_context_bundle --repo-root .
```

Expected: test suite passes and both v1 lint commands print `FAIL: 0  WARN: 0`.

- [ ] **Step 7: Commit documentation**

```bash
git add README.md skills/benchmark-repo-analyzer/references/analyzer-contract.md skills/benchmark-generator/references/generator-contract.md skills/benchmark-validator/references/validator-contract.md
git commit -m "Document v1.1 signal and gate workflow" \
  -m "The skill contracts now explain how v1.1 signals, answerability, structural gates, and adversarial dry-run records fit into the existing artifact pipeline." \
  -m "Constraint: Documentation must preserve v1 usage while explaining explicit v1.1 mode." \
  -m "Confidence: high" \
  -m "Scope-risk: narrow" \
  -m "Tested: rg documentation scan for v1.1 terms" \
  -m "Tested: uv run pytest and v1 lint commands for NVDLA/Vortex"
```

## Infrastructure Completion Checklist

- [ ] `uv run pytest` passes.
- [ ] v1 NVDLA and Vortex lint commands pass unchanged.
- [ ] `schemas/signal-index.schema.json` exists.
- [ ] `runs/nvdla_context_bundle/signal_index.jsonl` validates.
- [ ] `runs/vortex_context_bundle/signal_index.jsonl` validates.
- [ ] `--schema-version v1.1` is accepted by validator lint/evaluate.
- [ ] `--structural-gate-json` writes reason-coded records.
- [ ] `adversarial_gate.py --dry-run` writes one record per row x claim.
- [ ] README and all three skill contracts document the v1.1 workflow.
