import copy
import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills" / "benchmark-generator" / "scripts" / "lint_benchmark_jsonl.py"


def load_module():
    spec = importlib.util.spec_from_file_location("lint_benchmark_jsonl", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def base_row():
    return {
        "_file": "inline.jsonl",
        "_line": 1,
        "case_id": "case-1",
        "project": "demo",
        "layer": {"code": "L1", "zh": "单源检索"},
        "query": "当前快照里能确认这个行为吗？",
        "query_rewrite": "确认当前快照是否支持该行为",
        "answer_type": {"code": "negative", "zh": "无答案或证据不足"},
        "references": [],
        "evidence": [],
        "expected_answer": "无法从当前快照确认这个行为；可用源码和文档中没有提供足够证据支持该说法。",
        "answerability": "unanswerable_missing_evidence",
        "difficulty": {
            "axis1_layer": "L1",
            "axis2_retrieval": ["negative_evidence"],
            "axis3_reasoning": ["implicit_domain_knowledge"],
            "claim_sources": {
                "negative_evidence": ["sig:demo:negative"],
                "implicit_domain_knowledge": ["sig:demo:implicit"],
            },
        },
        "answer_rubric": {
            "answer_goal": "Refuse because the snapshot lacks evidence.",
            "required_atoms": [
                {
                    "id": "A1",
                    "role": "conclusion",
                    "statement": "The answer refuses because evidence is missing.",
                    "match_type": "semantic_fact",
                    "evidence_ids": [],
                    "weight": 1.0,
                }
            ],
            "forbidden_atoms": [],
            "citation_policy": {"required": "never"},
        },
    }


def lint_fail_messages(linter, row):
    findings = []
    linter.validate_row(
        copy.deepcopy(row),
        findings,
        ROOT,
        set(),
        schema_version="v1.1",
    )
    return [finding.message for finding in findings if finding.severity == "FAIL"]


class GeneratorLintV11Test(unittest.TestCase):
    def test_v1_1_allows_missing_evidence_refusal(self):
        linter = load_module()

        self.assertEqual(lint_fail_messages(linter, base_row()), [])

    def test_v1_1_rejects_invalid_answerability(self):
        linter = load_module()
        row = base_row()
        row["answerability"] = "bogus"

        self.assertIn("`answerability` is required in v1.1 mode", lint_fail_messages(linter, row))


if __name__ == "__main__":
    unittest.main()
