# Benchmark Generation Design v1.1

Status: draft for review
Reads from: `benchmark_generation_design_v1.0.md` (the as-implemented baseline)
Companion notes: `paper_reading_report.md`, `improvement_suggestions.md`

This document defines the next iteration of the kb_benchmark generation pipeline. It is organized so that each design decision can be traced back to a specific limitation of v1.0. Readers familiar with v1.0 should be able to skim §1 alone to know what is changing and why.

---

## 1. Motivation

### 1.1 What v1.0 produces well

The v1.0 toolkit (analyzer + generator + validator + LLM-judge evaluator) reliably emits **schema-clean** retrieval-QA benchmarks: every row passes lint, every cited line range exists in the source, every atom traces to evidence, and the LLM judge scores both oracle and grep baselines reproducibly. That is the floor v1.1 stands on, and none of it is being thrown out.

### 1.2 What v1.0 cannot tell us

Three independent pieces of evidence from the existing 100 cases show v1.0's headline limitation.

1. **Labels and structure disagree.** Of the 50 NVDLA cases, 31 carry `layer ∈ {L2, L3}` while 100 % have only one reference path. The breadth label is a claim that the evidence does not honor.
2. **The benchmark is solvable by grep.** On NVDLA, the oracle baseline reaches `strict_e2e = 0.860` and the grep-agent baseline reaches `0.820`. A 4-point gap means the questions are answerable by surface search; agentic retrieval has nowhere to differentiate.
3. **There is no notion of "I do not know."** The schema requires `references.minItems ≥ 1` and `evidence.minItems ≥ 1`. The benchmark cannot ask the engine to refuse, so it cannot detect hallucination.

These are not authoring mistakes. They are consequences of v1.0's design choices, summarized below.

### 1.3 Mapping v1.0 limitations to v1.1 responses

References point into `benchmark_generation_design_v1.0.md` §11.

| # | v1.0 limitation | v1.1 response | Where |
|---|---|---|---|
| 11.1 | Difficulty is structural in name only; L2/L3 labels not enforced. | Layer becomes one of three orthogonal axes; lint enforces evidence breadth. | §4.2, §6.1 |
| 11.2 | `capability` is descriptive but never enforced. | Capability is preserved as descriptive metadata. Difficulty is moved to a separate, enforced set of attributes. | §4.6 |
| 11.3 | No adversarial gate; no probe asks "does this case require deep search?" | Two-stage gate (structural + adversarial). Each declared attribute is bound to a baseline that should fail in its presence. | §6.2 |
| 11.4 | Schema forbids unanswerable cases. | `answerability` becomes a first-class structural status with four values; lint conditionally relaxes minima. | §4.5, §7.1 |
| 11.5 | No information-seeking efficiency metrics (`EEU`, `IC`). | Out of scope for v1.1. Tracked as a v1.2 evaluation extension. | §9 |
| 11.6 | LLM judge is single-model, single-prompt. | Out of scope for v1.1 generation. v1.1 ships *prompt dispatch by attribute* so the v1.2 jury upgrade is plumbing-only. | §6.2 |
| 11.7 | CodeGraph fallback skew leaves the relation graph 98 % `defines`. | Not solved here. v1.1 generates from whatever the analyzer produced; richer backends remain a v1.x analyzer concern. | §9 |
| 11.8 | Single-pass generation, no second-look auditing. | Adversarial gate is in effect a programmatic second look; manual two-verifier loop remains a v1.2 add-on. | §9 |
| 11.9 | Generator consumes coarse pool, not structural signals. | New analyzer artifact `signal_index.jsonl` exposes per-attribute signals; generator samples attribute-first. | §5.1, §7.3 |
| 11.10 | Single-language phrasing. | Unchanged. v1.1 is bilingual the way v1.0 is. | — |

The rest of this document fleshes out the rows marked addressed in §4–§7, and explains explicitly what is being deferred in §9.

