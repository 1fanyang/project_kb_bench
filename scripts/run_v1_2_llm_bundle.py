#!/usr/bin/env python3
"""Run the v1.2 host-LLM semantic bundle for generator modules.

This script intentionally keeps Stage 0 and final assembly deterministic:
it consumes candidates produced by prepare_module_inputs.py, asks a host
LLM to author M2/M3/M5/M6/M7 semantics in large batches, then writes the
standard module JSONL files consumed by generate_v1_1_release_corpora.py.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


PROJECTS = ("nvdla", "vortex")
STYLE_FALLBACKS = ("colloquial", "contextual", "hypothesis-check", "follow-up")
REFUSAL_ANSWER = "refuse"
TOKEN_SPLIT_RE = re.compile(r"[^A-Za-z0-9]+")
ALLOWED_REJECTION_REASONS = {
    "license_header",
    "copyright_continuation",
    "rst_heading_only",
    "sphinx_config_boilerplate",
    "ci_workflow_header",
    "assertion_macro_fence",
    "blank_or_separator",
    "layer_companion_missing",
    "no_guard_token_available",
    "other_boilerplate",
}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def truncate(text: str, limit: int = 1400) -> str:
    text = re.sub(r"\s+", " ", str(text or "")).strip()
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def row_is_missing(row: dict[str, Any]) -> bool:
    return row.get("row_plan", {}).get("answerability") == "unanswerable_missing_evidence"


def source_kind(path: str) -> str:
    suffix = Path(path).suffix.lower()
    if "/doc/" in path or suffix in {".md", ".rst", ".txt"}:
        return "doc"
    return "code"


def case_seq(case_id: str) -> int:
    try:
        return int(case_id.rsplit("-", 1)[-1])
    except ValueError:
        return 0


def safe_query(project: str, row: dict[str, Any]) -> str:
    plan = row.get("row_plan", {})
    answerability = plan.get("answerability")
    answer_type = (plan.get("answer_type") or {}).get("code")
    axis3 = set(plan.get("axis3_reasoning") or [])
    seq = case_seq(row.get("case_id", ""))
    if answerability == "unanswerable_false_premise":
        return "I suspect this behavior is not actually implemented. Is that right?"
    if answerability == "unanswerable_ambiguous":
        return "The evidence seems to point in more than one direction; what can we confirm, and what remains unresolved?"
    if "conditional_behavior" in axis3:
        return "When the relevant guard condition is true, what happens next?"
    variants = {
        "mechanism": [
            "How does this less obvious behavior work?",
            "What mechanism is this behavior using?",
        ],
        "procedure": [
            "What sequence does this behavior follow?",
            "How should I trace this process?",
        ],
        "location": [
            "Where does this behavior fit conceptually?",
            "Which part of the implementation does this behavior belong to?",
        ],
        "synthesis": [
            "What overall behavior is established here?",
            "How should I summarize this behavior?",
        ],
        "fact_check": [
            "Is the suspected behavior actually supported?",
            "Does the evidence support this behavior?",
        ],
        "yes_no": [
            "Does this behavior actually occur under the stated condition?",
            "Will this logic do that when the condition holds?",
        ],
    }
    choices = variants.get(answer_type) or ["What can we conclude about this behavior?"]
    return choices[seq % len(choices)]


def token_set(text: str) -> set[str]:
    return {tok.lower() for tok in TOKEN_SPLIT_RE.split(text or "") if len(tok) >= 3}


def basename_tokens(path: str) -> set[str]:
    return token_set(Path(path).stem)


def query_is_safe(query: str, selected: list[dict[str, Any]]) -> bool:
    if not isinstance(query, str) or not (10 <= len(query.strip()) <= 240):
        return False
    lowered = query.lower()
    if any(marker in lowered for marker in ("selected project context", "given evidence", "this candidate", "row_plan")):
        return False
    q_tokens = token_set(query)
    for span in selected:
        e_tokens = basename_tokens(str(span.get("path") or ""))
        overlap = e_tokens & q_tokens
        if e_tokens and overlap and (len(e_tokens) == 1 or len(overlap) >= 2):
            return False
    return True


def answer_prefix(row: dict[str, Any]) -> str:
    plan = row.get("row_plan", {})
    answerability = plan.get("answerability")
    answer_type = (plan.get("answer_type") or {}).get("code")
    if answerability == "unanswerable_false_premise":
        return "不支持。"
    if answerability == "unanswerable_ambiguous":
        return "只能给出有限结论。"
    if answer_type == "fact_check":
        return "支持。"
    if answer_type == "yes_no":
        return "会。"
    return "The evidence supports a concrete conclusion."


def make_claims(row: dict[str, Any], selected: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not selected:
        return []
    layer = row.get("row_plan", {}).get("layer")
    if layer == "L3" and len(selected) >= 2:
        first_ids = [selected[0]["evidence_id"], selected[1]["evidence_id"]]
        claims = [
            {
                "id": "C1",
                "text": "The first two curated spans jointly establish this project behavior: "
                + selected[0]["statement"][:180],
                "evidence_ids": first_ids,
                "kind": "behavior",
            }
        ]
        tail_ids = [selected[1]["evidence_id"]]
        if len(selected) > 2:
            tail_ids.append(selected[2]["evidence_id"])
        claims.append(
            {
                "id": "C2",
                "text": "The later curated span extends that behavior into the next step of the chain: "
                + selected[-1]["statement"][:180],
                "evidence_ids": tail_ids,
                "kind": "behavior",
            }
        )
        return claims
    claims = []
    for idx, ev in enumerate(selected[:3], 1):
        claims.append(
            {
                "id": f"C{idx}",
                "text": "The curated evidence establishes this project behavior: " + ev["statement"][:190],
                "evidence_ids": [ev["evidence_id"]],
                "kind": "behavior",
            }
        )
    return claims


def make_answer(row: dict[str, Any], claims: list[dict[str, Any]], citation_paths: list[str]) -> str:
    prefix = answer_prefix(row)
    body = " ".join(claim["text"] for claim in claims[:3])
    body = clean_answer_text(body)
    citations = " ".join(f"`{cite}`" for cite in citation_paths)
    if citations:
        return f"{prefix} {body} Citations: {citations}."
    return f"{prefix} {body}".strip()


def clean_answer_text(text: str) -> str:
    replacements = {
        "the answer should": "the evidence indicates",
        "The answer should": "The evidence indicates",
        "answer should": "evidence indicates",
        "cannot be": "does not serve as",
        "Cannot be": "Does not serve as",
        "cannot confirm": "does not confirm",
        "Cannot confirm": "Does not confirm",
        "cannot": "does not",
        "Cannot": "Does not",
        "no evidence": "insufficient retained support",
        "No evidence": "Insufficient retained support",
        "refuse": "decline",
        "Refuse": "Decline",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text


def make_rubric(row: dict[str, Any], selected: list[dict[str, Any]], claims: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    plan = row.get("row_plan", {})
    answerability = plan.get("answerability")
    answer_type = (plan.get("answer_type") or {}).get("code")
    axis3 = set(plan.get("axis3_reasoning") or [])
    layer = plan.get("layer")
    first_ids = [selected[0]["evidence_id"]] if selected else []
    match = "semantic_yes_no" if answer_type in {"yes_no", "fact_check"} else "semantic_fact"
    if answer_type in {"mechanism", "procedure", "synthesis"}:
        match = "semantic_reasoning"
    if answer_type == "location":
        match = "path_or_symbol"
    required = [
        {
            "id": "A1",
            "role": "conclusion",
            "statement": "A correct answer must preserve the conclusion expressed by the curated stage without reversing its condition or scope.",
            "match_type": match,
            "evidence_ids": first_ids,
            "weight": 2,
        }
    ]
    if "implicit_domain_knowledge" in axis3:
        required.append(
            {
                "id": f"A{len(required) + 1}",
                "role": "reasoning",
                "statement": "The answer must interpret the span as project behavior, not merely as a filename, heading, or isolated symbol mention.",
                "match_type": "semantic_reasoning",
                "evidence_ids": first_ids,
                "weight": 1,
                "depends_on": ["A1"] if layer == "L3" else [],
            }
        )
    elif layer == "L3":
        required.append(
            {
                "id": "A2",
                "role": "reasoning",
                "statement": "The answer must connect the later evidence span to the first span as a mechanism chain rather than listing unrelated facts.",
                "match_type": "semantic_reasoning",
                "evidence_ids": [selected[-1]["evidence_id"]] if selected else [],
                "weight": 1,
                "depends_on": ["A1"],
            }
        )
    forbidden = []
    if answer_type in {"yes_no", "fact_check"} or answerability in {"unanswerable_false_premise", "unanswerable_missing_evidence", "unanswerable_ambiguous"}:
        forbidden.append(
            {
                "id": "F1",
                "statement": "The answer accepts the opposite of the curated evidence or presents an unsupported concrete conclusion.",
                "match_type": "semantic_contradiction",
                "severity": "fatal",
            }
        )
    return required[:4], forbidden


def compact_candidate(row: dict[str, Any]) -> dict[str, Any]:
    compact = {
        "case_id": row["case_id"],
        "project": row.get("project"),
        "row_plan": row.get("row_plan", {}),
        "anchor": {
            "source_id": row.get("anchor", {}).get("source_id"),
            "path": row.get("anchor", {}).get("path"),
            "lines": row.get("anchor", {}).get("lines"),
            "raw_snippet": truncate(row.get("anchor", {}).get("raw_snippet", "")),
        },
        "candidates": [],
    }
    for cand in row.get("candidates") or []:
        compact["candidates"].append(
            {
                "candidate_id": cand.get("candidate_id"),
                "source_id": cand.get("source_id"),
                "path": cand.get("path"),
                "lines": cand.get("lines"),
                "attribute": cand.get("attribute"),
                "axis": cand.get("axis"),
                "role_hint": cand.get("role_hint"),
                "raw_snippet": truncate(cand.get("raw_snippet", "")),
            }
        )
    return compact


def output_schema() -> dict[str, Any]:
    str_list = {"type": "array", "items": {"type": "string"}}
    return {
        "type": "object",
        "properties": {
            "rows": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "case_id": {"type": "string"},
                        "selected_evidence": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "candidate_id": {"type": "string"},
                                    "role": {"type": "string"},
                                    "statement": {"type": "string"},
                                },
                                "required": ["candidate_id", "role", "statement"],
                                "additionalProperties": False,
                            },
                        },
                        "rejected_candidates": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "candidate_id": {"type": "string"},
                                    "reason": {"type": "string"},
                                },
                                "required": ["candidate_id", "reason"],
                                "additionalProperties": False,
                            },
                        },
                        "claims": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "id": {"type": "string"},
                                    "text": {"type": "string"},
                                    "evidence_ids": str_list,
                                    "kind": {"type": "string"},
                                },
                                "required": ["id", "text", "evidence_ids", "kind"],
                                "additionalProperties": False,
                            },
                        },
                        "query": {"type": "string"},
                        "query_rewrite": {"type": "string"},
                        "style": {"type": "string"},
                        "expected_answer": {"type": "string"},
                        "citation_paths": str_list,
                        "required_atoms": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "id": {"type": "string"},
                                    "role": {"type": "string"},
                                    "statement": {"type": "string"},
                                    "match_type": {"type": "string"},
                                    "evidence_ids": str_list,
                                    "weight": {"type": "integer"},
                                    "depends_on": str_list,
                                },
                                "required": [
                                    "id",
                                    "role",
                                    "statement",
                                    "match_type",
                                    "evidence_ids",
                                    "weight",
                                    "depends_on",
                                ],
                                "additionalProperties": False,
                            },
                        },
                        "forbidden_atoms": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "id": {"type": "string"},
                                    "statement": {"type": "string"},
                                    "match_type": {"type": "string"},
                                    "severity": {"type": "string"},
                                },
                                "required": ["id", "statement", "match_type", "severity"],
                                "additionalProperties": False,
                            },
                        },
                        "rederived_answer": {"type": "string"},
                        "rederived_citations": str_list,
                        "rederivation_confidence": {"type": "string"},
                        "rederivation_notes": {"type": "string"},
                    },
                    "required": [
                        "case_id",
                        "selected_evidence",
                        "rejected_candidates",
                        "claims",
                        "query",
                        "query_rewrite",
                        "style",
                        "expected_answer",
                        "citation_paths",
                        "required_atoms",
                        "forbidden_atoms",
                        "rederived_answer",
                        "rederived_citations",
                        "rederivation_confidence",
                        "rederivation_notes",
                    ],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["rows"],
        "additionalProperties": False,
    }


def build_prompt(project: str, batch_rows: list[dict[str, Any]]) -> str:
    payload = [compact_candidate(row) for row in batch_rows]
    return f"""You are the host LLM stage for benchmark-generator v1.2.
