# M3 — Behavioral Claim Extractor

**Stage 2 of the v1.1 modular generator.** Reads
`drafts/<project>.curated_evidence.jsonl` (from M2) plus the original
`drafts/<project>.candidates.jsonl` (for `row_plan` context). Writes
`drafts/<project>.claims.jsonl`. See `contracts.md` for I/O shapes.

## Purpose

Turn each row's curated evidence into a small set of propositional
claims — declarative sentences that describe what the code/doc actually
*does* or *says*. M6 (the answer drafter) reads these claims and uses
them as the substance of the expected_answer. The lint atomizer in
Ship 3 will turn these into rubric `required_atoms`.

## Why this is a host-LLM step

This stage is paraphrase + interpretation. The LLM reads code/doc
snippets and produces a structured, human-readable claim. Rules can't
do this; they would either copy the snippet verbatim (which is what
the current generator does, and what the lint flags as POINTER_STYLE)
or produce a generic placeholder.

## Procedure

For each line in the input JSONL:

1. Read the row's `row_plan` from the candidates file (matched by `case_id`).
2. Read the row's `selected_evidence` from the curated file.
3. If `selected_evidence` is empty:
   - For `unanswerable_missing_evidence`: emit one `kind: "negative"` claim
     of the form `"The current snapshot does not contain a span that
     confirms or refutes <derived topic>."` Set `evidence_ids: []`.
   - For any other answerability with empty evidence: skip the row
     (write nothing — the assembler will drop it).
4. Otherwise, write 1–3 claims that, together, support a complete answer
   to the row's target unknown:
   - **L1 / answerable**: usually 1 claim summarizing the single span.
   - **L2 / answerable**: 1–2 claims that name what the two sources agree
     on (corroboration) or disagree on (`doc_code_divergence`).
   - **L3 / answerable**: 2–3 claims that form a chain — claim N's
     evidence_ids include a later evidence_id than claim N-1.
   - **`unanswerable_false_premise`**: 1–2 claims; the first names the
     *correct* fact (with `kind: "behavior"` or `"state"`), making the
     false premise refutable.
   - **`unanswerable_ambiguous`**: 1 claim of `kind: "comparison"` that
     names the two (or more) candidates the evidence cannot disambiguate.

## Claim shape

```json
{
  "id": "C1",
  "text": "engine_dispatch returns -EINVAL when the request descriptor pointer is null.",
  "evidence_ids": ["E1"],
  "kind": "behavior"
}
```

Rules:
- `text` is one declarative sentence. No questions, no rubric language.
- `text` is **not** a verbatim substring of any `statement` from M2 and
  **not** a verbatim substring of any `raw_snippet` from the candidate
  evidence.
- Every `evidence_ids` entry references an `evidence_id` that M2 emitted
  for the same case_id.
- `id` is `C1`, `C2`, `C3` in claim order.
- `kind` is one of: `behavior`, `state`, `invariant`, `negative`,
  `comparison`.

## Kind taxonomy

| kind | use when |
|---|---|
| `behavior` | A procedure/function/script does something — actions, returns, side effects. |
| `state` | A register, variable, signal, or data-structure value/shape. |
| `invariant` | A constraint that must always hold (e.g., parameter relationships, ranges). |
| `negative` | An explicit absence — used by `unanswerable_missing_evidence` rows. |
| `comparison` | A fact that exists *between* two artifacts — doc vs code, two source sets, two versions. |

## Few-shot exemplars

### Example A — L1 behavior

M2 curated:
```json
{"case_id":"vortex-v1_1-L1-049","selected_evidence":[{"evidence_id":"E1","source_id":"src_vortex_00167","path":"repo_sources/vortex/vortex/hw/rtl/core/VX_alu_muldiv.sv","lines":"74-76","role":"evidence_fact","statement":"For W-form ALU ops (`is_alu_w`), VX_alu_muldiv masks rs2 to the low 32 bits before invoking the DPI multiplier; for non-W ops the full XLEN value is forwarded."}],"rejected_candidates":[]}
```

M3 output:
```json
{"case_id":"vortex-v1_1-L1-049","claims":[{"id":"C1","text":"VX_alu_muldiv truncates rs2 to its low 32 bits when the op is W-form before invoking the DPI multiplier; otherwise it passes the full XLEN value through unchanged.","evidence_ids":["E1"],"kind":"behavior"}]}
```

### Example B — L3 chain (multi-hop)

M2 curated (3 spans, parameter declaration → instantiation → wrapping CSR):
```json
{"case_id":"vortex-v1_1-L3-178","selected_evidence":[{"evidence_id":"E1","path":"...VX_local_mem.sv","lines":"33-35","role":"evidence_fact","statement":"VX_local_mem accepts a TAG_WIDTH parameter that sizes the response-buffer tag field."},{"evidence_id":"E2","path":"...VX_local_mem_wrap.sv","lines":"82-95","role":"evidence_fact","statement":"The wrapper passes the CSR-derived NUM_TAGS value into VX_local_mem.TAG_WIDTH via $clog2(NUM_TAGS)."},{"evidence_id":"E3","path":"...VX_csr.sv","lines":"210-218","role":"evidence_fact","statement":"NUM_TAGS is a runtime-configurable CSR field; default 16."}]}
```

M3 output:
```json
{"case_id":"vortex-v1_1-L3-178","claims":[{"id":"C1","text":"VX_local_mem's TAG_WIDTH parameter is computed from the wrapper's NUM_TAGS rather than fixed at compile time.","evidence_ids":["E1","E2"],"kind":"behavior"},{"id":"C2","text":"NUM_TAGS itself is a runtime CSR field (default 16), making the local-mem tag width software-configurable.","evidence_ids":["E2","E3"],"kind":"state"}]}
```

### Example C — unanswerable_missing_evidence

M2 curated:
```json
{"case_id":"nvdla-v1_1-L1-004","selected_evidence":[],"rejected_candidates":[]}
```

M3 output:
```json
{"case_id":"nvdla-v1_1-L1-004","claims":[{"id":"C1","text":"The current NVDLA snapshot does not contain a build-script span that confirms or refutes per-backend incremental cleanup.","evidence_ids":[],"kind":"negative"}]}
```

### Example D — unanswerable_false_premise

M2 curated has substantive evidence; the false premise to refute is "X
provides no useful information."

M3 output emits one `behavior`/`state` claim that *does* describe what X
provides, making the premise refutable:
```json
{"case_id":"nvdla-v1_1-L2-088","claims":[{"id":"C1","text":"NV_NVDLA_CDMA_WT_fifo declares an explicit FIFO read pointer and empty/full status outputs, contradicting the claim that the module exposes no usable behavior.","evidence_ids":["E1"],"kind":"behavior"}]}
```

## Validation

```bash
python skills/benchmark-generator/scripts/validate_module_outputs.py \
  --module M3 \
  --candidates drafts/<project>.candidates.jsonl \
  --curated drafts/<project>.curated_evidence.jsonl \
  drafts/<project>.claims.jsonl
```

FAIL on:
- claim text is a verbatim substring of any M2 `statement` or any
  candidate `raw_snippet`
- `evidence_ids` includes an id not present in M2's curated output
- L3 row's claims lack any pair sharing evidence_ids (no chain)
- `unanswerable_missing_evidence` row has zero claims

WARN on:
- claim text < 30 chars (likely too terse)
- > 3 claims on a single row
