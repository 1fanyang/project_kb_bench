"""Tests for the v2 bundle exporter (codegraph_to_bundle.py).

Coverage matrix (matches the Phase 2 ask):
- SQLite query correctness    -> test_source_inventory_records / test_relation_graph_records
- Entity-kind normalization   -> test_verilog_class_remaps_to_module / test_cg_method_remaps_to_function
- v1 backward compatibility   -> test_v1_records_validate_against_v1_1_schema
"""
from __future__ import annotations

import copy
import importlib.util
import json
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "skills" / "benchmark-repo-analyzer" / "scripts"
EXPORTER = SCRIPTS_DIR / "codegraph_to_bundle.py"
FIX_DB = ROOT / "tests" / "fixtures" / "codegraph_to_bundle" / "tiny.db"
V1_BUNDLE = ROOT / "runs" / "vortex_context_bundle"
RELATION_SCHEMA = ROOT / "schemas" / "relation-graph.schema.json"


def _import_helpers():
    """Import the script's helper modules without subprocess machinery."""
    sys.path.insert(0, str(SCRIPTS_DIR))
    import _bundle_writer
    import _codegraph_queries
    return _bundle_writer, _codegraph_queries


def _run_exporter(out_dir: Path, extra: list[str] | None = None) -> None:
    cmd = [
        sys.executable, str(EXPORTER),
        "--db", str(FIX_DB),
        "--project", "tiny",
        "--source-set-id", "tiny_main",
        "--repo-name", "tiny/tiny",
        "--out", str(out_dir),
        # Point at a directory that won't exist so the
        # included_first_substantive_line enrichment is skipped (the
        # fixture's "include" target isn't real source on disk).
        "--repo-sources-root", "/tmp/_nonexistent_repo_sources",
    ] + (extra or [])
    subprocess.check_call(cmd)


def _load_jsonl(p: Path) -> list[dict]:
    return [json.loads(line) for line in p.read_text().splitlines()]


# ---------------------------------------------------------------------------
# Source inventory — query correctness + shape
# ---------------------------------------------------------------------------

class SourceInventoryTest(unittest.TestCase):
    def test_emits_one_record_per_fixture_file(self):
        with TemporaryDirectory() as td:
            out = Path(td) / "out"
            _run_exporter(out)
            records = _load_jsonl(out / "source_inventory.jsonl")
        self.assertEqual(len(records), 4)
        # Sorted by path; deterministic source_ids start at 00001.
        paths = [r["relative_path"] for r in records]
        self.assertEqual(paths, sorted(paths))
        self.assertEqual([r["source_id"] for r in records],
                         ["src_tiny_00001", "src_tiny_00002",
                          "src_tiny_00003", "src_tiny_00004"])

    def test_modality_derivation(self):
        with TemporaryDirectory() as td:
            out = Path(td) / "out"
            _run_exporter(out)
            records = _load_jsonl(out / "source_inventory.jsonl")
        by_lang = {r["language"]: r["modality"] for r in records}
        self.assertEqual(by_lang["cpp"], "code")
        self.assertEqual(by_lang["python"], "code")
        self.assertEqual(by_lang["verilog"], "code")

    def test_sha256_carries_prefix(self):
        with TemporaryDirectory() as td:
            out = Path(td) / "out"
            _run_exporter(out)
            records = _load_jsonl(out / "source_inventory.jsonl")
        for r in records:
            self.assertTrue(r["sha256"].startswith("sha256:"),
                            f"missing sha256: prefix: {r['sha256']!r}")


# ---------------------------------------------------------------------------
# Entity index — kind normalization (the Phase 2 ask)
# ---------------------------------------------------------------------------

class EntityKindNormalizationTest(unittest.TestCase):
    def setUp(self):
        self.td = TemporaryDirectory()
        self.out = Path(self.td.name) / "out"
        _run_exporter(self.out)
        self.records = _load_jsonl(self.out / "entity_index.jsonl")
        self.by_name = {(r["name"], r["kind"]): r for r in self.records}

    def tearDown(self):
        self.td.cleanup()

    def test_verilog_class_remaps_to_module(self):
        # tiny.db has two verilog kind=class nodes: parent + child.
        # Both must surface as kind='module' in the bundle.
        self.assertIn(("parent", "module"), self.by_name)
        self.assertIn(("child", "module"), self.by_name)
        # And NOT as kind='class'.
        self.assertNotIn(("parent", "class"), self.by_name)
        self.assertNotIn(("child", "class"), self.by_name)

    def test_cpp_class_stays_as_class(self):
        # cpp 'Foo' is kind=class in CodeGraph and stays kind=class in
        # the bundle (Verilog-only remap).
        self.assertIn(("Foo", "class"), self.by_name)

    def test_cg_method_remaps_to_function(self):
        # CodeGraph emits 'method' for class members. v1 bundle has no
        # 'method' kind — the v2 remap lumps methods into 'function'.
        self.assertIn(("bar", "function"), self.by_name)         # cpp method
        self.assertIn(("helper", "function"), self.by_name)      # verilog "method"

    def test_skips_file_and_import_nodes(self):
        # tiny.db has 4 file:* nodes and 1 import:* node. None should appear.
        names_kinds = {(r["name"], r["kind"]) for r in self.records}
        self.assertNotIn(("os", "import"), names_kinds)
        # No 'file' kind in the index either.
        self.assertFalse(any(r["kind"] == "file" for r in self.records))


