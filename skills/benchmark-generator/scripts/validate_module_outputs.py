#!/usr/bin/env python3
"""Validate host-LLM outputs from M2 / M3 / M5 / M6 / M7 stages.

Run after each stage of the v1.1 modular generator pipeline; see
skills/benchmark-generator/modules/contracts.md for I/O contracts.

Usage:

    validate_module_outputs.py --module M2 \\
        --candidates drafts/<project>.candidates.jsonl \\
        drafts/<project>.curated_evidence.jsonl

    validate_module_outputs.py --module M3 \\
        --candidates drafts/<project>.candidates.jsonl \\
        --curated drafts/<project>.curated_evidence.jsonl \\
        drafts/<project>.claims.jsonl

    validate_module_outputs.py --module M5 \\
        --candidates drafts/<project>.candidates.jsonl \\
        --curated drafts/<project>.curated_evidence.jsonl \\
        drafts/<project>.queries.jsonl

    validate_module_outputs.py --module M6 \\
        --candidates drafts/<project>.candidates.jsonl \\
        --curated drafts/<project>.curated_evidence.jsonl \\
        --claims drafts/<project>.claims.jsonl \\
        drafts/<project>.answers.jsonl

    validate_module_outputs.py --module M7 \\
        --candidates drafts/<project>.candidates.jsonl \\
        --curated drafts/<project>.curated_evidence.jsonl \\
        --claims drafts/<project>.claims.jsonl \\
        --answers drafts/<project>.answers.jsonl \\
        drafts/<project>.rubrics.jsonl

Exit codes: 0 = pass, 1 = FAIL findings present, 2 = bad CLI.
With --fail-on-warn, exits 1 if WARN findings present.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


M2_BOILERPLATE_REASONS = {
    "license_header",
    "copyright_continuation",
    "rst_heading_only",
    "sphinx_config_boilerplate",
    "ci_workflow_header",
    "assertion_macro_fence",
    "blank_or_separator",
    "no_guard_token_available",
    "layer_companion_missing",
    "other_boilerplate",
}
M3_KINDS = {"behavior", "state", "invariant", "negative", "comparison"}
ANSWER_TYPE_CODES = {
    "yes_no",
    "mechanism",
    "fact_check",
    "comparison",
    "location",
    "procedure",
    "negative",
    "synthesis",
}
ANSWERABILITY_VALUES = {
    "answerable",
    "unanswerable_missing_evidence",
    "unanswerable_false_premise",
    "unanswerable_ambiguous",
}
LAYERS = {"L1", "L2", "L3"}
YES_NO_PREFIX_TOKENS = ("会", "不会", "无法判断", "Yes", "No", "Cannot")
FACT_CHECK_PREFIX_TOKENS = ("支持", "不支持", "Confirmed", "Refuted")
UNAMBIGUOUS_NEGATIVE_TOKENS = ("无法判断", "只能给出有限结论", "Cannot")
RUBRIC_LIKE_FRAGMENTS = (
    "应说明",
    "应当",
    "应该",
    "请检索",
    "答案需要",
    "答案应",
    "should explain",
    "the answer should",
)
PATH_LINE_FRAGMENT_RE = re.compile(r"`([^`]+):(\d+(?:-\d+)?)`")

# M5 — refusal cues and interrogative markers
M5_REFUSAL_CUES = (
    "我没有看到可核验证据",
    "没有提供任何可用信息",
    "请说明能确认什么、不能确认什么",
    "没有给出可核验",
    "我没有看到",
)
M5_QUERY_TOKEN_RE = re.compile(r"[\W_]+")
M5_INTERROGATIVE_MARKERS_CN = ("吗", "是否", "能否", "?", "？", "什么", "怎样", "怎么", "哪")
M5_INTERROGATIVE_MARKERS_EN = ("?", "Does ", "Is ", "Are ", "Can ", "How ", "What ", "Where ", "Why ", "Will ")
M5_STYLES = {"colloquial", "contextual", "hypothesis-check", "follow-up"}
M5_QUERY_MIN_CHARS = 10
M5_QUERY_MAX_CHARS = 240

# M7 — atom shapes
M7_ATOM_ROLES = {
    "conclusion",
    "evidence_fact",
    "reasoning",
    "boundary",
    "location",
    "procedure_step",
    "comparison_point",
}
M7_MATCH_TYPES = {
    "semantic_yes_no",
    "semantic_fact",
    "semantic_reasoning",
    "path_or_symbol",
    "numeric_or_version",
    "list_set",
    "semantic_contradiction",
}
M7_POINTER_ATOM_RE = re.compile(r"^[\w./@+\-]+:\d+(?:-\d+)?\s*显示：")
M7_GENERIC_FORBIDDEN_RE = re.compile(r"^答案声称\s+.+\s+支持与引用证据相反的结论\s*$")
M7_FORBIDDEN_TRIGGER_ANSWER_TYPES = {"yes_no", "fact_check"}
M7_FORBIDDEN_TRIGGER_ANSWERABILITY = {
    "unanswerable_false_premise",
    "unanswerable_missing_evidence",
    "unanswerable_ambiguous",
}
M7_MAX_ATOMS = 4

# M2 — axis-attribute physical evidence checks
M2_GUARD_TOKEN_RE = re.compile(
    r"\bif\s*\(|\belse\b|\bcase\b|\bwhen\b|\bassert\b|\bposedge\b|\bnegedge\b|"
    r"@\s*\(|`ifdef\b|`ifndef\b|\brequire\b|\bassume\b|\bwait\b"
)
M2_DOC_PATH_HINTS = (
    "/doc/", "/docs/", "/document/", "README", "/manual/",
)
M2_DOC_SUFFIXES = (".rst", ".md", ".txt", ".adoc", ".html")
M2_CODE_PATH_HINTS = (
    "/src/", "/sw/", "/hw/", "/rtl/", "/sim/", "/lib/", "/include/",
)
M2_CODE_SUFFIXES = (
    ".c", ".h", ".cc", ".cpp", ".cxx", ".hpp", ".sv", ".v", ".vh",
    ".sva", ".py", ".rb", ".go", ".rs", ".java", ".scala", ".ts", ".js",
)


def _path_is_doc(path: str) -> bool:
    lower = path.lower()
    if any(lower.endswith(s) for s in M2_DOC_SUFFIXES):
        return True
    return any(hint.lower() in lower for hint in M2_DOC_PATH_HINTS)


def _path_is_code(path: str) -> bool:
    lower = path.lower()
    if any(lower.endswith(s) for s in M2_CODE_SUFFIXES):
        return True
    # Build scripts and YAML configs sit alongside code; treat as code for
    # the purpose of doc_code_divergence pairing.
    if lower.endswith(("Makefile", ".mk", ".cmake", ".yaml", ".yml", ".tcl", ".sh")):
        return True
    return any(hint.lower() in lower for hint in M2_CODE_PATH_HINTS) and not _path_is_doc(path)


# M8 — self-verifier
M8_CONFIDENCES = {"low", "medium", "high"}
M8_REFUSAL_TOKENS_CN = ("无法判断", "只能给出有限结论", "无法确认", "没有证据")
M8_REFUSAL_TOKENS_EN = ("Cannot ", "cannot confirm", "no evidence", "Unable to")


@dataclass
class Finding:
    severity: str
    case_id: str | None
    message: str


@dataclass
class CandidateRow:
    case_id: str
    layer: str
    answerability: str
    answer_type: str
    axis2: list[str]
    axis3: list[str]
    candidates: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class CuratedRow:
    case_id: str
    selected_evidence: list[dict[str, Any]]


@dataclass
class ClaimsRow:
    case_id: str
    claims: list[dict[str, Any]]


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        if not raw.strip():
            continue
        rows.append(json.loads(raw))
    return rows


def index_by_case(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        case = row.get("case_id")
        if isinstance(case, str):
            out[case] = row
    return out


def candidate_row(raw: dict[str, Any]) -> CandidateRow:
    plan = raw.get("row_plan") or {}
    return CandidateRow(
        case_id=str(raw.get("case_id", "")),
        layer=str(plan.get("layer", "")),
        answerability=str(plan.get("answerability", "")),
        answer_type=str((plan.get("answer_type") or {}).get("code", "")),
        axis2=list(plan.get("axis2_retrieval") or []),
        axis3=list(plan.get("axis3_reasoning") or []),
        candidates=list(raw.get("candidates") or []),
    )


def curated_row(raw: dict[str, Any]) -> CuratedRow:
    return CuratedRow(
        case_id=str(raw.get("case_id", "")),
        selected_evidence=list(raw.get("selected_evidence") or []),
    )


def claims_row(raw: dict[str, Any]) -> ClaimsRow:
    return ClaimsRow(
        case_id=str(raw.get("case_id", "")),
        claims=list(raw.get("claims") or []),
    )


def validate_m2(
    curated: list[dict[str, Any]],
    candidates: list[dict[str, Any]] | None,
) -> list[Finding]:
    findings: list[Finding] = []
    cands_by_case = index_by_case(candidates or [])
    case_ids_seen: set[str] = set()

    for raw_row in curated:
        row = curated_row(raw_row)
        if not row.case_id:
            findings.append(Finding("FAIL", None, "row missing case_id"))
            continue
        if row.case_id in case_ids_seen:
            findings.append(Finding("FAIL", row.case_id, "duplicate case_id"))
        case_ids_seen.add(row.case_id)

        cand_raw = cands_by_case.get(row.case_id)
        if candidates and cand_raw is None:
            findings.append(Finding("FAIL", row.case_id, "case_id not present in candidates file"))
            continue
        cand = candidate_row(cand_raw) if cand_raw else None

        evidence_ids: set[str] = set()
        evidence_paths: set[tuple[str, str]] = set()
        for index, span in enumerate(row.selected_evidence):
            if not isinstance(span, dict):
                findings.append(Finding("FAIL", row.case_id, f"selected_evidence[{index}] must be an object"))
                continue
            eid = span.get("evidence_id")
            if not isinstance(eid, str) or not eid:
                findings.append(Finding("FAIL", row.case_id, f"selected_evidence[{index}].evidence_id required"))
            elif eid in evidence_ids:
                findings.append(Finding("FAIL", row.case_id, f"duplicate evidence_id: {eid}"))
            else:
                evidence_ids.add(eid)
            for field_ in ("source_id", "path", "lines", "role", "statement"):
                if not isinstance(span.get(field_), str) or not span.get(field_):
                    findings.append(Finding("FAIL", row.case_id, f"selected_evidence[{index}].{field_} required"))
            path = str(span.get("path", ""))
            lines = str(span.get("lines", ""))
            if path and lines:
                evidence_paths.add((path, lines))
            statement = str(span.get("statement", ""))
            if cand:
                matched = next(
                    (
                        c
                        for c in cand.candidates
                        if c.get("path") == path and c.get("lines") == lines
                    ),
                    None,
                )
                if not matched:
                    findings.append(
                        Finding(
                            "FAIL",
                            row.case_id,
                            f"selected_evidence[{index}] ({path}:{lines}) not in candidates",
                        )
                    )
                elif statement:
                    raw_snippet = str(matched.get("raw_snippet") or "")
                    if raw_snippet and statement in raw_snippet:
                        findings.append(
                            Finding(
                                "FAIL",
                                row.case_id,
                                f"selected_evidence[{index}].statement is a verbatim substring of raw_snippet",
                            )
                        )
            if len(statement) >= 200:
                findings.append(
                    Finding(
                        "WARN",
                        row.case_id,
                        f"selected_evidence[{index}].statement >= 200 chars (possibly over-broad)",
                    )
                )

        if cand:
            if cand.answerability == "unanswerable_missing_evidence":
                if row.selected_evidence:
                    findings.append(
                        Finding(
                            "FAIL",
                            row.case_id,
                            "unanswerable_missing_evidence must have empty selected_evidence",
                        )
                    )
            else:
                distinct_sources = {str(s.get("source_id", "")) for s in row.selected_evidence}
                distinct_sources.discard("")
                if cand.layer == "L1" and len(row.selected_evidence) != 1:
                    findings.append(
                        Finding("FAIL", row.case_id, "L1 requires exactly one selected evidence span")
                    )
                if cand.layer in {"L2", "L3"} and len(distinct_sources) < 2 and row.selected_evidence:
                    findings.append(
                        Finding(
                            "FAIL",
                            row.case_id,
                            f"{cand.layer} requires evidence from >= 2 distinct source_ids",
                        )
                    )
                # Build a (path, lines) → raw_snippet map from the candidate
                # list so axis-attribute checks can inspect what the analyzer
                # actually pulled, not the LLM-authored statement.
                candidate_raw_by_key: dict[tuple[str, str], str] = {}
                if cand_raw:
                    for c in cand_raw.get("candidates") or []:
                        if not isinstance(c, dict):
                            continue
                        key = (str(c.get("path", "")), str(c.get("lines", "")))
                        candidate_raw_by_key[key] = str(c.get("raw_snippet") or "")
                selected_raw_snippets: list[str] = []
                for span in row.selected_evidence:
                    key = (str(span.get("path", "")), str(span.get("lines", "")))
                    snippet = candidate_raw_by_key.get(key, "")
                    if snippet:
                        selected_raw_snippets.append(snippet)

                if "conditional_behavior" in cand.axis3 and row.selected_evidence:
                    if not any(M2_GUARD_TOKEN_RE.search(s) for s in selected_raw_snippets):
                        findings.append(
                            Finding(
                                "FAIL",
                                row.case_id,
                                "conditional_behavior claimed but no guard tokens (if/else/case/assert/posedge/...) in any selected raw_snippet",
                            )
                        )

                if "doc_code_divergence" in cand.axis3 and row.selected_evidence:
                    paths = [str(s.get("path", "")) for s in row.selected_evidence]
                    has_doc = any(_path_is_doc(p) for p in paths)
                    has_code = any(_path_is_code(p) for p in paths)
                    if not (has_doc and has_code):
                        findings.append(
                            Finding(
                                "FAIL",
                                row.case_id,
                                "doc_code_divergence claimed but evidence lacks one of {doc source, code source}",
                            )
                        )

        rejected = raw_row.get("rejected_candidates") or []
        for index, rej in enumerate(rejected):
            if not isinstance(rej, dict):
                findings.append(Finding("FAIL", row.case_id, f"rejected_candidates[{index}] must be an object"))
                continue
            reason = rej.get("reason")
            if reason not in M2_BOILERPLATE_REASONS:
                findings.append(
                    Finding(
                        "FAIL",
                        row.case_id,
                        f"rejected_candidates[{index}].reason invalid: {reason!r}",
                    )
                )

    if candidates:
        missing = set(cands_by_case) - case_ids_seen
        for case_id in sorted(missing):
            findings.append(Finding("FAIL", case_id, "case_id present in candidates but missing from curated_evidence"))

    return findings


def validate_m3(
    claims_rows: list[dict[str, Any]],
    curated: list[dict[str, Any]],
    candidates: list[dict[str, Any]] | None,
) -> list[Finding]:
    findings: list[Finding] = []
    curated_by_case = index_by_case(curated)
    cands_by_case = index_by_case(candidates or [])
    case_ids_seen: set[str] = set()

    for raw_row in claims_rows:
        row = claims_row(raw_row)
        if not row.case_id:
            findings.append(Finding("FAIL", None, "row missing case_id"))
            continue
        if row.case_id in case_ids_seen:
            findings.append(Finding("FAIL", row.case_id, "duplicate case_id"))
        case_ids_seen.add(row.case_id)

        cur_raw = curated_by_case.get(row.case_id)
        if cur_raw is None:
            findings.append(Finding("FAIL", row.case_id, "case_id not present in curated_evidence"))
            continue
        cur = curated_row(cur_raw)
        evidence_ids_available = {
            str(s.get("evidence_id"))
            for s in cur.selected_evidence
            if isinstance(s.get("evidence_id"), str)
        }
        statements = [
            str(s.get("statement") or "") for s in cur.selected_evidence if isinstance(s, dict)
        ]
        candidate_snippets: list[str] = []
        if cands_by_case:
            cand_raw = cands_by_case.get(row.case_id)
            if cand_raw:
                for c in (cand_raw.get("candidates") or []):
                    snippet = str(c.get("raw_snippet") or "")
                    if snippet:
                        candidate_snippets.append(snippet)

        cand = candidate_row(cands_by_case.get(row.case_id, {})) if cands_by_case else None

        if not row.claims:
            if cand and cand.answerability == "unanswerable_missing_evidence":
                findings.append(
                    Finding("FAIL", row.case_id, "unanswerable_missing_evidence row needs >= 1 claim of kind=negative")
                )
            elif cur.selected_evidence:
                findings.append(Finding("FAIL", row.case_id, "claims must be non-empty when evidence exists"))
            continue

        ids_seen: set[str] = set()
        chain_evidence_seen: set[str] = set()
        has_chain = False
        for index, claim in enumerate(row.claims):
            if not isinstance(claim, dict):
                findings.append(Finding("FAIL", row.case_id, f"claims[{index}] must be an object"))
                continue
            cid = claim.get("id")
            if not isinstance(cid, str) or not cid:
                findings.append(Finding("FAIL", row.case_id, f"claims[{index}].id required"))
            elif cid in ids_seen:
                findings.append(Finding("FAIL", row.case_id, f"duplicate claim id: {cid}"))
            else:
                ids_seen.add(cid)
            text = claim.get("text")
            if not isinstance(text, str) or not text.strip():
                findings.append(Finding("FAIL", row.case_id, f"claims[{index}].text required"))
                text = ""
            elif len(text) < 30:
                findings.append(Finding("WARN", row.case_id, f"claims[{index}].text < 30 chars"))
            kind = claim.get("kind")
            if kind not in M3_KINDS:
                findings.append(Finding("FAIL", row.case_id, f"claims[{index}].kind invalid: {kind!r}"))
            evidence_ids = claim.get("evidence_ids")
            if not isinstance(evidence_ids, list):
                findings.append(Finding("FAIL", row.case_id, f"claims[{index}].evidence_ids must be a list"))
                evidence_ids = []
            for eid in evidence_ids:
                if eid not in evidence_ids_available:
                    findings.append(
                        Finding("FAIL", row.case_id, f"claims[{index}] references unknown evidence_id {eid!r}")
                    )
                else:
                    if eid in chain_evidence_seen:
                        has_chain = True
                    chain_evidence_seen.add(eid)
            if kind == "negative" and evidence_ids and cand and cand.answerability == "unanswerable_missing_evidence":
                findings.append(
                    Finding(
                        "FAIL",
                        row.case_id,
                        f"claims[{index}] of kind=negative on missing-evidence row should have empty evidence_ids",
                    )
                )
            if text and any(text in s for s in statements):
                findings.append(
                    Finding("FAIL", row.case_id, f"claims[{index}].text is a verbatim substring of M2 statement")
                )
            if text and any(text in s for s in candidate_snippets):
                findings.append(
                    Finding("FAIL", row.case_id, f"claims[{index}].text is a verbatim substring of raw_snippet")
                )

        if cand and cand.layer == "L3" and cand.answerability == "answerable":
            if not has_chain:
                findings.append(
                    Finding(
                        "FAIL",
                        row.case_id,
                        "L3 answerable row needs claims sharing evidence_ids to form a chain",
                    )
                )
        if len(row.claims) > 3:
            findings.append(Finding("WARN", row.case_id, f"{len(row.claims)} claims (cap is 3)"))

    expected = set(curated_by_case)
    missing = expected - case_ids_seen - {
        cid for cid, raw in curated_by_case.items() if not (raw.get("selected_evidence") or [])
        and (not cands_by_case or candidate_row(cands_by_case.get(cid, {})).answerability != "unanswerable_missing_evidence")
    }
    for case_id in sorted(missing):
        findings.append(Finding("FAIL", case_id, "case_id present in curated_evidence but missing from claims"))

    return findings


def validate_m6(
    answer_rows: list[dict[str, Any]],
    candidates: list[dict[str, Any]] | None,
    curated: list[dict[str, Any]],
    claims: list[dict[str, Any]] | None,
) -> list[Finding]:
    findings: list[Finding] = []
    cands_by_case = index_by_case(candidates or [])
    curated_by_case = index_by_case(curated)
    claims_by_case = index_by_case(claims or [])
    case_ids_seen: set[str] = set()

    for raw_row in answer_rows:
        case_id = raw_row.get("case_id")
        if not isinstance(case_id, str) or not case_id:
            findings.append(Finding("FAIL", None, "row missing case_id"))
            continue
        if case_id in case_ids_seen:
            findings.append(Finding("FAIL", case_id, "duplicate case_id"))
        case_ids_seen.add(case_id)

        cur_raw = curated_by_case.get(case_id)
        if cur_raw is None:
            findings.append(Finding("FAIL", case_id, "case_id not in curated_evidence"))
            continue
        cur = curated_row(cur_raw)
        cand = candidate_row(cands_by_case.get(case_id, {})) if cands_by_case else None

        answer = raw_row.get("expected_answer")
        if not isinstance(answer, str) or not answer.strip():
            findings.append(Finding("FAIL", case_id, "expected_answer required"))
            continue

        for fragment in RUBRIC_LIKE_FRAGMENTS:
            if fragment in answer:
                findings.append(Finding("FAIL", case_id, f"expected_answer contains rubric language: {fragment!r}"))
        if "这些行显示：" in answer:
            findings.append(Finding("FAIL", case_id, "expected_answer contains literal 这些行显示： prefix"))

        evidence_lookup = {
            (str(s.get("path", "")), str(s.get("lines", ""))): s for s in cur.selected_evidence
        }
        citation_paths = raw_row.get("citation_paths") or []
        if not isinstance(citation_paths, list):
            findings.append(Finding("FAIL", case_id, "citation_paths must be a list"))
            citation_paths = []
        for path_line in citation_paths:
            if not isinstance(path_line, str) or ":" not in path_line:
                findings.append(Finding("FAIL", case_id, f"citation_paths entry invalid: {path_line!r}"))
                continue
            path, _, lines = path_line.rpartition(":")
            key = (path, lines)
            if key not in evidence_lookup:
                findings.append(
                    Finding("FAIL", case_id, f"citation_paths {path_line!r} not in curated_evidence")
                )
            if f"`{path_line}`" not in answer:
                findings.append(
                    Finding("FAIL", case_id, f"expected_answer missing backtick citation `{path_line}`")
                )

        if cand:
            if cand.answerability == "unanswerable_missing_evidence" and citation_paths:
                findings.append(
                    Finding("FAIL", case_id, "unanswerable_missing_evidence row must have empty citation_paths")
                )
            if cand.answer_type == "yes_no":
                first_seg = re.split(r"[。.!?？]", answer.strip(), maxsplit=1)[0]
                if not any(token in first_seg for token in YES_NO_PREFIX_TOKENS):
                    findings.append(
                        Finding("FAIL", case_id, "yes_no expected_answer first sentence missing 会/不会/无法判断 prefix")
                    )
            elif cand.answer_type == "fact_check":
                first_seg = re.split(r"[。.!?？]", answer.strip(), maxsplit=1)[0]
                if not any(token in first_seg for token in FACT_CHECK_PREFIX_TOKENS):
                    findings.append(
                        Finding("FAIL", case_id, "fact_check expected_answer first sentence missing 支持/不支持 prefix")
                    )
            if cand.answerability in {"unanswerable_missing_evidence", "unanswerable_ambiguous"}:
                first_seg = re.split(r"[。.!?？]", answer.strip(), maxsplit=1)[0]
                if not any(token in first_seg for token in UNAMBIGUOUS_NEGATIVE_TOKENS):
                    findings.append(
                        Finding(
                            "FAIL",
                            case_id,
                            "unanswerable_missing_evidence/ambiguous first sentence should begin with 无法判断/只能给出有限结论",
                        )
                    )

        for span in cur.selected_evidence:
            raw_snippet_field = "raw_snippet"
            raw = str(span.get(raw_snippet_field, ""))
            # raw_snippet is not stored on curated_evidence; pull from candidates if present
            if not raw and cand and cands_by_case:
                cand_raw = cands_by_case.get(case_id)
                if cand_raw:
                    for c in cand_raw.get("candidates") or []:
                        if c.get("path") == span.get("path") and c.get("lines") == span.get("lines"):
                            raw = str(c.get("raw_snippet") or "")
                            break
            if raw and len(raw) > 30 and raw in answer:
                findings.append(
                    Finding("FAIL", case_id, f"expected_answer contains verbatim raw_snippet ≥30 chars from {span.get('path')}:{span.get('lines')}")
                )

        if len(answer) > 400:
            findings.append(Finding("WARN", case_id, f"expected_answer {len(answer)} chars > 400"))
        if len(citation_paths) > 5:
            findings.append(Finding("WARN", case_id, f"citation_paths length {len(citation_paths)} > 5"))

    expected = set(curated_by_case)
    missing = expected - case_ids_seen - m2_dropped_case_ids(curated, candidates)
    for case_id in sorted(missing):
        findings.append(Finding("FAIL", case_id, "case_id present in curated_evidence but missing from answers"))

    return findings


def m2_dropped_case_ids(
    curated_rows: list[dict[str, Any]],
    candidates: list[dict[str, Any]] | None,
) -> set[str]:
    """Return case_ids whose M2 selected_evidence is empty AND that aren't
    legitimately empty (missing_evidence rows). Downstream stages may
    legitimately skip these rows."""
    if not candidates:
        return set()
    cands_by_case = index_by_case(candidates)
    dropped: set[str] = set()
    for raw in curated_rows:
        case_id = raw.get("case_id")
        if not isinstance(case_id, str):
            continue
        if raw.get("selected_evidence"):
            continue
        cand = candidate_row(cands_by_case.get(case_id, {}))
        if cand.answerability != "unanswerable_missing_evidence":
            dropped.add(case_id)
    return dropped


def evidence_basename_tokens(curated_rows: list[dict[str, Any]]) -> set[tuple[str, frozenset[str]]]:
    """Return {(case_id, basename_token_set)} for each curated row."""
    out: set[tuple[str, frozenset[str]]] = set()
    for raw in curated_rows:
        case_id = raw.get("case_id")
        if not isinstance(case_id, str):
            continue
        tokens: set[str] = set()
        for span in raw.get("selected_evidence") or []:
            if not isinstance(span, dict):
                continue
            stem = Path(str(span.get("path", ""))).stem
            for tok in M5_QUERY_TOKEN_RE.split(stem):
                if len(tok) >= 3:
                    tokens.add(tok.lower())
        out.add((case_id, frozenset(tokens)))
    return out


def query_token_set(query: str) -> set[str]:
    return {tok.lower() for tok in M5_QUERY_TOKEN_RE.split(query) if len(tok) >= 3}


def has_interrogative_marker(query: str) -> bool:
    if any(marker in query for marker in M5_INTERROGATIVE_MARKERS_CN):
        return True
    # English markers are case-sensitive on the leading capitalization so
    # we don't false-positive on "is" inside a word.
    return any(marker in query for marker in M5_INTERROGATIVE_MARKERS_EN)


def validate_m5(
    query_rows: list[dict[str, Any]],
    candidates: list[dict[str, Any]],
    curated: list[dict[str, Any]],
) -> list[Finding]:
    findings: list[Finding] = []
    cands_by_case = index_by_case(candidates)
    curated_by_case = index_by_case(curated)
    seen: set[str] = set()
    surface_counts: dict[str, int] = {}

    for raw in query_rows:
        case_id = raw.get("case_id")
        if not isinstance(case_id, str) or not case_id:
            findings.append(Finding("FAIL", None, "row missing case_id"))
            continue
        if case_id in seen:
            findings.append(Finding("FAIL", case_id, "duplicate case_id"))
        seen.add(case_id)

        query = raw.get("query")
        rewrite = raw.get("query_rewrite")
        if not isinstance(query, str) or not query.strip():
            findings.append(Finding("FAIL", case_id, "query required"))
            continue
        if not isinstance(rewrite, str) or not rewrite.strip():
            findings.append(Finding("FAIL", case_id, "query_rewrite required"))

        if len(query) < M5_QUERY_MIN_CHARS:
            findings.append(Finding("FAIL", case_id, f"query length {len(query)} < {M5_QUERY_MIN_CHARS}"))
        if len(query) > M5_QUERY_MAX_CHARS:
            findings.append(Finding("FAIL", case_id, f"query length {len(query)} > {M5_QUERY_MAX_CHARS}"))

        style = raw.get("style")
        if style is not None and style not in M5_STYLES:
            findings.append(Finding("FAIL", case_id, f"style {style!r} not in {sorted(M5_STYLES)}"))

        cand_raw = cands_by_case.get(case_id)
        cand = candidate_row(cand_raw) if cand_raw else None
        tags = set()
        style_hint = None
        if cand_raw:
            tags = {str(t) for t in (cand_raw.get("tags") or []) if isinstance(t, str)}
            row_plan = cand_raw.get("row_plan") or {}
            style_hint = row_plan.get("style_hint")
            if style_hint and style and style != style_hint:
                findings.append(
                    Finding("WARN", case_id, f"style {style!r} differs from row_plan style_hint {style_hint!r}")
                )

        # Anchor-token leak: any evidence-basename token of length ≥ 3 appearing
        # as a standalone token in the query. Skip when the row opts in via tag.
        cur_raw = curated_by_case.get(case_id)
        if cur_raw and "file_anchor_required" not in tags:
            q_tokens = query_token_set(query)
            for span in cur_raw.get("selected_evidence") or []:
                stem = Path(str(span.get("path", ""))).stem
                e_tokens = {t.lower() for t in M5_QUERY_TOKEN_RE.split(stem) if len(t) >= 3}
                overlap = e_tokens & q_tokens
                if len(overlap) >= 2:
                    findings.append(
                        Finding(
                            "FAIL",
                            case_id,
                            f"query leaks ≥2 evidence-basename tokens {sorted(overlap)} (file {stem})",
                        )
                    )
                    break
                if e_tokens and overlap and len(e_tokens) == 1:
                    # single-token basename: any match is leakage
                    findings.append(
                        Finding(
                            "FAIL",
                            case_id,
                            f"query leaks unique basename token {sorted(overlap)} (file {stem})",
                        )
                    )
                    break

        # Refusal cues on unanswerable rows.
        if cand and cand.answerability.startswith("unanswerable"):
            for cue in M5_REFUSAL_CUES:
                if cue in query:
                    findings.append(
                        Finding(
                            "FAIL",
                            case_id,
                            f"unanswerable query telegraphs the refusal: {cue!r}",
                        )
                    )
                    break

        # Interrogative marker for question-shaped answer types.
        if cand and cand.answer_type in {"yes_no", "fact_check"}:
            if not has_interrogative_marker(query):
                findings.append(
                    Finding(
                        "FAIL",
                        case_id,
                        f"{cand.answer_type} query missing interrogative marker (吗/是否/?/Does/Is/Can)",
                    )
                )

        # Style-length sanity (WARN only).
        if style_hint == "colloquial" and len(query) > 60:
            findings.append(Finding("WARN", case_id, f"colloquial query is {len(query)} chars (> 60)"))
        if style_hint == "contextual" and len(query) < 25:
            findings.append(Finding("WARN", case_id, f"contextual query is {len(query)} chars (< 25)"))

        # Surface-form fingerprint for corpus diversity (compute now, audit after).
        surface_counts[query.strip()] = surface_counts.get(query.strip(), 0) + 1

    # Corpus-level: same query verbatim across ≥ 3 rows is suspicious.
    for fingerprint, count in surface_counts.items():
        if count >= 3:
            findings.append(
                Finding(
                    "WARN",
                    None,
                    f"query {fingerprint[:60]!r} repeats {count}× across the corpus",
                )
            )

    expected = set(cands_by_case)
    missing = expected - seen - m2_dropped_case_ids(curated, candidates)
    for case_id in sorted(missing):
        findings.append(Finding("FAIL", case_id, "case_id present in candidates but missing from queries"))

    return findings


def validate_m7(
    rubric_rows: list[dict[str, Any]],
    candidates: list[dict[str, Any]],
    curated: list[dict[str, Any]],
    claims: list[dict[str, Any]] | None,
    answers: list[dict[str, Any]] | None,
) -> list[Finding]:
    findings: list[Finding] = []
    cands_by_case = index_by_case(candidates)
    curated_by_case = index_by_case(curated)
    claims_by_case = index_by_case(claims or [])
    seen: set[str] = set()

    for raw in rubric_rows:
        case_id = raw.get("case_id")
        if not isinstance(case_id, str) or not case_id:
            findings.append(Finding("FAIL", None, "row missing case_id"))
            continue
        if case_id in seen:
            findings.append(Finding("FAIL", case_id, "duplicate case_id"))
        seen.add(case_id)

        cand_raw = cands_by_case.get(case_id)
        cand = candidate_row(cand_raw) if cand_raw else None
        cur_raw = curated_by_case.get(case_id)
        if cur_raw is None:
            findings.append(Finding("FAIL", case_id, "case_id not in curated_evidence"))
            continue
        cur = curated_row(cur_raw)

        evidence_ids = {
            str(s.get("evidence_id"))
            for s in cur.selected_evidence
            if isinstance(s.get("evidence_id"), str)
        }
        evidence_bodies = [
            str(s.get("statement") or "") for s in cur.selected_evidence if isinstance(s, dict)
        ]
        claim_bodies: list[str] = []
        claims_raw = claims_by_case.get(case_id)
        if claims_raw:
            for c in claims_raw.get("claims") or []:
                if isinstance(c, dict):
                    text = str(c.get("text") or "")
                    if text:
                        claim_bodies.append(text)

        required = raw.get("required_atoms")
        if not isinstance(required, list) or not required:
            findings.append(Finding("FAIL", case_id, "required_atoms must be a non-empty list"))
            required = []
        if len(required) > M7_MAX_ATOMS:
            findings.append(Finding("WARN", case_id, f"{len(required)} required_atoms exceeds cap of {M7_MAX_ATOMS}"))

        atom_ids: set[str] = set()
        has_conclusion = False
        has_chain = False
        match_types_seen: set[str] = set()
        nonverbatim_reasoning = False
        for index, atom in enumerate(required):
            if not isinstance(atom, dict):
                findings.append(Finding("FAIL", case_id, f"required_atoms[{index}] must be an object"))
                continue
            aid = atom.get("id")
            if not isinstance(aid, str) or not aid:
                findings.append(Finding("FAIL", case_id, f"required_atoms[{index}].id required"))
            elif aid in atom_ids:
                findings.append(Finding("FAIL", case_id, f"duplicate atom id: {aid}"))
            else:
                atom_ids.add(aid)
            role = atom.get("role")
            if role not in M7_ATOM_ROLES:
                findings.append(Finding("FAIL", case_id, f"required_atoms[{index}].role invalid: {role!r}"))
            if role == "conclusion":
                has_conclusion = True
            match_type = atom.get("match_type")
            if match_type not in M7_MATCH_TYPES:
                findings.append(Finding("FAIL", case_id, f"required_atoms[{index}].match_type invalid: {match_type!r}"))
            else:
                match_types_seen.add(match_type)
            weight = atom.get("weight")
            if not isinstance(weight, (int, float)) or weight <= 0:
                findings.append(Finding("FAIL", case_id, f"required_atoms[{index}].weight must be > 0"))
            statement = atom.get("statement")
            if not isinstance(statement, str) or not statement.strip():
                findings.append(Finding("FAIL", case_id, f"required_atoms[{index}].statement required"))
                statement = ""
            statement = statement.strip()
            if M7_POINTER_ATOM_RE.match(statement):
                findings.append(
                    Finding(
                        "FAIL",
                        case_id,
                        f"required_atoms[{index}].statement is pointer-style path:lines 显示：…",
                    )
                )
            if statement and any(statement in body for body in evidence_bodies):
                findings.append(
                    Finding(
                        "FAIL",
                        case_id,
                        f"required_atoms[{index}].statement is verbatim substring of M2 statement",
                    )
                )
            if statement and any(statement in body for body in claim_bodies):
                findings.append(
                    Finding(
                        "FAIL",
                        case_id,
                        f"required_atoms[{index}].statement is verbatim substring of M3 claim text",
                    )
                )
            atom_evidence = atom.get("evidence_ids")
            if not isinstance(atom_evidence, list):
                findings.append(Finding("FAIL", case_id, f"required_atoms[{index}].evidence_ids must be a list"))
                atom_evidence = []
            for eid in atom_evidence:
                if eid not in evidence_ids:
                    findings.append(
                        Finding("FAIL", case_id, f"required_atoms[{index}].evidence_ids references unknown {eid!r}")
                    )
            depends_on = atom.get("depends_on") or []
            if not isinstance(depends_on, list):
                findings.append(Finding("FAIL", case_id, f"required_atoms[{index}].depends_on must be a list"))
                depends_on = []
            for dep in depends_on:
                if dep not in atom_ids and dep != aid:
                    # Forward references are allowed only if the dependency comes later;
                    # we'll cross-check after the loop.
                    pass
                if dep:
                    has_chain = True
            if role == "reasoning" and statement:
                if not any(statement in body for body in evidence_bodies) and not any(
                    statement in body for body in claim_bodies
                ):
                    nonverbatim_reasoning = True

        # depends_on must reference an existing atom id
        for index, atom in enumerate(required):
            if not isinstance(atom, dict):
                continue
            for dep in atom.get("depends_on") or []:
                if dep not in atom_ids:
                    findings.append(
                        Finding(
                            "FAIL",
                            case_id,
                            f"required_atoms[{index}].depends_on references unknown atom id {dep!r}",
                        )
                    )

        if not has_conclusion:
            findings.append(Finding("FAIL", case_id, "required_atoms must include at least one conclusion atom"))

        if cand and cand.layer == "L3" and cand.answerability == "answerable" and not has_chain:
            findings.append(Finding("FAIL", case_id, "L3 answerable row needs at least one atom with non-empty depends_on"))

        # Forbidden atoms
        forbidden = raw.get("forbidden_atoms") or []
        if not isinstance(forbidden, list):
            findings.append(Finding("FAIL", case_id, "forbidden_atoms must be a list"))
            forbidden = []

        for index, atom in enumerate(forbidden):
            if not isinstance(atom, dict):
                findings.append(Finding("FAIL", case_id, f"forbidden_atoms[{index}] must be an object"))
                continue
            if not isinstance(atom.get("id"), str) or not atom["id"]:
                findings.append(Finding("FAIL", case_id, f"forbidden_atoms[{index}].id required"))
            statement = atom.get("statement")
            if not isinstance(statement, str) or not statement.strip():
                findings.append(Finding("FAIL", case_id, f"forbidden_atoms[{index}].statement required"))
                statement = ""
            if M7_GENERIC_FORBIDDEN_RE.match(statement.strip()):
                findings.append(
                    Finding(
                        "FAIL",
                        case_id,
                        f"forbidden_atoms[{index}].statement is generic boilerplate; name the actual misconception",
                    )
                )
            mt = atom.get("match_type")
            if mt is not None and mt not in M7_MATCH_TYPES:
                findings.append(Finding("FAIL", case_id, f"forbidden_atoms[{index}].match_type invalid: {mt!r}"))
            severity = atom.get("severity")
            if severity is not None and severity not in {"fatal", "major", "minor"}:
                findings.append(Finding("FAIL", case_id, f"forbidden_atoms[{index}].severity invalid: {severity!r}"))

        if cand:
            trigger_forbidden = (
                cand.answer_type in M7_FORBIDDEN_TRIGGER_ANSWER_TYPES
                or cand.answerability in M7_FORBIDDEN_TRIGGER_ANSWERABILITY
            )
            if trigger_forbidden and not forbidden:
                findings.append(
                    Finding(
                        "FAIL",
                        case_id,
                        f"row requires ≥1 forbidden_atom (answer_type={cand.answer_type}, answerability={cand.answerability})",
                    )
                )
            if cand.answer_type == "yes_no" and "semantic_yes_no" not in match_types_seen:
                findings.append(
                    Finding("WARN", case_id, "yes_no row has no atom with match_type=semantic_yes_no")
                )
            if "implicit_domain_knowledge" in cand.axis3 and not nonverbatim_reasoning:
                findings.append(
                    Finding(
                        "FAIL",
                        case_id,
                        "implicit_domain_knowledge row needs a reasoning atom that is not a verbatim quote",
                    )
                )

    expected = set(curated_by_case)
    missing = expected - seen - m2_dropped_case_ids(curated, candidates)
    for case_id in sorted(missing):
        findings.append(Finding("FAIL", case_id, "case_id present in curated_evidence but missing from rubrics"))

    return findings


def _is_refusal(text: str) -> bool:
    if not text:
        return False
    if any(token in text for token in M8_REFUSAL_TOKENS_CN):
        return True
    lower = text.lower()
    return any(token.lower() in lower for token in M8_REFUSAL_TOKENS_EN)


def validate_m8(
    verifier_rows: list[dict[str, Any]],
    candidates: list[dict[str, Any]],
    curated: list[dict[str, Any]],
    answers: list[dict[str, Any]] | None,
) -> list[Finding]:
    findings: list[Finding] = []
    cands_by_case = index_by_case(candidates)
    curated_by_case = index_by_case(curated)
    answers_by_case = index_by_case(answers or [])
    seen: set[str] = set()

    for raw in verifier_rows:
        case_id = raw.get("case_id")
        if not isinstance(case_id, str) or not case_id:
            findings.append(Finding("FAIL", None, "row missing case_id"))
            continue
        if case_id in seen:
            findings.append(Finding("FAIL", case_id, "duplicate case_id"))
        seen.add(case_id)

        rederived = raw.get("rederived_answer")
        if not isinstance(rederived, str) or not rederived.strip():
            findings.append(Finding("FAIL", case_id, "rederived_answer required"))
            continue

        confidence = raw.get("rederivation_confidence")
        if confidence not in M8_CONFIDENCES:
            findings.append(
                Finding("FAIL", case_id, f"rederivation_confidence invalid: {confidence!r}")
            )

        cand = candidate_row(cands_by_case.get(case_id, {})) if cands_by_case else None
        cur_raw = curated_by_case.get(case_id)
        cur = curated_row(cur_raw) if cur_raw else None
        evidence_keys: set[tuple[str, str]] = set()
        if cur:
            evidence_keys = {
                (str(s.get("path", "")), str(s.get("lines", "")))
                for s in cur.selected_evidence
                if isinstance(s, dict)
            }

        rederived_citations = raw.get("rederived_citations") or []
        if not isinstance(rederived_citations, list):
            findings.append(Finding("FAIL", case_id, "rederived_citations must be a list"))
            rederived_citations = []
        for entry in rederived_citations:
            if not isinstance(entry, str) or ":" not in entry:
                findings.append(Finding("FAIL", case_id, f"rederived_citations entry invalid: {entry!r}"))
                continue
            path, _, lines = entry.rpartition(":")
            if evidence_keys and (path, lines) not in evidence_keys:
                findings.append(
                    Finding("FAIL", case_id, f"rederived_citations {entry!r} not in curated_evidence")
                )

        if cand:
            refused = _is_refusal(rederived)
            if cand.answerability == "answerable" and refused:
                findings.append(
                    Finding(
                        "FAIL",
                        case_id,
                        "row is answerable but re-derivation refused — evidence may not actually support an answer",
                    )
                )
            if cand.answerability == "unanswerable_missing_evidence" and not refused:
                findings.append(
                    Finding(
                        "FAIL",
                        case_id,
                        "row is unanswerable_missing_evidence but re-derivation produced a confident answer — row mislabeled or query leaks the answer",
                    )
                )
            if (
                cand.answerability.startswith("unanswerable")
                and confidence == "high"
            ):
                findings.append(
                    Finding(
                        "WARN",
                        case_id,
                        "rederivation_confidence=high on an unanswerable row is suspicious",
                    )
                )

        gold = answers_by_case.get(case_id)
        if gold:
            gold_answer = str(gold.get("expected_answer") or "")
            if gold_answer:
                a, b = len(rederived), len(gold_answer)
                if max(a, b) > 0 and (max(a, b) / max(min(a, b), 1)) > 3:
                    findings.append(
                        Finding(
                            "WARN",
                            case_id,
                            f"re-derived length {a} differs > 3× from M6 length {b}",
                        )
                    )
                gold_citation_set = {str(c) for c in (gold.get("citation_paths") or [])}
                redev_set = set(rederived_citations)
                if gold_citation_set and redev_set and gold_citation_set.isdisjoint(redev_set):
                    findings.append(
                        Finding(
                            "WARN",
                            case_id,
                            "re-derived citations disjoint from M6 citation_paths",
                        )
                    )

    expected = set(curated_by_case)
    missing = expected - seen
    for case_id in sorted(missing):
        findings.append(Finding("FAIL", case_id, "case_id present in curated_evidence but missing from verifier"))

    return findings


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path, help="JSONL output of the stage to validate")
    parser.add_argument("--module", choices=["M2", "M3", "M5", "M6", "M7", "M8"], required=True)
    parser.add_argument("--candidates", type=Path)
    parser.add_argument("--curated", type=Path)
    parser.add_argument("--claims", type=Path)
    parser.add_argument("--answers", type=Path)
    parser.add_argument("--fail-on-warn", action="store_true")
    parser.add_argument("--json-report", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    findings: list[Finding] = []

    output_rows = load_jsonl(args.output)
    candidates = load_jsonl(args.candidates) if args.candidates else None

    if args.module == "M2":
        if not candidates:
            print("ERROR: --candidates required for M2", file=sys.stderr)
            return 2
        findings = validate_m2(output_rows, candidates)
    elif args.module == "M3":
        if not args.curated:
            print("ERROR: --curated required for M3", file=sys.stderr)
            return 2
        curated = load_jsonl(args.curated)
        findings = validate_m3(output_rows, curated, candidates)
    elif args.module == "M5":
        if not candidates or not args.curated:
            print("ERROR: --candidates and --curated required for M5", file=sys.stderr)
            return 2
        curated = load_jsonl(args.curated)
        findings = validate_m5(output_rows, candidates, curated)
    elif args.module == "M6":
        if not args.curated:
            print("ERROR: --curated required for M6", file=sys.stderr)
            return 2
        curated = load_jsonl(args.curated)
        claims = load_jsonl(args.claims) if args.claims else None
        findings = validate_m6(output_rows, candidates, curated, claims)
    elif args.module == "M7":
        if not candidates or not args.curated:
            print("ERROR: --candidates and --curated required for M7", file=sys.stderr)
            return 2
        curated = load_jsonl(args.curated)
        claims = load_jsonl(args.claims) if args.claims else None
        answers = load_jsonl(args.answers) if args.answers else None
        findings = validate_m7(output_rows, candidates, curated, claims, answers)
    elif args.module == "M8":
        if not candidates or not args.curated:
            print("ERROR: --candidates and --curated required for M8", file=sys.stderr)
            return 2
        curated = load_jsonl(args.curated)
        answers = load_jsonl(args.answers) if args.answers else None
        findings = validate_m8(output_rows, candidates, curated, answers)

    fails = [f for f in findings if f.severity == "FAIL"]
    warns = [f for f in findings if f.severity == "WARN"]
    print(f"module={args.module} rows={len(output_rows)} FAIL={len(fails)} WARN={len(warns)}")
    for finding in findings[:120]:
        case = f" [{finding.case_id}]" if finding.case_id else ""
        print(f"{finding.severity}{case}: {finding.message}")
    if len(findings) > 120:
        print(f"... {len(findings) - 120} additional findings omitted")

    if args.json_report:
        args.json_report.parent.mkdir(parents=True, exist_ok=True)
        args.json_report.write_text(
            json.dumps(
                {
                    "module": args.module,
                    "rows": len(output_rows),
                    "fails": len(fails),
                    "warns": len(warns),
                    "findings": [
                        {"severity": f.severity, "case_id": f.case_id, "message": f.message}
                        for f in findings
                    ],
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    if fails:
        return 1
    if args.fail_on_warn and warns:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
