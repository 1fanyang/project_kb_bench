"""Integration tests for the Phase 3 signal emitter.

Strategy: build the v2 bundle from the Phase 2 tiny.db fixture (with
--strip-prefix tiny so paths align with our on-disk fixture mirror),
point signal_emitter at a small Verilog tree that matches the
fixture's relative paths, run it, and assert anchor shapes.

Coverage matrix (Phase 3 ask):
- always-if              -> AlwaysIfIntegrationTest
- nested if/else         -> via test_verilog_reparse.py (unit-tested
                            against the re-parser directly)
- case statements        -> via test_verilog_reparse.py
- signal read/write      -> SignalDataflowIntegrationTest
- license-zone regression-> via test_verilog_reparse.py
- provenance marking     -> ProvenanceMarkingTest
- bundle-schema stable   -> SchemaStabilityTest

The integration tests here also exercise the wider pipeline (bundle
loader, dedup, JSONL writer, language filter).
"""
from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills" / "benchmark-repo-analyzer" / "scripts"
EXPORTER = SCRIPTS / "codegraph_to_bundle.py"
EMITTER = SCRIPTS / "signal_emitter.py"
FIX_DB = ROOT / "tests" / "fixtures" / "codegraph_to_bundle" / "tiny.db"
FIX_REPO = ROOT / "tests" / "fixtures" / "signal_emitter" / "repo_sources"


def _build_v2_bundle(out_dir: Path) -> None:
    subprocess.check_call([
        sys.executable, str(EXPORTER),
        "--db", str(FIX_DB),
        "--project", "tiny",
        "--source-set-id", "tiny_main",
        "--repo-name", "tiny/tiny",
        "--strip-prefix", "tiny",
        "--out", str(out_dir),
        "--repo-sources-root", str(FIX_REPO),
    ])


def _run_emitter(bundle_dir: Path) -> list[dict]:
    subprocess.check_call([
        sys.executable, str(EMITTER),
        "--bundle", str(bundle_dir),
        "--project", "tiny",
        "--repo-sources-root", str(FIX_REPO),
        "--quiet",
    ])
    out = bundle_dir / "signal_index.jsonl"
    return [json.loads(line) for line in out.read_text().splitlines() if line.strip()]


class AlwaysIfIntegrationTest(unittest.TestCase):
    def test_emits_conditional_behavior_with_real_anchor_lines(self):
        with TemporaryDirectory() as td:
            bundle = Path(td) / "bundle"
            _build_v2_bundle(bundle)
            signals = _run_emitter(bundle)

        cb = [s for s in signals if s["attribute"] == "conditional_behavior"]
        self.assertGreaterEqual(len(cb), 2,
            "expected at least always_construct + conditional_statement anchors")
        # Anchor lines must be > 5 (the fixture has 5 license lines).
        # This is THE load-bearing regression check for Phase 3.
        for s in cb:
            line = int(s["anchor"]["lines"].split("-")[0])
            self.assertGreater(
                line, 5,
                f"conditional_behavior anchored at line {line} "
                f"(should be after the 5-line license header)"
            )
        # An always_construct anchor reports the if-write target in
        # contained_writes; the if anchor lists it too.
        cond = next(s for s in cb
                    if s["evidence"]["ast_kind"] == "conditional_statement")
        self.assertIn("q", cond["evidence"]["contained_writes"])


class SignalDataflowIntegrationTest(unittest.TestCase):
    def test_emits_signal_dataflow_records_for_all_assignments(self):
        with TemporaryDirectory() as td:
            bundle = Path(td) / "bundle"
            _build_v2_bundle(bundle)
            signals = _run_emitter(bundle)

        df = [s for s in signals if s["attribute"] == "signal_dataflow"]
        # parent.sv has 3 assignments: `assign b = d`, `q <= b`, `q <= 1'b0`.
        # That's 1 continuous_assign + 2 nonblocking_assignment.
        self.assertGreaterEqual(len(df), 3)
        kinds = {s["evidence"]["assignment_kind"] for s in df}
        self.assertIn("net_assignment", kinds)
        self.assertIn("nonblocking_assignment", kinds)
        # `b` is written by the continuous_assign reading `d`.
        b_write = next(s for s in df if s["evidence"]["signal_name"] == "b")
        self.assertEqual(b_write["evidence"]["rhs_signals"], ["d"])
        self.assertEqual(b_write["evidence"]["in_construct_type"],
                         "continuous_assign")
        # `q` writes come from inside the always_ff.
        q_writes = [s for s in df if s["evidence"]["signal_name"] == "q"]
        self.assertGreaterEqual(len(q_writes), 2)
        for w in q_writes:
            self.assertEqual(w["evidence"]["in_construct_type"],
                             "always_construct")


class ProvenanceMarkingTest(unittest.TestCase):
    """Phase 3 ask #2: anchors from tree-sitter re-parse must be
    explicitly tagged so downstream consumers can identify them."""

    def test_verilog_anchors_carry_extractor_and_evidence_provenance(self):
        with TemporaryDirectory() as td:
            bundle = Path(td) / "bundle"
            _build_v2_bundle(bundle)
            signals = _run_emitter(bundle)

        verilog_attrs = {"conditional_behavior", "signal_dataflow"}
        verilog_signals = [s for s in signals if s["attribute"] in verilog_attrs]
        self.assertGreater(len(verilog_signals), 0)
        for s in verilog_signals:
            self.assertEqual(s["extractor"], "verilog_tree_sitter_reparse_v2",
                             f"{s['attribute']} missing extractor tag")
            self.assertEqual(s["evidence"]["provenance"],
                             "tree_sitter_verilog_reparse_v2",
                             f"{s['attribute']} missing evidence.provenance")


class SchemaStabilityTest(unittest.TestCase):
    """Phase 3 ask #3: the v2 bundle schema stays stable. Signal records
    must validate against the existing signal-index schema."""

    def test_all_signals_validate_against_v1_signal_index_schema(self):
        import jsonschema  # type: ignore
        schema = json.loads(
            (ROOT / "schemas" / "signal-index.schema.json").read_text()
        )
        with TemporaryDirectory() as td:
            bundle = Path(td) / "bundle"
            _build_v2_bundle(bundle)
            signals = _run_emitter(bundle)
        self.assertGreater(len(signals), 0)
        for s in signals:
            jsonschema.validate(s, schema)


class DistractingInfoEvidenceShapeTest(unittest.TestCase):
    """Phase 3 plan: distracting_info evidence must carry the v1-shape
    fields prepare_module_inputs.py reads."""

    def test_distracting_info_evidence_keys_match_v1(self):
        with TemporaryDirectory() as td:
            bundle = Path(td) / "bundle"
            _build_v2_bundle(bundle)
            signals = _run_emitter(bundle)
        di = [s for s in signals if s["attribute"] == "distracting_info"]
        for s in di:
            ev = s["evidence"]
            self.assertIn("collision_sources", ev)
            self.assertIn("collision_source_count", ev)
            self.assertIn("total_entities_with_name", ev)


if __name__ == "__main__":
    unittest.main()