### 1.4 Design principles carried from external work

Three principles drawn from `paper_reading_report.md` shape the design decisions below.

| Principle | Source | Manifests as |
|---|---|---|
| Difficulty must be demonstrated by adversarial probes, not declared by labels. | InfoDeepSeek § Difficulty filter | §6.2 adversarial gate |
| Heterogeneity beats single-modality corpora; questions should require cross-source reasoning. | HERB § Deep Search | §4.2 retrieval-difficulty axis, §5.2 quotas |
| Unanswerability is a metric, not a corner case. | HERB § Unanswerability evaluation | §4.5 answerability |

---

## 2. Goals and non-goals

**Goals.**
1. Make difficulty controllable at generation time (analyzer signals → generator sampling).
2. Make difficulty verifiable at gating time (structural lint + adversarial probes).
3. Add unanswerability as a first-class case type.
4. Keep all v1.0 artifacts schema-valid under v1.1 (additive schema changes only).

**Non-goals for v1.1.**
- Information-seeking efficiency metrics (EEU/IC). Tracked as v1.2.
- Multi-judge jury. v1.1 lays the prompt-dispatch plumbing only.
- Replacement of `code_graph` regex fallback. Analyzer evolution is its own track.
- Multi-language phrasing rules. Unchanged.

---

## 3. Definitions

Used consistently below.

| Term | Definition |
|---|---|
| **Difficulty (operational)** | A case is *difficult* iff at least one adversarial baseline matched to one of its declared difficulty attributes fails to produce a correct answer. Difficulty labels are *claims*; the gate either confirms or rejects each claim. |
| **Attribute** | A boolean tag on a case naming a specific source of difficulty. Each attribute is bound to (a) an analyzer signal that makes it generatable, (b) at least one structural invariant on `evidence`/`rubric`, and (c) at least one adversarial baseline that should fail when the attribute is present. |
| **Axis** | A coordinate of the difficulty model. Three axes are defined in §4; attributes belong to exactly one axis. |
| **Answerability** | A structural status orthogonal to the axes that determines what `expected_answer` looks like and which `references`/`evidence` minima apply. |
| **Adversarial baseline** | A deliberately weak retrieval+answer system used to falsify an attribute claim. The mapping from attributes to baselines lives in §6.2. |
| **Claim, claim source** | A declared attribute and the analyzer signal id(s) that justify generating it. Recorded per row in `difficulty.claim_sources`. |

---

## 4. The difficulty model

Addresses v1.0 §11.1 (labels not enforced), §11.2 (capability not enforced), §11.4 (no unanswerable).

### 4.1 Why three axes

v1.0 has one difficulty axis (`layer`) that conflates two things: *how many sources you must consult* (breadth) and *how hard the search-and-reason is at each source*. v1.1 keeps the breadth axis and splits the rest into two cleanly separable axes:

- **Axis 1 — Retrieval breadth.** How many sources, and in what relationship?
- **Axis 2 — Retrieval difficulty.** Even knowing what to look for, why is finding it hard?
- **Axis 3 — Reasoning difficulty.** Even with the right evidence in hand, why is the answer hard?

Each axis has its own natural adversarial-baseline class (§6.2). A case is summarized as `L2 + {long_tail} + {doc_code_divergence}` — exactly one Axis-1 code plus zero-or-more Axis-2 attributes plus zero-or-more Axis-3 attributes.

**Minimum tagging rule.** A case must carry at least two difficulty signals across the three axes combined.

- `L1 + 0 + 0` — illegal. Pure lookup.
- `L1 + 1 attr` — legal.
- `L3` alone — legal. Multi-hop is non-trivial on its own.

### 4.2 Axis 1 — Retrieval breadth

Carried by the existing `layer` field, semantics unchanged from v1.0, but with operational definitions that lint will now enforce.

