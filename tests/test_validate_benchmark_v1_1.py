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


if __name__ == "__main__":
    unittest.main()
