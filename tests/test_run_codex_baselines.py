import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "run_codex_baselines.py"


def load_module():
    spec = importlib.util.spec_from_file_location("run_codex_baselines", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class RunCodexBaselinesTest(unittest.TestCase):
    def test_oracle_prompt_includes_gold_evidence_and_not_repo_search(self):
        runner = load_module()
        row = {
            "case_id": "case-1",
            "query": "BDMA zero transfer 会 launch 吗？",
            "evidence": [
                {
                    "evidence_id": "E1",
                    "path": "repo/a.c",
                    "source_id": "src:a",
                    "lines": "10-12",
                    "statement": "zero transfer exits before launch",
                    "text": "if (num_transfers == 0) goto exit;",
                }
            ],
        }

        prompt = runner.build_oracle_prompt(row)

        self.assertIn("case-1", prompt)
        self.assertIn("BDMA zero transfer", prompt)
        self.assertIn("repo/a.c:10-12", prompt)
        self.assertIn("if (num_transfers == 0)", prompt)
        self.assertIn("Do not inspect the repository", prompt)

    def test_grep_prompt_limits_agent_to_repo_and_basic_shell_search(self):
        runner = load_module()
        row = {"case_id": "case-2", "query": "Runtime::load 做什么？"}

        prompt = runner.build_grep_agent_prompt(row, repo_paths=["repo_sources/nvdla"])

        self.assertIn("case-2", prompt)
        self.assertIn("Runtime::load", prompt)
        self.assertIn("repo_sources/nvdla", prompt)
        self.assertIn("rg", prompt)
        self.assertIn("sed -n", prompt)
        self.assertIn("Do not use the benchmark gold evidence", prompt)

    def test_codex_command_uses_exec_schema_and_read_only_sandbox(self):
        runner = load_module()
        command = runner.codex_command(
            cwd=ROOT,
            schema_path=ROOT / "schemas" / "baseline-prediction.schema.json",
            output_path=Path("/tmp/out.json"),
            model="gpt-5.4-mini",
        )

        self.assertEqual(command[0], "codex")
        self.assertIn("exec", command)
        self.assertLess(command.index("--ask-for-approval"), command.index("exec"))
        self.assertIn("--output-schema", command)
        self.assertIn("--output-last-message", command)
        self.assertIn("--sandbox", command)
        self.assertIn("read-only", command)
        self.assertIn("--skip-git-repo-check", command)

    def test_codex_command_can_enable_json_event_stream(self):
        runner = load_module()
        command = runner.codex_command(
            cwd=ROOT,
            schema_path=ROOT / "schemas" / "baseline-prediction.schema.json",
            output_path=Path("/tmp/out.json"),
            model="gpt-5.4-mini",
            json_events=True,
        )

        self.assertIn("--json", command)
        self.assertGreater(command.index("--json"), command.index("exec"))

    def test_extract_codex_usage_reads_latest_token_count_event(self):
        runner = load_module()
        stdout = "\n".join(
            [
                json.dumps({"type": "session.started"}),
                json.dumps(
                    {
                        "type": "event_msg",
                        "payload": {
                            "type": "token_count",
                            "info": {
                                "total_token_usage": {
                                    "input_tokens": 10,
                                    "cached_input_tokens": 2,
                                    "output_tokens": 3,
                                    "reasoning_output_tokens": 1,
                                    "total_tokens": 13,
                                },
                                "last_token_usage": {"total_tokens": 13},
                                "model_context_window": 1000,
                            },
                            "rate_limits": {"primary": "ok"},
                        },
                    }
                ),
                "not json",
                json.dumps(
                    {
                        "type": "token_count",
                        "info": {
                            "total_token_usage": {
                                "input_tokens": 30,
                                "cached_input_tokens": 4,
                                "output_tokens": 5,
                                "reasoning_output_tokens": 2,
                                "total_tokens": 35,
                            },
                            "last_token_usage": {"total_tokens": 9},
                            "model_context_window": 1000,
                        },
                    }
                ),
            ]
        )

        usage = runner.extract_codex_usage(stdout)

        self.assertEqual(usage["total_token_usage"]["total_tokens"], 35)
        self.assertEqual(usage["last_token_usage"]["total_tokens"], 9)
        self.assertIn("model_context_window", usage)

    def test_extract_codex_usage_reads_turn_completed_usage_event(self):
        runner = load_module()
        stdout = "\n".join(
            [
                json.dumps({"type": "thread.started"}),
                json.dumps(
                    {
                        "type": "turn.completed",
                        "usage": {
                            "input_tokens": 31310,
                            "cached_input_tokens": 4480,
                            "output_tokens": 513,
                            "reasoning_output_tokens": 506,
                        },
                    }
                ),
            ]
        )

        usage = runner.extract_codex_usage(stdout)

        self.assertEqual(usage["total_token_usage"]["input_tokens"], 31310)
        self.assertEqual(usage["total_token_usage"]["cached_input_tokens"], 4480)
        self.assertEqual(usage["total_token_usage"]["output_tokens"], 513)
        self.assertEqual(usage["total_token_usage"]["reasoning_output_tokens"], 506)
        self.assertEqual(usage["total_token_usage"]["total_tokens"], 31823)
        self.assertEqual(usage["last_token_usage"]["total_tokens"], 31823)

    def test_oracle_prediction_preserves_gold_evidence_with_snippets(self):
        runner = load_module()
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            source = tmpdir / "repo" / "a.c"
            source.parent.mkdir()
            source.write_text("one\ntwo\nthree\nfour\n", encoding="utf-8")
            row = {
                "case_id": "case-3",
                "evidence": [
                    {
                        "evidence_id": "E1",
                        "path": "repo/a.c",
                        "source_id": "src:a",
                        "lines": "2-3",
                    }
                ],
            }
            model_json = {"case_id": "case-3", "pred_answer": "answer `repo/a.c:2-3`"}

            prediction = runner.build_prediction_row(
                benchmark_row=row,
                model_json=model_json,
                evidence_source="gold",
                repo_root=tmpdir,
            )

            self.assertEqual(prediction["case_id"], "case-3")
            self.assertEqual(prediction["pred_answer"], "answer `repo/a.c:2-3`")
            self.assertEqual(prediction["evidence"][0]["path"], "repo/a.c")
            self.assertEqual(prediction["evidence"][0]["lines"], "2-3")
            self.assertEqual(prediction["evidence"][0]["text"], "two\nthree")


if __name__ == "__main__":
    unittest.main()