| Code | Meaning | Operational definition (lint-enforced) |
|---|---|---|
| L1 | 单源检索 | All evidence spans share a single `source_id`. |
| L2 | 跨源核对 | Evidence spans ≥ 2 distinct `source_id`s, related in parallel (compare / verify / corroborate). |
| L3 | 多跳机制 | Evidence spans ≥ 2 distinct `source_id`s, related in a chain. The rubric's atom dependency graph must be a non-trivial DAG (at least one atom whose `depends_on` includes another atom's id). |

`multi_hop` is **not** an attribute; it is L3 by definition.

### 4.3 Axis 2 — Retrieval difficulty

"Even knowing what to look for, why is finding it hard?"

| Attribute | Operational definition | Analyzer signal required |
|---|---|---|
| `long_tail` | Every required evidence anchor has inbound-edge degree ≤ `tau_long_tail` (default 3) in the project relation graph. | `signal_index.entity.reference_count` |
| `distracting_info` | At least one entity in the project shares the anchor's name or near-identical name and is *not* in `evidence`. The wrong candidate must be plausible enough that dense top-k retrieval at k ≥ 3 returns it ahead of the right one. | `signal_index.entity.name_collision_set` |
| `version_fork` | Evidence is contributed by a `source_set` whose corresponding entity exists in another `source_set` with materially different content. | `signal_index.entity.version_fork_diff` |
| `non_code_anchor` | At least one evidence span is in a Makefile, build script, CI script, linker file, or configuration file (`modality ∈ {script, config, build}`). | `source_inventory.modality` |

`version_fork` is optional per-project. NVDLA has it (`nvdlav1` vs implicit master, see v1.0 §10.1). Vortex does not. Profile turns it on or off per project; lint must accept its absence.

### 4.4 Axis 3 — Reasoning difficulty

"Even with the right evidence in hand, why is the answer hard?"

| Attribute | Operational definition | Analyzer signal required |
|---|---|---|
| `false_premise` | The query asserts a fact contradicted by evidence; a correct answer must explicitly identify and reject the false premise. | hand-authored or guided by `signal_index.entity.expected_but_missing` |
| `doc_code_divergence` | Evidence includes both a `code.*` and a `doc.*` source whose statements about the same entity disagree; the rubric requires the answer to call out the mismatch and choose the authoritative source. | `signal_index.entity.doc_code_alignment_score` (low) |
| `conditional_behavior` | The answer depends on tracing a guard, predicate, or state machine; at least one evidence span has `role ∈ {trigger_condition, branch, guard, predicate, state}`. | `signal_index.entity.branch_density` |
| `negative_evidence` | The correct answer is "no such thing in this snapshot"; the agent must refuse to fabricate. Correlates with `answerability ∈ {unanswerable_missing_evidence, unanswerable_ambiguous}` but applies also to answerable cases where one sub-question is negative. | `signal_index.entity.expected_but_missing` |
| `implicit_domain_knowledge` | The literal evidence text is necessary but not sufficient; the answer requires applying external domain knowledge (RTL semantics, memory ordering, RISC-V ISA, kernel scheduling, etc.) to interpret. Rubric must contain a `reasoning`-role atom that is not a verbatim quote of the evidence. | hand-authored taxonomy in `signal_index.domain_tags` |
| `quantitative_aggregation` | The answer requires counting, summing, or comparing across ≥ 2 evidence pieces ("how many engine modules implement bias add?", "which mode has lower memory traffic?"). | `signal_index.entity.aggregation_candidates` |

### 4.5 Answerability

Addresses v1.0 §11.4.

Independent of the axes. Determines structural expectations.

