# kb_benchmark — Review and Improvement Suggestions

Comparing this benchmark against the design principles from:
- **InfoDeepSeek** (Xi et al., arXiv:2505.15872) — open-web agentic information seeking
- **HERB** (Choubey et al., arXiv:2506.23139) — heterogeneous enterprise Deep Search

## 1. What the repo already does well

**Architecture.** Clean three-stage pipeline (`benchmark-repo-analyzer` → `benchmark-generator` → `benchmark-validator`) with versioned JSON Schemas. Stages communicate through file artifacts, which keeps the workflow runnable from Codex, Claude, shell, or CI.

**Separation of retrieval and answer scoring.** `references` validate retrieval, `evidence` validate grounding, `answer_rubric.required_atoms` score the answer. This is closer in spirit to InfoDeepSeek's split into seeking quality vs. answer accuracy, and arguably cleaner than HERB's mixed Likert+F1.

**Evidence model.** Every row carries `evidence_id`, `path`, `lines`, `role`, `statement`; the validator does deterministic line-range overlap matching for `evidence_recall@k` and parses `path:line-range` citations. More precise than HERB (source-only matching) and InfoDeepSeek (gold-source-page list only).

**Anti-leakage guardrails.** `query_rewrite` rules (no hidden evidence-derived facts), "no rubric language in `expected_answer`" checks, and the explicit `additionalProperties: true` discipline codify the construction-leak warnings both papers had to police manually.

**Hybrid judge.** `evaluate_methods.py` already supports DeepSeek as a semantic answer judge while keeping retrieval/citation deterministic — the same hybrid pattern both reference papers adopted.

## 2. Gaps when measured against the two papers

| Axis | InfoDeepSeek / HERB practice | kb_benchmark today | Gap |
|---|---|---|---|
| **Difficulty enforcement** | InfoDeepSeek discards any question that GPT-4o **or** DeepSeek-R1 solves in single-turn search | `lint_benchmark_jsonl.py` only checks schema/structure | No difficulty filter |
| **Construction philosophy** | Both papers reject post-hoc multi-hop synthesis as "artificial" | Relation-graph predicates are shallow (`defines`/`contains`/`doc_mentions_entity`); NVDLA profile already flags this | Multi-hop rests on weak entity links |
| **Unanswerable queries** | HERB has 699 unanswerable + accuracy metric; InfoDeepSeek has 10.6 % false-premise | Schema requires `references.minItems ≥ 1` and `evidence.minItems ≥ 1` — unanswerable is structurally illegal | Zero abstention coverage |
| **Info-seeking efficiency** | `EEU = max_k IA@k / ACC` and `IC_q = n_q/|S_q|` catch over-retrieval | Only `evidence_recall@k`, precision, F1 | No compactness/utilization signal |
| **Diversity / attribute tags** | InfoDeepSeek: 6 difficulty attributes; HERB: 4 intents | Two free-form taxonomies (`layer`, `capability`) — no shared difficulty axis | Hard to compare runs across projects |
| **Judge robustness** | 2-LLM jury + arbiter + separate prompts for false-premise (95.57 % → 99.29 %) | Single judge, single prompt | Known failure modes untested |
| **Distractor injection** | HERB has 7 distractor types; InfoDeepSeek requires long-tail anchors | None | Easy to pass via shallow grep |
| **Test-time scaling axis** | InfoDeepSeek sweeps T = 1, 3, 5, 10, 20 | One execution per case | Can't characterize scaling |
| **Retrieval interference probe** | InfoDeepSeek's "interference rate" exposes when retrieval *hurts* | Not measured | No "RAG hurts" diagnostic |
| **Determinacy / temporal stability** | InfoDeepSeek demands time-invariant answers | Snapshot pinned to commit, but no answer-stability check | One refactor away from rot |
| **Annotation reliability** | InfoDeepSeek: 2 verifiers + decider, 97 % agreement | Single-pass generation, no second look | No measurable IAA |
| **Scale** | InfoDeepSeek 245, HERB 815 + 699 | 50 × 2 = 100 cases | Thin for stratified findings |

## 3. Suggestions, ranked by impact

### 1. Add a difficulty filter to the generator pipeline (InfoDeepSeek-style)
Before a case is accepted, run two cheap baselines:
- **`grep_agent`** (already present under `predictions/`)
- **`single-turn LLM`** with no retrieval

