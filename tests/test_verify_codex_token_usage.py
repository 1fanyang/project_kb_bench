import importlib.util
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "verify_codex_token_usage.py"


def load_module():
    spec = importlib.util.spec_from_file_location("verify_codex_token_usage", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class VerifyCodexTokenUsageTest(unittest.TestCase):
    def test_summarize_run_exposes_total_and_last_token_usage(self):
        verifier = load_module()
        usage = {
            "total_token_usage": {
                "input_tokens": 100,
                "cached_input_tokens": 20,
                "output_tokens": 30,
                "reasoning_output_tokens": 5,
                "total_tokens": 130,
            },
            "last_token_usage": {
                "input_tokens": 60,
                "cached_input_tokens": 10,
                "output_tokens": 8,
                "reasoning_output_tokens": 1,
                "total_tokens": 68,
            },
            "model_context_window": 258400,
        }

        summary = verifier.summarize_run(
            baseline="oracle",
            prompt="abc",
            usage=usage,
            model_json={"case_id": "case-1", "pred_answer": "答案"},
            token_count_events_seen=2,
        )

        self.assertEqual(summary["baseline"], "oracle")
        self.assertEqual(summary["prompt_chars"], 3)
        self.assertEqual(summary["token_count_events_seen"], 2)
        self.assertEqual(summary["total_tokens"], 130)
        self.assertEqual(summary["input_tokens"], 100)
        self.assertEqual(summary["cached_input_tokens"], 20)
        self.assertEqual(summary["output_tokens"], 30)
        self.assertEqual(summary["reasoning_output_tokens"], 5)
        self.assertEqual(summary["last_total_tokens"], 68)
        self.assertEqual(summary["model_context_window"], 258400)
        self.assertEqual(summary["raw_usage"], usage)

    def test_usage_event_count_supports_turn_completed_usage(self):
        verifier = load_module()
        stdout = "\n".join(
            [
                json.dumps({"type": "thread.started"}),
                json.dumps({"type": "turn.completed", "usage": {"total_tokens": 42}}),
            ]
        )

        self.assertEqual(verifier.usage_event_count(stdout), 1)

    def test_build_comparison_report_marks_grep_agent_more_expensive(self):
        verifier = load_module()
        oracle = {"baseline": "oracle", "total_tokens": 120, "raw_usage": {}}
        grep = {"baseline": "grep-agent", "total_tokens": 600, "raw_usage": {}}

        report = verifier.build_comparison_report(
            benchmark=Path("runs/nvdla_benchmark_v1.jsonl"),
            case_id="case-1",
            model="gpt-5.4-mini",
            repo_paths=["repo_sources/nvdla"],
            oracle_run=oracle,
            grep_run=grep,
        )

        self.assertEqual(report["case_id"], "case-1")
        self.assertEqual(report["runs"]["oracle"]["total_tokens"], 120)
        self.assertEqual(report["runs"]["grep-agent"]["total_tokens"], 600)
        self.assertEqual(report["comparison"]["grep_minus_oracle_total_tokens"], 480)
        self.assertEqual(report["comparison"]["grep_to_oracle_total_token_ratio"], 5.0)
        self.assertTrue(report["comparison"]["oracle_less_than_grep"])


if __name__ == "__main__":
    unittest.main()