| Value | `references` / `evidence` minima | `expected_answer` shape | Typical Axis-3 correlate |
|---|---|---|---|
| `answerable` | ≥ 1 each (unchanged from v1.0) | Direct grounded answer. | any |
| `unanswerable_missing_evidence` | 0 evidence required; `references` may list "places we looked." | Canonical refusal that names the gap. | `negative_evidence` |
| `unanswerable_false_premise` | 0 evidence required, but contradicting evidence is recommended for the gate. | Identifies and rejects the false premise. | `false_premise` |
| `unanswerable_ambiguous` | ≥ 1 evidence span showing the ambiguity. | Acknowledges ambiguity, lists candidates, refuses to pick one. | `distracting_info` |

### 4.6 Capability stays orthogonal

Addresses v1.0 §11.2.

The existing `capability` field (`mechanism_trace`, `doc_code_cross_check`, …) names *what kind of question* is being asked. It is descriptive, project-extensible, and **not** used for difficulty enforcement.

Difficulty attributes are orthogonal: a `mechanism_trace` case can be L1 + `conditional_behavior`, or L3 + `long_tail` + `doc_code_divergence`. This separation closes the v1.0 confusion where `doc_code_cross_check` was used to describe the question type but the rows only did doc fact-lookup.

Going forward:
- Want a doc-vs-code divergence case → set `doc_code_divergence` attribute.
- Want a doc-lookup case → use the `doc_code_cross_check` capability with no attribute claim.

### 4.7 Out-of-scope attributes

- `freshness` — not applicable to a frozen snapshot.
- `time_sensitive` — collapses to `version_fork` in our setting; subsumed.
- `multi_lingual` — corpus is mostly English with occasional Chinese; not a benchmark target yet.

---

## 5. Generation control

Addresses v1.0 §11.9 (generator does not consume signals).

v1.0 generation flows "pick a graph pattern, write a question, hope difficulty falls out." v1.1 inverts this: pick the difficulty first, then find graph patterns that realize it. The pipeline becomes four stages:

```
  ┌──────────┐  ┌─────────────┐  ┌──────────────┐  ┌──────────────┐
  │ profile  │→ │ candidate   │→ │ draft cases  │→ │ structural   │→ output
  │ + signals│  │ slot picker │  │ (query, ev,  │  │ + adversarial│
  └──────────┘  └─────────────┘  │  rubric)     │  │ gates        │
                                  └──────────────┘  └──────────────┘
       §5.1          §5.2              §5.3              §6
```

### 5.1 Inputs

Two changes vs. v1.0:

1. **`project_context_bundle/` gains `signal_index.jsonl`** (§7.3). One JSON record per analyzer-derived signal, keyed by `signal_id`. This is the bridge that makes attribute-first sampling tractable.
2. **`generation_profile.yaml` gains `attribute_quotas` and `answerability_mix` blocks** (§7.2). Quotas are soft minima expressed as fractions of the target case count.

```yaml
attribute_quotas:
  rule: "every_case_has_at_least_two_signals_across_axes_combined"
  per_attribute_minimum:
    # axis 2
    long_tail:                0.30
    distracting_info:         0.20
    version_fork:             0.10   # may be 0.0 if signal absent
    non_code_anchor:          0.15
    # axis 3
    false_premise:            0.08
    doc_code_divergence:      0.15
    conditional_behavior:     0.20
    negative_evidence:        0.10
    implicit_domain_knowledge:0.15
    quantitative_aggregation: 0.08
answerability_mix:
  answerable:                                  0.70
  unanswerable_missing_evidence:               0.15
  unanswerable_false_premise:                  0.10
  unanswerable_ambiguous:                      0.05
```

### 5.2 Attribute-first sampling

For each candidate slot the generator must fill:

1. Pick a target attribute set, weighted by the deficit between running coverage and the per-attribute minimum. At least two signals across axes (§4.1).
2. Query `signal_index.jsonl` for entities/relations matching **all** chosen attributes. If the intersection is empty, retry with a relaxed set; log the rejection in `generation_report.md`.
3. Pick a case anchor (entity + supporting evidence spans) from the matching candidates.
4. Hand the anchor to the draft step (§5.3).

