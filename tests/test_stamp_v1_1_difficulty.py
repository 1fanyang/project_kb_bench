import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "stamp_v1_1_difficulty.py"


def load_module():
    spec = importlib.util.spec_from_file_location("stamp_v1_1_difficulty", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def write_jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


class StampV11DifficultyTest(unittest.TestCase):
    def test_stamp_row_adds_answerability_difficulty_and_claim_sources(self):
        stamper = load_module()
        row = {
            "case_id": "case-1",
            "layer": {"code": "L2"},
            "evidence": [
                {"evidence_id": "E1", "source_id": "src:a", "path": "repo/a.py"},
                {"evidence_id": "E2", "source_id": "src:b", "path": "repo/b.py"},
            ],
        }
        signals = [
            {
                "signal_id": "sig:axis2:long-tail",
                "axis": 2,
                "attribute": "long_tail",
                "anchor": {"source_id": "src:a"},
            },
            {
                "signal_id": "sig:axis2:cross-file",
                "axis": 2,
                "attribute": "cross_file",
                "anchor": {"path": "repo/b.py"},
            },
            {
                "signal_id": "sig:axis2:long-tail-duplicate",
                "axis": 2,
                "attribute": "long_tail",
                "anchor": {"source_id": "src:b"},
            },
            {
                "signal_id": "sig:axis3:doc-code",
                "axis": 3,
                "attribute": "doc_code_divergence",
                "anchor": {"source_id": "src:a"},
            },
            {
                "signal_id": "sig:ignored",
                "axis": 3,
                "attribute": "snapshot_gap",
                "anchor": {"source_id": "src:missing"},
            },
        ]

        stamped = stamper.stamp_row(row, signals)

        self.assertIsNot(stamped, row)
        self.assertNotIn("answerability", row)
        self.assertNotIn("difficulty", row)
        self.assertEqual(stamped["answerability"], "answerable")
        self.assertEqual(stamped["difficulty"]["axis1_layer"], "L2")
        self.assertEqual(stamped["difficulty"]["axis2_retrieval"], ["cross_file", "long_tail"])
        self.assertEqual(
            stamped["difficulty"]["axis3_reasoning"],
            ["doc_code_divergence"],
        )
        self.assertEqual(
            stamped["difficulty"]["claim_sources"],
            {
                "cross_file": ["sig:axis2:cross-file"],
                "doc_code_divergence": ["sig:axis3:doc-code"],
                "long_tail": ["sig:axis2:long-tail", "sig:axis2:long-tail-duplicate"],
            },
        )
        stamped_attributes = (
            stamped["difficulty"]["axis2_retrieval"]
            + stamped["difficulty"]["axis3_reasoning"]
        )
        for attribute in stamped_attributes:
            self.assertIn(attribute, stamped["difficulty"]["claim_sources"])

    def test_stamp_row_preserves_existing_answerability_and_defaults_layer(self):
        stamper = load_module()
        row = {
            "case_id": "case-unanswerable",
            "answerability": "unanswerable_missing_evidence",
            "evidence": [{"source_id": "src:a"}],
        }

        stamped = stamper.stamp_row(row, [])

        self.assertEqual(stamped["answerability"], "unanswerable_missing_evidence")
        self.assertEqual(stamped["difficulty"]["axis1_layer"], "L1")
        self.assertEqual(stamped["difficulty"]["axis2_retrieval"], [])
        self.assertEqual(stamped["difficulty"]["axis3_reasoning"], [])
        self.assertEqual(stamped["difficulty"]["claim_sources"], {})

    def test_cli_reads_benchmark_and_signal_index_and_writes_stamped_jsonl(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            benchmark = root / "benchmark.jsonl"
            bundle = root / "context_bundle"
            output = root / "out" / "stamped.jsonl"
            write_jsonl(
                benchmark,
                [
                    {
                        "case_id": "case-1",
                        "layer": {"code": "L3"},
                        "evidence": [{"source_id": "src:a", "path": "repo/a.py"}],
                    }
                ],
            )
            write_jsonl(
                bundle / "signal_index.jsonl",
                [
                    {
                        "signal_id": "sig:axis2:long-tail",
                        "axis": 2,
                        "attribute": "long_tail",
                        "anchor": {"source_id": "src:a"},
                    },
                    {
                        "signal_id": "sig:axis3:multi-hop",
                        "axis": 3,
                        "attribute": "multi_hop_reasoning",
                        "anchor": {"path": "repo/a.py"},
                    },
                ],
            )

            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    str(benchmark),
                    "--context-bundle",
                    str(bundle),
                    "--output",
                    str(output),
                ],
                cwd=ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(result.stdout.strip(), f"Wrote 1 stamped rows to {output}")
            rows = [
                json.loads(line)
                for line in output.read_text(encoding="utf-8").splitlines()
            ]
            self.assertEqual(len(rows), 1)
            difficulty = rows[0]["difficulty"]
            self.assertEqual(difficulty["axis1_layer"], "L3")
            self.assertEqual(difficulty["axis2_retrieval"], ["long_tail"])
            self.assertEqual(difficulty["axis3_reasoning"], ["multi_hop_reasoning"])
            difficulty_attributes = (
                difficulty["axis2_retrieval"] + difficulty["axis3_reasoning"]
            )
            for attribute in difficulty_attributes:
                self.assertIn(attribute, difficulty["claim_sources"])


if __name__ == "__main__":
    unittest.main()