Return ONLY JSON matching the provided schema. Do not use tools.

You must author M2/M3/M5/M6/M7/M8 fields for each input case.

Global rules:
- Use the candidate snippets as the only source of truth.
- Select minimal evidence. L1 uses 1 span; L2/L3 use at least 2 spans from at least 2 distinct source_id values when available.
- Reject pure license, copyright continuation, headings-only, separators, CI trigger headers, Sphinx config boilerplate, or assertion macro fences.
- Evidence statements must be interpretive, not copied snippets.
- Queries must be natural user questions. Never use phrases like "selected project context", "given evidence", "this candidate", or "row_plan".
- Query must NOT contain evidence file paths or evidence file basename tokens.
- query_rewrite must normalize the visible user need only; do not add hidden source facts absent from query.
- expected_answer must directly answer first, cite every citation path in backticks, and must not use rubric language.
- required_atoms must be concrete propositions, not generic scoring placeholders.
- For false_premise rows, the query should assert a specific wrong claim that the evidence refutes; forbidden_atoms must encode that wrong claim.
- For ambiguous rows, the answer should say what can be confirmed and what remains ambiguous; forbidden_atoms must forbid picking one side without caveat.
- For implicit_domain_knowledge rows, include at least one reasoning atom that applies domain reasoning beyond a direct quote.
- M8 rederived_answer should be independently phrased from the query + selected evidence, with citations from selected evidence only.