If a quota is configured but the analyzer's `signal_index.jsonl` has zero qualifying sites, the generator emits a `known_limits` warning (the existing v1.0 mechanism). This is the right place for project-specific gaps to surface — e.g. "Vortex has no version-fork; that quota is forced to 0."

### 5.3 Draft discipline

The v1.0 row contract (query/query_rewrite/evidence/expected_answer/rubric) is unchanged. v1.1 adds enforceable rules that close gaps observed in the v1.0 sample audit.

#### 5.3.1 Symptom-anchored queries

> **Rule.** A query is *symptom-anchored* by default, *file-anchored* only when justified.

- Default: the query describes a behavior, question, or doubt; the agent must *discover* which file/symbol holds the answer.
- Exception: cases with `capability ∈ {repo_structure_location, build_sim_verif_flow}` or the `file_anchor_required` tag may name files explicitly.
- At most one of `{file path, function name, symbol name}` may appear in the query unless `file_anchor_required` is set.

Motivation: in v1.0, many queries name the file holding the answer ("`bdma.c` 里 `dla_bdma_enable` 遇到 `num_transfers=0`…"). The agent's task degenerates to `open <named-file> && grep`, which is why oracle and grep are only 4 points apart.

Enforcement: lint hard-fails any case where the query string contains a `path.ext` token that also appears in `evidence[*].path`, unless `file_anchor_required` is set.

#### 5.3.2 Evidence sufficiency

| Tag | Required structure |
|---|---|
| `L2` | Evidence covers ≥ 2 distinct `source_id`s. |
| `L3` | Evidence covers ≥ 2 distinct `source_id`s **and** the required-atom set has at least one atom whose `depends_on` references another atom's id. |
| `doc_code_divergence` | Evidence covers ≥ 1 `code.*` source **and** ≥ 1 `doc.*` source. |
| `conditional_behavior` | At least one evidence span has `role ∈ {trigger_condition, branch, guard, predicate, state}`. |
| `version_fork` | Evidence spans come from ≥ 2 source sets exhibiting the fork. |

Enforced by lint.

#### 5.3.3 Rubric discipline

- `yes_no`, `fact_check`, and any `false_premise`-tagged row must carry at least one `forbidden_atoms` entry. In v1.0 only 24 % of rows did; this becomes a hard requirement.
- Exactly one `role: conclusion` atom answers the primary question. Multi-part questions encode sub-conclusions as additional `conclusion` atoms only when the question literally asks for multiple things; otherwise `evidence_fact` or `reasoning`.
- For `unanswerable_*` rows: `required_atoms[0]` encodes the refusal proposition; `forbidden_atoms` encodes "answer accepts the premise / fabricates the missing fact."

#### 5.3.4 Per-row claim stamp

Each generated row carries a `difficulty` block that records the declared attributes and the analyzer signals that justify them:

```jsonc
"difficulty": {
  "axis1_layer": "L2",
  "axis2_retrieval": ["long_tail", "distracting_info"],
  "axis3_reasoning": ["doc_code_divergence"],
  "answerability": "answerable",
  "claim_sources": {
    "long_tail":          ["sig:nvdla:roi_array_addr#refcount=2"],
    "distracting_info":   ["sig:nvdla:wrapper.v#collision=4"],
    "doc_code_divergence":["sig:nvdla:bdma_doc_vs_code#align=0.31"]
  }
}
```

`claim_sources` is what makes the gates falsifiable. It is the artifact a reviewer can audit to ask "is this row really a long-tail case?" without re-running the analyzer.

### 5.4 Generation discipline summary

