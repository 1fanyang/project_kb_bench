"""Phase 4 — prepare against a v2 bundle.

Three things this test pins:
  1. `--bundle-path` flag accepts an arbitrary directory.
  2. `load_signals` tolerates the new `signal_dataflow` attribute (Phase 3)
     by dropping it silently and counting the drops; existing axis
     attributes still load.
  3. PREFERRED_ATTRIBUTE_GROUPS remains unchanged in scope (no new
     attribute slipped in by an over-eager wiring change).
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


ROOT = Path(__file__).resolve().parents[1]
GENERATOR = ROOT / "scripts" / "generate_v1_1_release_corpora.py"
PREPARE = ROOT / "skills" / "benchmark-generator" / "scripts" / "prepare_module_inputs.py"


def _load_gen():
    spec = importlib.util.spec_from_file_location("v1_1_generator", GENERATOR)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["v1_1_generator"] = mod  # dataclass introspection needs this
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# load_signals tolerance + drop counter
# ---------------------------------------------------------------------------

class LoadSignalsTolerateUnknownTest(unittest.TestCase):
    def _make_bundle(self, tmp: Path) -> Path:
        """Hand-build the minimum bundle that load_sources accepts."""
        bundle = tmp / "bundle"
        bundle.mkdir()
        # Need a real on-disk file for is_generation_source's
        # `(repo_root / path).exists()` check.
        src_file = tmp / "fake.cpp"
        src_file.write_text("int main(void) { return 0; }\n")
        rel = "fake.cpp"

        with (bundle / "source_inventory.jsonl").open("w") as f:
            f.write(json.dumps({
                "source_id": "src_test_00001",
                "project": "test",
                "path": rel,
                "relative_path": rel,
                "repo_name": "test/test",
                "language": "cpp",
                "modality": "code",
                "source_type": "code.source",
                "authority": "primary_source",
                "size_bytes": 30,
                "line_count": 1,
                "sha256": "sha256:zzz",
                "source_set_id": "test_main",
                "parse_status": "parsed",
            }) + "\n")

        with (bundle / "signal_index.jsonl").open("w") as f:
            # Two known + one unknown attribute; all anchored on the
            # same source so they survive the path-match filter.
            anchor_base = {
                "kind": "source",
                "source_id": "src_test_00001",
                "path": rel,
                "lines": "1",
            }
            for i, attr in enumerate([
                ("long_tail", 2),
                ("conditional_behavior", 3),
                ("signal_dataflow", 3),       # Phase 3 unknown
                ("totally_made_up_attr", 3),  # generic unknown
            ]):
                name, axis = attr
                f.write(json.dumps({
                    "signal_id": f"sig:test:{name}:src-test-00001-{i:04d}",
                    "project": "test",
                    "attribute": name,
                    "axis": axis,
                    "anchor": anchor_base,
                    "evidence": {},
                    "extractor": "test",
                    "confidence": 0.95,
                }) + "\n")
        return bundle

    def test_known_loaded_unknown_counted(self):
        gen = _load_gen()
        with TemporaryDirectory() as td:
            tmp = Path(td)
            bundle = self._make_bundle(tmp)
            sources = gen.load_sources(bundle, "test", tmp)
            self.assertEqual(set(sources), {"src_test_00001"})
            dropped: dict[str, int] = {}
            sig = gen.load_signals(bundle, "test", sources,
                                   dropped_unknown_attributes=dropped)

        # Known attributes loaded; unknown silently dropped + counted.
        self.assertIn("long_tail", sig)
        self.assertIn("conditional_behavior", sig)
        self.assertNotIn("signal_dataflow", sig)
        self.assertNotIn("totally_made_up_attr", sig)
        self.assertEqual(dropped.get("signal_dataflow"), 1)
        self.assertEqual(dropped.get("totally_made_up_attr"), 1)

    def test_counter_is_optional_and_default_silent(self):
        gen = _load_gen()
        with TemporaryDirectory() as td:
            tmp = Path(td)
            bundle = self._make_bundle(tmp)
            sources = gen.load_sources(bundle, "test", tmp)
            # No counter passed -> still loads, still drops silently.
            sig = gen.load_signals(bundle, "test", sources)
        self.assertIn("long_tail", sig)
        self.assertNotIn("signal_dataflow", sig)


# ---------------------------------------------------------------------------
# PREFERRED_ATTRIBUTE_GROUPS unchanged (Phase 4 constraint)
# ---------------------------------------------------------------------------

class PreferredAttributeGroupsStableTest(unittest.TestCase):
    """If a future change wired signal_dataflow as a new selection
    attribute, it would land here. This test will need updating then —
    deliberately."""

    EXPECTED_GROUPS = [
        ("long_tail", "implicit_domain_knowledge"),
        ("distracting_info", "conditional_behavior"),
        ("non_code_anchor", "implicit_domain_knowledge"),
        ("long_tail", "doc_code_divergence"),
        ("distracting_info", "implicit_domain_knowledge"),
        ("long_tail", "conditional_behavior"),
    ]

    def test_groups_match_v1(self):
        gen = _load_gen()
        self.assertEqual(list(gen.PREFERRED_ATTRIBUTE_GROUPS),
                         self.EXPECTED_GROUPS)

    def test_known_axis_attributes_whitelist_does_not_include_signal_dataflow(self):
        gen = _load_gen()
        self.assertIn("conditional_behavior", gen.KNOWN_AXIS_ATTRIBUTES)
        self.assertIn("long_tail", gen.KNOWN_AXIS_ATTRIBUTES)
        self.assertNotIn("signal_dataflow", gen.KNOWN_AXIS_ATTRIBUTES,
            "Phase 4 ignore-and-ship: signal_dataflow must NOT be wired "
            "as a selection attribute yet")


# ---------------------------------------------------------------------------
# CLI smoke (against the live Vortex v2 bundle if present)
# ---------------------------------------------------------------------------

class CliBundlePathSmokeTest(unittest.TestCase):
    V2_BUNDLE = ROOT / "runs" / "vortex_context_bundle_v2"
    MAIN_CHECKOUT = Path("/Users/yangyifan/projects/work/kb_benchmark")
    REPO_SOURCES = MAIN_CHECKOUT / "repo_sources"

    def setUp(self):
        if not self.V2_BUNDLE.exists():
            self.skipTest("Phase 2 v2 bundle absent; skipping CLI smoke")
        if not self.REPO_SOURCES.exists():
            self.skipTest("repo_sources/ not on disk; skipping CLI smoke")

    def test_prepare_accepts_v2_bundle_path_and_logs_dropped_attrs(self):
        with TemporaryDirectory() as td:
            r = subprocess.run(
                [sys.executable, str(PREPARE),
                 "--project", "vortex",
                 "--bundle-path", str(self.V2_BUNDLE),
                 "--repo-root", str(self.MAIN_CHECKOUT),
                 "--output-dir", td],
                capture_output=True, text=True,
                # prepare resolves `Path("runs")/<project>_generation_profile_v1_1.yaml`
                # relative to cwd; make that cwd the worktree root.
                cwd=str(ROOT),
            )
            self.assertEqual(r.returncode, 0, msg=r.stderr or r.stdout)
            self.assertIn("signal_dataflow=", r.stdout,
                "expected prepare to log signal_dataflow drops under "
                "Phase 4 ignore-and-ship")
            out_file = Path(td) / "vortex.candidates.jsonl"
            self.assertTrue(out_file.exists(),
                            f"missing output; tmpdir contents: {list(Path(td).iterdir())}")
            rows = out_file.read_text().splitlines()
            self.assertEqual(len(rows), 200)

    def test_v2_bundle_yields_zero_conditional_behavior_rescues(self):
        with TemporaryDirectory() as td:
            subprocess.check_call(
                [sys.executable, str(PREPARE),
                 "--project", "vortex",
                 "--bundle-path", str(self.V2_BUNDLE),
                 "--repo-root", str(self.MAIN_CHECKOUT),
                 "--output-dir", td],
                stdout=subprocess.DEVNULL,
                cwd=str(ROOT),
            )
            rows = [json.loads(line) for line in
                    (Path(td) / "vortex.candidates.jsonl").read_text().splitlines()]
        # The whole point of the analyzer-v2 work: Stage-0 should not
        # need to rescue or drop conditional_behavior signals because
        # the analyzer never anchors them at license-zone lines.
        total_rescued = 0
        total_dropped = 0
        for row in rows:
            audit = (row.get("row_plan") or {}).get("_dropped_at_prepare") or {}
            total_rescued += len(audit.get("conditional_behavior_rescued", []))
            total_dropped += len(audit.get("conditional_behavior_dropped", []))
        self.assertEqual(total_rescued, 0,
            "v2 bundle should require zero Stage-0 conditional_behavior rescues")
        self.assertEqual(total_dropped, 0,
            "v2 bundle should produce zero conditional_behavior drops")


if __name__ == "__main__":
    unittest.main()