If both solve it, drop the case. Track in `generation_report.md`:
```
candidates_drafted: 180
dropped_solvable_by_grep: 42
dropped_solvable_by_llm_no_retrieval: 18
final_cases: 50
```
Reframes the benchmark from "schema-valid Q&A" to "agentic-search-required."

### 2. Make unanswerable cases first-class (HERB-style)
Relax `references.minItems` / `evidence.minItems` to `0` when a new `answerability` field is `unanswerable` or `false_premise`. Add to `answer_rubric`:
```json
{"abstention_required": true, "reason": "missing_evidence | false_premise | ambiguous"}
```
Validator measures abstention accuracy separately from answer accuracy.

### 3. Introduce a shared difficulty-attribute taxonomy
Per-row boolean flags orthogonal to `layer`/`capability`:
```
multi_hop, long_tail, cross_source, distracting_info,
freshness, false_premise, requires_compute, abstain_expected
```
Require ≥ 2 attributes per row. Report per-attribute pass-rates.

### 4. Information-seeking quality metrics analogous to IA@k / EEU / IC
- `IA@k` = `evidence_recall@k` for `k ∈ {1, 3, 5, 10}`.
- `EEU = max_k evidence_recall@k / recall_with_all_retrieved` — catches augmentation-stage info loss.
- `IC = |pred_evidence_at_top_k| / |gold_evidence|` with a failure penalty — penalizes over-retrieval.
All computable from existing schema.

### 5. Two-judge jury with disagreement arbitration
Primary: DeepSeek-V3 + Gemini-2.5-Flash. Arbiter on disagreement: GPT-4o-mini or human. **Separate prompts** for `abstain_expected` / `false_premise`. Report judge agreement as a benchmark-quality metric.

### 6. Inject distractors during generation (HERB-style)
- **Name-collision queries** — symbol exists in two files.
- **Stale-doc queries** — doc says X, code says Y.
- **Cross-module bait** — plausible-but-wrong files in `references`.
- **Version-fork bait** — NVDLA `nvdlav1` vs. master differences.
Encode `distractor_kind` per row.

### 7. Test-time scaling sweeps
Run each method at multiple retrieval budgets (`T ∈ {1, 5, 20}`). Plot scaling curves. Separates "model too weak" from "needs more compute."

### 8. Retrieval-interference diagnostic
Run each LLM closed-book vs. with retrieval. Compute `interference_rate = |correct_closed ∧ ¬correct_with_RAG| / |correct_closed|`. Tells you when your retrieval *hurts*.

### 9. Two-verifier annotation loop
Route generated cases through a second LLM (different family) that re-derives the answer using only the listed evidence. Disagreements go to human review. Record `verification_status` in metadata.

### 10. Determinacy / temporal-stability check
- Lint fails if `git blame` of any evidence path is newer than the manifest snapshot commit.
- Periodic re-judge stability check; flag rows whose verdict flips.

### 11. Scale beyond 50 cases per project
Suggested budget: ≥ 200 per project, split 60 % answerable / 25 % multi-hop hard / 15 % unanswerable.

### 12. Publish a leaderboard schema
A stable `leaderboard_entry.json` capturing: system name, retrieval budget, judge config, attribute-level pass rates, abstention accuracy, IA@k curve, EEU, IC, interference rate, judge agreement. Makes cross-project comparison meaningful.

### 13. Generation-leakage taxonomy
Extend existing lint rules to catch:
- evidence-statement words leaking into `query`
- exact gold-answer span verbatim in `query_rewrite`
- single-source dominance (> 80 % of evidence from one file → not really cross-source)

### 14. Tag deep-search vs. shallow-search trajectories
Per case: minimum tool sequence needed (`[unstructured_search]` vs. `[search → browse → search]`). HERB's Table 8 showed most agents collapse to shallow patterns — without this tag the benchmark can't expose that.

## 4. Highest-leverage trio

1. **Difficulty filter (#1)** — turns the benchmark from "valid" into "agentic-required."
2. **Unanswerable + abstention metric (#2)** — closes the largest blind spot.
3. **2-judge jury with abstain-aware prompts (#5)** — raises judgment reliability from ~95 % to ~99 %.

These three alone move the benchmark from "structurally clean RAG test set" to "Deep-Search agent stress-test."