| Rule | Enforced where |
|---|---|
| ≥ 2 difficulty signals across axes | lint (hard fail) |
| Symptom-anchored queries by default | lint (hard fail when file token leaks) |
| L2 ⇒ ≥ 2 source_ids in evidence | lint (hard fail) |
| L3 ⇒ ≥ 2 source_ids AND chained atoms | lint (hard fail) |
| `doc_code_divergence` ⇒ doc + code evidence | lint (hard fail) |
| `conditional_behavior` ⇒ guard/branch role span | lint (hard fail) |
| `yes_no` / `false_premise` ⇒ ≥ 1 forbidden atom | lint (hard fail) |
| Quotas met within tolerance (e.g. ±20 %) | generation report (warning) |

---

## 6. Validation: from schema lint to dual gates

Addresses v1.0 §11.1 and §11.3.

v1.0's validator only checks schema and structural well-formedness. v1.1 adds a second gate that probes the *behavioral* claim of each attribute.

### 6.1 Structural gate (deterministic; extends lint)

Augments `lint_benchmark_jsonl.py` with the rules in §5.4. Output: existing `<benchmark>.lint.json` plus a new `<benchmark>.structural_gate.json` listing per-row pass/fail with reason codes.

The structural gate is cheap, runs in CI, and must pass before the adversarial gate is invoked.

### 6.2 Adversarial gate (model-based; runs once per claim, cached)

For each declared attribute on a row, the gate runs a *matched* baseline that *should* fail when the attribute is present. The attribute is confirmed iff the baseline fails.

| Attribute | Matched adversarial baseline | Pass criterion (attribute confirmed) |
|---|---|---|
| L1 / L2 / L3 — breadth | `single_pass_retrieval` (one retrieval call, no iteration) at top-k = 5 | baseline judged not correct for L2/L3; trivially passes for L1 |
| `long_tail` | `closed_book_llm` (no retrieval) | not correct |
| `distracting_info` | `top_1_dense_only` | not correct |
| `version_fork` | `single_source_set_retrieval` | not correct |
| `non_code_anchor` | `code_only_retrieval` (excludes script/config/build modalities) | not correct |
| `false_premise` | `closed_book_llm` AND `oracle_evidence_llm` | both judged "answer accepts premise" or "answer wrong" |
| `doc_code_divergence` | `doc_only_retrieval` | not correct |
| `conditional_behavior` | `top_1_dense_only` | not correct |
| `negative_evidence` | `closed_book_llm` | fabricates (does not correctly refuse) |
| `implicit_domain_knowledge` | `oracle_evidence_no_reasoning_llm` (quotes evidence without inferring) | not correct |
| `quantitative_aggregation` | `top_1_dense_only` | not correct |

**Verdict rule.** A row passes the adversarial gate iff for **at least one** of its claimed attributes the matching baseline fails. Rows whose claimed attributes' baselines all *succeed* are flagged for re-tagging — either the claims are wrong (revise tags) or the case is genuinely easy (drop or downgrade).

**Prompt dispatch.** The judge prompt template varies by attribute family — e.g., `false_premise` and `negative_evidence` use a different prompt than `conditional_behavior`. This is the v1.1 plumbing that makes the v1.2 jury upgrade (v1.0 §11.6) a configuration change rather than new code.

Output: `<benchmark>.adversarial_gate.jsonl`, one record per row × claim, with judge verdict, score, rationale, and baseline metadata.

### 6.3 Verdict composition

```
case_admitted = structural_gate_pass AND adversarial_gate_pass
```

Rejected rows go to `<benchmark>.rejected.jsonl` with reason codes. The generator must over-draft (`drafts ≈ 2× target_count`) to absorb expected rejection rates.

`generation_report.md` reports per-attribute drafted-vs-kept funnels:

```
attribute             drafted   kept   drop_structural   drop_adversarial
long_tail             45        30     8                 7
distracting_info      30        18     5                 7
doc_code_divergence   20        14     3                 3
...
```

---

## 7. Schema and artifact changes

All changes are additive. Every v1.0 row remains valid under v1.1 schemas.

### 7.1 Row schema (additive)

`schemas/benchmark-row.schema.json` v1.1:

