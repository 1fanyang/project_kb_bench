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
        # After Phase 5 v2 promotion the canonical bundle is the v2
        # analyzer output; the v1 benchmark JSONL files still live at
        # their historical paths and lint against the *archived* v1
        # bundle (source_ids and schemas were locked together at
        # release time). The v1 bundles moved to runs/archive/ in
        # 2026-06-30; this test follows the move.
        cases = [
            (
                ROOT / "runs" / "nvdla_benchmark_v1.jsonl",
                ROOT / "runs" / "archive" / "nvdla_context_bundle_v1",
            ),
            (
                ROOT / "runs" / "vortex_benchmark_v1.jsonl",
                ROOT / "runs" / "archive" / "vortex_context_bundle_v1",
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
        row["difficulty"] = {
            "axis1_layer": "L1",
            "axis2_retrieval": ["negative_evidence"],
            "axis3_reasoning": ["snapshot_gap"],
            "claim_sources": {
                "negative_evidence": ["sig:demo:negative"],
                "snapshot_gap": ["sig:demo:snapshot"],
            },
        }
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

    def test_evaluate_case_allows_missing_evidence_refusal_without_retrieval(self):
        validator = load_module()
        row = answerable_row()
        row["case_id"] = "case-missing-eval"
        row["answerability"] = "unanswerable_missing_evidence"
        row["references"] = []
        row["evidence"] = []
        row["answer_rubric"]["required_atoms"] = [
            {
                "id": "A1",
                "role": "conclusion",
                "statement": "The answer refuses because evidence is missing.",
                "match_type": "semantic_fact",
                "evidence_ids": [],
                "weight": 1.0,
            }
        ]
        row["answer_rubric"]["forbidden_atoms"] = []
        row["answer_rubric"]["citation_policy"] = {"required": "never"}

        result = validator.evaluate_case(
            row,
            {"case_id": "case-missing-eval", "answer": "The answer refuses because evidence is missing."},
            top_k=10,
            answer_threshold=0.7,
        )

        self.assertEqual(result.reference_recall, 1.0)
        self.assertEqual(result.evidence_recall, 1.0)
        self.assertEqual(result.verdict, "PASS")
        self.assertNotIn("evidence_recall below 1.0", result.notes)

    def test_v1_1_rejects_answerable_row_with_empty_evidence(self):
        validator = load_module()
        row = answerable_row()
        row["answerability"] = "answerable"
        row["evidence"] = []

        messages = lint_fail_messages(validator, row, schema_version="v1.1")

        self.assertIn("`evidence` must be a non-empty list for answerable rows", messages)

    def test_v1_1_rejects_non_missing_evidence_unanswerable_rows_with_empty_anchors(self):
        validator = load_module()
        for answerability in ("unanswerable_false_premise", "unanswerable_ambiguous"):
            with self.subTest(answerability=answerability):
                row = answerable_row()
                row["case_id"] = f"case-{answerability}"
                row["answerability"] = answerability
                row["references"] = []
                row["evidence"] = []
                row["answer_rubric"]["required_atoms"][0]["evidence_ids"] = []
                row["answer_rubric"]["citation_policy"] = {"required": "never"}

                messages = lint_fail_messages(validator, row, schema_version="v1.1")

                self.assertIn("`references` must be a non-empty list for answerable rows", messages)
                self.assertIn("`evidence` must be a non-empty list for answerable rows", messages)

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

    def test_v1_1_rejects_missing_claim_sources(self):
        validator = load_module()
        row = answerable_row()
        row["answerability"] = "answerable"
        row["difficulty"] = {
            "axis1_layer": "L1",
            "axis2_retrieval": ["long_tail"],
            "axis3_reasoning": ["conditional_behavior"],
        }

        messages = lint_fail_messages(validator, row, schema_version="v1.1")

        self.assertIn("`difficulty.claim_sources` is required in v1.1 mode", messages)

    def test_v1_1_rejects_claim_sources_missing_difficulty_attribute(self):
        validator = load_module()
        row = answerable_row()
        row["answerability"] = "answerable"
        row["difficulty"] = {
            "axis1_layer": "L1",
            "axis2_retrieval": ["long_tail"],
            "axis3_reasoning": ["conditional_behavior"],
            "claim_sources": {"long_tail": ["sig:demo:long-tail"]},
        }

        messages = lint_fail_messages(validator, row, schema_version="v1.1")

        self.assertIn(
            "`difficulty.claim_sources` must include signals for every difficulty attribute",
            messages,
        )

    def test_v1_1_rejects_unknown_claim_source_signal_when_signal_index_is_loaded(self):
        validator = load_module()
        row = answerable_row()
        row["answerability"] = "answerable"
        row["difficulty"] = {
            "axis1_layer": "L1",
            "axis2_retrieval": ["long_tail"],
            "axis3_reasoning": ["conditional_behavior"],
            "claim_sources": {
                "long_tail": ["sig:demo:long-tail"],
                "conditional_behavior": ["sig:demo:missing"],
            },
        }
        findings = []

        validator.validate_benchmark_rows(
            [row],
            findings,
            ROOT,
            {},
            schema_version="v1.1",
            signals={
                "sig:demo:long-tail": {
                    "signal_id": "sig:demo:long-tail",
                    "project": "demo",
                    "axis": 2,
                    "attribute": "long_tail",
                }
            },
        )

        self.assertIn(
            "`difficulty.claim_sources` references unknown signal_id: sig:demo:missing",
            [finding.message for finding in findings if finding.severity == "FAIL"],
        )

    def test_v1_1_rejects_claim_source_signal_axis_or_attribute_mismatch(self):
        validator = load_module()
        row = answerable_row()
        row["answerability"] = "answerable"
        row["difficulty"] = {
            "axis1_layer": "L1",
            "axis2_retrieval": ["long_tail"],
            "axis3_reasoning": ["conditional_behavior"],
            "claim_sources": {
                "long_tail": ["sig:demo:wrong-axis"],
                "conditional_behavior": ["sig:demo:conditional"],
            },
        }
        findings = []

        validator.validate_benchmark_rows(
            [row],
            findings,
            ROOT,
            {},
            schema_version="v1.1",
            signals={
                "sig:demo:wrong-axis": {
                    "signal_id": "sig:demo:wrong-axis",
                    "project": "demo",
                    "axis": 3,
                    "attribute": "long_tail",
                },
                "sig:demo:conditional": {
                    "signal_id": "sig:demo:conditional",
                    "project": "demo",
                    "axis": 3,
                    "attribute": "conditional_behavior",
                },
            },
        )

        self.assertIn(
            "`difficulty.claim_sources` signal does not match row project, axis, or attribute: sig:demo:wrong-axis",
            [finding.message for finding in findings if finding.severity == "FAIL"],
        )

    def test_v1_1_rejects_corpus_with_too_many_file_anchored_queries(self):
        validator = load_module()
        rows = []
        for index in range(3):
            row = answerable_row()
            row["case_id"] = f"case-file-anchor-{index}"
            row["answerability"] = "answerable"
            row["difficulty"] = {
                "axis1_layer": "L1",
                "axis2_retrieval": ["long_tail"],
                "axis3_reasoning": ["conditional_behavior"],
                "claim_sources": {"long_tail": ["sig:demo:a"], "conditional_behavior": ["sig:demo:b"]},
            }
            row["tags"] = ["file_anchor_required"]
            row["query"] = "请直接查看 repo/a.c 这几行并告诉我结论。"
            rows.append(row)

        findings = []
        validator.validate_benchmark_rows(
            rows,
            findings,
            ROOT,
            {},
            schema_version="v1.1",
        )

        self.assertIn(
            "file-anchored query ratio exceeds v1.1 limit",
            [finding.message for finding in findings if finding.severity == "FAIL"],
        )

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


if __name__ == "__main__":
    unittest.main()
