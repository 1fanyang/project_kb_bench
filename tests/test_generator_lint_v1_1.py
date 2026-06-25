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
            # missing-evidence rows are single-axis by design: axis3 carries
            # only `negative_evidence`, claim_sources for it is intentionally
            # empty since the absence of evidence IS the claim.
            "axis1_layer": "L1",
            "axis2_retrieval": [],
            "axis3_reasoning": ["negative_evidence"],
            "claim_sources": {
                "negative_evidence": [],
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
            "forbidden_atoms": [
                {
                    "id": "F1",
                    "statement": "The answer fabricates a concrete conclusion despite missing evidence.",
                    "match_type": "semantic_contradiction",
                    "severity": "fatal",
                }
            ],
            "citation_policy": {"required": "never"},
        },
    }


def answerable_l1_row():
    """A v1.1-clean answerable L1 row with substantive evidence and a propositional atom."""
    return {
        "_file": "inline.jsonl",
        "_line": 1,
        "case_id": "case-answerable-1",
        "project": "demo",
        "layer": {"code": "L1", "zh": "单源检索"},
        "query": "在快照里这个行为是怎样实现的？",
        "query_rewrite": "确认快照里这个行为的实现路径",
        "answer_type": {"code": "mechanism", "zh": "机制解释"},
        "references": [
            {
                "source_id": "src:demo:foo",
                "path": "src/foo/bar/baz.c",
                "repo_name": "demo",
                "source_type": "code.source",
                "authority": "primary_source",
            }
        ],
        "evidence": [
            {
                "evidence_id": "E1",
                "source_id": "src:demo:foo",
                "path": "src/foo/bar/baz.c",
                "lines": "10-12",
                "role": "trigger_condition",
                "statement": "这些行显示：int dispatch(int req) { if (req == 0) return -EINVAL; }",
            }
        ],
        "expected_answer": "在 req 为 0 时函数会立即返回 -EINVAL，从而短路后续处理。",
        "answerability": "answerable",
        "difficulty": {
            "axis1_layer": "L1",
            "axis2_retrieval": ["long_tail"],
            "axis3_reasoning": ["conditional_behavior"],
            "claim_sources": {
                "long_tail": ["sig:demo:long_tail"],
                "conditional_behavior": ["sig:demo:cond"],
            },
        },
        "answer_rubric": {
            "answer_goal": "Describe the dispatch short-circuit.",
            "required_atoms": [
                {
                    "id": "A1",
                    "role": "conclusion",
                    "statement": "dispatch returns -EINVAL when req is zero.",
                    "match_type": "semantic_yes_no",
                    "evidence_ids": ["E1"],
                    "weight": 2.0,
                }
            ],
            "forbidden_atoms": [],
            "citation_policy": {"required": "always", "required_evidence_ids": ["E1"]},
        },
    }


def lint_findings(linter, row, severities=("FAIL", "WARN")):
    findings = []
    linter.validate_row(
        copy.deepcopy(row),
        findings,
        ROOT,
        set(),
        schema_version="v1.1",
    )
    return [
        (finding.severity, finding.message)
        for finding in findings
        if finding.severity in severities
    ]


def lint_fail_messages(linter, row):
    return [msg for sev, msg in lint_findings(linter, row, severities=("FAIL",))]


def lint_warn_messages(linter, row):
    return [msg for sev, msg in lint_findings(linter, row, severities=("WARN",))]