```jsonc
{
  // existing v1.0 fields unchanged ...
  "difficulty": {                                    // NEW, optional in v1.1.0, required in v1.1.1
    "axis1_layer": "L1 | L2 | L3",                   // mirrors layer.code
    "axis2_retrieval": ["long_tail", ...],
    "axis3_reasoning": ["doc_code_divergence", ...],
    "claim_sources": { "<attr>": ["<signal_id>", ...] }
  },
  "answerability": "answerable
                    | unanswerable_missing_evidence
                    | unanswerable_false_premise
                    | unanswerable_ambiguous",
  "tags": [..., "file_anchor_required"]              // optional opt-out
}
```

The conditional `references.minItems` / `evidence.minItems` rule from §4.5 is encoded in JSON Schema with `allOf` / `if` / `then`.

### 7.2 Generation profile schema (additive)

`schemas/generation-profile.schema.json` v1.1 adds:

```jsonc
{
  "attribute_quotas": { /* §5.1 shape */ },
  "answerability_mix": { /* §5.1 shape */ },
  "adversarial_gate": {
    "enabled": true,
    "judge": {
      "provider": "deepseek",
      "model": "deepseek-v4-pro",
      "api_key_env": "DEEPSEEK_API_KEY",
      "threshold": 0.7
    },
    "baselines": {
      "closed_book_llm":  { "model": "deepseek-v4-flash" },
      "top_1_dense_only": { "top_k": 1 }
    }
  }
}
```

### 7.3 New artifact: `signal_index.jsonl`

Produced by the analyzer alongside the existing five bundle files. One record per signal, keyed by `signal_id`.

```jsonc
{
  "signal_id": "sig:nvdla:roi_array_addr#refcount=2",
  "project": "nvdla",
  "axis": 2,
  "attribute": "long_tail",
  "anchor": {
    "kind": "entity",
    "entity_id": "ent:nvdla_sw:engine.c:roi_array_addr",
    "path": "repo_sources/nvdla/sw/kmd/firmware/engine.c",
    "lines": "172"
  },
  "evidence": { "reference_count": 2 },
  "extractor": "analyzer/relation_graph_indegree",
  "confidence": 0.95
}
```

One signal kind per attribute. The analyzer emits all entities/relations satisfying the operational definition of an attribute (§4.3, §4.4). The generator reads only this file for attribute-first sampling.

### 7.4 New artifact: per-row `difficulty.jsonl` side-car

Produced by the generator. Records, for each row, the full set of analyzer signals the row claims and the adversarial gate verdicts. Survives into the leaderboard so reviewers can audit any claim.

### 7.5 What does not change

- `project_manifest.json`, `source_inventory.jsonl`, `entity_index.jsonl`, `relation_graph.jsonl` shapes.
- `case_id`, `query`, `query_rewrite`, `evidence`, `references`, `expected_answer`, `answer_rubric` shapes.
- `validate_benchmark.py evaluate` retrieval / citation scoring. New per-axis pass-rate aggregates are computed by extension, not replacement.

---

## 8. Migration

### 8.1 Disposition of the existing 100 v1.0 cases

For each row:

1. **Auto-stamp.** A one-shot script walks each row, infers `difficulty.axis1_layer` from `layer.code`, computes Axis-2/Axis-3 attribute candidates from `signal_index.jsonl`, and writes a candidate `difficulty` block.
2. **Lint under v1.1 structural rules.** Rows that fail (expected: most NVDLA L2/L3-labeled rows that are actually single-source) are either:
   - re-labeled down to a defensible layer, or
   - rewritten with additional evidence to honor the layer, or
   - deprecated into `archive/`.
3. **Adversarial gate.** Surviving rows go through the gate. Predicted survival: ~40–60 % of v1.0 makes it into v1.1 unchanged or lightly edited.

### 8.2 Target sizes

