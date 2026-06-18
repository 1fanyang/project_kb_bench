#!/usr/bin/env python3
"""Validate v1 benchmark files and evaluate run results."""

from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from collections import Counter
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any


REQUIRED_ROW_FIELDS = {
    "case_id",
    "project",
    "layer",
    "query",
    "query_rewrite",
    "answer_type",
    "references",
    "evidence",
    "expected_answer",
    "answer_rubric",
}

ANSWER_TYPES = {
    "yes_no": "是否判断",
    "mechanism": "机制解释",
    "fact_check": "事实核查",
    "comparison": "对比分析",
    "location": "位置定位",
    "procedure": "操作流程",
    "negative": "无答案或证据不足",
    "synthesis": "综合归纳",
}

SCHEMA_VERSIONS = {"v1", "v1.1"}
ANSWERABILITY_VALUES = {
    "answerable",
    "unanswerable_missing_evidence",
    "unanswerable_false_premise",
    "unanswerable_ambiguous",
}
CONDITIONAL_EVIDENCE_ROLES = {"trigger_condition", "branch", "guard", "predicate", "state"}
STRUCTURAL_REASON_MESSAGES = {
    "MISSING_DIFFICULTY": "`difficulty` is required in v1.1 mode",
    "DIFFICULTY_LAYER_MISMATCH": "`difficulty.axis1_layer` must match `layer.code`",
    "INSUFFICIENT_DIFFICULTY_SIGNALS": "v1.1 rows need at least two difficulty signals across axes",
    "L2_SINGLE_SOURCE": "L2 rows need evidence from at least two source_id values",
    "L3_SINGLE_SOURCE": "L3 rows need evidence from at least two source_id values",
    "L3_NO_ATOM_CHAIN": "L3 rows need at least one required atom with depends_on",
    "CONDITIONAL_BEHAVIOR_WITHOUT_ROLE": "`conditional_behavior` needs guard/branch/predicate/state evidence",
    "FORBIDDEN_ATOMS_REQUIRED": "yes_no, fact_check, and false_premise rows need forbidden_atoms",
    "FILE_ANCHOR_LEAK": "query names an evidence file without file_anchor_required tag",
    "MISSING_CLAIM_SOURCES": "`difficulty.claim_sources` is required in v1.1 mode",
    "MISSING_CLAIM_SOURCE_ATTRIBUTE": "`difficulty.claim_sources` must include signals for every difficulty attribute",
    "UNKNOWN_CLAIM_SOURCE_SIGNAL": "`difficulty.claim_sources` references an unknown signal_id",
    "CLAIM_SOURCE_SIGNAL_MISMATCH": "`difficulty.claim_sources` signal does not match row project, axis, or attribute",
}
ZERO_EVIDENCE_ANSWERABILITY = {
    "unanswerable_missing_evidence",
}

ATOM_ROLES = {
    "conclusion",
    "evidence_fact",
    "reasoning",
    "boundary",
    "location",
    "procedure_step",
    "comparison_point",
}

MATCH_TYPES = {
    "semantic_yes_no",
    "semantic_fact",
    "semantic_reasoning",
    "path_or_symbol",
    "numeric_or_version",
    "list_set",
    "semantic_contradiction",
}

CITATION_REQUIRED_VALUES = {"always", "never", "when_query_requests_evidence"}
CITATION_GRANULARITY_VALUES = {"path_line", "path_only", "source_only"}
RUBRIC_LIKE_PATTERNS = (
    "应说明",
    "应把",
    "应围绕 query 指定的上下文",
    "检索并串联这些关键证据",
    "答案需要说明",
    "如何支持或修正用户的假设",
)
QUERY_REWRITE_FORBIDDEN_PATTERNS = (
    "检索并回答",
    "验证假设",
    "优先参考实体",
    "范围约束",
    "需要定位触发条件",
    "状态/数据更新",
    "后续调用或消费关系",
    "不能只做符号定位",
    "回答应服务后续推理",
)
CHATTY_QUERY_PATTERNS = (
    "帮我",
    "我想",
    "我知道",
    "我在看",
    "我已经知道",
    "想看",
    "到底",
    "顺便",
    "吧",
    "不用泛泛",
)
CITATION_TRIGGER_PATTERNS = (
    "证据",
    "代码证据",
    "行号",
    "片段",
    "引用",
    "cite",
    "citation",
    "line",
    "proof",
)

LINES_RE = re.compile(r"^(\d+)(?:-(\d+))?$")
CITATION_RE = re.compile(r"[\w./@+-]+:\d+(?:-\d+)?")
CODE_TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_:.>\\/-]*")
CJK_RE = re.compile(r"[\u4e00-\u9fff]+")


@dataclass
class Finding:
    severity: str
    file: str
    line: int | None
    case_id: str | None
    message: str


@dataclass
class CaseEval:
    case_id: str
    reference_recall: float
    evidence_recall: float
    citation_pass: bool
    atom_coverage: float
    conclusion_atoms_matched: bool
    fatal_forbidden_matched: bool
    verdict: str
    notes: list[str]
    atom_matches: dict[str, bool]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate benchmark JSONL or evaluate run results.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    lint = subparsers.add_parser("lint", help="Validate benchmark JSONL structure and evidence anchors")
    lint.add_argument("benchmark", nargs="+", type=Path, help="Benchmark JSONL file(s)")
    lint.add_argument("--context-bundle", type=Path, help="Analyzer project_context_bundle directory")
    lint.add_argument("--repo-root", type=Path, default=Path.cwd(), help="Base path for relative source paths")
    lint.add_argument("--sample-size", type=int, default=5, help="Number of cases to include in evidence sample report")
    lint.add_argument("--markdown-report", type=Path, help="Write Markdown report")
    lint.add_argument("--json-report", type=Path, help="Write JSON report")
    lint.add_argument("--structural-gate-json", type=Path, help="Write v1.1 structural gate records to JSON")
    lint.add_argument("--fail-on-warn", action="store_true", help="Exit non-zero when WARN findings exist")
    lint.add_argument(
        "--schema-version",
        choices=sorted(SCHEMA_VERSIONS),
        default="v1",
        help="Validation rules to enforce. v1 keeps legacy compatibility; v1.1 enables answerability and structural rules.",
    )

    evaluate = subparsers.add_parser("evaluate", help="Evaluate run results against a benchmark")
    evaluate.add_argument("benchmark", type=Path, help="Benchmark JSONL file")
    evaluate.add_argument("run_results", type=Path, help="Run results JSONL file")
    evaluate.add_argument("--context-bundle", type=Path, help="Analyzer project_context_bundle directory")
    evaluate.add_argument("--repo-root", type=Path, default=Path.cwd(), help="Base path for relative source paths")
    evaluate.add_argument("--top-k", type=int, default=10, help="Only score retrieved contexts with rank <= K")
    evaluate.add_argument("--answer-threshold", type=float, default=0.7, help="Weighted atom coverage threshold")
    evaluate.add_argument("--sample-size", type=int, default=5, help="Number of cases to include in sample report")
    evaluate.add_argument("--markdown-report", type=Path, help="Write Markdown report")
    evaluate.add_argument("--json-report", type=Path, help="Write JSON report")
    evaluate.add_argument(
        "--schema-version",
        choices=sorted(SCHEMA_VERSIONS),
        default="v1",
        help="Validation rules to enforce before scoring run results.",
    )
    return parser.parse_args()


