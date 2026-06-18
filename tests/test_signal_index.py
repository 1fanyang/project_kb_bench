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


def write_jsonl(path, rows):
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


class SignalIndexTest(unittest.TestCase):
    def test_signal_index_schema_file_exists_and_names_required_fields(self):
        schema_path = ROOT / "schemas" / "signal-index.schema.json"
        self.assertTrue(schema_path.exists())
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        self.assertEqual(schema["title"], "Analyzer Signal Index Row")
        self.assertIn("relation_id", schema["properties"]["anchor"]["properties"])
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

    def test_context_validator_rejects_unknown_relation_anchor(self):
        validator = load_validator()
        rows = [
            {
                "_line": 1,
                "signal_id": "sig:demo:relation",
                "project": "demo",
                "axis": 3,
                "attribute": "doc_code_divergence",
                "anchor": {"kind": "relation", "relation_id": "rel:missing"},
                "evidence": {"predicate": "doc_mentions_entity"},
                "extractor": "test",
                "confidence": 0.9,
            }
        ]
        findings = []

        validator.validate_signals(
            rows,
            Path("signal_index.jsonl"),
            project_id="demo",
            sources={},
            entities={},
            relations={},
            findings=findings,
        )

        self.assertIn(
            "anchor.relation_id not present in relation graph",
            [f.message for f in findings if f.severity == "FAIL"],
        )

    def test_context_validator_rejects_schema_invalid_signal_rows_without_crashing(self):
        validator = load_validator()
        rows = [
            {
                "_line": 1,
                "signal_id": "",
                "project": "",
                "axis": 2.0,
                "attribute": "",
                "anchor": {"kind": "entity", "entity_id": ["ent:a"], "source_id": ["src:a"]},
                "evidence": [],
                "extractor": "",
                "confidence": 0.9,
            },
            {
                "_line": 2,
                "signal_id": "sig:bool-axis",
                "project": "demo",
                "axis": True,
                "attribute": "long_tail",
                "anchor": {"kind": "entity", "entity_id": "ent:a", "source_id": "src:a"},
                "evidence": {"reference_count": 1},
                "extractor": "test",
                "confidence": 0.9,
            },
            {
                "_line": 3,
                "signal_id": "sig:bool-confidence",
                "project": "demo",
                "axis": 2,
                "attribute": "long_tail",
                "anchor": {"kind": "entity", "entity_id": "ent:a", "source_id": "src:a"},
                "evidence": {"reference_count": 1},
                "extractor": "test",
                "confidence": True,
            },
            {
                "_line": 4,
                "signal_id": "sig:duplicate",
                "project": "demo",
                "axis": 2,
                "attribute": "long_tail",
                "anchor": {"kind": "entity", "entity_id": "ent:a", "source_id": "src:a"},
                "evidence": {"reference_count": 1},
                "extractor": "test",
                "confidence": 0.9,
            },
            {
                "_line": 5,
                "signal_id": "sig:duplicate",
                "project": "demo",
                "axis": 2,
                "attribute": "long_tail",
                "anchor": {"kind": "entity", "entity_id": "ent:a", "source_id": "src:a"},
                "evidence": {"reference_count": 1},
                "extractor": "test",
                "confidence": 0.9,
            },
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

        fail_messages = [f.message for f in findings if f.severity == "FAIL"]
        self.assertIn("`signal_id` must be a non-empty string", fail_messages)
        self.assertIn("`project` must be a non-empty string", fail_messages)
        self.assertIn("`attribute` must be a non-empty string", fail_messages)
        self.assertIn("`extractor` must be a non-empty string", fail_messages)
        self.assertEqual(fail_messages.count("`axis` must be integer 2 or 3"), 2)
        self.assertIn("`evidence` must be an object", fail_messages)
        self.assertIn("`confidence` must be a number from 0 to 1", fail_messages)
        self.assertIn("anchor.source_id must be a string", fail_messages)
        self.assertIn("anchor.entity_id must be a string", fail_messages)
        self.assertIn("duplicate signal_id", fail_messages)

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

    def test_signal_builder_default_long_tail_threshold_is_three(self):
        with tempfile.TemporaryDirectory() as tmp:
            bundle = Path(tmp) / "bundle"
            bundle.mkdir()
            write_jsonl(
                bundle / "source_inventory.jsonl",
                [
                    {
                        "source_id": "src:code",
                        "project": "demo",
                        "source_set_id": "main",
                        "repo_name": "demo",
                        "path": "main.py",
                        "relative_path": "main.py",
                        "modality": "code",
                        "source_type": "code.python",
                        "authority": "primary_source",
                        "language": "python",
                        "line_count": 10,
                        "size_bytes": 10,
                        "sha256": "sha256:1",
                        "parse_status": "parsed",
                    }
                ],
            )
            write_jsonl(
                bundle / "entity_index.jsonl",
                [
                    {
                        "entity_id": "ent:target",
                        "project": "demo",
                        "source_id": "src:code",
                        "name": "target",
                        "kind": "function",
                        "path": "main.py",
                        "line_start": 1,
                        "line_end": 2,
                        "extractor": "test",
                        "confidence": 0.9,
                    }
                ],
            )
            write_jsonl(
                bundle / "relation_graph.jsonl",
                [
                    {
                        "relation_id": f"rel:{index}",
                        "project": "demo",
                        "subject": {"type": "source", "id": "src:code", "name": "main.py"},
                        "predicate": "contains",
                        "object": {"type": "entity", "id": "ent:target", "name": "target"},
                        "evidence": [{"source_id": "src:code", "path": "main.py", "lines": str(index)}],
                        "extractor": "test",
                        "confidence": 0.8,
                    }
                    for index in (1, 2)
                ],
            )
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
            long_tail = [item for item in signals if item["attribute"] == "long_tail"]
            self.assertEqual(len(long_tail), 1)
            self.assertEqual(long_tail[0]["evidence"]["threshold"], 3)
            self.assertEqual(long_tail[0]["evidence"]["reference_count"], 2)

    def test_signal_builder_emits_distracting_info_on_axis_two(self):
        with tempfile.TemporaryDirectory() as tmp:
            bundle = Path(tmp) / "bundle"
            bundle.mkdir()
            sources = []
            entities = []
            for index in (1, 2):
                source_id = f"src:code:{index}"
                sources.append(
                    {
                        "source_id": source_id,
                        "project": "demo",
                        "source_set_id": "main",
                        "repo_name": "demo",
                        "path": f"file{index}.py",
                        "relative_path": f"file{index}.py",
                        "modality": "code",
                        "source_type": "code.python",
                        "authority": "primary_source",
                        "language": "python",
                        "line_count": 10,
                        "size_bytes": 10,
                        "sha256": f"sha256:{index}",
                        "parse_status": "parsed",
                    }
                )
                entities.append(
                    {
                        "entity_id": f"ent:duplicate:{index}",
                        "project": "demo",
                        "source_id": source_id,
                        "name": "duplicate",
                        "kind": "function",
                        "path": f"file{index}.py",
                        "line_start": 1,
                        "line_end": 2,
                        "extractor": "test",
                        "confidence": 0.9,
                    }
                )
            write_jsonl(bundle / "source_inventory.jsonl", sources)
            write_jsonl(bundle / "entity_index.jsonl", entities)
            write_jsonl(bundle / "relation_graph.jsonl", [])
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
            distracting = [item for item in signals if item["attribute"] == "distracting_info"]
            self.assertEqual(len(distracting), 2)
            self.assertEqual({item["axis"] for item in distracting}, {2})

    def test_signal_builder_emits_conditional_behavior_on_axis_three(self):
        with tempfile.TemporaryDirectory() as tmp:
            bundle = Path(tmp) / "bundle"
            bundle.mkdir()
            write_jsonl(
                bundle / "source_inventory.jsonl",
                [
                    {
                        "source_id": "src:code",
                        "project": "demo",
                        "source_set_id": "main",
                        "repo_name": "demo",
                        "path": "main.py",
                        "relative_path": "main.py",
                        "modality": "code",
                        "source_type": "code.python",
                        "authority": "primary_source",
                        "language": "python",
                        "line_count": 10,
                        "size_bytes": 10,
                        "sha256": "sha256:1",
                        "parse_status": "parsed",
                    }
                ],
            )
            write_jsonl(
                bundle / "entity_index.jsonl",
                [
                    {
                        "entity_id": "ent:target",
                        "project": "demo",
                        "source_id": "src:code",
                        "name": "target",
                        "kind": "function",
                        "path": "main.py",
                        "line_start": 1,
                        "line_end": 2,
                        "extractor": "test",
                        "confidence": 0.9,
                    }
                ],
            )
            write_jsonl(
                bundle / "relation_graph.jsonl",
                [
                    {
                        "relation_id": "rel:condition",
                        "project": "demo",
                        "subject": {"type": "source", "id": "src:code", "name": "main.py"},
                        "predicate": "checks_condition",
                        "object": {"type": "entity", "id": "ent:target", "name": "target"},
                        "evidence": [
                            {
                                "source_id": "src:code",
                                "path": "main.py",
                                "lines": "4",
                                "summary": "main.py checks target condition",
                            }
                        ],
                        "extractor": "test",
                        "confidence": 0.8,
                    }
                ],
            )
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
            conditional = [item for item in signals if item["attribute"] == "conditional_behavior"]
            self.assertEqual(len(conditional), 1)
            self.assertEqual(conditional[0]["axis"], 3)

    def test_signal_builder_does_not_label_reads_as_conditional_behavior(self):
        with tempfile.TemporaryDirectory() as tmp:
            bundle = Path(tmp) / "bundle"
            bundle.mkdir()
            write_jsonl(
                bundle / "source_inventory.jsonl",
                [
                    {
                        "source_id": "src:code",
                        "project": "demo",
                        "source_set_id": "main",
                        "repo_name": "demo",
                        "path": "main.py",
                        "relative_path": "main.py",
                        "modality": "code",
                        "source_type": "code.python",
                        "authority": "primary_source",
                        "language": "python",
                        "line_count": 10,
                        "size_bytes": 10,
                        "sha256": "sha256:1",
                        "parse_status": "parsed",
                    }
                ],
            )
            write_jsonl(bundle / "entity_index.jsonl", [])
            write_jsonl(
                bundle / "relation_graph.jsonl",
                [
                    {
                        "relation_id": "rel:read",
                        "project": "demo",
                        "subject": {"type": "source", "id": "src:code", "name": "main.py"},
                        "predicate": "reads",
                        "object": {"type": "source", "id": "src:code", "name": "main.py"},
                        "evidence": [
                            {
                                "source_id": "src:code",
                                "path": "main.py",
                                "lines": "4",
                                "summary": "main.py reads value",
                            }
                        ],
                        "extractor": "test",
                        "confidence": 0.8,
                    }
                ],
            )
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
            conditional = [item for item in signals if item["attribute"] == "conditional_behavior"]
            self.assertEqual(conditional, [])

    def test_signal_builder_emits_conditional_behavior_from_source_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            source = tmpdir / "main.py"
            source.write_text("def launch(count):\n    if count == 0:\n        return\n", encoding="utf-8")
            bundle = tmpdir / "bundle"
            bundle.mkdir()
            write_jsonl(
                bundle / "source_inventory.jsonl",
                [
                    {
                        "source_id": "src:code",
                        "project": "demo",
                        "source_set_id": "main",
                        "repo_name": "demo",
                        "path": str(source),
                        "relative_path": "main.py",
                        "modality": "code",
                        "source_type": "code.python",
                        "authority": "primary_source",
                        "language": "python",
                        "line_count": 3,
                        "size_bytes": source.stat().st_size,
                        "sha256": "sha256:1",
                        "parse_status": "parsed",
                    }
                ],
            )
            write_jsonl(bundle / "entity_index.jsonl", [])
            write_jsonl(bundle / "relation_graph.jsonl", [])
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
            conditional = [item for item in signals if item["attribute"] == "conditional_behavior"]
            self.assertEqual(len(conditional), 1)
            self.assertEqual(conditional[0]["axis"], 3)

    def test_generated_context_signal_indexes_include_axis_three_signals(self):
        for signal_index in (
            ROOT / "runs" / "nvdla_context_bundle" / "signal_index.jsonl",
            ROOT / "runs" / "vortex_context_bundle" / "signal_index.jsonl",
        ):
            if not signal_index.exists():
                self.skipTest(f"missing local artifact: {signal_index}")
            axes = {
                json.loads(line)["axis"]
                for line in signal_index.read_text(encoding="utf-8").splitlines()
                if line.strip()
            }

            self.assertIn(3, axes, signal_index)


if __name__ == "__main__":
    unittest.main()