| Project | v1.0 | v1.1 target |
|---|---:|---:|
| NVDLA | 50 | 200 (140 answerable + 60 unanswerable mix) |
| Vortex | 50 | 200 (140 + 60) |

Sizes are stratified across `(axis1, axis2_set, axis3_set, answerability)` to give per-attribute pass-rate reporting non-trivial statistical power.

### 8.3 Phased delivery

The order is dependency-driven, not calendar-driven.

1. **Analyzer extension** — emit `signal_index.jsonl`. Blocks everything downstream.
2. **Schema bump** to v1.1. Existing rows still validate.
3. **Lint extension** for the structural rules in §5.4 / §6.1.
4. **Adversarial gate** as a stand-alone script under `skills/benchmark-validator/scripts/`. Reuses the existing DeepSeek judge plumbing.
5. **Generator restructure** to the four-stage flow in §5. Depends on 1–3.
6. **Auto-stamp + audit** of the v1.0 corpus. Depends on 1–5.
7. **Fresh generation** to v1.1 targets per project. Depends on 1–5.

Steps 1–4 can land in parallel.

---

## 9. What v1.1 explicitly defers

Recorded so reviewers can see the seams.

| Deferred | Reason | Likely landing |
|---|---|---|
| EEU / IC information-seeking metrics (v1.0 §11.5) | Generation is the bottleneck. Once v1.1 produces variety, evaluation can be enriched. | v1.2 evaluator |
| 2-judge jury (v1.0 §11.6) | v1.1 ships prompt dispatch, which is the precondition. Jury itself is a config change. | v1.1.1 |
| CodeGraph adoption (v1.0 §11.7) | Analyzer track, not generation track. v1.1 generates from whatever signals are available. | analyzer v1.x |
| Two-verifier manual loop (v1.0 §11.8) | The adversarial gate is a partial substitute. Manual review is still recommended for the first v1.1 corpus. | v1.2 (or operational practice) |
| Multi-language phrasing (v1.0 §11.10) | Out of scope. | undecided |

---

## 10. Open questions

To be resolved by reviewers or in a v1.1.1 amendment.

1. **`quantitative_aggregation` viability.** Are there enough natural counting/summing questions in NVDLA and Vortex to justify the attribute? Suggested check: hand-draft 5 candidates per project from `signal_index`; if all feel natural, keep; otherwise drop.
2. **`version_fork` scope.** Confirmed off for Vortex. Should NVDLA expand source sets beyond `nvdlav1` + master to widen the fork surface, or accept the limited material?
3. **Adversarial judge robustness.** §6.2 relies on a single judge with per-attribute prompts. Land the jury upgrade now or as v1.1.1?
4. **Threshold tuning.** `tau_long_tail = 3`, similarity threshold for `doc_code_alignment_score`, top-k for `top_1_dense_only` — all picked by judgment. Revisit after the first v1.1 corpus.
5. **Cross-axis quota interaction.** Quotas in §5.1 are per-attribute. Natural co-occurrence (e.g. `long_tail` ∧ `distracting_info`) may compress the rest of the distribution. Watch and adjust.

---

## 11. Glossary (v1.1-specific terms)

| Term | Meaning |
|---|---|
| Axis | A coordinate of the difficulty model (Axis 1 breadth, Axis 2 retrieval difficulty, Axis 3 reasoning difficulty) |
| Attribute | A boolean tag belonging to one axis |
| Anchor | The primary entity around which a case is built |
| Adversarial baseline | A deliberately weak system used to falsify an attribute claim |
| Signal | An analyzer-produced datum that justifies an attribute being generatable for a given anchor |
| Structural gate | Deterministic schema + rule validation (lint extension) |
| Adversarial gate | Model-based per-attribute falsification |
| Answerability | Orthogonal structural status: answerable / unanswerable variant |
| Capability | Descriptive question kind, kept from v1.0, *not* used for difficulty |
| Claim | A difficulty attribute as declared on a row, before the gate confirms or rejects |