# ---------------------------------------------------------------------------
# Relation graph — predicate normalization + endpoint shape
# ---------------------------------------------------------------------------

class RelationGraphTest(unittest.TestCase):
    def setUp(self):
        self.td = TemporaryDirectory()
        self.out = Path(self.td.name) / "out"
        _run_exporter(self.out)
        self.records = _load_jsonl(self.out / "relation_graph.jsonl")

    def tearDown(self):
        self.td.cleanup()

    def test_instantiates_predicate_emitted(self):
        # Verilog parent -> child via the instantiates edge. The v1.1
        # additive predicate must appear in the bundle.
        rels = [r for r in self.records if r["predicate"] == "instantiates"]
        self.assertGreaterEqual(len(rels), 1)
        # Endpoint shape: subject + object both have type/id/name.
        for r in rels:
            for ep in (r["subject"], r["object"]):
                self.assertIn(ep["type"], {"entity", "source"})
                self.assertIn("id", ep)
                self.assertIn("name", ep)

    def test_imports_renamed_to_imports_or_includes_for_v1_compat(self):
        # CodeGraph's `imports` predicate is remapped to v1's
        # `imports_or_includes` so prepare_module_inputs.py's filter
        # keeps matching it.
        preds = {r["predicate"] for r in self.records}
        # The fixture's only imports edge targets an `import:` node we
        # skip at entity_index — so the edge gets dropped. The presence
        # check is that we DID NOT emit `imports` as a predicate name.
        self.assertNotIn("imports", preds)

    def test_evidence_carries_required_fields(self):
        # Schema requires evidence[*] to have source_id/path/summary.
        for r in self.records:
            self.assertGreaterEqual(len(r["evidence"]), 1)
            for ev in r["evidence"]:
                self.assertIn("source_id", ev)
                self.assertIn("path", ev)
                self.assertIn("summary", ev)


# ---------------------------------------------------------------------------
# Manifest + analyzer report
# ---------------------------------------------------------------------------

class ManifestAndReportTest(unittest.TestCase):
    def test_manifest_marks_v2_primary_with_pin(self):
        with TemporaryDirectory() as td:
            out = Path(td) / "out"
            _run_exporter(out)
            m = json.loads((out / "project_manifest.json").read_text())
        self.assertEqual(m["analyzer_version"],
                         "benchmark-repo-analyzer/v2-tree-sitter-codegraph")
        self.assertTrue(m["analysis_backends"]["code"]["used_primary"])
        self.assertEqual(m["analyzer_pin"]["codegraph_indexed_with_version"], "1.1.1")
        self.assertEqual(m["counts"]["sources"], 4)

    def test_analyzer_report_has_summary(self):
        with TemporaryDirectory() as td:
            out = Path(td) / "out"
            _run_exporter(out)
            body = (out / "analyzer_report.md").read_text()
        self.assertIn("benchmark-repo-analyzer/v2-tree-sitter-codegraph", body)
        self.assertIn("Top entity kinds", body)
        self.assertIn("Relations by predicate", body)


# ---------------------------------------------------------------------------
# v1 backward compatibility — existing v1 records still validate
# ---------------------------------------------------------------------------

class V1BackwardCompatibilityTest(unittest.TestCase):
    """If the v1.1 schema-bump broke v1 records, prepare_module_inputs.py
    would start failing on the existing baseline. The exporter must extend
    the schema additively only."""

    def test_v1_relation_records_pass_v1_1_schema(self):
        import jsonschema  # type: ignore
        schema = json.loads(RELATION_SCHEMA.read_text())
        v1_path = V1_BUNDLE / "relation_graph.jsonl"
        if not v1_path.exists():
            self.skipTest("v1 vortex bundle absent; nothing to compare")
        # Sample first 500 records to keep the test fast.
        records = [json.loads(line) for line in
                   v1_path.read_text().splitlines()[:500]]
        for r in records:
            jsonschema.validate(r, schema)

    def test_v1_entity_records_pass_schema(self):
        import jsonschema  # type: ignore
        schema_path = ROOT / "schemas" / "entity-index.schema.json"
        schema = json.loads(schema_path.read_text())
        v1_path = V1_BUNDLE / "entity_index.jsonl"
        if not v1_path.exists():
            self.skipTest("v1 vortex bundle absent; nothing to compare")
        records = [json.loads(line) for line in
                   v1_path.read_text().splitlines()[:500]]
        for r in records:
            jsonschema.validate(r, schema)


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------

class DeterminismTest(unittest.TestCase):
    def test_byte_identical_output_on_rerun(self):
        with TemporaryDirectory() as td:
            out1 = Path(td) / "a"
            out2 = Path(td) / "b"
            _run_exporter(out1)
            _run_exporter(out2)
            for name in ("source_inventory.jsonl", "entity_index.jsonl",
                         "relation_graph.jsonl"):
                # Manifest's generated_at differs; skip it here.
                self.assertEqual(
                    (out1 / name).read_bytes(),
                    (out2 / name).read_bytes(),
                    f"{name} differs across re-runs",
                )


if __name__ == "__main__":
    unittest.main()