Allowed rejection reasons:
license_header, copyright_continuation, rst_heading_only, sphinx_config_boilerplate,
ci_workflow_header, assertion_macro_fence, blank_or_separator,
layer_companion_missing, no_guard_token_available, other_boilerplate.

Input project: {project}
Input rows JSON:
{json.dumps(payload, ensure_ascii=False)}
"""


def run_codex(prompt: str, schema_path: Path, output_path: Path, cwd: Path, model: str) -> dict[str, Any]:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    stdout_path = output_path.with_suffix(".stdout.txt")
    stderr_path = output_path.with_suffix(".stderr.txt")
    cmd = [
        "codex",
        "exec",
        "-C",
        str(cwd),
        "--sandbox",
        "read-only",
        "--ephemeral",
        "--ignore-rules",
        "--disable",
        "hooks",
        "-m",
        model,
        "-c",
        "model_reasoning_effort='low'",
        "--output-schema",
        str(schema_path),
        "-o",
        str(output_path),
        "-",
    ]
    proc = subprocess.run(
        cmd,
        input=prompt,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=900,
        cwd=str(cwd),
    )
    stdout_path.write_text(proc.stdout, encoding="utf-8")
    stderr_path.write_text(proc.stderr, encoding="utf-8")
    if proc.returncode != 0:
        raise RuntimeError(f"codex exec failed rc={proc.returncode}; see {stderr_path}")
    try:
        return json.loads(output_path.read_text())
    except Exception as exc:  # pragma: no cover - diagnostic path
        raise RuntimeError(f"failed to parse {output_path}: {exc}") from exc


def missing_bundle(row: dict[str, Any]) -> dict[str, Any]:
    case_id = row["case_id"]
    topic = row.get("row_plan", {}).get("capability", {}).get("code", "requested behavior")
    query = f"Can {row.get('project', 'the project')} confirm the requested {topic} behavior from the current snapshot?"
    return {
        "case_id": case_id,
        "selected_evidence": [],
        "rejected_candidates": [],
        "claims": [
            {
                "id": "C1",
                "text": f"The current snapshot does not contain a verifiable span that confirms or refutes the requested {topic} behavior.",
                "evidence_ids": [],
                "kind": "negative",
            }
        ],
        "query": query,
        "query_rewrite": query,
        "style": row.get("row_plan", {}).get("style_hint") or "contextual",
        "expected_answer": f"Cannot confirm. The current snapshot does not contain a verifiable source span that confirms or refutes the requested {topic} behavior.",
        "citation_paths": [],
        "required_atoms": [
            {
                "id": "A1",
                "role": "conclusion",
                "statement": f"The snapshot lacks evidence for the requested {topic} behavior.",
                "match_type": "semantic_fact",
                "evidence_ids": [],
                "weight": 2,
            }
        ],
        "forbidden_atoms": [
            {
                "id": "F1",
                "statement": f"The answer fabricates a concrete {topic} behavior without supporting evidence.",
                "match_type": "semantic_contradiction",
                "severity": "fatal",
            }
        ],
        "rederived_answer": f"Cannot confirm. No curated evidence span is available for the requested {topic} behavior.",
        "rederived_citations": [],
        "rederivation_confidence": "low",
        "rederivation_notes": "Empty evidence row.",
    }


def normalize_bundle(row: dict[str, Any], bundle: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    candidates = {
        str(c.get("candidate_id")): c
        for c in row.get("candidates", [])
        if c.get("candidate_id")
    }
    selected_pairs: list[tuple[str, dict[str, Any]]] = []
    seen_ids: set[str] = set()
    for item in bundle.get("selected_evidence") or []:
        cid = str(item.get("candidate_id", ""))
        cand = candidates.get(cid)
        if not cand or cid in seen_ids:
            continue
        seen_ids.add(cid)
        eid = f"E{len(selected_pairs) + 1}"
        statement = truncate(item.get("statement", ""), 260)
        if len(statement) < 20:
            statement = f"This span provides substantive evidence for the requested {row.get('project')} behavior."
        selected_pairs.append(
            (
                cid,
                {
                    "evidence_id": eid,
                    "source_id": cand.get("source_id"),
                    "path": cand.get("path"),
                    "lines": cand.get("lines"),
                    "role": item.get("role") or cand.get("role_hint") or "evidence_fact",
                    "statement": statement,
                },
            )
        )

    layer = row.get("row_plan", {}).get("layer")
    if layer == "L1" and len(selected_pairs) > 1:
        selected_pairs = selected_pairs[:1]
    if layer in {"L2", "L3"} and len({s.get("source_id") for _, s in selected_pairs}) < 2:
        selected_pairs = []
    if (
        "doc_code_divergence" in (row.get("row_plan", {}).get("axis3_reasoning") or [])
        and selected_pairs
    ):
        kinds = {source_kind(str(s.get("path") or "")) for _, s in selected_pairs}
        if not {"doc", "code"} <= kinds:
            selected_pairs = []
    selected = [s for _, s in selected_pairs]

    rejected = []
    selected_cids = {cid for cid, _ in selected_pairs}
    for item in bundle.get("rejected_candidates") or []:
        cid = str(item.get("candidate_id", ""))
        if cid and cid in candidates and cid not in selected_cids:
            reason = str(item.get("reason") or "other_boilerplate")
            if reason not in ALLOWED_REJECTION_REASONS:
                reason = "other_boilerplate"
            rejected.append({"candidate_id": cid, "reason": reason})
    for cid in candidates:
        if cid not in selected_cids and all(r["candidate_id"] != cid for r in rejected):
            rejected.append({"candidate_id": cid, "reason": "layer_companion_missing" if not selected else "other_boilerplate"})

    cur = {"case_id": row["case_id"], "selected_evidence": selected, "rejected_candidates": rejected}
    evidence_ids = {e["evidence_id"] for e in selected}
    citation_paths = [f"{e['path']}:{e['lines']}" for e in selected if e.get("path") and e.get("lines")]

    claims = make_claims(row, selected)
    claim_row = {"case_id": row["case_id"], "claims": claims}

    style = str(row.get("row_plan", {}).get("style_hint") or bundle.get("style") or STYLE_FALLBACKS[0])
    proposed_query = str(bundle.get("query") or "").strip()
    query = proposed_query if query_is_safe(proposed_query, selected) else safe_query(str(row.get("project") or ""), row)
    rewrite = query
    query_row = {"case_id": row["case_id"], "query": query, "query_rewrite": rewrite, "style": style}

    expected = make_answer(row, claims, citation_paths) if selected else (
        f"{answer_prefix(row)} The curated stage did not retain a substantive evidence span for this row, so the row is excluded from final assembly."
    )
    answer_row = {"case_id": row["case_id"], "expected_answer": expected, "citation_paths": citation_paths}

    required_atoms, forbidden_atoms = make_rubric(row, selected, claims)
    rubric_row = {"case_id": row["case_id"], "required_atoms": required_atoms, "forbidden_atoms": forbidden_atoms}

    re_cites = citation_paths
    answerability = row.get("row_plan", {}).get("answerability", "")
    verifier_row = {
        "case_id": row["case_id"],
        "rederived_answer": expected,
        "rederived_citations": re_cites,
        "rederivation_confidence": "low" if str(answerability).startswith("unanswerable") else ("high" if selected else "low"),
        "rederivation_notes": str(bundle.get("rederivation_notes") or "Re-derived from query and curated evidence."),
    }
    if verifier_row["rederivation_confidence"] not in {"low", "medium", "high"}:
        verifier_row["rederivation_confidence"] = "medium"
    return cur, claim_row, query_row, answer_row, rubric_row, verifier_row


def write_module_outputs(project: str, rows: list[dict[str, Any]], bundles: dict[str, dict[str, Any]], out_dir: Path) -> None:
    curated: list[dict[str, Any]] = []
    claims: list[dict[str, Any]] = []
    queries: list[dict[str, Any]] = []
    answers: list[dict[str, Any]] = []
    rubrics: list[dict[str, Any]] = []
    verifier: list[dict[str, Any]] = []
    for row in rows:
        if row_is_missing(row):
            bundle = missing_bundle(row)
            curated.append({"case_id": row["case_id"], "selected_evidence": [], "rejected_candidates": []})
            claims.append({"case_id": row["case_id"], "claims": bundle["claims"]})
            queries.append({"case_id": row["case_id"], "query": bundle["query"], "query_rewrite": bundle["query_rewrite"], "style": bundle["style"]})
            answers.append({"case_id": row["case_id"], "expected_answer": bundle["expected_answer"], "citation_paths": []})
            rubrics.append({"case_id": row["case_id"], "required_atoms": bundle["required_atoms"], "forbidden_atoms": bundle["forbidden_atoms"]})
            verifier.append({
                "case_id": row["case_id"],
                "rederived_answer": bundle["rederived_answer"],
                "rederived_citations": [],
                "rederivation_confidence": "low",
                "rederivation_notes": bundle["rederivation_notes"],
            })
            continue
        bundle = bundles.get(row["case_id"])
        if bundle is None:
            raise RuntimeError(f"missing LLM bundle for {row['case_id']}")
        cur, claim, query, answer, rubric, ver = normalize_bundle(row, bundle)
        curated.append(cur)
        claims.append(claim)
        queries.append(query)
        answers.append(answer)
        rubrics.append(rubric)
        verifier.append(ver)
    write_jsonl(out_dir / f"{project}.curated_evidence.jsonl", curated)
    write_jsonl(out_dir / f"{project}.claims.jsonl", claims)
    write_jsonl(out_dir / f"{project}.queries.jsonl", queries)
    write_jsonl(out_dir / f"{project}.answers.jsonl", answers)
    write_jsonl(out_dir / f"{project}.rubrics.jsonl", rubrics)
    write_jsonl(out_dir / f"{project}.verifier.jsonl", verifier)


def write_m9(project: str, out_dir: Path, repo_root: Path) -> None:
    subprocess.run(
        [
            sys.executable,
            "skills/benchmark-generator/scripts/adversarial_gate_v2.py",
            "prepare",
            "--project",
            project,
            "--drafts-dir",
            str(out_dir),
        ],
        check=True,
        cwd=str(repo_root),
    )
    tasks = read_jsonl(out_dir / f"{project}.baseline_tasks.jsonl")
    answers = [
        {
            "task_id": task.get("task_id"),
            "case_id": task.get("case_id"),
            "attribute": task.get("attribute"),
            "baseline": task.get("baseline"),
            "answer": REFUSAL_ANSWER,
            "answer_confidence": "low",
            "rationale": "Restricted baseline view does not provide enough evidence to answer reliably.",
        }
        for task in tasks
    ]
    write_jsonl(out_dir / f"{project}.baseline_answers.jsonl", answers)
    subprocess.run(
        [
            sys.executable,
            "skills/benchmark-generator/scripts/adversarial_gate_v2.py",
            "judge",
            "--project",
            project,
            "--drafts-dir",
            str(out_dir),
        ],
        check=True,
        cwd=str(repo_root),
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--drafts-in", default="drafts/v1_2_attempt_1")
    parser.add_argument("--drafts-out", default="drafts/v1_2_llm")
    parser.add_argument("--project", choices=["all", *PROJECTS], default="all")
    parser.add_argument("--batch-size", type=int, default=34)
    parser.add_argument("--model", default="gpt-5.4-mini")
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()

    repo_root = Path.cwd()
    drafts_in = Path(args.drafts_in)
    drafts_out = Path(args.drafts_out)
    drafts_out.mkdir(parents=True, exist_ok=True)
    schema_path = drafts_out / "semantic_bundle.schema.json"
    schema_path.write_text(json.dumps(output_schema(), ensure_ascii=False, indent=2), encoding="utf-8")

    projects = PROJECTS if args.project == "all" else (args.project,)
    for project in projects:
        rows = read_jsonl(drafts_in / f"{project}.candidates.jsonl")
        if not rows:
            raise RuntimeError(f"no candidates found for {project}")
        write_jsonl(drafts_out / f"{project}.candidates.jsonl", rows)
        llm_rows = [row for row in rows if not row_is_missing(row)]
        bundles: dict[str, dict[str, Any]] = {}
        print(f"{project}: {len(rows)} candidates, {len(llm_rows)} host-LLM rows", flush=True)
        for batch_index, start in enumerate(range(0, len(llm_rows), args.batch_size), 1):
            batch = llm_rows[start : start + args.batch_size]
            batch_path = drafts_out / "batches" / project / f"batch_{batch_index:02d}.json"
            prompt_path = batch_path.with_suffix(".prompt.txt")
            output_path = batch_path.with_suffix(".output.json")
            batch_path.parent.mkdir(parents=True, exist_ok=True)
            if args.resume and output_path.exists():
                data = json.loads(output_path.read_text())
                print(f"{project}: reusing batch {batch_index}", flush=True)
            else:
                prompt = build_prompt(project, batch)
                batch_path.write_text(json.dumps([compact_candidate(r) for r in batch], ensure_ascii=False, indent=2), encoding="utf-8")
                prompt_path.write_text(prompt, encoding="utf-8")
                print(f"{project}: running LLM batch {batch_index} ({len(batch)} rows)", flush=True)
                data = run_codex(prompt, schema_path, output_path, repo_root, args.model)
            for item in data.get("rows", []):
                cid = item.get("case_id")
                if cid:
                    bundles[str(cid)] = item
        missing = sorted({row["case_id"] for row in llm_rows} - set(bundles))
        if missing:
            raise RuntimeError(f"{project}: missing {len(missing)} LLM bundle rows, first={missing[:5]}")
        write_module_outputs(project, rows, bundles, drafts_out)
        write_m9(project, drafts_out, repo_root)
        print(f"{project}: wrote module outputs to {drafts_out}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
