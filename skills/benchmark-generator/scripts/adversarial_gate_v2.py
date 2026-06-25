#!/usr/bin/env python3
"""M9 adversarial gate orchestrator (v2).

Two subcommands:

    adversarial_gate_v2.py prepare --project P --drafts-dir D
        Read candidates / curated / queries / answers; emit one task
        per (row, declared attribute) into <drafts>/<P>.baseline_tasks.jsonl.

    adversarial_gate_v2.py judge --project P --drafts-dir D
        Read <drafts>/<P>.baseline_answers.jsonl produced by the host LLM;
        judge each task using a deterministic content-overlap heuristic;
        write <drafts>/<P>.adversarial_gate.jsonl with per-row verdicts.

Per design §6.2:
- A baseline FAILS when the cheap-baseline answer does not reach the M6
  conclusion. Failure is GOOD — it confirms the row's difficulty claim.
- A row PASSES the gate iff at least one declared attribute's matched
  baseline failed. Rows where every baseline succeeded or stayed
  inconclusive are demoted (excluded by the assembler).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any


ATTRIBUTE_BASELINES: dict[str, list[str]] = {
    "long_tail": ["closed_book_llm"],
    "distracting_info": ["top_1_dense_only"],
    "version_fork": ["single_source_set_retrieval"],
    "non_code_anchor": ["code_only_retrieval"],
    "false_premise": ["closed_book_llm", "oracle_evidence_llm"],
    "doc_code_divergence": ["doc_only_retrieval"],
    "conditional_behavior": ["top_1_dense_only"],
    "negative_evidence": ["closed_book_llm"],
    "implicit_domain_knowledge": ["oracle_evidence_no_reasoning_llm"],
    "quantitative_aggregation": ["top_1_dense_only"],
}


REFUSAL_TOKENS = (
    "refuse",
    "无法判断",
    "无法确认",
    "no evidence",
    "Cannot ",
    "cannot confirm",
    "只能给出有限结论",
)

TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]{2,}|[一-鿿]{2,}")
STOP_TOKENS = {
    "the", "and", "for", "with", "this", "that", "from", "any", "are", "but",
    "了", "的", "是", "在", "也", "和", "或", "由", "对", "为",
}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            out.append(json.loads(line))
    return out


def index_by_case(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {row["case_id"]: row for row in rows if isinstance(row.get("case_id"), str)}


def declared_attributes(row_plan: dict[str, Any]) -> list[str]:
    attrs: list[str] = []
    for key in ("axis2_retrieval", "axis3_reasoning"):
        for value in row_plan.get(key) or []:
            if isinstance(value, str):
                attrs.append(value)
    return attrs


def evidence_for_baseline(
    selected_evidence: list[dict[str, Any]],
    candidates: list[dict[str, Any]],
    baseline: str,
) -> list[dict[str, Any]]:
    if baseline == "closed_book_llm":
        return []
    if baseline == "top_1_dense_only":
        # Pick the first candidate as the top-1 dense retrieval result.
        if candidates:
            head = candidates[0]
            return [
                {
                    "path": head.get("path", ""),
                    "lines": head.get("lines", ""),
                    "snippet": head.get("raw_snippet", ""),
                }
            ]
        return selected_evidence[:1]
    if baseline == "doc_only_retrieval":
        return [
            s for s in selected_evidence
            if "doc" in str(s.get("path", "")) or str(s.get("path", "")).endswith((".rst", ".md", ".txt"))
        ]
    if baseline == "code_only_retrieval":
        return [
            s for s in selected_evidence
            if not any(seg in str(s.get("path", "")) for seg in ("doc/", ".rst", ".md", ".txt", "Makefile", "/ci/", "/.github/"))
        ]
    if baseline == "single_source_set_retrieval":
        if not selected_evidence:
            return []
        first_source = selected_evidence[0].get("source_id")
        return [s for s in selected_evidence if s.get("source_id") == first_source]
    if baseline in {"oracle_evidence_llm", "oracle_evidence_no_reasoning_llm"}:
        return list(selected_evidence)
    return list(selected_evidence)


def instructions_for_baseline(baseline: str, query: str) -> str:
    if baseline == "closed_book_llm":
        return (
            'You have NO evidence and NO retrieval. Answer the query from prior knowledge only. '
            'If you cannot answer reliably from prior knowledge, output exactly: {"answer": "refuse", "rationale": "no evidence available", "answer_confidence": "low"}'
        )
    if baseline == "top_1_dense_only":
        return (
            "You have exactly one evidence snippet — what a top-1 dense retriever would return. "
            "Answer only from that single snippet. Refuse if it does not support an answer."
        )
    if baseline == "doc_only_retrieval":
        return (
            "You have only documentation spans. Answer from docs alone. Do not infer code-level behavior beyond what docs state."
        )
    if baseline == "code_only_retrieval":
        return (
            "You have only code/RTL spans (no docs, no build scripts). Answer strictly from code."
        )
    if baseline == "single_source_set_retrieval":
        return (
            "You have evidence from a single source set only (other source sets are unavailable). Answer from this set."
        )
    if baseline == "oracle_evidence_llm":
        return (
            "You have the oracle evidence. The user sounds confident in their premise; verify it against the evidence and answer."
        )
    if baseline == "oracle_evidence_no_reasoning_llm":
        return (
            "You have the oracle evidence. Quote the most relevant span(s) verbatim with citations. Do NOT add inference, do NOT apply domain knowledge."
        )
    return "Answer the query from the provided evidence."


def emit_tasks(project: str, drafts_dir: Path) -> Path:
    cands = load_jsonl(drafts_dir / f"{project}.candidates.jsonl")
    curated = load_jsonl(drafts_dir / f"{project}.curated_evidence.jsonl")
    queries = load_jsonl(drafts_dir / f"{project}.queries.jsonl")
    answers = load_jsonl(drafts_dir / f"{project}.answers.jsonl")

    cands_by = index_by_case(cands)
    curated_by = index_by_case(curated)
    queries_by = index_by_case(queries)
    answers_by = index_by_case(answers)

    tasks: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for case_id, cand in cands_by.items():
        plan = cand.get("row_plan") or {}
        if plan.get("answerability") == "unanswerable_missing_evidence":
            # For missing-evidence rows the closed_book baseline is exactly the row's adversarial baseline.
            # Continue — the negative_evidence attribute (if claimed) will be tested by closed_book.
            pass
        attrs = declared_attributes(plan)
        if not attrs:
            skipped.append({"case_id": case_id, "reason": "no_declared_attributes"})
            continue
        query_row = queries_by.get(case_id)
        if not query_row:
            skipped.append({"case_id": case_id, "reason": "missing_M5_query"})
            continue
        cur_row = curated_by.get(case_id)
        selected = (cur_row or {}).get("selected_evidence") or []
        candidates = cand.get("candidates") or []
        for attr in attrs:
            baselines = ATTRIBUTE_BASELINES.get(attr)
            if not baselines:
                skipped.append({"case_id": case_id, "reason": f"unknown_attribute:{attr}"})
                continue
            for baseline in baselines:
                view_evidence = evidence_for_baseline(selected, candidates, baseline)
                view = {
                    "query": query_row.get("query"),
                    "evidence": view_evidence,
                }
                tasks.append(
                    {
                        "task_id": f"{case_id}::{attr}::{baseline}",
                        "case_id": case_id,
                        "attribute": attr,
                        "baseline": baseline,
                        "view": view,
                        "instructions": instructions_for_baseline(baseline, view["query"]),
                    }
                )

    tasks_path = drafts_dir / f"{project}.baseline_tasks.jsonl"
    tasks_path.parent.mkdir(parents=True, exist_ok=True)
    with tasks_path.open("w", encoding="utf-8") as handle:
        for task in tasks:
            handle.write(json.dumps(task, ensure_ascii=False) + "\n")
    summary_path = drafts_dir / f"{project}.baseline_tasks.summary.json"
    summary = {
        "project": project,
        "task_count": len(tasks),
        "skipped": skipped,
        "by_baseline": dict(Counter(t["baseline"] for t in tasks)),
        "by_attribute": dict(Counter(t["attribute"] for t in tasks)),
    }
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"{project}: wrote {len(tasks)} baseline tasks to {tasks_path}")
    if skipped:
        print(f"  skipped {len(skipped)} (no_declared_attributes / missing_M5 / unknown_attribute)")
    return tasks_path


def tokenize(text: str) -> set[str]:
    return {t.lower() for t in TOKEN_RE.findall(text or "") if t.lower() not in STOP_TOKENS}


def baseline_outcome(answer: str, query: str, gold_answer: str, attribute: str | None = None) -> str:
    """Return 'baseline_failed' (good — attribute confirmed), 'baseline_succeeded' (bad — attribute unconfirmed), or 'inconclusive'.

    For `negative_evidence` the gold answer is itself a refusal, so the
    default overlap heuristic flips meaning: a confident closed-book answer
    means the question is in the LLM's prior knowledge, i.e. the row is not
    actually unanswerable. So refusal = good, confident answer = bad.
    """
    text = (answer or "").strip()
    if not text:
        return "inconclusive"
    refused = any(token.lower() in text.lower() for token in REFUSAL_TOKENS)
    if attribute == "negative_evidence":
        return "baseline_failed" if refused else "baseline_succeeded"
    if refused:
        return "baseline_failed"
    # Per M9_adversarial_gate.md: any distinctive-token overlap with the M6
    # expected_answer (i.e. a token in the gold answer that is NOT already in
    # the query) signals the baseline reached the same conclusion → attribute
    # unconfirmed. A non-refusal answer with no overlap is ambiguous and
    # waits for a host-LLM judge resolution — until one runs, treat it as
    # inconclusive (which does NOT count as a baseline_failed under the
    # per-attribute confirmation rule, so the row will be demoted rather
    # than admitted on weak evidence).
    gold_tokens = tokenize(gold_answer)
    query_tokens = tokenize(query)
    distinctive = gold_tokens - query_tokens
    answer_tokens = tokenize(text)
    overlap = distinctive & answer_tokens
    if len(overlap) >= 1:
        return "baseline_succeeded"
    return "inconclusive"


def judge_answers(project: str, drafts_dir: Path) -> Path:
    answers_path = drafts_dir / f"{project}.baseline_answers.jsonl"
    if not answers_path.exists():
        print(f"ERROR: {answers_path} not found — host LLM has not written baseline answers yet", file=sys.stderr)
        sys.exit(2)
    baseline_answers = load_jsonl(answers_path)
    cands = index_by_case(load_jsonl(drafts_dir / f"{project}.candidates.jsonl"))
    queries = index_by_case(load_jsonl(drafts_dir / f"{project}.queries.jsonl"))
    gold = index_by_case(load_jsonl(drafts_dir / f"{project}.answers.jsonl"))

    by_case: dict[str, list[dict[str, Any]]] = {}
    for ans in baseline_answers:
        case_id = ans.get("case_id")
        if not isinstance(case_id, str):
            continue
        query_row = queries.get(case_id) or {}
        gold_row = gold.get(case_id) or {}
        outcome = baseline_outcome(
            str(ans.get("answer", "")),
            str(query_row.get("query", "")),
            str(gold_row.get("expected_answer", "")),
            attribute=str(ans.get("attribute", "")) or None,
        )
        record = {
            "attribute": ans.get("attribute"),
            "baseline": ans.get("baseline"),
            "outcome": outcome,
            "rationale": ans.get("rationale") or "",
        }
        by_case.setdefault(case_id, []).append(record)

    verdicts: list[dict[str, Any]] = []
    for case_id, cand in cands.items():
        per_attr = by_case.get(case_id, [])
        plan = cand.get("row_plan") or {}
        declared = declared_attributes(plan)
        if not declared:
            # No difficulty claims to falsify — admit by default.
            passed = True
            reason = "no_attributes_to_test"
        else:
            # Coverage check: every (attribute, baseline) pair from the
            # design's ATTRIBUTE_BASELINES mapping must have a recorded
            # outcome. Multi-baseline attributes (e.g. false_premise → two
            # baselines) need both runs before the attribute can be judged.
            required_pairs = {
                (attr, baseline)
                for attr in declared
                for baseline in ATTRIBUTE_BASELINES.get(attr, [])
            }
            present_pairs = {(r["attribute"], r["baseline"]) for r in per_attr}
            untested = sorted(required_pairs - present_pairs)
            if untested:
                passed = False
                reason = "untested_baselines:" + ",".join(
                    f"{a}/{b}" for a, b in untested[:3]
                )
                if len(untested) > 3:
                    reason += f"...(+{len(untested) - 3})"
            else:
                # Per-attribute confirmation:
                #   - For multi-baseline attributes, ALL matched baselines
                #     must fail to count the attribute as confirmed.
                #   - For single-baseline attributes, the one baseline
                #     failing confirms.
                # The row passes iff at least one declared attribute is
                # confirmed under this stricter rule.
                attr_confirmed: dict[str, bool] = {}
                for attr in declared:
                    matched = [
                        r for r in per_attr if r["attribute"] == attr
                    ]
                    if not matched:
                        attr_confirmed[attr] = False
                        continue
                    attr_confirmed[attr] = all(
                        r["outcome"] == "baseline_failed" for r in matched
                    )
                passed = any(attr_confirmed.values())
                reason = (
                    "at_least_one_attribute_confirmed"
                    if passed
                    else "no_attribute_confirmed"
                )
        verdicts.append(
            {
                "case_id": case_id,
                "passed": passed,
                "verdict_reason": reason,
                "per_attribute": per_attr,
            }
        )

    out_path = drafts_dir / f"{project}.adversarial_gate.jsonl"
    with out_path.open("w", encoding="utf-8") as handle:
        for v in verdicts:
            handle.write(json.dumps(v, ensure_ascii=False) + "\n")

    summary = {
        "project": project,
        "verdict_count": len(verdicts),
        "passed": sum(1 for v in verdicts if v["passed"]),
        "failed": sum(1 for v in verdicts if not v["passed"]),
        "outcome_breakdown": dict(
            Counter(r["outcome"] for v in verdicts for r in v["per_attribute"])
        ),
    }
    (drafts_dir / f"{project}.adversarial_gate.summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8",
    )
    print(
        f"{project}: gate verdicts written — {summary['passed']} pass, {summary['failed']} fail "
        f"({len(verdicts)} rows assessed)"
    )
    return out_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p_prepare = sub.add_parser("prepare", help="Emit baseline_tasks.jsonl for the host LLM to answer")
    p_prepare.add_argument("--project", required=True)
    p_prepare.add_argument("--drafts-dir", type=Path, default=Path("drafts"))
    p_judge = sub.add_parser("judge", help="Consume baseline_answers.jsonl and emit adversarial_gate.jsonl")
    p_judge.add_argument("--project", required=True)
    p_judge.add_argument("--drafts-dir", type=Path, default=Path("drafts"))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.command == "prepare":
        emit_tasks(args.project, args.drafts_dir)
    elif args.command == "judge":
        judge_answers(args.project, args.drafts_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
