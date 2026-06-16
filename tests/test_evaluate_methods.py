import argparse
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "evaluate_methods.py"


def load_module():
    spec = importlib.util.spec_from_file_location("evaluate_methods", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class EvaluateMethodsTest(unittest.TestCase):
    def test_retrieval_scores_require_path_and_line_overlap(self):
        evaluator = load_module()
        gold = {
            "references": [{"path": "repo/a.c", "source_id": "src:a"}],
            "evidence": [
                {"evidence_id": "E1", "path": "repo/a.c", "source_id": "src:a", "lines": "10-20"},
                {"evidence_id": "E2", "path": "repo/b.c", "source_id": "src:b", "lines": "5-6"},
            ],
        }
        pred = {
            "evidence": [
                {"rank": 1, "path": "repo/a.c", "source_id": "src:a", "lines": "15-16"},
                {"rank": 2, "path": "repo/c.c", "source_id": "src:c", "lines": "1-2"},
            ]
        }

        scores = evaluator.score_retrieval(gold, pred, top_k=10)

        self.assertEqual(scores["matched_evidence_ids"], ["E1"])
        self.assertEqual(scores["evidence_recall_at_k"], 0.5)
        self.assertEqual(scores["evidence_precision_at_k"], 0.5)
        self.assertEqual(scores["reference_recall_at_k"], 1.0)

    def test_citation_pass_requires_gold_evidence_path_line_in_pred_answer(self):
        evaluator = load_module()
        gold = {
            "evidence": [
                {"evidence_id": "E1", "path": "repo/a.c", "source_id": "src:a", "lines": "10-20"},
                {"evidence_id": "E2", "path": "repo/b.c", "source_id": "src:b", "lines": "5"},
            ],
            "answer_rubric": {
                "citation_policy": {
                    "required": "always",
                    "acceptable_granularity": "path_line",
                    "required_evidence_ids": ["E1"],
                }
            },
        }

        self.assertTrue(evaluator.citation_pass(gold, "答案见 `repo/a.c:10-20`。"))
        self.assertTrue(evaluator.citation_pass(gold, "答案见 `repo/a.c:15`。"))
        self.assertFalse(evaluator.citation_pass(gold, "答案见 `repo/a.c`。"))

    def test_cli_aggregates_llm_judge_scores(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            benchmark = tmpdir / "benchmark.jsonl"
            preds = tmpdir / "preds.jsonl"
            judge = tmpdir / "judge.py"
            output = tmpdir / "report.json"
            markdown = tmpdir / "report.md"

            case = {
                "case_id": "case-1",
                "query": "q",
                "expected_answer": "标准答案",
                "references": [{"path": "repo/a.c", "source_id": "src:a"}],
                "evidence": [
                    {"evidence_id": "E1", "path": "repo/a.c", "source_id": "src:a", "lines": "10-20"}
                ],
                "answer_rubric": {
                    "citation_policy": {
                        "required": "always",
                        "acceptable_granularity": "path_line",
                        "required_evidence_ids": ["E1"],
                    }
                },
            }
            pred = {
                "case_id": "case-1",
                "pred_answer": "标准答案 `repo/a.c:10-20`",
                "evidence": [
                    {"rank": 1, "path": "repo/a.c", "source_id": "src:a", "lines": "10-20", "text": "..."}
                ],
            }
            benchmark.write_text(json.dumps(case, ensure_ascii=False) + "\n", encoding="utf-8")
            preds.write_text(json.dumps(pred, ensure_ascii=False) + "\n", encoding="utf-8")
            judge.write_text(
                "import json, sys\n"
                "payload = json.load(sys.stdin)\n"
                "assert payload['case_id'] == 'case-1'\n"
                "print(json.dumps({'score': 0.92, 'verdict': 'correct', 'rationale': 'matches'}))\n",
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    str(benchmark),
                    str(preds),
                    "--llm-judge-command",
                    f"{sys.executable} {judge}",
                    "--output-json",
                    str(output),
                    "--output-md",
                    str(markdown),
                ],
                cwd=ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(report["summary"]["cases"], 1)
            self.assertEqual(report["summary"]["strict_e2e_pass_rate"], 1.0)
            self.assertEqual(report["summary"]["mean_llm_judge_score"], 0.92)
            self.assertIn("LLM Judge", markdown.read_text(encoding="utf-8"))

    def test_evaluation_report_aggregates_prediction_token_usage(self):
        evaluator = load_module()
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            benchmark = tmpdir / "benchmark.jsonl"
            preds = tmpdir / "preds.jsonl"

            case = {
                "case_id": "case-1",
                "query": "q",
                "expected_answer": "标准答案",
                "references": [{"path": "repo/a.c", "source_id": "src:a"}],
                "evidence": [{"evidence_id": "E1", "path": "repo/a.c", "source_id": "src:a"}],
                "answer_rubric": {"citation_policy": {"required": "never"}},
            }
            pred = {
                "case_id": "case-1",
                "pred_answer": "标准答案",
                "evidence": [{"rank": 1, "path": "repo/a.c", "source_id": "src:a"}],
                "prompt_chars": 321,
                "token_usage": {
                    "source": "codex_exec_json",
                    "events_seen": 1,
                    "total_token_usage": {
                        "input_tokens": 100,
                        "cached_input_tokens": 20,
                        "output_tokens": 30,
                        "reasoning_output_tokens": 5,
                        "total_tokens": 130,
                    },
                    "last_token_usage": {"total_tokens": 40},
                },
            }
            benchmark.write_text(json.dumps(case, ensure_ascii=False) + "\n", encoding="utf-8")
            preds.write_text(json.dumps(pred, ensure_ascii=False) + "\n", encoding="utf-8")
            args = argparse.Namespace(
                benchmark=benchmark,
                predictions=preds,
                repo_root=ROOT,
                top_k=10,
                judge_threshold=0.8,
                llm_judge_command=None,
                llm_judge_provider=None,
                llm_judge_api_key_env="DEEPSEEK_API_KEY",
                llm_judge_base_url="https://api.deepseek.com",
                llm_judge_model="deepseek-v4-pro",
                llm_judge_temperature=0.0,
                llm_judge_thinking=None,
                llm_judge_reasoning_effort=None,
                judge_timeout=60.0,
                require_llm_judge=False,
                output_json=None,
                output_md=None,
            )

            report, exit_code = evaluator.evaluate(args)

        self.assertEqual(exit_code, 0)
        summary = report["summary"]
        self.assertEqual(summary["token_usage_coverage"], 1.0)
        self.assertEqual(summary["mean_total_tokens"], 130)
        self.assertEqual(summary["sum_total_tokens"], 130)
        self.assertEqual(summary["mean_cached_input_tokens"], 20)
        self.assertEqual(report["cases"][0]["total_tokens"], 130)
        self.assertEqual(report["cases"][0]["prompt_chars"], 321)

    def test_cli_calls_deepseek_compatible_judge(self):
        evaluator = load_module()
        captured = {}

        class FakeResponse:
            def __enter__(self):
                content = json.dumps(
                    {"score": 0.86, "verdict": "correct", "rationale": "semantically matches"},
                    ensure_ascii=False,
                )
                self.payload = json.dumps(
                    {
                        "choices": [{"message": {"content": content}}],
                        "usage": {"prompt_tokens": 12, "completion_tokens": 8},
                    }
                ).encode("utf-8")
                return self

            def __exit__(self, *_args):
                return False

            def read(self):
                return self.payload

        def fake_urlopen(request, timeout):
            captured["url"] = request.full_url
            captured["timeout"] = timeout
            captured["authorization"] = request.headers.get("Authorization")
            captured["body"] = json.loads(request.data.decode("utf-8"))
            return FakeResponse()

        old_key = os.environ.get("DEEPSEEK_API_KEY")
        os.environ["DEEPSEEK_API_KEY"] = "test-key"

        def restore_key():
            if old_key is None:
                os.environ.pop("DEEPSEEK_API_KEY", None)
            else:
                os.environ["DEEPSEEK_API_KEY"] = old_key

        self.addCleanup(restore_key)

        config = evaluator.JudgeConfig(
            provider="deepseek",
            command=None,
            timeout=7.0,
            threshold=0.8,
            api_key_env="DEEPSEEK_API_KEY",
            base_url="https://api.deepseek.com",
            model="deepseek-v4-pro",
            temperature=0.0,
            thinking=None,
            reasoning_effort=None,
        )
        payload = {"case_id": "case-2", "query": "q", "pred_answer": "标准答案"}

        with mock.patch.object(evaluator.urlrequest, "urlopen", side_effect=fake_urlopen):
            result = evaluator.run_deepseek_judge(config, payload)

        self.assertEqual(result.score, 0.86)
        self.assertEqual(result.verdict, "correct")
        self.assertEqual(captured["url"], "https://api.deepseek.com/chat/completions")
        self.assertEqual(captured["timeout"], 7.0)
        self.assertEqual(captured["authorization"], "Bearer test-key")
        self.assertEqual(captured["body"]["model"], "deepseek-v4-pro")
        self.assertEqual(captured["body"]["response_format"], {"type": "json_object"})

    def test_deepseek_judge_rejects_key_value_as_env_name_without_leaking_it(self):
        evaluator = load_module()
        mistaken_key_value = "sk-test-secret"
        config = evaluator.JudgeConfig(
            provider="deepseek",
            command=None,
            timeout=7.0,
            threshold=0.8,
            api_key_env=mistaken_key_value,
            base_url="https://api.deepseek.com",
            model="deepseek-v4-pro",
            temperature=0.0,
            thinking=None,
            reasoning_effort=None,
        )

        result = evaluator.run_deepseek_judge(config, {"case_id": "case-3"})

        self.assertEqual(result.verdict, "error")
        self.assertNotIn(mistaken_key_value, result.rationale)
        self.assertNotIn(mistaken_key_value, result.error or "")
        self.assertIn("environment variable name", result.error or "")

    def test_evaluation_report_redacts_invalid_api_key_env_name(self):
        evaluator = load_module()
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            benchmark = tmpdir / "benchmark.jsonl"
            preds = tmpdir / "preds.jsonl"
            mistaken_key_value = "sk-test-secret"

            case = {
                "case_id": "case-1",
                "query": "q",
                "expected_answer": "标准答案",
                "references": [{"path": "repo/a.c", "source_id": "src:a"}],
                "evidence": [{"evidence_id": "E1", "path": "repo/a.c", "source_id": "src:a"}],
                "answer_rubric": {"citation_policy": {"required": "never"}},
            }
            pred = {
                "case_id": "case-1",
                "pred_answer": "标准答案",
                "evidence": [{"rank": 1, "path": "repo/a.c", "source_id": "src:a"}],
            }
            benchmark.write_text(json.dumps(case, ensure_ascii=False) + "\n", encoding="utf-8")
            preds.write_text(json.dumps(pred, ensure_ascii=False) + "\n", encoding="utf-8")

            args = argparse.Namespace(
                benchmark=benchmark,
                predictions=preds,
                repo_root=ROOT,
                top_k=10,
                judge_threshold=0.8,
                llm_judge_command=None,
                llm_judge_provider="deepseek",
                llm_judge_api_key_env=mistaken_key_value,
                llm_judge_base_url="https://api.deepseek.com",
                llm_judge_model="deepseek-v4-pro",
                llm_judge_temperature=0.0,
                llm_judge_thinking=None,
                llm_judge_reasoning_effort=None,
                judge_timeout=60.0,
                require_llm_judge=True,
                output_json=None,
                output_md=None,
            )

            report, exit_code = evaluator.evaluate(args)

        serialized = json.dumps(report, ensure_ascii=False)
        self.assertEqual(exit_code, 2)
        self.assertNotIn(mistaken_key_value, serialized)
        self.assertEqual(
            report["config"]["llm_judge_api_key_env"], "<invalid-env-name-redacted>"
        )


if __name__ == "__main__":
    unittest.main()
