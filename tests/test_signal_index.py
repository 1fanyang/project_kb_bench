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
