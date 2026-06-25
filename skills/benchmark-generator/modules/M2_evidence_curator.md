# M2 — Evidence Curator

**Stage 1 of the v1.1 modular generator.** Reads
`drafts/<project>.candidates.jsonl` and writes
`drafts/<project>.curated_evidence.jsonl`. See `contracts.md` for I/O shapes.

## Purpose

Select the minimum set of evidence spans that supports answering each row,
and reject spans whose `raw_snippet` is boilerplate (license headers, RST
heading underlines, Sphinx config, CI yml headers, assertion macro fences).
Replace the analyzer's mechanical `这些行显示：<paste>` evidence statement
with a one-sentence description of what the span *shows*.

## Why this is a host-LLM step

The deterministic rule list in
`skills/benchmark-generator/scripts/lint_benchmark_jsonl.py`
(`BOILERPLATE_EVIDENCE_PHRASES`) catches the worst cases, but it cannot
distinguish "this `parameter X = ...;` line is the answer" from "this
`parameter X = ...;` line is incidental to the answer." That is semantic
judgment, which is what the host LLM is for.

## Procedure

For each line in the input JSONL:

1. Read the row's `row_plan` to know the layer, attributes, capability,
   and answer_type the row is targeting.
2. For `answerability == "unanswerable_missing_evidence"`: emit
   `{"case_id": "...", "selected_evidence": [], "rejected_candidates": []}`
   and move on.
3. Otherwise, walk `candidates`:
   - Reject any `raw_snippet` matching the boilerplate categories
     (`license_header`, `copyright_continuation`, `rst_heading_only`,
     `sphinx_config_boilerplate`, `ci_workflow_header`,
     `assertion_macro_fence`, `blank_or_separator`).
   - Among survivors, pick the minimal set that satisfies the layer:
     - L1: exactly 1 span.
     - L2: ≥ 2 spans from ≥ 2 distinct `source_id` values, related in
       parallel (compare / verify / corroborate the same fact).
     - L3: ≥ 2 spans from ≥ 2 distinct `source_id`, related as a chain
       (the second span builds on or follows the first).
   - For `conditional_behavior` in axis3: at least one selected span
     must contain a real guard/branch token (`if`, `case`, `assert`,
     `posedge`, etc.). If none of the candidates does, mark the row's
     `selected_evidence` as `[]` and add a rejected_candidates entry
     with `reason: "no_guard_token_available"` — the row should be
     dropped in assembly.
   - For `doc_code_divergence` in axis3: must include ≥ 1 code source
     and ≥ 1 doc source whose claims actually disagree.
4. For each kept span, write a `statement` field that names what the
   span shows in one declarative sentence. The statement must not be a
   verbatim substring of the `raw_snippet`. Use the same language as
   the project's documentation (NVDLA: English; Vortex: English).
5. Renumber kept spans as `E1`, `E2`, `E3` in selection order.

## Boilerplate categories

When rejecting, use exactly one of these `reason` codes:

| code | matches |
|---|---|
| `license_header` | Apache / MIT / proprietary license header bodies |
| `copyright_continuation` | `// this distribution for more information ...` |
| `rst_heading_only` | A short title plus `=====` or `-----` underline |
| `sphinx_config_boilerplate` | `# If extensions (or modules to document with autodoc) ...` |
| `ci_workflow_header` | A `.yml` line beginning `on:` / `workflow_dispatch:` with no payload |
| `assertion_macro_fence` | NVDLA-style `` `define ASSERT_RESET ...`` macro fence |
| `blank_or_separator` | Only whitespace, `===`, `---`, or `// ===` separators |
| `layer_companion_missing` | The candidate itself is substantive but no co-source exists that would let an L2/L3 row meet its layer constraint; use this instead of pretending the candidate is boilerplate |
| `other_boilerplate` | Catch-all; over-use is flagged by the validator |

## Statement style

