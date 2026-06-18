import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills" / "benchmark-validator" / "scripts" / "adversarial_gate.py"


class AdversarialGateTest(unittest.TestCase):
    def test_dry_run_writes_one_record_per_claim(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            benchmark = tmpdir / "benchmark.jsonl"
            output = tmpdir / "gate.jsonl"
            row = {
                "case_id": "case-1",
                "difficulty": {
                    "axis1_layer": "L2",
                    "axis2_retrieval": ["long_tail"],
                    "axis3_reasoning": ["conditional_behavior"],
                    "claim_sources": {
                        "long_tail": ["sig:demo:a"],
                        "conditional_behavior": ["sig:demo:b"],
                    },
                },
            }
            benchmark.write_text(json.dumps(row, ensure_ascii=False) + "\n", encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    str(benchmark),
                    "--dry-run",
                    "--output-jsonl",
                    str(output),
                ],
                cwd=ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            records = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
            self.assertEqual([record["attribute"] for record in records], ["long_tail", "conditional_behavior"])
            self.assertTrue(all(record["status"] == "skipped_no_provider" for record in records))


if __name__ == "__main__":
    unittest.main()