class GeneratorLintV11Test(unittest.TestCase):
    def test_v1_1_allows_missing_evidence_refusal(self):
        linter = load_module()
        self.assertEqual(lint_fail_messages(linter, base_row()), [])

    def test_v1_1_rejects_invalid_answerability(self):
        linter = load_module()
        row = base_row()
        row["answerability"] = "bogus"
        self.assertIn("`answerability` is required in v1.1 mode", lint_fail_messages(linter, row))

    def test_answerable_l1_row_is_clean(self):
        linter = load_module()
        self.assertEqual(lint_fail_messages(linter, answerable_l1_row()), [])

    def test_forbidden_atoms_required_for_unanswerable_missing_evidence(self):
        linter = load_module()
        row = base_row()
        row["answer_rubric"]["forbidden_atoms"] = []
        msgs = lint_fail_messages(linter, row)
        self.assertTrue(any("forbidden_atoms" in m for m in msgs), msgs)

    def test_forbidden_atoms_required_for_unanswerable_ambiguous(self):
        linter = load_module()
        row = base_row()
        row["answerability"] = "unanswerable_ambiguous"
        row["answer_type"] = {"code": "negative", "zh": "无答案或证据不足"}
        row["answer_rubric"]["forbidden_atoms"] = []
        msgs = lint_fail_messages(linter, row)
        self.assertTrue(any("forbidden_atoms" in m for m in msgs), msgs)

    def test_anchor_token_leak_in_query(self):
        linter = load_module()
        row = answerable_l1_row()
        row["evidence"][0]["path"] = "src/foo/VX_cache_bypass.sv"
        row["query"] = "VX cache bypass 中怎么处理？"
        msgs = lint_fail_messages(linter, row)
        self.assertTrue(any("file_anchor_required" in m or "evidence file" in m for m in msgs), msgs)

    def test_anchor_token_leak_allowed_with_tag(self):
        linter = load_module()
        row = answerable_l1_row()
        row["evidence"][0]["path"] = "src/foo/VX_cache_bypass.sv"
        row["query"] = "VX cache bypass 中怎么处理？"
        row["tags"] = ["file_anchor_required"]
        msgs = lint_fail_messages(linter, row)
        self.assertFalse(any("evidence file" in m for m in msgs), msgs)

    def test_unanswerable_refusal_leak(self):
        linter = load_module()
        row = base_row()
        row["query"] = "这个行为在快照里能确认吗？我没有看到可核验证据。"
        msgs = lint_fail_messages(linter, row)
        self.assertTrue(any("telegraphs" in m for m in msgs), msgs)

    def test_unanswerable_refusal_leak_negative(self):
        linter = load_module()
        row = base_row()
        row["query"] = "这个行为在当前快照里是怎样的？"
        msgs = lint_fail_messages(linter, row)
        self.assertFalse(any("telegraphs" in m for m in msgs), msgs)

    def test_boilerplate_evidence_license(self):
        linter = load_module()
        row = answerable_l1_row()
        row["evidence"][0]["statement"] = (
            "这些行显示：// Unless required by applicable law or agreed to in writing, software"
        )
        msgs = lint_fail_messages(linter, row)
        self.assertTrue(any("boilerplate" in m for m in msgs), msgs)

    def test_boilerplate_evidence_heading_underline(self):
        linter = load_module()
        row = answerable_l1_row()
        row["evidence"][0]["statement"] = "这些行显示：Hardware Manual / ==============="
        msgs = lint_fail_messages(linter, row)
        self.assertTrue(any("boilerplate" in m for m in msgs), msgs)

    def test_pointer_style_atom(self):
        linter = load_module()
        row = answerable_l1_row()
        row["answer_rubric"]["required_atoms"][0]["statement"] = (
            "src/foo/bar/baz.c:10-12 显示：int dispatch(int req) { if (req == 0) return -EINVAL; }"
        )
        msgs = lint_fail_messages(linter, row)
        self.assertTrue(any("pointer" in m for m in msgs), msgs)

    def test_implicit_dk_verbatim_reasoning(self):
        linter = load_module()
        # Build a v1.1 L3-shaped row claiming implicit_domain_knowledge, with a
        # `reasoning` atom that is verbatim from the evidence statement.
        row = answerable_l1_row()
        row["case_id"] = "case-l3-1"
        row["layer"] = {"code": "L3", "zh": "多跳机制"}
        row["evidence"] = [
            {
                "evidence_id": "E1",
                "source_id": "src:demo:a",
                "path": "src/a.c",
                "lines": "1-3",
                "role": "evidence_fact",
                "statement": "这些行显示：module foo (input clk, output q);",
            },
            {
                "evidence_id": "E2",
                "source_id": "src:demo:b",
                "path": "src/b.c",
                "lines": "1-3",
                "role": "evidence_fact",
                "statement": "这些行显示：always @(posedge clk) q <= d;",
            },
        ]
        row["references"].append(
            {
                "source_id": "src:demo:b",
                "path": "src/b.c",
                "repo_name": "demo",
                "source_type": "code.source",
                "authority": "primary_source",
            }
        )
        row["difficulty"] = {
            "axis1_layer": "L3",
            "axis2_retrieval": ["long_tail"],
            "axis3_reasoning": ["implicit_domain_knowledge"],
            "claim_sources": {
                "long_tail": ["sig:demo:lt"],
                "implicit_domain_knowledge": ["sig:demo:idk"],
            },
        }
        row["answer_rubric"]["required_atoms"] = [
            {
                "id": "A1",
                "role": "conclusion",
                "statement": "The module latches q on every rising edge of clk.",
                "match_type": "semantic_fact",
                "evidence_ids": ["E1"],
                "weight": 2.0,
            },
            {
                "id": "A2",
                "role": "reasoning",
                "statement": "always @(posedge clk) q <= d;",
                "match_type": "semantic_fact",
                "evidence_ids": ["E2"],
                "weight": 1.0,
                "depends_on": ["A1"],
            },
        ]
        row["answer_rubric"]["citation_policy"] = {
            "required": "always",
            "required_evidence_ids": ["E1", "E2"],
        }
        msgs = lint_fail_messages(linter, row)
        self.assertTrue(
            any("verbatim" in m for m in msgs),
            f"expected verbatim-reasoning failure; got: {msgs}",
        )

    def test_conditional_behavior_guard_warning(self):
        linter = load_module()
        row = answerable_l1_row()
        # Trigger-condition role present, but the snippet contains no guard token.
        row["evidence"][0]["statement"] = "这些行显示：const char *name = \"demo\";"
        warn_msgs = lint_warn_messages(linter, row)
        self.assertTrue(
            any("guard" in m for m in warn_msgs),
            f"expected guard-token warning; got: {warn_msgs}",
        )

    def test_corpus_filler_cap(self):
        linter = load_module()
        row_template = answerable_l1_row()
        rows = []
        for index in range(4):
            row = copy.deepcopy(row_template)
            row["case_id"] = f"case-filler-{index}"
            row["_line"] = index + 1
            rows.append(row)
        findings = linter.corpus_level_findings(rows)
        msgs = [finding.message for finding in findings if finding.severity == "FAIL"]
        self.assertTrue(any("corpus filler" in m for m in msgs), msgs)

    def test_corpus_query_diversity_warning(self):
        linter = load_module()
        rows = []
        # 60 rows all sharing the same surface form (after Latin/CJK normalization)
        # should trip the diversity-floor warning.
        for index in range(60):
            row = answerable_l1_row()
            row["case_id"] = f"case-div-{index}"
            row["_line"] = index + 1
            row["query"] = "项目X 中的行为是怎样的？"
            rows.append(row)
        findings = linter.corpus_level_findings(rows)
        warn_msgs = [finding.message for finding in findings if finding.severity == "WARN"]
        self.assertTrue(any("diversity" in m for m in warn_msgs), warn_msgs)


if __name__ == "__main__":
    unittest.main()