| Bad (verbatim) | Good (interpretive) |
|---|---|
| `这些行显示：if (req == NULL) return -EINVAL;` | `engine_dispatch rejects null request pointers with -EINVAL before any register write.` |
| `这些行显示：parameter NUM_CORES = 4;` | `The cluster instantiates four cores by default; this parameter feeds the cluster-wide cache sizing.` |
| `这些行显示：Hardware Manual / ============` | (reject — `rst_heading_only`) |

## Few-shot exemplars

### Example A — L1 answerable (substantive RTL anchor)

Input line:
```json
{"case_id":"vortex-v1_1-L1-049","project":"vortex","row_plan":{"layer":"L1","answerability":"answerable","axis2_retrieval":["long_tail"],"axis3_reasoning":["implicit_domain_knowledge"],"capability":{"code":"repo_structure_location","zh":"项目结构定位"},"answer_type":{"code":"location","zh":"位置定位"}},"anchor":{"source_id":"src_vortex_00167","path":"repo_sources/vortex/vortex/hw/rtl/core/VX_alu_muldiv.sv","lines":"74-76","raw_snippet":"wire [`XLEN-1:0] mul_in2 = is_alu_w ? (execute_if.data.rs2_data[i] & `XLEN'hFFFFFFFF) : execute_if.data.rs2_data[i];\n            always @(*) begin\n                dpi_imul (mul_fire_in, is_signed_mul_a, is_signed_mul_b, mul_in1, mul_in2, mul_result_tmp);"},"candidates":[{"candidate_id":"C1","source_id":"src_vortex_00167","path":"repo_sources/vortex/vortex/hw/rtl/core/VX_alu_muldiv.sv","lines":"74-76","raw_snippet":"wire [`XLEN-1:0] mul_in2 = is_alu_w ? (execute_if.data.rs2_data[i] & `XLEN'hFFFFFFFF) : execute_if.data.rs2_data[i];\n            always @(*) begin\n                dpi_imul (mul_fire_in, is_signed_mul_a, is_signed_mul_b, mul_in1, mul_in2, mul_result_tmp);","attribute":"long_tail","axis":2,"role_hint":"evidence_fact"}]}
```

Output line:
```json
{"case_id":"vortex-v1_1-L1-049","selected_evidence":[{"evidence_id":"E1","source_id":"src_vortex_00167","path":"repo_sources/vortex/vortex/hw/rtl/core/VX_alu_muldiv.sv","lines":"74-76","role":"evidence_fact","statement":"For W-form ALU ops (`is_alu_w`), VX_alu_muldiv masks rs2 to the low 32 bits before invoking the DPI multiplier; for non-W ops the full XLEN value is forwarded."}],"rejected_candidates":[]}
```

### Example B — L2 with one substantive span and one boilerplate filler

Input candidates: an RTL `define ASSERT_RESET` macro fence plus a real
parameter declaration in a related file.

Output: keep the parameter declaration as E1, reject the `define
ASSERT_RESET ...` candidate with `reason: "assertion_macro_fence"`. If
the row's layer demands L2 but no second substantive candidate is
available, return `selected_evidence: []` so the assembler drops the row.

### Example C — `unanswerable_missing_evidence`

Input line: `{"case_id":"nvdla-v1_1-L1-004", ...,"candidates":[]}`
Output line: `{"case_id":"nvdla-v1_1-L1-004","selected_evidence":[],"rejected_candidates":[]}`

## Validation after writing

```bash
python skills/benchmark-generator/scripts/validate_module_outputs.py \
  --module M2 \
  --candidates drafts/<project>.candidates.jsonl \
  drafts/<project>.curated_evidence.jsonl
```

The validator will FAIL on:
- missing or extra case_ids vs. candidates file
- evidence_id collisions within a row
- `path` or `lines` not matching any candidate from the row
- L2/L3 source-count violation
- `conditional_behavior` axis3 without guard tokens in any selected span
- `statement` that is a verbatim substring of `raw_snippet`

And WARN on:
- `other_boilerplate` reason used in more than 10% of rejections (suggests
  the curator is over-rejecting)
- Selected snippets ≥ 200 chars (suggests over-broad span)
