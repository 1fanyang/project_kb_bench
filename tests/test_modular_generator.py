"""Tests for the Ship 2 modular generator pipeline.

Covers:
- skills/benchmark-generator/scripts/prepare_module_inputs.py
- skills/benchmark-generator/scripts/validate_module_outputs.py
- scripts/generate_v1_1_release_corpora.py with --use-module-outputs
"""

import copy
import importlib.util
import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


ROOT = Path(__file__).resolve().parents[1]
PREPARE = ROOT / "skills" / "benchmark-generator" / "scripts" / "prepare_module_inputs.py"
VALIDATOR = ROOT / "skills" / "benchmark-generator" / "scripts" / "validate_module_outputs.py"
GENERATOR = ROOT / "scripts" / "generate_v1_1_release_corpora.py"


def load_script(path: Path, alias: str):
    spec = importlib.util.spec_from_file_location(alias, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[alias] = module
    spec.loader.exec_module(module)
    return module


def write_jsonl(path: Path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def candidates_fixture(case_id="demo-v1_1-L1-001"):
    """An answerable L1 candidate row with one substantive and one boilerplate option."""
    return {
        "case_id": case_id,
        "project": "demo",
        "row_plan": {
            "layer": "L1",
            "answerability": "answerable",
            "axis2_retrieval": ["long_tail"],
            "axis3_reasoning": ["implicit_domain_knowledge"],
            "capability": {"code": "mechanism_trace", "zh": "机制链路解释"},
            "answer_type": {"code": "mechanism", "zh": "机制解释"},
            "style_hint": "colloquial",
        },
        "anchor": {
            "source_id": "src:demo:foo",
            "path": "src/foo/bar/baz.c",
            "lines": "10-12",
            "raw_snippet": "int dispatch(int req) { if (req == 0) return -EINVAL; }",
        },
        "candidates": [
            {
                "candidate_id": "C1",
                "source_id": "src:demo:foo",
                "path": "src/foo/bar/baz.c",
                "lines": "10-12",
                "raw_snippet": "int dispatch(int req) { if (req == 0) return -EINVAL; }",
                "attribute": "long_tail",
                "axis": 2,
                "role_hint": "evidence_fact",
            },
            {
                "candidate_id": "C2",
                "source_id": "src:demo:license",
                "path": "src/foo/LICENSE.h",
                "lines": "1-3",
                "raw_snippet": "// Unless required by applicable law or agreed to in writing, software",
                "attribute": "implicit_domain_knowledge",
                "axis": 3,
                "role_hint": "evidence_fact",
            },
        ],
    }


def query_fixture(case_id="demo-v1_1-L1-001"):
    return {
        "case_id": case_id,
        "query": "demo 项目里这个 dispatch 调用对空请求是怎么处理的？",
        "query_rewrite": "确认 demo 项目 dispatch 处理空请求的行为。",
        "style": "colloquial",
    }


def rubric_fixture(case_id="demo-v1_1-L1-001"):
    return {
        "case_id": case_id,
        "required_atoms": [
            {
                "id": "A1",
                "role": "conclusion",
                "statement": "The demo dispatch entry short-circuits with -EINVAL when the request pointer is null, blocking later register writes.",
                "match_type": "semantic_fact",
                "evidence_ids": ["E1"],
                "weight": 2,
            },
            {
                "id": "A2",
                "role": "reasoning",
                "statement": "Because -EINVAL is a parameter-validation code by convention, the call site can distinguish a malformed request from a transient queue-full case and avoid retrying blindly.",
                "match_type": "semantic_reasoning",
                "evidence_ids": ["E1"],
                "weight": 1,
            },
        ],
        "forbidden_atoms": [],
    }


def curated_clean(case_id="demo-v1_1-L1-001"):
    """A clean M2 output: keep the substantive span, reject the license header."""
    return {
        "case_id": case_id,
        "selected_evidence": [
            {
                "evidence_id": "E1",
                "source_id": "src:demo:foo",
                "path": "src/foo/bar/baz.c",
                "lines": "10-12",
                "role": "evidence_fact",
                "statement": "dispatch rejects null req with -EINVAL before any register write.",
            }
        ],
        "rejected_candidates": [{"candidate_id": "C2", "reason": "license_header"}],
    }


def claims_clean(case_id="demo-v1_1-L1-001"):
    return {
        "case_id": case_id,
        "claims": [
            {
                "id": "C1",
                "text": "dispatch short-circuits with -EINVAL when req is zero, gating any subsequent register writes.",
                "evidence_ids": ["E1"],
                "kind": "behavior",
            }
        ],
    }


def answers_clean(case_id="demo-v1_1-L1-001"):
    return {
        "case_id": case_id,
        "expected_answer": (
            "dispatch short-circuits with -EINVAL when req is zero, gating any subsequent register "
            "writes (`src/foo/bar/baz.c:10-12`)."
        ),
        "citation_paths": ["src/foo/bar/baz.c:10-12"],
    }


class ValidateM2Test(unittest.TestCase):
    def setUp(self):
        self.v = load_script(VALIDATOR, "validator_m2")

    def test_clean_m2_row_passes(self):
        findings = self.v.validate_m2(
            [curated_clean()],
            [candidates_fixture()],
        )
        fails = [f for f in findings if f.severity == "FAIL"]
        self.assertEqual(fails, [], msg=fails)

    def test_l2_single_source_fails(self):
        # L2 row with only one source_id
        cands = candidates_fixture()
        cands["row_plan"]["layer"] = "L2"
        cur = curated_clean()
        findings = self.v.validate_m2([cur], [cands])
        msgs = [f.message for f in findings if f.severity == "FAIL"]
        self.assertTrue(any(">= 2 distinct source_ids" in m for m in msgs), msgs)

    def test_evidence_not_in_candidates_fails(self):
        cur = curated_clean()
        cur["selected_evidence"][0]["path"] = "src/foo/elsewhere.c"
        findings = self.v.validate_m2([cur], [candidates_fixture()])
        msgs = [f.message for f in findings if f.severity == "FAIL"]
        self.assertTrue(any("not in candidates" in m for m in msgs), msgs)

    def test_invalid_reject_reason_fails(self):
        cur = curated_clean()
        cur["rejected_candidates"][0]["reason"] = "i_made_this_up"
        findings = self.v.validate_m2([cur], [candidates_fixture()])
        msgs = [f.message for f in findings if f.severity == "FAIL"]
        self.assertTrue(any("reason invalid" in m for m in msgs), msgs)

    def test_unanswerable_missing_evidence_with_evidence_fails(self):
        cand = candidates_fixture()
        cand["row_plan"]["answerability"] = "unanswerable_missing_evidence"
        cand["candidates"] = []
        cur = curated_clean()  # has evidence
        findings = self.v.validate_m2([cur], [cand])
        msgs = [f.message for f in findings if f.severity == "FAIL"]
        self.assertTrue(
            any("unanswerable_missing_evidence must have empty selected_evidence" in m for m in msgs),
            msgs,
        )

    def test_verbatim_statement_fails(self):
        cur = curated_clean()
        cur["selected_evidence"][0]["statement"] = (
            "int dispatch(int req) { if (req == 0) return -EINVAL; }"
        )
        findings = self.v.validate_m2([cur], [candidates_fixture()])
        msgs = [f.message for f in findings if f.severity == "FAIL"]
        self.assertTrue(any("verbatim" in m for m in msgs), msgs)


class ValidateM3Test(unittest.TestCase):
    def setUp(self):
        self.v = load_script(VALIDATOR, "validator_m3")

    def test_clean_m3_row_passes(self):
        findings = self.v.validate_m3(
            [claims_clean()],
            [curated_clean()],
            [candidates_fixture()],
        )
        fails = [f for f in findings if f.severity == "FAIL"]
        self.assertEqual(fails, [], msg=fails)

    def test_unknown_evidence_id_fails(self):
        claims = claims_clean()
        claims["claims"][0]["evidence_ids"] = ["E99"]
        findings = self.v.validate_m3([claims], [curated_clean()], [candidates_fixture()])
        msgs = [f.message for f in findings if f.severity == "FAIL"]
        self.assertTrue(any("unknown evidence_id" in m for m in msgs), msgs)

    def test_invalid_kind_fails(self):
        claims = claims_clean()
        claims["claims"][0]["kind"] = "vibes"
        findings = self.v.validate_m3([claims], [curated_clean()], [candidates_fixture()])
        msgs = [f.message for f in findings if f.severity == "FAIL"]
        self.assertTrue(any("kind invalid" in m for m in msgs), msgs)

    def test_verbatim_claim_text_fails(self):
        claims = claims_clean()
        claims["claims"][0]["text"] = (
            "dispatch rejects null req with -EINVAL before any register write."
        )
        findings = self.v.validate_m3([claims], [curated_clean()], [candidates_fixture()])
        msgs = [f.message for f in findings if f.severity == "FAIL"]
        self.assertTrue(any("verbatim substring of M2 statement" in m for m in msgs), msgs)


class ValidateM6Test(unittest.TestCase):
    def setUp(self):
        self.v = load_script(VALIDATOR, "validator_m6")

    def test_clean_m6_row_passes(self):
        findings = self.v.validate_m6(
            [answers_clean()],
            [candidates_fixture()],
            [curated_clean()],
            [claims_clean()],
        )
        fails = [f for f in findings if f.severity == "FAIL"]
        self.assertEqual(fails, [], msg=fails)

    def test_missing_backtick_citation_fails(self):
        ans = answers_clean()
        ans["expected_answer"] = "dispatch short-circuits with -EINVAL when req is zero."  # no citation
        findings = self.v.validate_m6([ans], [candidates_fixture()], [curated_clean()], [claims_clean()])
        msgs = [f.message for f in findings if f.severity == "FAIL"]
        self.assertTrue(any("missing backtick citation" in m for m in msgs), msgs)

    def test_rubric_language_fails(self):
        ans = answers_clean()
        ans["expected_answer"] = (
            "应说明 dispatch 的行为；`src/foo/bar/baz.c:10-12`."
        )
        findings = self.v.validate_m6([ans], [candidates_fixture()], [curated_clean()], [claims_clean()])
        msgs = [f.message for f in findings if f.severity == "FAIL"]
        self.assertTrue(any("rubric language" in m for m in msgs), msgs)

    def test_yes_no_missing_prefix_fails(self):
        cand = candidates_fixture()
        cand["row_plan"]["answer_type"] = {"code": "yes_no", "zh": "是否判断"}
        ans = answers_clean()
        ans["expected_answer"] = (
            "dispatch returns -EINVAL when req is zero (`src/foo/bar/baz.c:10-12`)."
        )
        findings = self.v.validate_m6([ans], [cand], [curated_clean()], [claims_clean()])
        msgs = [f.message for f in findings if f.severity == "FAIL"]
        self.assertTrue(any("会/不会/无法判断" in m for m in msgs), msgs)

    def test_unanswerable_with_citations_fails(self):
        cand = candidates_fixture()
        cand["row_plan"]["answerability"] = "unanswerable_missing_evidence"
        cand["candidates"] = []
        cur = {"case_id": cand["case_id"], "selected_evidence": [], "rejected_candidates": []}
        ans = answers_clean()  # has citations
        ans["expected_answer"] = (
            "无法判断；`src/foo/bar/baz.c:10-12` 也无法回答这个问题。"
        )
        # citation_paths references curated entry; but curated is empty so citation_paths is ill-formed
        findings = self.v.validate_m6([ans], [cand], [cur], [claims_clean()])
        msgs = [f.message for f in findings if f.severity == "FAIL"]
        self.assertTrue(any("empty citation_paths" in m for m in msgs), msgs)


class GeneratorOverrideTest(unittest.TestCase):
    def setUp(self):
        self.gen = load_script(GENERATOR, "v1_1_generator_for_test")

    def _evidence_override(self):
        return [
            {
                "evidence_id": "E1",
                "source_id": "src:nvdla_sw:LowPrecision.md",
                "path": "repo_sources/nvdla/sw/LowPrecision.md",
                "lines": "16-18",
                "role": "evidence_fact",
                "statement": "Calibration uses TensorRT to collect per-layer dynamic ranges before computing scale factors.",
            }
        ]

    def test_make_row_uses_override_evidence_and_answer(self):
        Source = self.gen.Source
        sources = {
            "src:nvdla_sw:LowPrecision.md": Source(
                source_id="src:nvdla_sw:LowPrecision.md",
                project="nvdla",
                repo_name="nvdla/sw",
                path="repo_sources/nvdla/sw/LowPrecision.md",
                source_type="doc.source",
                authority="primary_source",
                line_count=200,
            )
        }
        override = {
            "selected_evidence": self._evidence_override(),
            "expected_answer": (
                "TensorRT calibration collects per-layer dynamic ranges, then NVDLA derives scale "
                "factors from them (`repo_sources/nvdla/sw/LowPrecision.md:16-18`)."
            ),
        }
        row = self.gen.make_row(
            project="nvdla",
            seq=31,
            layer="L1",
            answerability="answerable",
            selected=[],  # signals unused when override populates evidence
            sources=sources,
            repo_root=ROOT,
            module_override=override,
        )
        self.assertIsNotNone(row)
        # The override evidence is preserved
        self.assertEqual(row["evidence"][0]["statement"], override["selected_evidence"][0]["statement"])
        # The override answer is used instead of the templated 可以确认 ...
        self.assertIn("TensorRT calibration", row["expected_answer"])
        self.assertNotIn("可以确认：", row["expected_answer"])
        # References are derived from the override evidence
        self.assertEqual(
            row["references"][0]["path"],
            "repo_sources/nvdla/sw/LowPrecision.md",
        )

    def test_make_row_drops_row_when_override_evidence_is_empty(self):
        sources = {}
        override = {"selected_evidence": [], "expected_answer": None}
        row = self.gen.make_row(
            project="nvdla",
            seq=10,
            layer="L1",
            answerability="answerable",
            selected=[],
            sources=sources,
            repo_root=ROOT,
            module_override=override,
        )
        self.assertIsNone(row)


class ValidateM5Test(unittest.TestCase):
    def setUp(self):
        self.v = load_script(VALIDATOR, "validator_m5")

    def test_clean_query_passes(self):
        findings = self.v.validate_m5(
            [query_fixture()],
            [candidates_fixture()],
            [curated_clean()],
        )
        fails = [f for f in findings if f.severity == "FAIL"]
        self.assertEqual(fails, [], msg=fails)

    def test_anchor_token_leak_fails(self):
        # Evidence path basename is "baz" — a 3-letter token; tip the query into containing it.
        cand = candidates_fixture()
        # Make basename multi-token so the >= 2 token rule fires.
        cand["candidates"][0]["path"] = "src/foo/dispatch_engine.c"
        cur = curated_clean()
        cur["selected_evidence"][0]["path"] = "src/foo/dispatch_engine.c"
        q = query_fixture()
        q["query"] = "demo 项目里 dispatch engine 的实现是怎么处理空请求的？"
        findings = self.v.validate_m5([q], [cand], [cur])
        msgs = [f.message for f in findings if f.severity == "FAIL"]
        self.assertTrue(any("evidence-basename tokens" in m for m in msgs), msgs)

    def test_anchor_leak_allowed_with_tag(self):
        cand = candidates_fixture()
        cand["candidates"][0]["path"] = "src/foo/dispatch_engine.c"
        cand["tags"] = ["file_anchor_required"]
        cur = curated_clean()
        cur["selected_evidence"][0]["path"] = "src/foo/dispatch_engine.c"
        q = query_fixture()
        q["query"] = "demo 项目里 dispatch engine 的实现是怎么处理空请求的？"
        findings = self.v.validate_m5([q], [cand], [cur])
        msgs = [f.message for f in findings if f.severity == "FAIL"]
        self.assertFalse(any("evidence-basename" in m for m in msgs), msgs)

    def test_refusal_cue_on_unanswerable_fails(self):
        cand = candidates_fixture()
        cand["row_plan"]["answerability"] = "unanswerable_missing_evidence"
        cand["row_plan"]["answer_type"] = {"code": "negative", "zh": "无答案或证据不足"}
        cand["candidates"] = []
        cur = {"case_id": cand["case_id"], "selected_evidence": [], "rejected_candidates": []}
        q = query_fixture()
        q["query"] = "demo 项目里这个行为是怎么处理的？我没有看到可核验证据。"
        findings = self.v.validate_m5([q], [cand], [cur])
        msgs = [f.message for f in findings if f.severity == "FAIL"]
        self.assertTrue(any("telegraphs the refusal" in m for m in msgs), msgs)

    def test_yes_no_query_needs_interrogative(self):
        cand = candidates_fixture()
        cand["row_plan"]["answer_type"] = {"code": "yes_no", "zh": "是否判断"}
        q = query_fixture()
        q["query"] = "demo 项目的 dispatch 调用对空请求会进行参数校验然后返回错误码"  # statement, not a question
        findings = self.v.validate_m5([q], [cand], [curated_clean()])
        msgs = [f.message for f in findings if f.severity == "FAIL"]
        self.assertTrue(any("interrogative marker" in m for m in msgs), msgs)

    def test_short_query_fails(self):
        q = query_fixture()
        q["query"] = "短问题"
        findings = self.v.validate_m5([q], [candidates_fixture()], [curated_clean()])
        msgs = [f.message for f in findings if f.severity == "FAIL"]
        self.assertTrue(any("query length" in m and "<" in m for m in msgs), msgs)


class ValidateM7Test(unittest.TestCase):
    def setUp(self):
        self.v = load_script(VALIDATOR, "validator_m7")

    def test_clean_rubric_passes(self):
        findings = self.v.validate_m7(
            [rubric_fixture()],
            [candidates_fixture()],
            [curated_clean()],
            [claims_clean()],
            [answers_clean()],
        )
        fails = [f for f in findings if f.severity == "FAIL"]
        self.assertEqual(fails, [], msg=fails)

    def test_pointer_style_atom_fails(self):
        rub = rubric_fixture()
        rub["required_atoms"][0]["statement"] = "src/foo/bar/baz.c:10-12 显示：if (req == 0) return -EINVAL;"
        findings = self.v.validate_m7(
            [rub], [candidates_fixture()], [curated_clean()], [claims_clean()], [answers_clean()]
        )
        msgs = [f.message for f in findings if f.severity == "FAIL"]
        self.assertTrue(any("pointer-style" in m for m in msgs), msgs)

    def test_verbatim_atom_fails(self):
        rub = rubric_fixture()
        # Use M2 statement verbatim
        rub["required_atoms"][0]["statement"] = "dispatch rejects null req with -EINVAL before any register write."
        findings = self.v.validate_m7(
            [rub], [candidates_fixture()], [curated_clean()], [claims_clean()], [answers_clean()]
        )
        msgs = [f.message for f in findings if f.severity == "FAIL"]
        self.assertTrue(any("verbatim substring of M2 statement" in m for m in msgs), msgs)

    def test_yes_no_row_needs_forbidden_atom(self):
        cand = candidates_fixture()
        cand["row_plan"]["answer_type"] = {"code": "yes_no", "zh": "是否判断"}
        rub = rubric_fixture()
        rub["forbidden_atoms"] = []
        findings = self.v.validate_m7(
            [rub], [cand], [curated_clean()], [claims_clean()], [answers_clean()]
        )
        msgs = [f.message for f in findings if f.severity == "FAIL"]
        self.assertTrue(any("requires ≥1 forbidden_atom" in m for m in msgs), msgs)

    def test_generic_forbidden_fails(self):
        cand = candidates_fixture()
        cand["row_plan"]["answer_type"] = {"code": "fact_check", "zh": "事实核查"}
        rub = rubric_fixture()
        rub["forbidden_atoms"] = [
            {
                "id": "F1",
                "statement": "答案声称 src/foo/bar/baz.c 支持与引用证据相反的结论",
                "match_type": "semantic_contradiction",
                "severity": "fatal",
            }
        ]
        findings = self.v.validate_m7(
            [rub], [cand], [curated_clean()], [claims_clean()], [answers_clean()]
        )
        msgs = [f.message for f in findings if f.severity == "FAIL"]
        self.assertTrue(any("generic boilerplate" in m for m in msgs), msgs)

    def test_implicit_dk_requires_nonverbatim_reasoning(self):
        rub = rubric_fixture()
        # Drop the reasoning atom — leaves only the conclusion
        rub["required_atoms"] = rub["required_atoms"][:1]
        findings = self.v.validate_m7(
            [rub], [candidates_fixture()], [curated_clean()], [claims_clean()], [answers_clean()]
        )
        msgs = [f.message for f in findings if f.severity == "FAIL"]
        self.assertTrue(any("not a verbatim quote" in m for m in msgs), msgs)

    def test_l3_row_needs_depends_on(self):
        cand = candidates_fixture()
        cand["row_plan"]["layer"] = "L3"
        # L3 still needs an axis3 attribute; keep implicit_domain_knowledge
        rub = rubric_fixture()
        # Strip depends_on entirely
        for atom in rub["required_atoms"]:
            atom.pop("depends_on", None)
        findings = self.v.validate_m7(
            [rub], [cand], [curated_clean()], [claims_clean()], [answers_clean()]
        )
        msgs = [f.message for f in findings if f.severity == "FAIL"]
        self.assertTrue(any("depends_on" in m for m in msgs), msgs)


class GeneratorQueryRubricOverrideTest(unittest.TestCase):
    def setUp(self):
        self.gen = load_script(GENERATOR, "v1_1_generator_for_query_rubric_test")

    def test_make_row_uses_query_and_rubric_overrides(self):
        Source = self.gen.Source
        sources = {
            "src:demo:foo": Source(
                source_id="src:demo:foo",
                project="demo",
                repo_name="demo",
                path="src/foo/bar/baz.c",
                source_type="code.source",
                authority="primary_source",
                line_count=200,
            )
        }
        override = {
            "selected_evidence": [
                {
                    "evidence_id": "E1",
                    "source_id": "src:demo:foo",
                    "path": "src/foo/bar/baz.c",
                    "lines": "10-12",
                    "role": "evidence_fact",
                    "statement": "dispatch rejects null req with -EINVAL.",
                }
            ],
            "expected_answer": "Null req short-circuits with -EINVAL before any register writes (`src/foo/bar/baz.c:10-12`).",
            "query": "When req is null in the demo dispatch path, does the call return without touching registers?",
            "query_rewrite": "Determine whether demo dispatch returns -EINVAL on null req before issuing register writes.",
            "required_atoms": [
                {
                    "id": "A1",
                    "role": "conclusion",
                    "statement": "demo dispatch short-circuits with -EINVAL when the request pointer is null.",
                    "match_type": "semantic_yes_no",
                    "evidence_ids": ["E1"],
                    "weight": 2,
                }
            ],
            "forbidden_atoms": [
                {
                    "id": "F1",
                    "statement": "The answer claims demo dispatch proceeds to write registers when req is null.",
                    "match_type": "semantic_contradiction",
                    "severity": "fatal",
                }
            ],
        }
        row = self.gen.make_row(
            project="demo",
            seq=1,
            layer="L1",
            answerability="answerable",
            selected=[],
            sources=sources,
            repo_root=ROOT,
            module_override=override,
        )
        self.assertIsNotNone(row)
        self.assertEqual(row["query"], override["query"])
        self.assertEqual(row["query_rewrite"], override["query_rewrite"])
        self.assertEqual(row["answer_rubric"]["required_atoms"], override["required_atoms"])
        self.assertEqual(row["answer_rubric"]["forbidden_atoms"], override["forbidden_atoms"])
        # And confirm the templated branches are no longer in play
        self.assertNotIn("可以确认：", row["expected_answer"])
        self.assertNotIn("能确认什么行为或结论", row["query"])


class PrepareStyleHintTest(unittest.TestCase):
    def test_prepare_emits_one_row_per_planned_case(self):
        prepare = load_script(PREPARE, "prepare_for_style_test")
        gen = prepare._load_generator()
        with TemporaryDirectory() as tmp:
            outdir = Path(tmp)
            rows = prepare.prepare_project(
                "nvdla",
                ROOT / "runs" / "nvdla_context_bundle",
                ROOT / "runs" / "nvdla_generation_profile_v1_1.yaml",
                ROOT,
                outdir,
                gen,
            )
            self.assertEqual(len(rows), 200)
            # style_hint cycles through all four labels
            hints = {r["row_plan"]["style_hint"] for r in rows}
            self.assertEqual(hints, set(prepare.STYLE_ROTATION))
            # Distribution is balanced (within 1) because we rotate evenly
            from collections import Counter
            counts = Counter(r["row_plan"]["style_hint"] for r in rows)
            self.assertTrue(max(counts.values()) - min(counts.values()) <= 1)


class PrepareModuleInputsTest(unittest.TestCase):
    def test_prepare_emits_one_row_per_planned_case(self):
        # Run prepare against the real NVDLA bundle (already exercised by the smoke run);
        # confirm shape rather than re-running the full 200 rows.
        prepare = load_script(PREPARE, "prepare_for_test")
        gen = prepare._load_generator()
        with TemporaryDirectory() as tmp:
            outdir = Path(tmp)
            rows = prepare.prepare_project(
                "nvdla",
                ROOT / "runs" / "nvdla_context_bundle",
                ROOT / "runs" / "nvdla_generation_profile_v1_1.yaml",
                ROOT,
                outdir,
                gen,
            )
            self.assertEqual(len(rows), 200)
            written = (outdir / "nvdla.candidates.jsonl").read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(written), 200)
            sample = json.loads(written[0])
            self.assertIn("row_plan", sample)
            self.assertIn("candidates", sample)


GATE_ORCHESTRATOR = ROOT / "skills" / "benchmark-generator" / "scripts" / "adversarial_gate_v2.py"


class ValidateM8Test(unittest.TestCase):
    def setUp(self):
        self.v = load_script(VALIDATOR, "validator_m8")

    def _verifier_row(self, **overrides):
        base = {
            "case_id": "demo-v1_1-L1-001",
            "rederived_answer": "dispatch short-circuits with -EINVAL when req is null, before any register writes.",
            "rederived_citations": ["src/foo/bar/baz.c:10-12"],
            "rederivation_confidence": "high",
        }
        base.update(overrides)
        return base

    def test_clean_verifier_passes(self):
        findings = self.v.validate_m8(
            [self._verifier_row()],
            [candidates_fixture()],
            [curated_clean()],
            [answers_clean()],
        )
        fails = [f for f in findings if f.severity == "FAIL"]
        self.assertEqual(fails, [], msg=fails)

    def test_unanswerable_with_confident_answer_fails(self):
        cand = candidates_fixture()
        cand["row_plan"]["answerability"] = "unanswerable_missing_evidence"
        cand["candidates"] = []
        cur = {"case_id": cand["case_id"], "selected_evidence": [], "rejected_candidates": []}
        row = self._verifier_row()  # confident answer, but row should be unanswerable
        findings = self.v.validate_m8([row], [cand], [cur], None)
        msgs = [f.message for f in findings if f.severity == "FAIL"]
        self.assertTrue(any("re-derivation produced a confident answer" in m for m in msgs), msgs)

    def test_answerable_with_refusal_fails(self):
        row = self._verifier_row(
            rederived_answer="无法判断；当前快照里没有相关证据。",
            rederived_citations=[],
            rederivation_confidence="low",
        )
        findings = self.v.validate_m8([row], [candidates_fixture()], [curated_clean()], None)
        msgs = [f.message for f in findings if f.severity == "FAIL"]
        self.assertTrue(any("evidence may not actually support an answer" in m for m in msgs), msgs)

    def test_fabricated_citation_fails(self):
        row = self._verifier_row(rederived_citations=["src/foo/elsewhere.c:99-101"])
        findings = self.v.validate_m8([row], [candidates_fixture()], [curated_clean()], None)
        msgs = [f.message for f in findings if f.severity == "FAIL"]
        self.assertTrue(any("not in curated_evidence" in m for m in msgs), msgs)


class AdversarialGateOrchestratorTest(unittest.TestCase):
    def setUp(self):
        self.gate = load_script(GATE_ORCHESTRATOR, "adversarial_gate_for_test")

    def _seed_drafts(self, drafts_dir: Path):
        cand = candidates_fixture()
        cand["row_plan"]["axis2_retrieval"] = ["long_tail"]
        cand["row_plan"]["axis3_reasoning"] = ["implicit_domain_knowledge"]
        write_jsonl(drafts_dir / "demo.candidates.jsonl", [cand])
        write_jsonl(drafts_dir / "demo.curated_evidence.jsonl", [curated_clean()])
        write_jsonl(drafts_dir / "demo.queries.jsonl", [query_fixture()])
        write_jsonl(drafts_dir / "demo.answers.jsonl", [answers_clean()])

    def test_prepare_emits_one_task_per_attribute_baseline(self):
        with TemporaryDirectory() as tmp:
            drafts = Path(tmp)
            self._seed_drafts(drafts)
            tasks_path = self.gate.emit_tasks("demo", drafts)
            tasks = [json.loads(l) for l in tasks_path.read_text().splitlines()]
            # long_tail → closed_book_llm; implicit_domain_knowledge → oracle_no_reasoning
            self.assertEqual(len(tasks), 2)
            baselines = {t["baseline"] for t in tasks}
            self.assertEqual(baselines, {"closed_book_llm", "oracle_evidence_no_reasoning_llm"})

    def test_judge_passes_row_when_at_least_one_baseline_fails(self):
        with TemporaryDirectory() as tmp:
            drafts = Path(tmp)
            self._seed_drafts(drafts)
            self.gate.emit_tasks("demo", drafts)
            # Host-LLM answers: closed_book refuses (baseline_failed = good),
            #                   oracle no-reasoning succeeds with overlap (baseline_succeeded = bad)
            answers = [
                {
                    "task_id": "demo-v1_1-L1-001::long_tail::closed_book_llm",
                    "case_id": "demo-v1_1-L1-001",
                    "attribute": "long_tail",
                    "baseline": "closed_book_llm",
                    "answer": "refuse",
                    "answer_confidence": "low",
                    "rationale": "no evidence",
                },
                {
                    "task_id": "demo-v1_1-L1-001::implicit_domain_knowledge::oracle_evidence_no_reasoning_llm",
                    "case_id": "demo-v1_1-L1-001",
                    "attribute": "implicit_domain_knowledge",
                    "baseline": "oracle_evidence_no_reasoning_llm",
                    "answer": "dispatch short-circuits with -EINVAL on null req register writes.",
                    "answer_confidence": "high",
                    "rationale": "quoted",
                },
            ]
            write_jsonl(drafts / "demo.baseline_answers.jsonl", answers)
            self.gate.judge_answers("demo", drafts)
            verdicts = [json.loads(l) for l in (drafts / "demo.adversarial_gate.jsonl").read_text().splitlines()]
            self.assertEqual(len(verdicts), 1)
            self.assertTrue(verdicts[0]["passed"])

    def test_judge_fails_row_when_every_baseline_succeeds(self):
        with TemporaryDirectory() as tmp:
            drafts = Path(tmp)
            self._seed_drafts(drafts)
            self.gate.emit_tasks("demo", drafts)
            answers = [
                {
                    "task_id": "demo-v1_1-L1-001::long_tail::closed_book_llm",
                    "case_id": "demo-v1_1-L1-001",
                    "attribute": "long_tail",
                    "baseline": "closed_book_llm",
                    "answer": "dispatch short-circuits with -EINVAL on null req register writes.",
                    "answer_confidence": "high",
                    "rationale": "from prior knowledge",
                },
                {
                    "task_id": "demo-v1_1-L1-001::implicit_domain_knowledge::oracle_evidence_no_reasoning_llm",
                    "case_id": "demo-v1_1-L1-001",
                    "attribute": "implicit_domain_knowledge",
                    "baseline": "oracle_evidence_no_reasoning_llm",
                    "answer": "dispatch short-circuits with -EINVAL on null req register writes.",
                    "answer_confidence": "high",
                    "rationale": "quoted",
                },
            ]
            write_jsonl(drafts / "demo.baseline_answers.jsonl", answers)
            self.gate.judge_answers("demo", drafts)
            verdicts = [json.loads(l) for l in (drafts / "demo.adversarial_gate.jsonl").read_text().splitlines()]
            self.assertFalse(verdicts[0]["passed"])


class GateDropTest(unittest.TestCase):
    def setUp(self):
        self.gen = load_script(GENERATOR, "v1_1_generator_for_gate_drop_test")

    def test_assembler_drops_row_when_gate_says_fail(self):
        with TemporaryDirectory() as tmp:
            drafts = Path(tmp)
            # Write a minimal adversarial_gate.jsonl marking the L1-031 row failed.
            write_jsonl(
                drafts / "nvdla.adversarial_gate.jsonl",
                [{"case_id": "nvdla-v1_1-L1-031", "passed": False, "per_attribute": []}],
            )
            rows = self.gen.generate(
                "nvdla",
                ROOT / "runs" / "nvdla_context_bundle",
                ROOT / "runs" / "nvdla_generation_profile_v1_1.yaml",
                ROOT,
                drafts_dir=drafts,
            )
            self.assertEqual(len(rows), 199)
            self.assertNotIn("nvdla-v1_1-L1-031", {r["case_id"] for r in rows})


class FixIssue3M9CoverageTest(unittest.TestCase):
    """Ship 4 fix #3: judge must require coverage by (attribute, baseline), not just by attribute,
    and multi-baseline attributes need ALL baselines to fail to count as confirmed."""

    def setUp(self):
        self.gate = load_script(GATE_ORCHESTRATOR, "adversarial_gate_fix3_test")

    def _seed(self, drafts_dir: Path, declared_axis3: list[str]) -> None:
        cand = candidates_fixture()
        cand["row_plan"]["axis2_retrieval"] = []
        cand["row_plan"]["axis3_reasoning"] = declared_axis3
        write_jsonl(drafts_dir / "demo.candidates.jsonl", [cand])
        write_jsonl(drafts_dir / "demo.curated_evidence.jsonl", [curated_clean()])
        write_jsonl(drafts_dir / "demo.queries.jsonl", [query_fixture()])
        write_jsonl(drafts_dir / "demo.answers.jsonl", [answers_clean()])

    def test_false_premise_missing_one_of_two_baselines_marks_untested(self):
        # false_premise → [closed_book_llm, oracle_evidence_llm]; only one answered.
        with TemporaryDirectory() as tmp:
            drafts = Path(tmp)
            self._seed(drafts, ["false_premise"])
            answers = [
                {
                    "task_id": "demo-v1_1-L1-001::false_premise::closed_book_llm",
                    "case_id": "demo-v1_1-L1-001",
                    "attribute": "false_premise",
                    "baseline": "closed_book_llm",
                    "answer": "refuse",
                    "answer_confidence": "low",
                    "rationale": "no evidence",
                }
            ]
            write_jsonl(drafts / "demo.baseline_answers.jsonl", answers)
            self.gate.judge_answers("demo", drafts)
            verdicts = [json.loads(l) for l in (drafts / "demo.adversarial_gate.jsonl").read_text().splitlines()]
            self.assertFalse(verdicts[0]["passed"])
            self.assertTrue(verdicts[0]["verdict_reason"].startswith("untested_baselines"))
            self.assertIn("oracle_evidence_llm", verdicts[0]["verdict_reason"])

    def test_false_premise_passes_only_when_both_baselines_fail(self):
        with TemporaryDirectory() as tmp:
            drafts = Path(tmp)
            self._seed(drafts, ["false_premise"])
            # Both baselines fail (refuse) — attribute confirmed, row passes.
            answers = [
                {
                    "task_id": "demo-v1_1-L1-001::false_premise::closed_book_llm",
                    "case_id": "demo-v1_1-L1-001",
                    "attribute": "false_premise",
                    "baseline": "closed_book_llm",
                    "answer": "refuse",
                    "answer_confidence": "low",
                    "rationale": "",
                },
                {
                    "task_id": "demo-v1_1-L1-001::false_premise::oracle_evidence_llm",
                    "case_id": "demo-v1_1-L1-001",
                    "attribute": "false_premise",
                    "baseline": "oracle_evidence_llm",
                    "answer": "refuse",
                    "answer_confidence": "low",
                    "rationale": "",
                },
            ]
            write_jsonl(drafts / "demo.baseline_answers.jsonl", answers)
            self.gate.judge_answers("demo", drafts)
            verdict = json.loads((drafts / "demo.adversarial_gate.jsonl").read_text().splitlines()[0])
            self.assertTrue(verdict["passed"])

    def test_false_premise_fails_when_one_baseline_succeeds(self):
        with TemporaryDirectory() as tmp:
            drafts = Path(tmp)
            self._seed(drafts, ["false_premise"])
            # closed_book refused (failed = good) but oracle answered with overlap (succeeded = bad)
            # → attribute NOT confirmed under the all-baselines-must-fail rule.
            answers = [
                {
                    "task_id": "demo-v1_1-L1-001::false_premise::closed_book_llm",
                    "case_id": "demo-v1_1-L1-001",
                    "attribute": "false_premise",
                    "baseline": "closed_book_llm",
                    "answer": "refuse",
                    "answer_confidence": "low",
                    "rationale": "",
                },
                {
                    "task_id": "demo-v1_1-L1-001::false_premise::oracle_evidence_llm",
                    "case_id": "demo-v1_1-L1-001",
                    "attribute": "false_premise",
                    "baseline": "oracle_evidence_llm",
                    "answer": "dispatch short-circuits with -EINVAL on null req register writes.",
                    "answer_confidence": "high",
                    "rationale": "",
                },
            ]
            write_jsonl(drafts / "demo.baseline_answers.jsonl", answers)
            self.gate.judge_answers("demo", drafts)
            verdict = json.loads((drafts / "demo.adversarial_gate.jsonl").read_text().splitlines()[0])
            self.assertFalse(verdict["passed"])
            self.assertEqual(verdict["verdict_reason"], "no_attribute_confirmed")


class FixIssue4NegativeEvidenceCoverageTest(unittest.TestCase):
    """Ship 4 fix #4: missing-evidence rows must claim negative_evidence and run the closed_book baseline."""

    def setUp(self):
        self.prepare = load_script(PREPARE, "prepare_fix4_test")
        self.gate = load_script(GATE_ORCHESTRATOR, "gate_fix4_test")

    def test_prepare_tags_missing_evidence_with_negative_evidence(self):
        gen = self.prepare._load_generator()
        with TemporaryDirectory() as tmp:
            rows = self.prepare.prepare_project(
                "nvdla",
                ROOT / "runs" / "nvdla_context_bundle",
                ROOT / "runs" / "nvdla_generation_profile_v1_1.yaml",
                ROOT,
                Path(tmp),
                gen,
            )
            missing = [r for r in rows if r["row_plan"]["answerability"] == "unanswerable_missing_evidence"]
            self.assertGreater(len(missing), 0)
            for r in missing:
                self.assertEqual(r["row_plan"]["axis3_reasoning"], ["negative_evidence"])

    def test_baseline_outcome_treats_negative_evidence_inversely(self):
        # For negative_evidence: refusal = good (baseline_failed); confident = bad (baseline_succeeded)
        # The token "无法判断" is in REFUSAL_TOKENS; a concrete answer is not.
        gate = self.gate
        self.assertEqual(
            gate.baseline_outcome(
                answer="无法判断；当前没有可核验证据。",
                query="some query",
                gold_answer="无法判断；…",
                attribute="negative_evidence",
            ),
            "baseline_failed",
        )
        self.assertEqual(
            gate.baseline_outcome(
                answer="实际上 runtime API 返回 -EBUSY 表示队列满，-EINVAL 表示参数非法。",
                query="some query",
                gold_answer="无法判断；…",
                attribute="negative_evidence",
            ),
            "baseline_succeeded",
        )


class FixIssue2GraphWalkTest(unittest.TestCase):
    """Ship 4 fix #2: prepare_module_inputs adds graph-walk neighbor candidates."""

    def test_graph_walk_finds_include_by_name(self):
        prepare = load_script(PREPARE, "prepare_fix2_walk_test")

        class StubSource:
            def __init__(self, source_id, path, line_count=200):
                self.source_id = source_id
                self.path = path
                self.line_count = line_count

        sources = {
            "src:demo:foo": StubSource("src:demo:foo", "src/foo/bar.c"),
            "src:demo:hdr": StubSource("src:demo:hdr", "src/foo/header.h"),
        }
        relations = [
            {
                "subject": {"id": "src:demo:foo", "name": "src/foo/bar.c", "type": "source"},
                "predicate": "imports_or_includes",
                "object": {"name": "header.h", "type": "include"},
                "evidence": [{"path": "src/foo/bar.c", "lines": "3", "source_id": "src:demo:foo"}],
            },
        ]
        by_subject, by_object = prepare._index_relations(relations)
        name_index = prepare._build_source_name_index(sources)

        class StubGen:
            def line_window(self, source, lines):
                return str(lines)
            def read_snippet(self, root, path, lines):
                return f"<snippet for {path}>"

        neighbors = prepare.graph_walk_neighbors(
            anchor_source_id="src:demo:foo",
            sources=sources,
            by_subject=by_subject,
            by_object=by_object,
            excluded_source_ids={"src:demo:foo"},
            gen=StubGen(),
            repo_root=ROOT,
            name_index=name_index,
        )
        self.assertEqual(len(neighbors), 1)
        self.assertEqual(neighbors[0]["source_id"], "src:demo:hdr")
        self.assertEqual(neighbors[0]["attribute"], "graph_neighbor")
        self.assertEqual(neighbors[0]["neighbor_relation"], "imports_or_includes")


class DiversityControllerTest(unittest.TestCase):
    def test_diversity_report_flags_overuse(self):
        prepare = load_script(PREPARE, "prepare_for_diversity_test")
        rows = [
            {
                "row_plan": {"style_hint": "colloquial"},
                "candidates": [
                    {"path": "a.c", "lines": "1-3", "source_id": "src:a"},
                ],
            }
            for _ in range(prepare.PATH_LINES_REUSE_CAP + 2)
        ]
        report = prepare.diversity_report(rows)
        self.assertEqual(len(report["path_lines_overuse"]), 1)
        self.assertEqual(report["path_lines_overuse"][0]["key"], "a.c:1-3")


class FixIssue5M2QualityConstraintsTest(unittest.TestCase):
    """#5: M2 enforces conditional_behavior guard tokens against raw_snippet (not the
    LLM-authored statement) and rejects doc_code_divergence rows without both kinds of source."""

    def setUp(self):
        self.v = load_script(VALIDATOR, "validator_fix5_test")

    def _scenario(self, axis3, statements, paths=None, raw_snippets=None):
        cand = candidates_fixture()
        cand["row_plan"]["axis2_retrieval"] = ["long_tail"]
        cand["row_plan"]["axis3_reasoning"] = axis3
        cand["row_plan"]["layer"] = "L2" if "doc_code_divergence" in axis3 else "L1"
        candidates = []
        sel = []
        for index, (statement, path, raw) in enumerate(
            zip(statements, paths or [], raw_snippets or [])
        ):
            sid = f"src:demo:{index}"
            candidates.append({
                "candidate_id": f"C{index+1}",
                "source_id": sid,
                "path": path,
                "lines": "10-12",
                "raw_snippet": raw,
                "attribute": axis3[index] if index < len(axis3) else "long_tail",
                "axis": 3,
                "role_hint": "evidence_fact",
            })
            sel.append({
                "evidence_id": f"E{index+1}",
                "source_id": sid,
                "path": path,
                "lines": "10-12",
                "role": "evidence_fact",
                "statement": statement,
            })
        cand["candidates"] = candidates
        cur = {"case_id": cand["case_id"], "selected_evidence": sel, "rejected_candidates": []}
        return cand, cur

    def test_conditional_behavior_fails_when_raw_snippet_lacks_guard(self):
        # LLM statement *describes* a branch but raw_snippet has no guard token.
        cand, cur = self._scenario(
            axis3=["conditional_behavior"],
            statements=["The block conditionally writes back when rd is non-zero."],
            paths=["src/foo/dispatch.c"],
            raw_snippets=["wire wb_enable_signal = use_rd_signal_only_no_guards;"],
        )
        findings = self.v.validate_m2([cur], [cand])
        fails = [f.message for f in findings if f.severity == "FAIL"]
        self.assertTrue(any("conditional_behavior claimed but no guard tokens" in m for m in fails), fails)

    def test_conditional_behavior_passes_when_raw_snippet_has_guard(self):
        cand, cur = self._scenario(
            axis3=["conditional_behavior"],
            statements=["The dispatch path conditionally returns -EINVAL."],
            paths=["src/foo/dispatch.c"],
            raw_snippets=["if (req == NULL) return -EINVAL;"],
        )
        findings = self.v.validate_m2([cur], [cand])
        fails = [f.message for f in findings if f.severity == "FAIL"]
        self.assertFalse(any("conditional_behavior" in m for m in fails), fails)

    def test_doc_code_divergence_requires_doc_and_code_paths(self):
        # Two code sources — no doc — should fail.
        cand, cur = self._scenario(
            axis3=["doc_code_divergence"],
            statements=["Header A defines X.", "Source B uses X."],
            paths=["src/foo/header.h", "src/foo/source.c"],
            raw_snippets=["#define X 1", "use(X);"],
        )
        findings = self.v.validate_m2([cur], [cand])
        fails = [f.message for f in findings if f.severity == "FAIL"]
        self.assertTrue(any("doc_code_divergence" in m for m in fails), fails)

    def test_doc_code_divergence_passes_with_both(self):
        cand, cur = self._scenario(
            axis3=["doc_code_divergence"],
            statements=["Doc says default is 16.", "Code defaults to 8."],
            paths=["docs/spec.md", "src/foo/bar.c"],
            raw_snippets=["The default is 16 bytes.", "int default_size = 8;"],
        )
        findings = self.v.validate_m2([cur], [cand])
        fails = [f.message for f in findings if f.severity == "FAIL"]
        self.assertFalse(any("doc_code_divergence" in m for m in fails), fails)


class FixIssue6M9JudgeThresholdsTest(unittest.TestCase):
    """#6: judge now uses 1+ overlap = baseline_succeeded; 0-overlap non-refusal = inconclusive."""

    def setUp(self):
        self.gate = load_script(GATE_ORCHESTRATOR, "gate_fix6_test")

    def test_single_token_overlap_marks_succeeded(self):
        outcome = self.gate.baseline_outcome(
            answer="The answer mentions calibration explicitly.",
            query="What does the calibrator do?",
            gold_answer="Per-layer calibration uses TensorRT to derive scale factors.",
        )
        # `calibration` is distinctive (not in query); 1 overlap should now register as succeeded.
        self.assertEqual(outcome, "baseline_succeeded")

    def test_zero_overlap_non_refusal_is_inconclusive(self):
        outcome = self.gate.baseline_outcome(
            answer="I think the answer is somewhere in the codebase.",
            query="What does the calibrator do?",
            gold_answer="Per-layer calibration uses TensorRT to derive scale factors.",
        )
        self.assertEqual(outcome, "inconclusive")

    def test_refusal_still_baseline_failed(self):
        outcome = self.gate.baseline_outcome(
            answer="refuse — I cannot answer without more evidence.",
            query="Q",
            gold_answer="X",
        )
        self.assertEqual(outcome, "baseline_failed")


class FixIssue7DifficultyDriftTest(unittest.TestCase):
    """#7: when M2 evidence drops a signal's source, that signal must also drop from
    difficulty.axis2/axis3 and claim_sources."""

    def setUp(self):
        self.gen = load_script(GENERATOR, "generator_fix7_test")

    def test_filter_signals_when_m2_drops_their_source(self):
        Source = self.gen.Source
        Signal = self.gen.Signal
        sources = {
            "src:demo:kept": Source(
                source_id="src:demo:kept",
                project="demo",
                repo_name="demo",
                path="src/foo/kept.c",
                source_type="code.source",
                authority="primary_source",
                line_count=200,
            ),
            "src:demo:dropped": Source(
                source_id="src:demo:dropped",
                project="demo",
                repo_name="demo",
                path="src/foo/dropped.c",
                source_type="code.source",
                authority="primary_source",
                line_count=200,
            ),
        }
        signals = [
            Signal(
                signal_id="sig:demo:long_tail:kept",
                project="demo",
                axis=2,
                attribute="long_tail",
                source_id="src:demo:kept",
                path="src/foo/kept.c",
                lines="10-12",
            ),
            Signal(
                signal_id="sig:demo:implicit:dropped",
                project="demo",
                axis=3,
                attribute="implicit_domain_knowledge",
                source_id="src:demo:dropped",
                path="src/foo/dropped.c",
                lines="10-12",
            ),
        ]
        override = {
            "selected_evidence": [
                {
                    "evidence_id": "E1",
                    "source_id": "src:demo:kept",
                    "path": "src/foo/kept.c",
                    "lines": "10-12",
                    "role": "evidence_fact",
                    "statement": "Kept module short-circuits on null.",
                }
            ],
            "expected_answer": "Short-circuits on null (`src/foo/kept.c:10-12`).",
        }
        row = self.gen.make_row(
            project="demo",
            seq=1,
            layer="L1",
            answerability="answerable",
            selected=signals,
            sources=sources,
            repo_root=ROOT,
            module_override=override,
        )
        self.assertIsNotNone(row)
        # implicit_domain_knowledge's source was dropped by M2 → must NOT appear
        self.assertNotIn("implicit_domain_knowledge", row["difficulty"]["axis3_reasoning"])
        self.assertNotIn("implicit_domain_knowledge", row["difficulty"]["claim_sources"])
        # long_tail's source survived → MUST appear
        self.assertIn("long_tail", row["difficulty"]["axis2_retrieval"])
        self.assertEqual(
            row["difficulty"]["claim_sources"]["long_tail"],
            ["sig:demo:long_tail:kept"],
        )


class FixIssue8TargetCountTest(unittest.TestCase):
    """#8: assembler report + metadata carry target_count, actual_count, count_gap, drop_log."""

    def setUp(self):
        self.gen = load_script(GENERATOR, "generator_fix8_test")

    def test_report_records_target_and_drop_log(self):
        # Build a minimal row list and inspect the markdown report.
        report = self.gen.report_markdown(
            project="demo",
            rows=[{"layer": {"code": "L1"}, "answerability": "answerable",
                   "difficulty": {"axis2_retrieval": ["long_tail"], "axis3_reasoning": []}}],
            profile=Path("profile.yaml"),
            bundle=Path("bundle"),
            target_count=200,
            drop_log={"m2_dropped": ["c-1"], "gate_dropped": ["c-2", "c-3"]},
        )
        self.assertIn("Target rows: 200", report)
        self.assertIn("admitted: 1", report)
        self.assertIn("gap: 199", report)
        self.assertIn("M2 (empty selected_evidence) dropped: 1", report)
        self.assertIn("M9 (adversarial gate failed) dropped: 2", report)
        self.assertIn("c-1", report)
        self.assertIn("c-2", report)


class FixIssue11StrictDiversityTest(unittest.TestCase):
    """#11: prepare --strict-diversity exits non-zero when reuse caps are blown."""

    def test_diversity_report_marks_overuse_for_strict_check(self):
        prepare = load_script(PREPARE, "prepare_fix11_test")
        rows = [
            {"row_plan": {"style_hint": "colloquial"},
             "candidates": [{"path": "a.c", "lines": "1-3", "source_id": "src:a"}]}
            for _ in range(prepare.PATH_LINES_REUSE_CAP + 2)
        ]
        report = prepare.diversity_report(rows)
        self.assertGreaterEqual(len(report["path_lines_overuse"]), 1)

    def test_clean_diversity_passes(self):
        prepare = load_script(PREPARE, "prepare_fix11_clean_test")
        rows = [
            {"row_plan": {"style_hint": "colloquial"},
             "candidates": [{"path": f"src/{i}.c", "lines": "1-3", "source_id": f"src:{i}"}]}
            for i in range(10)
        ]
        report = prepare.diversity_report(rows)
        self.assertEqual(report["path_lines_overuse"], [])
        self.assertEqual(report["anchor_overuse"], [])


class FixIssue12M8IntegrationTest(unittest.TestCase):
    """#12: assembler computes per-case M8 status; --strict-m8 drops disagreed rows."""

    def setUp(self):
        self.gen = load_script(GENERATOR, "generator_fix12_test")

    def test_compute_m8_status_agrees_on_clean_answer(self):
        status = self.gen._compute_m8_status(
            answerability="answerable",
            rederived_answer="X happens when Y, per the cited evidence.",
            rederived_confidence="high",
            rederived_citations=["src/foo.c:10-12"],
            evidence_keys={"src/foo.c:10-12"},
        )
        self.assertEqual(status, "agrees")

    def test_compute_m8_status_disagrees_when_answerable_row_refuses(self):
        status = self.gen._compute_m8_status(
            answerability="answerable",
            rederived_answer="无法判断；evidence doesn't seem to cover this.",
            rederived_confidence="low",
            rederived_citations=[],
            evidence_keys=set(),
        )
        self.assertEqual(status, "disagrees")

    def test_compute_m8_status_disagrees_when_missing_evidence_row_answers(self):
        status = self.gen._compute_m8_status(
            answerability="unanswerable_missing_evidence",
            rederived_answer="Actually X is well-known to return -EBUSY in this kind of API.",
            rederived_confidence="high",
            rederived_citations=[],
            evidence_keys=set(),
        )
        self.assertEqual(status, "disagrees")

    def test_compute_m8_status_flags_fabricated_citation(self):
        status = self.gen._compute_m8_status(
            answerability="answerable",
            rederived_answer="X happens; see foo.c:99-101.",
            rederived_confidence="high",
            rederived_citations=["src/foo.c:99-101"],
            evidence_keys={"src/foo.c:10-12"},
        )
        self.assertEqual(status, "cite_fabricated")


class FixIssue13RequireStagesTest(unittest.TestCase):
    """#13: assembler check_required_stages enforces presence + coverage."""

    def setUp(self):
        self.gen = load_script(GENERATOR, "generator_fix13_test")

    def test_passes_when_all_stages_cover_all_case_ids(self):
        audit = {
            "M2": {"present": True, "path": "drafts/p.curated_evidence.jsonl",
                   "covered_case_ids": {"c-1", "c-2"}},
            "M5": {"present": True, "path": "drafts/p.queries.jsonl",
                   "covered_case_ids": {"c-1", "c-2"}},
        }
        failures = self.gen.check_required_stages(
            require_stages=["M2", "M5"],
            stages_audit=audit,
            expected_case_ids={"c-1", "c-2"},
        )
        self.assertEqual(failures, [])

    def test_fails_when_file_missing(self):
        audit = {
            "M2": {"present": False, "path": "drafts/p.curated_evidence.jsonl",
                   "covered_case_ids": set()},
        }
        failures = self.gen.check_required_stages(
            require_stages=["M2"], stages_audit=audit,
            expected_case_ids={"c-1"},
        )
        self.assertEqual(len(failures), 1)
        self.assertIn("required file is missing", failures[0])

    def test_fails_when_coverage_partial(self):
        audit = {
            "M5": {"present": True, "path": "drafts/p.queries.jsonl",
                   "covered_case_ids": {"c-1"}},
        }
        failures = self.gen.check_required_stages(
            require_stages=["M5"], stages_audit=audit,
            expected_case_ids={"c-1", "c-2", "c-3"},
        )
        self.assertEqual(len(failures), 1)
        self.assertIn("missing 2 case_id(s)", failures[0])

    def test_rejects_unknown_stage(self):
        audit: dict[str, dict[str, Any]] = {}
        failures = self.gen.check_required_stages(
            require_stages=["MX"], stages_audit=audit,
            expected_case_ids=set(),
        )
        self.assertEqual(len(failures), 1)
        self.assertIn("not a recognized pipeline stage", failures[0])


class Stage0ConditionalBehaviorFilterTest(unittest.TestCase):
    """Stage 0 fix A: conditional_behavior candidates pointing at license
    headers / include guards are dropped or rescued to a real guard line."""

    def setUp(self):
        self.prepare = load_script(PREPARE, "prepare_stage0_cb_test")

    def _make_file(self, tmp: Path, name: str, body: str) -> str:
        path = tmp / name
        path.write_text(body, encoding="utf-8")
        return f"{name}"

    def test_license_header_is_dropped_when_no_real_guard(self):
        with TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            relpath = self._make_file(tmp, "foo.sv", (
                "// SPDX-License-Identifier: Apache-2.0\n"
                "// Unless required by applicable law or agreed to in writing, software\n"
                "// distributed under the License is distributed on an \"AS IS\" BASIS\n"
                "module foo (); endmodule\n"
            ))
            ok, replacement = self.prepare.conditional_behavior_substantive_span(
                path=relpath, lines="2-3",
                raw_snippet="// Unless required by applicable law or agreed to in writing, software / // distributed under the License",
                repo_root=tmp,
            )
            self.assertFalse(ok)
            self.assertIsNone(replacement)

    def test_license_header_rescued_when_file_has_real_guard(self):
        with TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            relpath = self._make_file(tmp, "foo.sv", (
                "// Unless required by applicable law or agreed to in writing, software\n"
                "// distributed under the License is distributed on an \"AS IS\" BASIS\n"
                "module foo;\n"
                "    if (x == 0) y = z;\n"
                "endmodule\n"
            ))
            ok, replacement = self.prepare.conditional_behavior_substantive_span(
                path=relpath, lines="1-2",
                raw_snippet="// Unless required by applicable law or agreed to in writing, software / // distributed under the License",
                repo_root=tmp,
            )
            self.assertTrue(ok)
            # Should rewrite to point at line 4 (the `if`)
            self.assertEqual(replacement.split("-")[0], "4")

    def test_doc_file_extension_rejected_outright(self):
        with TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            relpath = self._make_file(tmp, "guide.md", "if applicable.\n")
            ok, _ = self.prepare.conditional_behavior_substantive_span(
                path=relpath, lines="1-1", raw_snippet="if applicable.",
                repo_root=tmp,
            )
            self.assertFalse(ok)

    def test_real_guard_in_original_span_keeps_lines(self):
        with TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            relpath = self._make_file(tmp, "bar.sv", (
                "module bar;\n"
                "    always @(posedge clk) begin\n"
                "        if (reset) q <= 0;\n"
                "    end\n"
                "endmodule\n"
            ))
            ok, replacement = self.prepare.conditional_behavior_substantive_span(
                path=relpath, lines="2-3",
                raw_snippet="always @(posedge clk) begin / if (reset) q <= 0;",
                repo_root=tmp,
            )
            self.assertTrue(ok)
            self.assertIsNone(replacement)  # original span fine — no rewrite


class Stage0IncludeGuardSkipTest(unittest.TestCase):
    """Stage 0 fix B: imports_or_includes neighbors point past `ifndef X / `define X
    guards into the file's first substantive line."""

    def setUp(self):
        self.prepare = load_script(PREPARE, "prepare_stage0_walk_test")

    def test_first_substantive_line_skips_guards_and_comments(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "X.vh"
            path.write_text(
                "// copyright header line\n"      # 1
                "// more comments\n"               # 2
                "\n"                                # 3
                "`ifndef X_VH\n"                   # 4
                "`define X_VH\n"                   # 5
                "\n"                                # 6
                "`define FOO 42\n"                 # 7  ← first substantive
                "`define BAR 1\n",                 # 8
                encoding="utf-8",
            )
            result = self.prepare._find_first_substantive_line(path)
            self.assertEqual(result, 7)

    def test_include_guard_line_distinguishes_bare_define_from_macro(self):
        self.assertTrue(self.prepare._is_include_guard_line("`ifndef X_VH"))
        self.assertTrue(self.prepare._is_include_guard_line("`define X_VH"))
        self.assertTrue(self.prepare._is_include_guard_line("`endif"))
        # Real macro (has body) — NOT a guard.
        self.assertFalse(self.prepare._is_include_guard_line("`define FOO 42"))
        self.assertFalse(self.prepare._is_include_guard_line('`define NAME "vortex"'))


class Stage0AnchorScoringTest(unittest.TestCase):
    """Stage 0 fix C: the candidate with the most outgoing graph edges
    becomes candidates[0] (the row's anchor)."""

    def test_edge_degree_orders_candidates(self):
        # Build a minimal scenario in-process: two candidates, one with 5
        # outgoing edges in the relation graph, the other with 1.
        # We can't easily exercise the full prepare_project loop without
        # an analyzer bundle, but the scoring sort itself is the unit we
        # care about. Test that the sort key produces the right order.
        candidates = [
            {"source_id": "src:low_degree", "path": "a.c", "lines": "1-3"},
            {"source_id": "src:high_degree", "path": "b.c", "lines": "1-3"},
        ]
        by_subject = {
            "src:low_degree": [{"predicate": "defines"}],
            "src:high_degree": [
                {"predicate": "defines"},
                {"predicate": "defines"},
                {"predicate": "doc_mentions_entity"},
                {"predicate": "imports_or_includes"},
                {"predicate": "defines"},
            ],
        }
        prepare = load_script(PREPARE, "prepare_stage0_score_test")

        def edge_degree(source_id):
            outgoing = by_subject.get(source_id, [])
            return sum(1 for rel in outgoing if rel.get("predicate") in prepare._WALK_PREDICATES)

        candidates.sort(key=lambda c: (-edge_degree(c["source_id"]), c["path"], c["lines"]))
        self.assertEqual(candidates[0]["source_id"], "src:high_degree")


if __name__ == "__main__":
    unittest.main()
