# M6 — Answer Drafter

**Stage 3 of the v1.1 modular generator.** Reads
`drafts/<project>.candidates.jsonl` (for `row_plan`),
`drafts/<project>.curated_evidence.jsonl` (M2), and
`drafts/<project>.claims.jsonl` (M3). Writes
`drafts/<project>.answers.jsonl`. See `contracts.md` for I/O shapes.

## Purpose

Produce the `expected_answer` string. First sentence is the direct answer
to the row's target unknown. The body interprets the claims and embeds
the required citations. No rubric language. No verbatim evidence paste.

## Why this is a host-LLM step

This is composition — selecting the right cadence, voice, and yes/no
prefix while threading citations into prose. Rules produce the
"可以确认：path:lines 显示：snippet" output we already have, which fails
on every quality dimension the lint checks.

## Procedure

For each line in the candidates file:

1. Look up the row's `row_plan`, the M2 `selected_evidence`, and the M3
   `claims` by `case_id`.
2. Decide the answer's first-sentence prefix from `answer_type`:
   - `yes_no` → begin with `会`, `不会`, or `无法判断` (Chinese rows),
     or `Yes`/`No`/`Cannot confirm` (English rows).
   - `fact_check` → begin with `支持` / `不支持` (or `Confirmed` / `Refuted`).
   - `mechanism` / `procedure` / `synthesis` / `location` / `comparison`
     → begin with a declarative sentence stating the conclusion.
   - `negative` → begin with `无法判断` / `只能给出有限结论` for
     `unanswerable_ambiguous`; `无法判断` for `unanswerable_missing_evidence`.
3. Write the body in 1–3 sentences. Each substantive sentence either:
   - paraphrases one M3 claim, with the relevant citation in backticks
     directly after the sentence, **or**
   - explicitly says what the evidence does *not* support (for
     `unanswerable_*` rows).
4. The final position contains the citation list when more than one
   span backs the answer. The format mirrors the existing convention:
   `引用：\`path:lines\`；\`path:lines\``.
5. Write `citation_paths` as a list of `path:lines` strings, one per
   distinct M2 `selected_evidence` entry referenced in the answer.

## Rules (lint-enforced after writing)

- The expected_answer must contain each `path:lines` from
  `citation_paths` in backtick form somewhere in the text.
- Every `citation_paths` entry must match exactly one
  `selected_evidence[i].path` + `:` + `lines` from M2.
- No `应说明`, `答案需要`, `应当`, `应该`, `请检索并`, or English
  equivalents.
- No literal `这些行显示：` prefix.
- No verbatim quote of any M2 `raw_snippet` longer than 30 chars.
- For yes_no rows, the first segment (up to `。` or `.`) starts with
  one of the prefix tokens above.
- For `answerability == "unanswerable_missing_evidence"`,
  `citation_paths` is `[]` and the body names the gap.

## Few-shot exemplars

### Example A — L1 mechanism

claims:
```json
[{"id":"C1","text":"VX_alu_muldiv truncates rs2 to its low 32 bits when the op is W-form before invoking the DPI multiplier; otherwise it passes the full XLEN value through unchanged.","evidence_ids":["E1"],"kind":"behavior"}]
```

curated_evidence:
```json
[{"evidence_id":"E1","path":"repo_sources/vortex/vortex/hw/rtl/core/VX_alu_muldiv.sv","lines":"74-76", ...}]
```

answer:
```json
{"case_id":"vortex-v1_1-L1-049","expected_answer":"W-form ALU multiplications zero out the upper bits of rs2 before the DPI multiplier sees them; non-W-form multiplies pass the full XLEN value through (`repo_sources/vortex/vortex/hw/rtl/core/VX_alu_muldiv.sv:74-76`).","citation_paths":["repo_sources/vortex/vortex/hw/rtl/core/VX_alu_muldiv.sv:74-76"]}
```

### Example B — yes/no

answer_type: `yes_no`. The first sentence begins with `会` or `不会`.

```json
{"case_id":"vortex-v1-L2-009","expected_answer":"会。`ci/blackbox.sh` 的 parse_args 把 --l2cache 追加为 -DL2_ENABLE 并把 --l3cache 追加为 -DL3_ENABLE (`repo_sources/vortex/vortex/ci/blackbox.sh:67-68`)。","citation_paths":["repo_sources/vortex/vortex/ci/blackbox.sh:67-68"]}
```

### Example C — unanswerable_missing_evidence

```json
{"case_id":"nvdla-v1_1-L1-004","expected_answer":"无法判断。当前 NVDLA 快照里没有给出可核验的构建脚本片段说明是否支持按 backend 增量清理；需要补充对应 Makefile 或脚本片段后才能回答。","citation_paths":[]}
```

### Example D — unanswerable_false_premise

```json
{"case_id":"nvdla-v1_1-L2-088","expected_answer":"不支持这个说法。NV_NVDLA_CDMA_WT_fifo 明确暴露了 FIFO 的读指针和空/满状态输出，并不是“没有提供任何可用信息” (`repo_sources/nvdla/hw/vmod/nvdla/cdma/NV_NVDLA_CDMA_WT_fifo.v:10-12`)。","citation_paths":["repo_sources/nvdla/hw/vmod/nvdla/cdma/NV_NVDLA_CDMA_WT_fifo.v:10-12"]}
```

### Example E — L3 chain

```json
{"case_id":"vortex-v1_1-L3-178","expected_answer":"VX_local_mem 的 TAG_WIDTH 不是编译期固定值：包装层把 NUM_TAGS 通过 $clog2 计算后送入 TAG_WIDTH (`repo_sources/.../VX_local_mem.sv:33-35`；`repo_sources/.../VX_local_mem_wrap.sv:82-95`)；NUM_TAGS 自身是运行时可配的 CSR 字段（默认 16）(`repo_sources/.../VX_csr.sv:210-218`)。","citation_paths":["repo_sources/.../VX_local_mem.sv:33-35","repo_sources/.../VX_local_mem_wrap.sv:82-95","repo_sources/.../VX_csr.sv:210-218"]}
```

## Validation

```bash
python skills/benchmark-generator/scripts/validate_module_outputs.py \
  --module M6 \
  --candidates drafts/<project>.candidates.jsonl \
  --curated drafts/<project>.curated_evidence.jsonl \
  --claims drafts/<project>.claims.jsonl \
  drafts/<project>.answers.jsonl
```

FAIL on:
- expected_answer missing a `citation_paths` entry in backtick form
- `citation_paths` entry does not match any M2 selected_evidence
- yes_no row missing 会/不会/无法判断 prefix in first sentence
- rubric-like language present
- verbatim copy of `raw_snippet` longer than 30 chars
- `unanswerable_missing_evidence` row with non-empty `citation_paths`

WARN on:
- expected_answer > 400 chars (over-long)
- citation_paths length > 5 (likely over-citing)