def add(findings: list[Finding], severity: str, file: str, line: int | None, case_id: str | None, message: str) -> None:
    findings.append(Finding(severity, file, line, case_id, message))


def load_jsonl(path: Path, findings: list[Finding] | None = None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    local_findings = findings if findings is not None else []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        add(local_findings, "FAIL", str(path), None, None, f"cannot read file: {exc}")
        return rows
    for lineno, line in enumerate(lines, 1):
        if not line.strip():
            add(local_findings, "WARN", str(path), lineno, None, "blank JSONL line")
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            add(local_findings, "FAIL", str(path), lineno, None, f"JSON parse error: {exc}")
            continue
        if not isinstance(row, dict):
            add(local_findings, "FAIL", str(path), lineno, None, "JSONL row must be an object")
            continue
        row["_file"] = str(path)
        row["_line"] = lineno
        rows.append(row)
    return rows


def load_source_inventory(bundle: Path | None, findings: list[Finding]) -> dict[str, dict[str, Any]]:
    if bundle is None:
        return {}
    inventory_path = bundle / "source_inventory.jsonl"
    if not inventory_path.exists():
        add(findings, "FAIL", str(inventory_path), None, None, "context bundle missing source_inventory.jsonl")
        return {}
    sources: dict[str, dict[str, Any]] = {}
    for row in load_jsonl(inventory_path, findings):
        source_id = row.get("source_id")
        if isinstance(source_id, str) and source_id:
            sources[source_id] = row
    return sources


def load_signal_index(bundle: Path | None, findings: list[Finding]) -> dict[str, dict[str, Any]]:
    if bundle is None:
        return {}
    signal_path = bundle / "signal_index.jsonl"
    if not signal_path.exists():
        return {}
    signals: dict[str, dict[str, Any]] = {}
    for row in load_jsonl(signal_path, findings):
        signal_id = row.get("signal_id")
        if isinstance(signal_id, str) and signal_id:
            signals[signal_id] = row
    return signals


def is_nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def parse_line_range(value: Any) -> tuple[int, int] | None:
    if value in (None, ""):
        return None
    if not isinstance(value, str):
        return None
    match = LINES_RE.match(value)
    if not match:
        return None
    start = int(match.group(1))
    end = int(match.group(2) or start)
    if start <= 0 or end < start:
        return None
    return start, end


def line_ranges_overlap(left: Any, right: Any) -> bool:
    left_range = parse_line_range(left)
    right_range = parse_line_range(right)
    if left_range is None or right_range is None:
        return True
    return max(left_range[0], right_range[0]) <= min(left_range[1], right_range[1])


def resolve_path(value: str, repo_root: Path) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return repo_root / path


def label_code(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("code", "<missing>"))
    return str(value)


def row_tags(row: dict[str, Any]) -> set[str]:
    tags = row.get("tags", [])
    return {str(item) for item in tags if isinstance(item, str)} if isinstance(tags, list) else set()


def difficulty_attributes(row: dict[str, Any]) -> list[str]:
    return [attribute for _, attribute in difficulty_axis_attributes(row)]


def difficulty_axis_attributes(row: dict[str, Any]) -> list[tuple[int, str]]:
    difficulty = row.get("difficulty")
    if not isinstance(difficulty, dict):
        return []
    attrs: list[tuple[int, str]] = []
    for key, axis in (("axis2_retrieval", 2), ("axis3_reasoning", 3)):
        values = difficulty.get(key, [])
        if isinstance(values, list):
            attrs.extend((axis, str(value)) for value in values if isinstance(value, str))
    return attrs


def missing_evidence_refusal(row: dict[str, Any]) -> bool:
    references = row.get("references", [])
    evidence = row.get("evidence", [])
    return (
        row.get("answerability") == "unanswerable_missing_evidence"
        and isinstance(references, list)
        and not references
        and isinstance(evidence, list)
        and not evidence
    )


def evidence_source_ids(row: dict[str, Any]) -> set[str]:
    evidence = row.get("evidence", [])
    if not isinstance(evidence, list):
        return set()
    return {
        str(item.get("source_id"))
        for item in evidence
        if isinstance(item, dict) and is_nonempty_string(item.get("source_id"))
    }


def has_atom_dependency(row: dict[str, Any]) -> bool:
    rubric = row.get("answer_rubric", {})
    atoms = rubric.get("required_atoms", []) if isinstance(rubric, dict) else []
    if not isinstance(atoms, list):
        return False
    for atom in atoms:
        if isinstance(atom, dict) and isinstance(atom.get("depends_on"), list) and atom["depends_on"]:
            return True
    return False


def has_conditional_evidence_role(row: dict[str, Any]) -> bool:
    evidence = row.get("evidence", [])
    if not isinstance(evidence, list):
        return False
    return any(
        isinstance(item, dict) and item.get("role") in CONDITIONAL_EVIDENCE_ROLES
        for item in evidence
    )


def query_mentions_evidence_file(row: dict[str, Any]) -> bool:
    query = str(row.get("query", ""))
    evidence = row.get("evidence", [])
    if not isinstance(evidence, list):
        return False
    for item in evidence:
        if not isinstance(item, dict):
            continue
        path = str(item.get("path", ""))
        if path and path in query:
            return True
        filename = Path(path).name
        if filename and "." in filename and filename in query:
            return True
    return False


def citation_required(row: dict[str, Any]) -> tuple[bool, list[str], str]:
    rubric = row.get("answer_rubric", {})
    policy = rubric.get("citation_policy", {}) if isinstance(rubric, dict) else {}
    required = policy.get("required", "when_query_requests_evidence") if isinstance(policy, dict) else "when_query_requests_evidence"
    if required == "never":
        return False, [], "path_line"
    query_triggered = contains_citation_trigger(str(row.get("query", "")))
    required_now = required == "always" or (required == "when_query_requests_evidence" and query_triggered)
    evidence_ids = policy.get("required_evidence_ids", []) if isinstance(policy, dict) else []
    if not isinstance(evidence_ids, list):
        evidence_ids = []
    granularity = policy.get("acceptable_granularity", "path_line") if isinstance(policy, dict) else "path_line"
    return required_now, [str(item) for item in evidence_ids], str(granularity)


def contains_citation_trigger(query: str) -> bool:
    query_lower = query.lower()
    return any(pattern.lower() in query_lower for pattern in CITATION_TRIGGER_PATTERNS)


def is_chatty_query(query: str) -> bool:
    return any(pattern in query for pattern in CHATTY_QUERY_PATTERNS)


def significant_tokens(text: str) -> set[str]:
    text_lower = text.lower()
    tokens = {tok for tok in CODE_TOKEN_RE.findall(text_lower) if len(tok) >= 3}
    for chunk in CJK_RE.findall(text):
        if len(chunk) == 1:
            tokens.add(chunk)
        else:
            tokens.update(chunk[i : i + 2] for i in range(len(chunk) - 1))
    return tokens


def lexical_match(statement: str, answer: str, threshold: float = 0.45) -> bool:
    statement_tokens = significant_tokens(statement)
    if not statement_tokens:
        return False
    answer_tokens = significant_tokens(answer)
    if not answer_tokens:
        return False
    overlap = len(statement_tokens & answer_tokens) / len(statement_tokens)
    code_like = {tok for tok in statement_tokens if "_" in tok or tok.isupper() or "." in tok or "/" in tok}
    if code_like and not code_like.issubset(answer_tokens):
        return False
    return overlap >= threshold


def validate_label_object(row: dict[str, Any], field: str, findings: list[Finding]) -> None:
    value = row.get(field)
    case_id = str(row.get("case_id", "<missing>"))
    if not isinstance(value, dict):
        add(findings, "FAIL", row["_file"], row["_line"], case_id, f"`{field}` must be an object with code and zh")
        return
    if not is_nonempty_string(value.get("code")) or not is_nonempty_string(value.get("zh")):
        add(findings, "FAIL", row["_file"], row["_line"], case_id, f"`{field}.code` and `{field}.zh` are required")


def validate_query_rewrite(row: dict[str, Any], findings: list[Finding]) -> None:
    case_id = str(row.get("case_id", "<missing>"))
    query = str(row.get("query", ""))
    rewrite = str(row.get("query_rewrite", ""))
    if not is_nonempty_string(query):
        add(findings, "FAIL", row["_file"], row["_line"], case_id, "`query` must be a non-empty string")
        return
    if not is_nonempty_string(rewrite):
        add(findings, "FAIL", row["_file"], row["_line"], case_id, "`query_rewrite` must be a non-empty string")
        return
    if query.strip() == rewrite.strip() and is_chatty_query(query):
        add(findings, "WARN", row["_file"], row["_line"], case_id, "`query_rewrite` duplicates a chatty query")
    for pattern in QUERY_REWRITE_FORBIDDEN_PATTERNS:
        if pattern in rewrite:
            add(findings, "FAIL", row["_file"], row["_line"], case_id, f"`query_rewrite` contains hidden-context marker: {pattern}")
    query_tokens = set(CODE_TOKEN_RE.findall(query))
    for token in CODE_TOKEN_RE.findall(rewrite):
        if len(token) < 4 or token in query_tokens:
            continue
        if token.isupper() or "_" in token or "::" in token or "." in token:
            add(findings, "WARN", row["_file"], row["_line"], case_id, f"`query_rewrite` introduces technical token absent from query: {token}")


def validate_expected_answer(row: dict[str, Any], findings: list[Finding]) -> None:
    case_id = str(row.get("case_id", "<missing>"))
    answer = row.get("expected_answer")
    if not is_nonempty_string(answer):
        add(findings, "FAIL", row["_file"], row["_line"], case_id, "`expected_answer` must be a non-empty string")
        return
    if any(pattern in answer for pattern in RUBRIC_LIKE_PATTERNS):
        add(findings, "FAIL", row["_file"], row["_line"], case_id, "`expected_answer` is rubric-like, not a direct answer")
    if len(answer.strip()) < 40:
        add(findings, "WARN", row["_file"], row["_line"], case_id, "`expected_answer` is short for a standard reference answer")
    answer_type = row.get("answer_type")
    if isinstance(answer_type, dict) and answer_type.get("code") == "yes_no":
        first_sentence = re.split(r"[。.!?？]", answer.strip(), maxsplit=1)[0]
        if not any(token in first_sentence for token in ("会", "不会", "无法判断", "不能确认", "可以", "不可以", "支持", "不支持")):
            add(findings, "WARN", row["_file"], row["_line"], case_id, "yes_no expected_answer should answer directly in the first sentence")
    required, _, _ = citation_required(row)
    if required and not CITATION_RE.search(answer):
        add(findings, "FAIL", row["_file"], row["_line"], case_id, "citation is required but expected_answer has no path:line citation")


def validate_references_and_evidence(
    row: dict[str, Any],
    findings: list[Finding],
    repo_root: Path,
    sources: dict[str, dict[str, Any]],
    schema_version: str = "v1",
) -> set[str]:
    case_id = str(row.get("case_id", "<missing>"))
    answerability = str(row.get("answerability", "answerable"))
    zero_evidence_allowed = (
        schema_version == "v1.1"
        and answerability in ZERO_EVIDENCE_ANSWERABILITY
    )
    references = row.get("references")
    reference_paths: set[str] = set()
    reference_source_ids: set[str] = set()
    if not isinstance(references, list):
        add(findings, "FAIL", row["_file"], row["_line"], case_id, "`references` must be a list")
    elif not references and not zero_evidence_allowed:
        add(findings, "FAIL", row["_file"], row["_line"], case_id, "`references` must be a non-empty list for answerable rows")
    else:
        for index, ref in enumerate(references):
            if not isinstance(ref, dict):
                add(findings, "FAIL", row["_file"], row["_line"], case_id, f"references[{index}] must be an object")
                continue
            source_id = ref.get("source_id")
            path = ref.get("path")
            if not is_nonempty_string(source_id) and not is_nonempty_string(path):
                add(findings, "FAIL", row["_file"], row["_line"], case_id, f"references[{index}] needs source_id or path")
            if is_nonempty_string(source_id):
                reference_source_ids.add(source_id)
                if sources and source_id not in sources:
                    add(findings, "FAIL", row["_file"], row["_line"], case_id, f"references[{index}].source_id not in context bundle: {source_id}")
            if is_nonempty_string(path):
                reference_paths.add(path)
                if not resolve_path(path, repo_root).exists():
                    add(findings, "WARN", row["_file"], row["_line"], case_id, f"reference path does not exist: {path}")
            for recommended in ("repo_name", "source_type", "authority"):
                if recommended not in ref:
                    add(findings, "WARN", row["_file"], row["_line"], case_id, f"references[{index}] missing recommended `{recommended}`")

    evidence = row.get("evidence")
    evidence_ids: set[str] = set()
    if not isinstance(evidence, list):
        add(findings, "FAIL", row["_file"], row["_line"], case_id, "`evidence` must be a list")
        return evidence_ids
    if not evidence and not zero_evidence_allowed:
        add(findings, "FAIL", row["_file"], row["_line"], case_id, "`evidence` must be a non-empty list for answerable rows")
        return evidence_ids
    for index, item in enumerate(evidence):
        if not isinstance(item, dict):
            add(findings, "FAIL", row["_file"], row["_line"], case_id, f"evidence[{index}] must be an object")
            continue
        evidence_id = item.get("evidence_id")
        if not is_nonempty_string(evidence_id):
            add(findings, "FAIL", row["_file"], row["_line"], case_id, f"evidence[{index}].evidence_id is required")
        elif evidence_id in evidence_ids:
            add(findings, "FAIL", row["_file"], row["_line"], case_id, f"duplicate evidence_id: {evidence_id}")
        else:
            evidence_ids.add(evidence_id)
        for field in ("source_id", "path", "role", "statement"):
            if not is_nonempty_string(item.get(field)):
                add(findings, "FAIL", row["_file"], row["_line"], case_id, f"evidence[{index}].{field} is required")
        source_id = item.get("source_id")
        path = item.get("path")
        if is_nonempty_string(source_id) and sources and source_id not in sources:
            add(findings, "FAIL", row["_file"], row["_line"], case_id, f"evidence[{index}].source_id not in context bundle: {source_id}")
        if is_nonempty_string(path):
            if not resolve_path(path, repo_root).exists():
                add(findings, "WARN", row["_file"], row["_line"], case_id, f"evidence path does not exist: {path}")
            if reference_paths and path not in reference_paths and source_id not in reference_source_ids:
                add(findings, "WARN", row["_file"], row["_line"], case_id, f"evidence source is not covered by references: {path}")
        line_range = parse_line_range(item.get("lines"))
        if "lines" in item and item.get("lines") not in ("", None) and line_range is None:
            add(findings, "FAIL", row["_file"], row["_line"], case_id, f"evidence[{index}].lines must be N or N-M")
        if line_range and is_nonempty_string(source_id) and source_id in sources:
            line_count = sources[source_id].get("line_count")
            if isinstance(line_count, int) and line_count > 0 and line_range[1] > line_count:
                add(findings, "FAIL", row["_file"], row["_line"], case_id, f"evidence[{index}].lines exceed source line_count")
    return evidence_ids


def validate_rubric(row: dict[str, Any], findings: list[Finding], evidence_ids: set[str]) -> None:
    case_id = str(row.get("case_id", "<missing>"))
    rubric = row.get("answer_rubric")
    if not isinstance(rubric, dict):
        add(findings, "FAIL", row["_file"], row["_line"], case_id, "`answer_rubric` must be an object")
        return
    if not is_nonempty_string(rubric.get("answer_goal")):
        add(findings, "FAIL", row["_file"], row["_line"], case_id, "`answer_rubric.answer_goal` is required")
    atoms = rubric.get("required_atoms")
    if not isinstance(atoms, list) or not atoms:
        add(findings, "FAIL", row["_file"], row["_line"], case_id, "`answer_rubric.required_atoms` must be a non-empty list")
        atoms = []
    atom_ids: set[str] = set()
    conclusion_seen = False
    for index, atom in enumerate(atoms):
        if not isinstance(atom, dict):
            add(findings, "FAIL", row["_file"], row["_line"], case_id, f"required_atoms[{index}] must be an object")
            continue
        atom_id = atom.get("id")
        if not is_nonempty_string(atom_id):
            add(findings, "FAIL", row["_file"], row["_line"], case_id, f"required_atoms[{index}].id is required")
        elif atom_id in atom_ids:
            add(findings, "FAIL", row["_file"], row["_line"], case_id, f"duplicate atom id: {atom_id}")
        else:
            atom_ids.add(atom_id)
        role = atom.get("role")
        if role not in ATOM_ROLES:
            add(findings, "WARN", row["_file"], row["_line"], case_id, f"required_atoms[{index}] has non-standard role: {role}")
        if role == "conclusion":
            conclusion_seen = True
        if atom.get("match_type") not in MATCH_TYPES:
            add(findings, "WARN", row["_file"], row["_line"], case_id, f"required_atoms[{index}] has non-standard match_type: {atom.get('match_type')}")
        if not is_nonempty_string(atom.get("statement")):
            add(findings, "FAIL", row["_file"], row["_line"], case_id, f"required_atoms[{index}].statement is required")
        if not isinstance(atom.get("weight"), (int, float)) or atom.get("weight") <= 0:
            add(findings, "FAIL", row["_file"], row["_line"], case_id, f"required_atoms[{index}].weight must be positive")
        atom_evidence = atom.get("evidence_ids", [])
        if not isinstance(atom_evidence, list):
            add(findings, "FAIL", row["_file"], row["_line"], case_id, f"required_atoms[{index}].evidence_ids must be a list")
            atom_evidence = []
        for evidence_id in atom_evidence:
            if evidence_id not in evidence_ids:
                add(findings, "FAIL", row["_file"], row["_line"], case_id, f"required_atoms[{index}] references unknown evidence_id: {evidence_id}")
    if not conclusion_seen:
        add(findings, "FAIL", row["_file"], row["_line"], case_id, "`required_atoms` must include at least one conclusion atom")

    forbidden_atoms = rubric.get("forbidden_atoms", [])
    if forbidden_atoms is not None and not isinstance(forbidden_atoms, list):
        add(findings, "FAIL", row["_file"], row["_line"], case_id, "`forbidden_atoms` must be a list when present")
    elif isinstance(forbidden_atoms, list):
        for index, atom in enumerate(forbidden_atoms):
            if not isinstance(atom, dict):
                add(findings, "FAIL", row["_file"], row["_line"], case_id, f"forbidden_atoms[{index}] must be an object")
                continue
            if not is_nonempty_string(atom.get("id")) or not is_nonempty_string(atom.get("statement")):
                add(findings, "FAIL", row["_file"], row["_line"], case_id, f"forbidden_atoms[{index}] needs id and statement")
            if atom.get("match_type") not in (None, "semantic_contradiction"):
                add(findings, "WARN", row["_file"], row["_line"], case_id, f"forbidden_atoms[{index}].match_type should be semantic_contradiction")
            if atom.get("severity") not in (None, "fatal", "major", "minor"):
                add(findings, "WARN", row["_file"], row["_line"], case_id, f"forbidden_atoms[{index}] has non-standard severity: {atom.get('severity')}")

    policy = rubric.get("citation_policy")
    if policy is None:
        return
    if not isinstance(policy, dict):
        add(findings, "FAIL", row["_file"], row["_line"], case_id, "`citation_policy` must be an object")
        return
    if policy.get("required") not in CITATION_REQUIRED_VALUES:
        add(findings, "WARN", row["_file"], row["_line"], case_id, f"non-standard citation_policy.required: {policy.get('required')}")
    if policy.get("acceptable_granularity") not in CITATION_GRANULARITY_VALUES:
        add(findings, "WARN", row["_file"], row["_line"], case_id, f"non-standard citation granularity: {policy.get('acceptable_granularity')}")
    required_evidence = policy.get("required_evidence_ids", [])
    if not isinstance(required_evidence, list):
        add(findings, "FAIL", row["_file"], row["_line"], case_id, "`citation_policy.required_evidence_ids` must be a list")
        return
    for evidence_id in required_evidence:
        if evidence_id not in evidence_ids:
            add(findings, "FAIL", row["_file"], row["_line"], case_id, f"citation_policy references unknown evidence_id: {evidence_id}")


def structural_gate_record(row: dict[str, Any], signals: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
    case_id = str(row.get("case_id", "<missing>"))
    layer = label_code(row.get("layer"))
    answer_type = label_code(row.get("answer_type"))
    answerability = str(row.get("answerability", "answerable"))
    difficulty = row.get("difficulty")
    reason_codes: list[str] = []
    reason_messages: list[str] = []

    def add_reason(code: str, message: str | None = None) -> None:
        reason_codes.append(code)
        reason_messages.append(message or STRUCTURAL_REASON_MESSAGES[code])

    if not isinstance(difficulty, dict):
        add_reason("MISSING_DIFFICULTY")
        attrs: list[str] = []
    else:
        attrs = difficulty_attributes(row)
        if difficulty.get("axis1_layer") != layer:
            add_reason("DIFFICULTY_LAYER_MISMATCH")
        claim_sources = difficulty.get("claim_sources")
        if not isinstance(claim_sources, dict):
            add_reason("MISSING_CLAIM_SOURCES")
        else:
            for axis, attribute in difficulty_axis_attributes(row):
                signal_ids = claim_sources.get(attribute)
                if (
                    not isinstance(signal_ids, list)
                    or not signal_ids
                    or not all(is_nonempty_string(signal_id) for signal_id in signal_ids)
                ):
                    add_reason("MISSING_CLAIM_SOURCE_ATTRIBUTE")
                    continue
                if signals:
                    for signal_id in signal_ids:
                        signal = signals.get(signal_id)
                        if signal is None:
                            add_reason(
                                "UNKNOWN_CLAIM_SOURCE_SIGNAL",
                                f"`difficulty.claim_sources` references unknown signal_id: {signal_id}",
                            )
                            continue
                        if (
                            signal.get("project") != row.get("project")
                            or signal.get("axis") != axis
                            or signal.get("attribute") != attribute
                        ):
                            add_reason(
                                "CLAIM_SOURCE_SIGNAL_MISMATCH",
                                "`difficulty.claim_sources` signal does not match row project, axis, or attribute: "
                                f"{signal_id}",
                            )

    if len(set(attrs + ([layer] if layer == "L3" else []))) < 2:
        add_reason("INSUFFICIENT_DIFFICULTY_SIGNALS")

    source_ids = evidence_source_ids(row)
    if layer == "L2" and len(source_ids) < 2:
        add_reason("L2_SINGLE_SOURCE")
    if layer == "L3":
        if len(source_ids) < 2:
            add_reason("L3_SINGLE_SOURCE")
        if not has_atom_dependency(row):
            add_reason("L3_NO_ATOM_CHAIN")

    if "conditional_behavior" in attrs and not has_conditional_evidence_role(row):
        add_reason("CONDITIONAL_BEHAVIOR_WITHOUT_ROLE")

    rubric = row.get("answer_rubric", {})
    forbidden_atoms = rubric.get("forbidden_atoms", []) if isinstance(rubric, dict) else []
    if (
        answer_type in {"yes_no", "fact_check"}
        or answerability == "unanswerable_false_premise"
        or "false_premise" in attrs
    ) and not forbidden_atoms:
        add_reason("FORBIDDEN_ATOMS_REQUIRED")

    if "file_anchor_required" not in row_tags(row) and query_mentions_evidence_file(row):
        add_reason("FILE_ANCHOR_LEAK")

    return {
        "case_id": case_id,
        "pass": not reason_codes,
        "reason_codes": reason_codes,
        "reasons": reason_messages,
        "layer": layer,
        "answerability": answerability,
        "attributes": attrs,
    }


def validate_benchmark_rows(
    rows: list[dict[str, Any]],
    findings: list[Finding],
    repo_root: Path,
    sources: dict[str, dict[str, Any]],
    schema_version: str = "v1",
    signals: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    seen_case_ids: set[str] = set()
    structural_records: list[dict[str, Any]] = []
    for row in rows:
        case_id = str(row.get("case_id", "<missing>"))
        missing = sorted(REQUIRED_ROW_FIELDS - set(row))
        if missing:
            add(findings, "FAIL", row["_file"], row["_line"], case_id, f"row missing fields: {', '.join(missing)}")
        if not is_nonempty_string(row.get("case_id")):
            add(findings, "FAIL", row["_file"], row["_line"], case_id, "`case_id` is required")
        elif row["case_id"] in seen_case_ids:
            add(findings, "FAIL", row["_file"], row["_line"], case_id, "duplicate case_id")
        else:
            seen_case_ids.add(row["case_id"])
        if not is_nonempty_string(row.get("project")):
            add(findings, "FAIL", row["_file"], row["_line"], case_id, "`project` is required")
        validate_label_object(row, "layer", findings)
        if "capability" in row:
            validate_label_object(row, "capability", findings)
        validate_label_object(row, "answer_type", findings)
        answer_type = row.get("answer_type")
        if isinstance(answer_type, dict):
            code = answer_type.get("code")
            zh = answer_type.get("zh")
            if code not in ANSWER_TYPES:
                add(findings, "WARN", row["_file"], row["_line"], case_id, f"non-standard answer_type.code: {code}")
            elif zh != ANSWER_TYPES[code]:
                add(findings, "WARN", row["_file"], row["_line"], case_id, f"answer_type.zh should be {ANSWER_TYPES[code]!r}")
        if schema_version == "v1.1":
            answerability = row.get("answerability")
            if answerability not in ANSWERABILITY_VALUES:
                add(findings, "FAIL", row["_file"], row["_line"], case_id, "`answerability` is required in v1.1 mode")
        validate_query_rewrite(row, findings)
        evidence_ids = validate_references_and_evidence(
            row,
            findings,
            repo_root,
            sources,
            schema_version=schema_version,
        )
        validate_expected_answer(row, findings)
        validate_rubric(row, findings, evidence_ids)
        if schema_version == "v1.1":
            record = structural_gate_record(row, signals=signals)
            structural_records.append(record)
            for message in record["reasons"]:
                add(findings, "FAIL", row["_file"], row["_line"], case_id, message)
    return structural_records


def selected_samples(rows: list[dict[str, Any]], findings: list[Finding], sample_size: int) -> list[dict[str, Any]]:
    if sample_size <= 0:
        return []
    by_case = {str(row.get("case_id")): row for row in rows}
    selected: list[dict[str, Any]] = []
    selected_ids: set[str] = set()
    for finding in findings:
        if finding.case_id and finding.case_id in by_case and finding.case_id not in selected_ids:
            selected.append(by_case[finding.case_id])
            selected_ids.add(finding.case_id)
            if len(selected) >= sample_size:
                return selected
    seen_buckets: set[tuple[str, str, str]] = set()
    for row in rows:
        bucket = (
            str(row.get("project", "")),
            label_code(row.get("layer")),
            label_code(row.get("capability")),
        )
        case_id = str(row.get("case_id"))
        if case_id in selected_ids:
            continue
        if bucket in seen_buckets and len(selected) + len(seen_buckets) < sample_size:
            continue
        selected.append(row)
        selected_ids.add(case_id)
        seen_buckets.add(bucket)
        if len(selected) >= sample_size:
            return selected
    return selected


def read_snippet(path_value: str, lines_value: Any, repo_root: Path, context: int = 1) -> str:
    path = resolve_path(path_value, repo_root)
    line_range = parse_line_range(lines_value)
    if not path.exists() or line_range is None:
        return ""
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return ""
    start = max(1, line_range[0] - context)
    end = min(len(lines), line_range[1] + context)
    rendered = []
    for lineno in range(start, end + 1):
        rendered.append(f"{lineno}: {lines[lineno - 1]}")
    return "\n".join(rendered)


def coverage(rows: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    counters = {
        "project": Counter(str(row.get("project", "<missing>")) for row in rows),
        "layer": Counter(label_code(row.get("layer")) for row in rows),
        "capability": Counter(label_code(row.get("capability")) for row in rows),
        "answer_type": Counter(label_code(row.get("answer_type")) for row in rows),
    }
    return {key: dict(counter) for key, counter in counters.items()}


def make_lint_markdown(
    rows: list[dict[str, Any]],
    findings: list[Finding],
    samples: list[dict[str, Any]],
    repo_root: Path,
) -> str:
    fail_count = sum(1 for finding in findings if finding.severity == "FAIL")
    warn_count = sum(1 for finding in findings if finding.severity == "WARN")
    verdict = "FAIL" if fail_count else ("WARN" if warn_count else "PASS")
    lines = [
        "# Benchmark Validation Report",
        "",
        f"## Verdict: {verdict}",
        "",
        f"- Rows: {len(rows)}",
        f"- FAIL: {fail_count}",
        f"- WARN: {warn_count}",
        "",
        "## Coverage",
        "",
    ]
    cov = coverage(rows)
    for name, values in cov.items():
        lines.append(f"### {name}")
        for key, count in sorted(values.items()):
            lines.append(f"- `{key}`: {count}")
        lines.append("")
    lines.append("## Findings")
    lines.append("")
    if findings:
        for finding in findings[:200]:
            loc = f"{finding.file}:{finding.line}" if finding.line else finding.file
            case = f" `{finding.case_id}`" if finding.case_id else ""
            lines.append(f"- **{finding.severity}** {loc}{case}: {finding.message}")
    else:
        lines.append("- No findings.")
    lines.append("")
    lines.append("## Sampled Cases")
    lines.append("")
    for row in samples:
        lines.append(f"### {row.get('case_id')}")
        lines.append("")
        lines.append(f"- Query: {row.get('query')}")
        lines.append(f"- Rewrite: {row.get('query_rewrite')}")
        lines.append("- References:")
        for ref in row.get("references", []) if isinstance(row.get("references"), list) else []:
            if isinstance(ref, dict):
                lines.append(f"  - `{ref.get('source_id', '')}` `{ref.get('path', '')}`")
        lines.append("- Evidence:")
        for item in row.get("evidence", []) if isinstance(row.get("evidence"), list) else []:
            if not isinstance(item, dict):
                continue
            lines.append(f"  - `{item.get('evidence_id')}` `{item.get('path')}:{item.get('lines', '')}`: {item.get('statement')}")
            snippet = read_snippet(str(item.get("path", "")), item.get("lines"), repo_root)
            if snippet:
                lines.append("")
                lines.append("```text")
                lines.append(snippet)
                lines.append("```")
                lines.append("")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def normalize_contexts(row: dict[str, Any], top_k: int) -> list[dict[str, Any]]:
    contexts = row.get("retrieved_contexts")
    if contexts is None:
        contexts = row.get("retrieved")
    if contexts is None:
        contexts = row.get("contexts")
    if not isinstance(contexts, list):
        return []
    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(contexts, 1):
        if not isinstance(item, dict):
            continue
        rank = item.get("rank", index)
        if not isinstance(rank, int):
            rank = index
        if rank <= top_k:
            clone = dict(item)
            clone["rank"] = rank
            normalized.append(clone)
    normalized.sort(key=lambda item: item.get("rank", 999999))
    return normalized


def reference_matched(ref: dict[str, Any], contexts: list[dict[str, Any]]) -> bool:
    ref_source = ref.get("source_id")
    ref_path = ref.get("path")
    for ctx in contexts:
        if is_nonempty_string(ref_source) and ctx.get("source_id") == ref_source:
            return True
        if is_nonempty_string(ref_path) and ctx.get("path") == ref_path:
            return True
    return False


def evidence_matched(evidence: dict[str, Any], contexts: list[dict[str, Any]]) -> bool:
    ev_source = evidence.get("source_id")
    ev_path = evidence.get("path")
    for ctx in contexts:
        same_source = is_nonempty_string(ev_source) and ctx.get("source_id") == ev_source
        same_path = is_nonempty_string(ev_path) and ctx.get("path") == ev_path
        if (same_source or same_path) and line_ranges_overlap(evidence.get("lines"), ctx.get("lines")):
            return True
    return False


def answer_citation_pass(row: dict[str, Any], answer: str) -> bool:
    required, required_ids, granularity = citation_required(row)
    if not required:
        return True
    evidence_items = row.get("evidence", [])
    if not isinstance(evidence_items, list):
        return False
    required_set = set(required_ids)
    selected = [
        item for item in evidence_items
        if isinstance(item, dict) and (not required_set or item.get("evidence_id") in required_set)
    ]
    if not selected:
        return False
    for item in selected:
        path = str(item.get("path", ""))
        source_id = str(item.get("source_id", ""))
        if granularity == "source_only":
            if source_id and source_id in answer:
                continue
            if path and path in answer:
                continue
            return False
        if granularity == "path_only":
            if path and path in answer:
                continue
            return False
        citation = f"{path}:{item.get('lines')}" if item.get("lines") else path
        if citation not in answer:
            return False
    return True


def score_atoms(row: dict[str, Any], answer: str, lexical_threshold: float = 0.35) -> tuple[float, bool, bool, dict[str, bool]]:
    rubric = row.get("answer_rubric", {})
    atoms = rubric.get("required_atoms", []) if isinstance(rubric, dict) else []
    forbidden = rubric.get("forbidden_atoms", []) if isinstance(rubric, dict) else []
    total_weight = 0.0
    matched_weight = 0.0
    conclusion_total = 0
    conclusion_matched = 0
    atom_matches: dict[str, bool] = {}
    for atom in atoms if isinstance(atoms, list) else []:
        if not isinstance(atom, dict):
            continue
        atom_id = str(atom.get("id", ""))
        weight = atom.get("weight", 1)
        if not isinstance(weight, (int, float)) or weight <= 0:
            weight = 1
        matched = lexical_match(str(atom.get("statement", "")), answer, threshold=lexical_threshold)
        atom_matches[atom_id] = matched
        total_weight += float(weight)
        if matched:
            matched_weight += float(weight)
        if atom.get("role") == "conclusion":
            conclusion_total += 1
            if matched:
                conclusion_matched += 1
    fatal_forbidden = False
    for atom in forbidden if isinstance(forbidden, list) else []:
        if not isinstance(atom, dict):
            continue
        matched = lexical_match(str(atom.get("statement", "")), answer, threshold=0.65)
        atom_matches[str(atom.get("id", ""))] = matched
        if matched and atom.get("severity", "fatal") == "fatal":
            fatal_forbidden = True
    coverage_value = matched_weight / total_weight if total_weight else 0.0
    conclusion_ok = conclusion_total > 0 and conclusion_total == conclusion_matched
    return coverage_value, conclusion_ok, fatal_forbidden, atom_matches


def evaluate_case(row: dict[str, Any], run_row: dict[str, Any], top_k: int, answer_threshold: float) -> CaseEval:
    contexts = normalize_contexts(run_row, top_k)
    references = [ref for ref in row.get("references", []) if isinstance(ref, dict)]
    evidence_items = [item for item in row.get("evidence", []) if isinstance(item, dict)]
    no_gold_retrieval_required = missing_evidence_refusal(row)
    matched_refs = sum(1 for ref in references if reference_matched(ref, contexts))
    matched_evidence = sum(1 for item in evidence_items if evidence_matched(item, contexts))
    reference_recall = matched_refs / len(references) if references else (1.0 if no_gold_retrieval_required else 0.0)
    evidence_recall = matched_evidence / len(evidence_items) if evidence_items else (1.0 if no_gold_retrieval_required else 0.0)
    answer = str(run_row.get("answer", ""))
    citation_ok = answer_citation_pass(row, answer)
    atom_coverage, conclusions_ok, fatal_forbidden, atom_matches = score_atoms(row, answer)
    retrieval_ok = no_gold_retrieval_required or evidence_recall == 1.0
    answer_ok = conclusions_ok and atom_coverage >= answer_threshold and not fatal_forbidden
    if retrieval_ok and answer_ok and citation_ok:
        verdict = "PASS"
    elif evidence_recall == 0 or fatal_forbidden:
        verdict = "FAIL"
    else:
        verdict = "WARN"
    notes = []
    if not retrieval_ok:
        notes.append("evidence_recall below 1.0")
    if not conclusions_ok:
        notes.append("not all conclusion atoms matched by lexical heuristic")
    if atom_coverage < answer_threshold:
        notes.append("atom coverage below threshold")
    if fatal_forbidden:
        notes.append("fatal forbidden atom matched")
    if not citation_ok:
        notes.append("citation policy not satisfied")
    return CaseEval(
        case_id=str(row.get("case_id", "")),
        reference_recall=reference_recall,
        evidence_recall=evidence_recall,
        citation_pass=citation_ok,
        atom_coverage=atom_coverage,
        conclusion_atoms_matched=conclusions_ok,
        fatal_forbidden_matched=fatal_forbidden,
        verdict=verdict,
        notes=notes,
        atom_matches=atom_matches,
    )


def make_eval_markdown(evals: list[CaseEval], benchmark_rows: dict[str, dict[str, Any]], run_rows: dict[str, dict[str, Any]], sample_size: int) -> str:
    verdict_counter = Counter(item.verdict for item in evals)
    overall = "FAIL" if verdict_counter["FAIL"] else ("WARN" if verdict_counter["WARN"] else "PASS")
    ref_values = [item.reference_recall for item in evals]
    ev_values = [item.evidence_recall for item in evals]
    atom_values = [item.atom_coverage for item in evals]
    lines = [
        "# Benchmark Run Evaluation Report",
        "",
        f"## Verdict: {overall}",
        "",
        f"- Cases evaluated: {len(evals)}",
        f"- PASS: {verdict_counter['PASS']}",
        f"- WARN: {verdict_counter['WARN']}",
        f"- FAIL: {verdict_counter['FAIL']}",
        f"- Mean reference_recall@k: {statistics.mean(ref_values):.3f}" if ref_values else "- Mean reference_recall@k: n/a",
        f"- Mean evidence_recall@k: {statistics.mean(ev_values):.3f}" if ev_values else "- Mean evidence_recall@k: n/a",
        f"- Mean atom_coverage_heuristic: {statistics.mean(atom_values):.3f}" if atom_values else "- Mean atom_coverage_heuristic: n/a",
        "",
        "## Per-Case Results",
        "",
    ]
    for item in evals:
        note_text = "; ".join(item.notes) if item.notes else "ok"
        lines.append(
            f"- **{item.verdict}** `{item.case_id}` "
            f"ref={item.reference_recall:.2f} ev={item.evidence_recall:.2f} "
            f"atom={item.atom_coverage:.2f} citation={item.citation_pass}: {note_text}"
        )
    lines.append("")
    lines.append("## Sampled Cases")
    lines.append("")
    priority = sorted(evals, key=lambda item: {"FAIL": 0, "WARN": 1, "PASS": 2}.get(item.verdict, 3))
    for item in priority[:sample_size]:
        row = benchmark_rows[item.case_id]
        run = run_rows[item.case_id]
        lines.append(f"### {item.case_id} - {item.verdict}")
        lines.append("")
        lines.append(f"- Query: {row.get('query')}")
        lines.append(f"- Expected: {row.get('expected_answer')}")
        lines.append(f"- Answer: {run.get('answer')}")
        lines.append(f"- Atom matches: `{json.dumps(item.atom_matches, ensure_ascii=False)}`")
        lines.append("- Retrieved contexts:")
        for ctx in normalize_contexts(run, 10):
            lines.append(f"  - rank={ctx.get('rank')} `{ctx.get('source_id', '')}` `{ctx.get('path', '')}:{ctx.get('lines', '')}`")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def run_lint(args: argparse.Namespace) -> int:
    findings: list[Finding] = []
    rows: list[dict[str, Any]] = []
    for path in args.benchmark:
        rows.extend(load_jsonl(path, findings))
    sources = load_source_inventory(args.context_bundle, findings)
    signals = load_signal_index(args.context_bundle, findings)
    structural_records = validate_benchmark_rows(
        rows,
        findings,
        args.repo_root,
        sources,
        schema_version=args.schema_version,
        signals=signals,
    )
    fail_count = sum(1 for finding in findings if finding.severity == "FAIL")
    warn_count = sum(1 for finding in findings if finding.severity == "WARN")
    samples = selected_samples(rows, findings, args.sample_size)
    report = {
        "mode": "lint",
        "rows": len(rows),
        "fails": fail_count,
        "warnings": warn_count,
        "coverage": coverage(rows),
        "findings": [asdict(finding) for finding in findings],
        "sample_case_ids": [row.get("case_id") for row in samples],
    }
    print(f"Rows: {len(rows)}")
    print(f"FAIL: {fail_count}  WARN: {warn_count}")
    for finding in findings[:120]:
        loc = f"{finding.file}:{finding.line}" if finding.line else finding.file
        case = f" [{finding.case_id}]" if finding.case_id else ""
        print(f"{finding.severity} {loc}{case}: {finding.message}")
    if args.markdown_report:
        args.markdown_report.parent.mkdir(parents=True, exist_ok=True)
        args.markdown_report.write_text(make_lint_markdown(rows, findings, samples, args.repo_root), encoding="utf-8")
    if args.json_report:
        args.json_report.parent.mkdir(parents=True, exist_ok=True)
        args.json_report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.structural_gate_json:
        args.structural_gate_json.parent.mkdir(parents=True, exist_ok=True)
        args.structural_gate_json.write_text(
            json.dumps(structural_records, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    if fail_count:
        return 1
    if args.fail_on_warn and warn_count:
        return 1
    return 0


def run_evaluate(args: argparse.Namespace) -> int:
    findings: list[Finding] = []
    benchmark_rows = load_jsonl(args.benchmark, findings)
    sources = load_source_inventory(args.context_bundle, findings)
    signals = load_signal_index(args.context_bundle, findings)
    structural_records = validate_benchmark_rows(
        benchmark_rows,
        findings,
        args.repo_root,
        sources,
        schema_version=args.schema_version,
        signals=signals,
    )
    benchmark_by_id = {str(row.get("case_id")): row for row in benchmark_rows if is_nonempty_string(row.get("case_id"))}
    run_by_id: dict[str, dict[str, Any]] = {}
    for row in load_jsonl(args.run_results, findings):
        case_id = row.get("case_id")
        if not is_nonempty_string(case_id):
            add(findings, "FAIL", row["_file"], row["_line"], None, "run row missing case_id")
            continue
        if case_id in run_by_id:
            add(findings, "FAIL", row["_file"], row["_line"], str(case_id), "duplicate run case_id")
            continue
        if not is_nonempty_string(row.get("answer")):
            add(findings, "FAIL", row["_file"], row["_line"], str(case_id), "run row missing answer")
        run_by_id[str(case_id)] = row
    for case_id in benchmark_by_id:
        if case_id not in run_by_id:
            add(findings, "FAIL", str(args.run_results), None, case_id, "missing run result for benchmark case")
    evals: list[CaseEval] = []
    for case_id, row in benchmark_by_id.items():
        if case_id in run_by_id:
            evals.append(evaluate_case(row, run_by_id[case_id], args.top_k, args.answer_threshold))
    fail_count = sum(1 for finding in findings if finding.severity == "FAIL")
    warn_count = sum(1 for finding in findings if finding.severity == "WARN")
    verdict_counter = Counter(item.verdict for item in evals)
    print(f"Cases evaluated: {len(evals)}")
    print(f"Validation FAIL: {fail_count}  WARN: {warn_count}")
    print(f"Run PASS: {verdict_counter['PASS']}  WARN: {verdict_counter['WARN']}  FAIL: {verdict_counter['FAIL']}")
    for item in evals[:120]:
        print(
            f"{item.verdict} {item.case_id}: "
            f"ref={item.reference_recall:.2f} ev={item.evidence_recall:.2f} "
            f"atom={item.atom_coverage:.2f} citation={item.citation_pass}"
        )
    report = {
        "mode": "evaluate",
        "validation_fails": fail_count,
        "validation_warnings": warn_count,
        "run_counts": dict(verdict_counter),
        "cases": [asdict(item) for item in evals],
        "findings": [asdict(finding) for finding in findings],
    }
    if args.markdown_report:
        args.markdown_report.parent.mkdir(parents=True, exist_ok=True)
        args.markdown_report.write_text(make_eval_markdown(evals, benchmark_by_id, run_by_id, args.sample_size), encoding="utf-8")
    if args.json_report:
        args.json_report.parent.mkdir(parents=True, exist_ok=True)
        args.json_report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if fail_count:
        return 1
    if verdict_counter["FAIL"]:
        return 1
    return 0


def main() -> int:
    args = parse_args()
    if args.command == "lint":
        return run_lint(args)
    if args.command == "evaluate":
        return run_evaluate(args)
    raise AssertionError(f"unknown command: {args.command}")


if __name__ == "__main__":
    sys.exit(main())
