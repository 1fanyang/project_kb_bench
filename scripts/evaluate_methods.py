#!/usr/bin/env python3
"""Evaluate benchmark method outputs with retrieval evidence and LLM judging.

This script is intentionally separate from the benchmark validator. The
validator checks whether a benchmark is well-formed; this runner scores a
method's predictions against a finished benchmark.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import statistics
import subprocess
import sys
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from urllib import error as urlerror
from urllib import request as urlrequest


LINE_RANGE_RE = re.compile(r"^(\d+)(?:-(\d+))?$")
CITATION_RE = re.compile(r"(?P<path>[\w./@+-]+):(?P<lines>\d+(?:-\d+)?)")
ENV_VAR_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
SECRET_TOKEN_RE = re.compile(r"(?i)\b(?:sk|ds)-[A-Za-z0-9_-]{8,}\b")


@dataclass
class JudgeResult:
    score: float | None
    verdict: str
    rationale: str
    raw: dict[str, Any] | None = None
    error: str | None = None


@dataclass
class JudgeConfig:
    provider: str | None
    command: str | None
    timeout: float
    threshold: float
    api_key_env: str
    base_url: str
    model: str
    temperature: float
    thinking: str | None
    reasoning_effort: str | None


@dataclass
class CaseResult:
    case_id: str
    reference_recall_at_k: float
    evidence_recall_at_k: float
    evidence_precision_at_k: float
    evidence_f1_at_k: float
    matched_evidence_ids: list[str]
    citation_pass: bool
    llm_judge_score: float | None
    llm_judge_verdict: str
    llm_judge_rationale: str
    llm_judge_error: str | None
    answer_pass: bool
    retrieval_pass: bool
    strict_e2e_pass: bool
    missing_prediction: bool
    notes: list[str]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate method predictions against a benchmark JSONL."
    )
    parser.add_argument("benchmark", type=Path, help="Benchmark JSONL")
    parser.add_argument("predictions", type=Path, help="Method output JSONL")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--judge-threshold", type=float, default=0.8)
    parser.add_argument(
        "--llm-judge-command",
        help=(
            "External judge command. It receives one JSON payload on stdin and "
            "must print JSON with score, verdict, and rationale."
        ),
    )
    parser.add_argument(
        "--llm-judge-provider",
        choices=["command", "deepseek"],
        help="LLM judge backend. Defaults to command when --llm-judge-command is set.",
    )
    parser.add_argument(
        "--llm-judge-api-key-env",
        default="DEEPSEEK_API_KEY",
        help=(
            "Name of the environment variable containing the API key for "
            "provider-backed judges, for example DEEPSEEK_API_KEY. Do not pass "
            "the API key value here."
        ),
    )
    parser.add_argument(
        "--llm-judge-base-url",
        default=os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
        help="OpenAI-compatible base URL for provider-backed judges.",
    )
    parser.add_argument(
        "--llm-judge-model",
        default=os.environ.get("DEEPSEEK_MODEL", "deepseek-v4-pro"),
        help="Model name for provider-backed judges.",
    )
    parser.add_argument("--llm-judge-temperature", type=float, default=0.0)
    parser.add_argument(
        "--llm-judge-thinking",
        choices=["enabled", "disabled"],
        help="Optional DeepSeek thinking mode setting.",
    )
    parser.add_argument(
        "--llm-judge-reasoning-effort",
        help="Optional DeepSeek reasoning_effort value, for example low/medium/high.",
    )
    parser.add_argument("--judge-timeout", type=float, default=60.0)
    parser.add_argument("--require-llm-judge", action="store_true")
    parser.add_argument("--output-json", type=Path)
    parser.add_argument("--output-md", type=Path)
    return parser.parse_args()


def judge_config_from_args(args: argparse.Namespace) -> JudgeConfig:
    provider = args.llm_judge_provider
    if provider is None and args.llm_judge_command:
        provider = "command"
    return JudgeConfig(
        provider=provider,
        command=args.llm_judge_command,
        timeout=args.judge_timeout,
        threshold=args.judge_threshold,
        api_key_env=args.llm_judge_api_key_env,
        base_url=args.llm_judge_base_url,
        model=args.llm_judge_model,
        temperature=args.llm_judge_temperature,
        thinking=args.llm_judge_thinking,
        reasoning_effort=args.llm_judge_reasoning_effort,
    )


def valid_env_var_name(value: str) -> bool:
    return bool(ENV_VAR_NAME_RE.match(value))


def display_env_var_name(value: str) -> str:
    if valid_env_var_name(value):
        return value
    return "<invalid-env-name-redacted>"


def sanitize_report_text(value: Any) -> str:
    return SECRET_TOKEN_RE.sub("<redacted-secret>", str(value))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{lineno}: invalid JSON: {exc}") from exc
        if not isinstance(row, dict):
            raise ValueError(f"{path}:{lineno}: JSONL row must be an object")
        row["_line"] = lineno
        rows.append(row)
    return rows


def parse_line_range(value: Any) -> tuple[int, int] | None:
    if not isinstance(value, str) or not value:
        return None
    match = LINE_RANGE_RE.match(value)
    if not match:
        return None
    start = int(match.group(1))
    end = int(match.group(2) or start)
    if start <= 0 or end < start:
        return None
    return start, end


def ranges_overlap(left: tuple[int, int], right: tuple[int, int]) -> bool:
    return max(left[0], right[0]) <= min(left[1], right[1])


def same_source_or_path(gold: dict[str, Any], pred: dict[str, Any]) -> bool:
    gold_source = gold.get("source_id")
    pred_source = pred.get("source_id")
    if gold_source and pred_source and gold_source == pred_source:
        return True
    gold_path = gold.get("path")
    pred_path = pred.get("path")
    return bool(gold_path and pred_path and gold_path == pred_path)


def evidence_matches(gold: dict[str, Any], pred: dict[str, Any]) -> bool:
    if not same_source_or_path(gold, pred):
        return False
    gold_range = parse_line_range(gold.get("lines"))
    pred_range = parse_line_range(pred.get("lines"))
    if gold_range is None:
        return True
    if pred_range is None:
        return False
    return ranges_overlap(gold_range, pred_range)


def normalize_pred_evidence(prediction: dict[str, Any], top_k: int) -> list[dict[str, Any]]:
    evidence = prediction.get("evidence")
    if evidence is None:
        evidence = prediction.get("pred_evidence")
    if evidence is None:
        evidence = prediction.get("retrieved_contexts")
    if evidence is None:
        evidence = prediction.get("retrieved")
    if evidence is None:
        evidence = prediction.get("contexts")
    if not isinstance(evidence, list):
        return []

    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(evidence, 1):
        if not isinstance(item, dict):
            continue
        rank = item.get("rank", index)
        if not isinstance(rank, int):
            rank = index
        if rank <= top_k:
            clone = dict(item)
            clone["rank"] = rank
            normalized.append(clone)
    normalized.sort(key=lambda item: item.get("rank", 1_000_000))
    return normalized


def score_retrieval(
    benchmark_row: dict[str, Any], prediction: dict[str, Any], top_k: int
) -> dict[str, Any]:
    pred_evidence = normalize_pred_evidence(prediction, top_k)
    gold_references = [
        item for item in benchmark_row.get("references", []) if isinstance(item, dict)
    ]
    gold_evidence = [
        item for item in benchmark_row.get("evidence", []) if isinstance(item, dict)
    ]

    matched_references = 0
    for ref in gold_references:
        if any(same_source_or_path(ref, pred) for pred in pred_evidence):
            matched_references += 1

    matched_evidence_ids: list[str] = []
    for item in gold_evidence:
        if any(evidence_matches(item, pred) for pred in pred_evidence):
            matched_evidence_ids.append(str(item.get("evidence_id", "")))

    matched_pred_count = 0
    for pred in pred_evidence:
        if any(evidence_matches(item, pred) for item in gold_evidence):
            matched_pred_count += 1

    reference_recall = (
        matched_references / len(gold_references) if gold_references else 0.0
    )
    evidence_recall = (
        len(matched_evidence_ids) / len(gold_evidence) if gold_evidence else 0.0
    )
    evidence_precision = (
        matched_pred_count / len(pred_evidence) if pred_evidence else 0.0
    )
    if evidence_recall + evidence_precision:
        evidence_f1 = (
            2 * evidence_recall * evidence_precision / (evidence_recall + evidence_precision)
        )
    else:
        evidence_f1 = 0.0

    return {
        "reference_recall_at_k": reference_recall,
        "evidence_recall_at_k": evidence_recall,
        "evidence_precision_at_k": evidence_precision,
        "evidence_f1_at_k": evidence_f1,
        "matched_evidence_ids": matched_evidence_ids,
        "pred_evidence_count_at_k": len(pred_evidence),
    }


def citation_required(benchmark_row: dict[str, Any]) -> tuple[bool, str, set[str]]:
    rubric = benchmark_row.get("answer_rubric", {})
    policy = rubric.get("citation_policy", {}) if isinstance(rubric, dict) else {}
    required = policy.get("required", "always") if isinstance(policy, dict) else "always"
    if required == "never":
        return False, "path_line", set()
    granularity = (
        policy.get("acceptable_granularity", "path_line")
        if isinstance(policy, dict)
        else "path_line"
    )
    ids = policy.get("required_evidence_ids", []) if isinstance(policy, dict) else []
    if not isinstance(ids, list):
        ids = []
    return True, str(granularity), {str(item) for item in ids}


def citation_pass(benchmark_row: dict[str, Any], pred_answer: str) -> bool:
    required, granularity, required_ids = citation_required(benchmark_row)
    if not required:
        return True

    evidence_items = [
        item for item in benchmark_row.get("evidence", []) if isinstance(item, dict)
    ]
    selected = [
        item
        for item in evidence_items
        if not required_ids or str(item.get("evidence_id")) in required_ids
    ]
    if not selected:
        return False

    for item in selected:
        path = str(item.get("path", ""))
        source_id = str(item.get("source_id", ""))
        lines = item.get("lines")
        if granularity == "source_only":
            if source_id and source_id in pred_answer:
                continue
            if path and path in pred_answer:
                continue
            return False
        if granularity == "path_only":
            if path and path in pred_answer:
                continue
            return False
        if not lines:
            if path and path in pred_answer:
                continue
            return False
        gold_range = parse_line_range(lines)
        matched = False
        for citation in CITATION_RE.finditer(pred_answer):
            if citation.group("path") != path:
                continue
            cited_range = parse_line_range(citation.group("lines"))
            if gold_range and cited_range and ranges_overlap(gold_range, cited_range):
                matched = True
                break
        if not matched:
            return False
    return True


def normalize_verdict(value: Any) -> str:
    text = str(value or "").strip().lower()
    if text in {"correct", "pass", "passed", "yes", "true"}:
        return "correct"
    if text in {"partial", "partially_correct", "warn"}:
        return "partial"
    if text in {"incorrect", "fail", "failed", "no", "false"}:
        return "incorrect"
    if text in {"not_run", "error"}:
        return text
    return "unknown"


def build_judge_payload(
    benchmark_row: dict[str, Any],
    prediction: dict[str, Any],
) -> dict[str, Any]:
    return {
        "case_id": benchmark_row.get("case_id"),
        "query": benchmark_row.get("query"),
        "expected_answer": benchmark_row.get("expected_answer"),
        "pred_answer": prediction_answer(prediction),
        "gold_evidence": benchmark_row.get("evidence", []),
        "pred_evidence": normalize_pred_evidence(prediction, top_k=50),
        "answer_rubric": benchmark_row.get("answer_rubric", {}),
        "judge_instruction": (
            "Judge only answer semantic correctness for the query. Retrieval recall "
            "and citation formatting are scored separately by deterministic checks. "
            "Ignore harmless wording differences. Penalize unsupported, missing, "
            "or contradictory claims. Return JSON with score in [0,1], verdict "
            "correct|partial|incorrect, and rationale."
        ),
    }


def parse_judge_response(text: str) -> dict[str, Any]:
    try:
        raw = json.loads(text)
        if isinstance(raw, dict):
            return raw
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not match:
        raise json.JSONDecodeError("no JSON object found", text, 0)
    raw = json.loads(match.group(0))
    if not isinstance(raw, dict):
        raise json.JSONDecodeError("JSON payload is not an object", text, 0)
    return raw


def judge_result_from_raw(raw: dict[str, Any]) -> JudgeResult:
    score_value = raw.get("score")
    score: float | None
    if isinstance(score_value, (int, float)):
        score = float(score_value)
    elif isinstance(score_value, str):
        try:
            score = float(score_value)
        except ValueError:
            score = None
    else:
        score = None
    if score is not None:
        score = min(1.0, max(0.0, score))
    verdict = normalize_verdict(raw.get("verdict"))
    rationale = str(raw.get("rationale", ""))
    return JudgeResult(score=score, verdict=verdict, rationale=rationale, raw=raw)


def run_command_judge(
    config: JudgeConfig,
    payload: dict[str, Any],
) -> JudgeResult:
    if not config.command:
        return JudgeResult(
            score=None,
            verdict="not_run",
            rationale="No --llm-judge-command was provided.",
        )

    try:
        completed = subprocess.run(
            shlex.split(config.command),
            input=json.dumps(payload, ensure_ascii=False),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=config.timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return JudgeResult(
            score=None,
            verdict="error",
            rationale="LLM judge command failed before producing a result.",
            error=sanitize_report_text(exc),
        )

    if completed.returncode != 0:
        return JudgeResult(
            score=None,
            verdict="error",
            rationale="LLM judge command returned non-zero exit status.",
            error=sanitize_report_text(
                completed.stderr.strip() or f"exit status {completed.returncode}"
            ),
        )

    try:
        raw = parse_judge_response(completed.stdout)
    except json.JSONDecodeError as exc:
        return JudgeResult(
            score=None,
            verdict="error",
            rationale="LLM judge did not return valid JSON.",
            error=sanitize_report_text(f"{exc}: {completed.stdout[:500]}"),
        )
    return judge_result_from_raw(raw)


def run_deepseek_judge(config: JudgeConfig, payload: dict[str, Any]) -> JudgeResult:
    if not valid_env_var_name(config.api_key_env):
        message = (
            "--llm-judge-api-key-env expects an environment variable name such "
            "as DEEPSEEK_API_KEY, not an API key value."
        )
        return JudgeResult(
            score=None,
            verdict="error",
            rationale=message,
            error=message,
        )

    api_key = os.environ.get(config.api_key_env)
    if not api_key:
        return JudgeResult(
            score=None,
            verdict="error",
            rationale=f"Missing API key environment variable {config.api_key_env}.",
            error=f"{config.api_key_env} is not set",
        )

    endpoint = config.base_url.rstrip("/") + "/chat/completions"
    body: dict[str, Any] = {
        "model": config.model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a strict but fair benchmark answer judge. "
                    "Respond with one JSON object only."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(payload, ensure_ascii=False, indent=2),
            },
        ],
        "temperature": config.temperature,
        "stream": False,
        "response_format": {"type": "json_object"},
    }
    if config.thinking:
        body["thinking"] = {"type": config.thinking}
    if config.reasoning_effort:
        body["reasoning_effort"] = config.reasoning_effort

    request = urlrequest.Request(
        endpoint,
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urlrequest.urlopen(request, timeout=config.timeout) as response:
            raw_response = json.loads(response.read().decode("utf-8"))
    except (OSError, urlerror.URLError, json.JSONDecodeError) as exc:
        return JudgeResult(
            score=None,
            verdict="error",
            rationale="DeepSeek judge request failed.",
            error=sanitize_report_text(exc),
        )

    try:
        content = raw_response["choices"][0]["message"]["content"]
        raw = parse_judge_response(str(content))
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
        return JudgeResult(
            score=None,
            verdict="error",
            rationale="DeepSeek judge response did not contain parseable JSON content.",
            raw=raw_response if isinstance(raw_response, dict) else None,
            error=sanitize_report_text(exc),
        )
    result = judge_result_from_raw(raw)
    result.raw = {
        "provider": "deepseek",
        "model": config.model,
        "judge": raw,
        "usage": raw_response.get("usage") if isinstance(raw_response, dict) else None,
    }
    return result


def run_llm_judge(
    config: JudgeConfig,
    benchmark_row: dict[str, Any],
    prediction: dict[str, Any],
) -> JudgeResult:
    if not config.provider:
        return JudgeResult(
            score=None,
            verdict="not_run",
            rationale="No LLM judge provider was configured.",
        )
    payload = build_judge_payload(benchmark_row, prediction)
    if config.provider == "command":
        return run_command_judge(config, payload)
    if config.provider == "deepseek":
        return run_deepseek_judge(config, payload)
    return JudgeResult(
        score=None,
        verdict="error",
        rationale=f"Unsupported LLM judge provider: {config.provider}",
        error=f"unsupported provider {config.provider}",
    )

def prediction_answer(prediction: dict[str, Any]) -> str:
    answer = prediction.get("pred_answer")
    if answer is None:
        answer = prediction.get("answer")
    return str(answer or "")


def evaluate_case(
    benchmark_row: dict[str, Any],
    prediction: dict[str, Any] | None,
    top_k: int,
    judge_config: JudgeConfig,
) -> CaseResult:
    case_id = str(benchmark_row.get("case_id", ""))
    if prediction is None:
        return CaseResult(
            case_id=case_id,
            reference_recall_at_k=0.0,
            evidence_recall_at_k=0.0,
            evidence_precision_at_k=0.0,
            evidence_f1_at_k=0.0,
            matched_evidence_ids=[],
            citation_pass=False,
            llm_judge_score=None,
            llm_judge_verdict="not_run",
            llm_judge_rationale="Missing prediction row.",
            llm_judge_error=None,
            answer_pass=False,
            retrieval_pass=False,
            strict_e2e_pass=False,
            missing_prediction=True,
            notes=["missing prediction"],
        )

    if "pred_answer" not in prediction:
        prediction = dict(prediction)
        prediction["pred_answer"] = prediction_answer(prediction)

    retrieval = score_retrieval(benchmark_row, prediction, top_k)
    pred_answer = prediction_answer(prediction)
    citation_ok = citation_pass(benchmark_row, pred_answer)
    judge = run_llm_judge(judge_config, benchmark_row, prediction)
    answer_ok = (
        judge.score is not None
        and judge.score >= judge_config.threshold
        and judge.verdict == "correct"
    )
    retrieval_ok = retrieval["evidence_recall_at_k"] == 1.0
    strict_ok = retrieval_ok and citation_ok and answer_ok

    notes: list[str] = []
    if "pred_answer" not in prediction:
        notes.append("missing pred_answer")
    if not normalize_pred_evidence(prediction, top_k):
        notes.append("missing evidence")
    if not retrieval_ok:
        notes.append("gold evidence not fully retrieved")
    if not citation_ok:
        notes.append("citation policy not satisfied")
    if judge.verdict in {"not_run", "error"}:
        notes.append("llm judge not available")
    elif not answer_ok:
        notes.append("llm judge did not mark answer correct")

    return CaseResult(
        case_id=case_id,
        reference_recall_at_k=retrieval["reference_recall_at_k"],
        evidence_recall_at_k=retrieval["evidence_recall_at_k"],
        evidence_precision_at_k=retrieval["evidence_precision_at_k"],
        evidence_f1_at_k=retrieval["evidence_f1_at_k"],
        matched_evidence_ids=retrieval["matched_evidence_ids"],
        citation_pass=citation_ok,
        llm_judge_score=judge.score,
        llm_judge_verdict=judge.verdict,
        llm_judge_rationale=judge.rationale,
        llm_judge_error=judge.error,
        answer_pass=answer_ok,
        retrieval_pass=retrieval_ok,
        strict_e2e_pass=strict_ok,
        missing_prediction=False,
        notes=notes,
    )


def label_code(row: dict[str, Any], field: str) -> str:
    value = row.get(field)
    if isinstance(value, dict):
        return str(value.get("code", "unknown"))
    if isinstance(value, str):
        return value
    return "unknown"


def mean(values: list[float]) -> float:
    return statistics.mean(values) if values else 0.0


def summarize(results: list[CaseResult], benchmark_by_id: dict[str, dict[str, Any]]) -> dict[str, Any]:
    cases = len(results)
    judged_scores = [item.llm_judge_score for item in results if item.llm_judge_score is not None]
    judge_verdict_counts = Counter(item.llm_judge_verdict for item in results)
    judge_error_counts = Counter(
        sanitize_report_text(item.llm_judge_error)
        for item in results
        if item.llm_judge_error
    )
    summary: dict[str, Any] = {
        "cases": cases,
        "missing_predictions": sum(1 for item in results if item.missing_prediction),
        "retrieval_pass_rate": mean([1.0 if item.retrieval_pass else 0.0 for item in results]),
        "strict_e2e_pass_rate": mean([1.0 if item.strict_e2e_pass else 0.0 for item in results]),
        "answer_pass_rate": mean([1.0 if item.answer_pass else 0.0 for item in results]),
        "citation_pass_rate": mean([1.0 if item.citation_pass else 0.0 for item in results]),
        "mean_reference_recall_at_k": mean([item.reference_recall_at_k for item in results]),
        "mean_evidence_recall_at_k": mean([item.evidence_recall_at_k for item in results]),
        "mean_evidence_precision_at_k": mean([item.evidence_precision_at_k for item in results]),
        "mean_evidence_f1_at_k": mean([item.evidence_f1_at_k for item in results]),
        "llm_judge_coverage": len(judged_scores) / cases if cases else 0.0,
        "mean_llm_judge_score": mean(judged_scores),
        "llm_judge_verdict_counts": dict(sorted(judge_verdict_counts.items())),
        "llm_judge_error_counts": dict(judge_error_counts.most_common(10)),
    }

    grouped: dict[str, dict[str, list[CaseResult]]] = {
        "layer": defaultdict(list),
        "capability": defaultdict(list),
        "answer_type": defaultdict(list),
    }
    for result in results:
        row = benchmark_by_id.get(result.case_id, {})
        for field in grouped:
            grouped[field][label_code(row, field)].append(result)

    by_slice: dict[str, dict[str, Any]] = {}
    for field, buckets in grouped.items():
        by_slice[field] = {}
        for name, items in sorted(buckets.items()):
            by_slice[field][name] = {
                "cases": len(items),
                "strict_e2e_pass_rate": mean(
                    [1.0 if item.strict_e2e_pass else 0.0 for item in items]
                ),
                "retrieval_pass_rate": mean(
                    [1.0 if item.retrieval_pass else 0.0 for item in items]
                ),
                "mean_evidence_recall_at_k": mean(
                    [item.evidence_recall_at_k for item in items]
                ),
                "mean_llm_judge_score": mean(
                    [
                        item.llm_judge_score
                        for item in items
                        if item.llm_judge_score is not None
                    ]
                ),
            }
    summary["by_slice"] = by_slice
    return summary


def make_markdown(report: dict[str, Any], benchmark_by_id: dict[str, dict[str, Any]]) -> str:
    summary = report["summary"]
    lines = [
        "# Method Evaluation Report",
        "",
        "## Summary",
        "",
        f"- Cases: {summary['cases']}",
        f"- Strict E2E pass rate: {summary['strict_e2e_pass_rate']:.3f}",
        f"- Retrieval pass rate: {summary['retrieval_pass_rate']:.3f}",
        f"- Evidence recall@{report['config']['top_k']}: {summary['mean_evidence_recall_at_k']:.3f}",
        f"- Evidence precision@{report['config']['top_k']}: {summary['mean_evidence_precision_at_k']:.3f}",
        f"- Citation pass rate: {summary['citation_pass_rate']:.3f}",
        f"- LLM Judge coverage: {summary['llm_judge_coverage']:.3f}",
        f"- Mean LLM Judge score: {summary['mean_llm_judge_score']:.3f}",
        f"- LLM Judge verdicts: {summary['llm_judge_verdict_counts']}",
        "",
        "## Slice Summary",
        "",
    ]
    if summary["llm_judge_error_counts"]:
        lines.extend(["## LLM Judge Errors", ""])
        for message, count in summary["llm_judge_error_counts"].items():
            lines.append(f"- {count}x {message}")
        lines.append("")

    for field, buckets in summary["by_slice"].items():
        lines.append(f"### {field}")
        for name, values in buckets.items():
            lines.append(
                f"- `{name}`: cases={values['cases']} "
                f"strict={values['strict_e2e_pass_rate']:.3f} "
                f"retrieval={values['retrieval_pass_rate']:.3f} "
                f"ev_recall={values['mean_evidence_recall_at_k']:.3f} "
                f"judge={values['mean_llm_judge_score']:.3f}"
            )
        lines.append("")

    lines.extend(["## Per Case", ""])
    for item in report["cases"]:
        row = benchmark_by_id.get(item["case_id"], {})
        query = row.get("query", "")
        notes = "; ".join(item["notes"]) if item["notes"] else "ok"
        lines.append(
            f"- `{item['case_id']}` strict={item['strict_e2e_pass']} "
            f"ev_recall={item['evidence_recall_at_k']:.2f} "
            f"citation={item['citation_pass']} "
            f"judge={item['llm_judge_verdict']}:{item['llm_judge_score']} "
            f"notes={notes} query={query}"
        )
    lines.append("")
    return "\n".join(lines)


def evaluate(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    benchmark_rows = load_jsonl(args.benchmark)
    prediction_rows = load_jsonl(args.predictions)
    judge_config = judge_config_from_args(args)
    benchmark_by_id = {
        str(row.get("case_id")): row for row in benchmark_rows if row.get("case_id")
    }
    prediction_by_id: dict[str, dict[str, Any]] = {}
    duplicate_predictions: list[str] = []
    for row in prediction_rows:
        case_id = str(row.get("case_id", ""))
        if not case_id:
            continue
        if case_id in prediction_by_id:
            duplicate_predictions.append(case_id)
            continue
        prediction_by_id[case_id] = row

    results = [
        evaluate_case(
            row,
            prediction_by_id.get(case_id),
            args.top_k,
            judge_config,
        )
        for case_id, row in benchmark_by_id.items()
    ]
    summary = summarize(results, benchmark_by_id)
    report = {
        "mode": "method_evaluation",
        "config": {
            "benchmark": str(args.benchmark),
            "predictions": str(args.predictions),
            "top_k": args.top_k,
            "judge_threshold": args.judge_threshold,
            "llm_judge_provider": judge_config.provider,
            "llm_judge_command": (
                sanitize_report_text(args.llm_judge_command)
                if args.llm_judge_command
                else None
            ),
            "llm_judge_api_key_env": display_env_var_name(judge_config.api_key_env),
            "llm_judge_base_url": sanitize_report_text(judge_config.base_url),
            "llm_judge_model": judge_config.model if judge_config.provider else None,
            "llm_judge_thinking": judge_config.thinking,
            "llm_judge_reasoning_effort": judge_config.reasoning_effort,
        },
        "summary": summary,
        "prediction_warnings": {
            "duplicate_case_ids": sorted(duplicate_predictions),
            "unknown_case_ids": sorted(set(prediction_by_id) - set(benchmark_by_id)),
        },
        "cases": [asdict(item) for item in results],
    }

    exit_code = 0
    if duplicate_predictions:
        exit_code = 2
    if args.require_llm_judge and not judge_config.provider:
        report["prediction_warnings"]["missing_llm_judge_provider"] = True
        exit_code = 2
    if args.require_llm_judge and summary["llm_judge_coverage"] < 1.0:
        exit_code = 2
    return report, exit_code


def write_outputs(report: dict[str, Any], args: argparse.Namespace, benchmark_by_id: dict[str, dict[str, Any]]) -> None:
    if args.output_json:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    if args.output_md:
        args.output_md.parent.mkdir(parents=True, exist_ok=True)
        args.output_md.write_text(make_markdown(report, benchmark_by_id), encoding="utf-8")


def main() -> int:
    args = parse_args()
    try:
        report, exit_code = evaluate(args)
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    benchmark_by_id = {
        str(row.get("case_id")): row for row in load_jsonl(args.benchmark) if row.get("case_id")
    }
    write_outputs(report, args, benchmark_by_id)

    summary = report["summary"]
    print(f"Cases: {summary['cases']}")
    print(f"Strict E2E pass rate: {summary['strict_e2e_pass_rate']:.3f}")
    print(f"Evidence recall@{args.top_k}: {summary['mean_evidence_recall_at_k']:.3f}")
    print(f"Evidence precision@{args.top_k}: {summary['mean_evidence_precision_at_k']:.3f}")
    print(f"Citation pass rate: {summary['citation_pass_rate']:.3f}")
    print(f"LLM judge coverage: {summary['llm_judge_coverage']:.3f}")
    print(f"Mean LLM judge score: {summary['mean_llm_judge_score']:.3f}")
    print(f"LLM judge verdicts: {summary['llm_judge_verdict_counts']}")
    if summary["llm_judge_error_counts"]:
        first_error, first_count = next(iter(summary["llm_judge_error_counts"].items()))
        print(f"LLM judge top error: {first_count}x {first_error}")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
