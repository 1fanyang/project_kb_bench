# M5 — Question Author

**Stage 4 of the v1.1 modular generator.** Reads
`drafts/<project>.candidates.jsonl` (for `row_plan` and `style_hint`),
`drafts/<project>.curated_evidence.jsonl` (M2), and
`drafts/<project>.claims.jsonl` (M3). Writes
`drafts/<project>.queries.jsonl`.

See `contracts.md` for the canonical I/O shape. Run after M3 and before M6
in normal pipeline order, or in parallel with M6 — both consume the same
M2/M3 outputs.

## Purpose

Compose one realistic user query per row plus its `query_rewrite`. The
query is the part of the benchmark the agent actually sees. The current
template-only generator produced just nine surface forms across the entire
corpus; M5 produces one query per row with naturalness, diversity, and
explicit per-attribute difficulty.

## Why this is a host-LLM step

Phrasing is the hardest part to template. Templates produce surface
uniformity that defeats every downstream metric:

- They make queries grep-solvable by leaking the anchor file's tokens.
- They tip off unanswerable cases ("我没有看到可核验证据") so the agent
  doesn't need to detect the gap.
- They erase the difficulty axes M5 is supposed to surface (a
  `distracting_info` row reads identically to a `long_tail` row).

The host LLM resolves all three because composition, register, and
domain-aware phrasing are what LLMs do well.

## Inputs the host LLM receives per row

From the row plan:

- `layer`: L1 / L2 / L3
- `answerability`: answerable / unanswerable_missing_evidence /
  unanswerable_false_premise / unanswerable_ambiguous
- `axis2_retrieval`: list — long_tail / distracting_info / version_fork /
  non_code_anchor
- `axis3_reasoning`: list — false_premise / doc_code_divergence /
  conditional_behavior / negative_evidence / implicit_domain_knowledge /
  quantitative_aggregation
- `capability`: descriptive label (`mechanism_trace`,
  `doc_code_cross_check`, ...)
- `answer_type`: yes_no / mechanism / fact_check / comparison / location /
  procedure / negative / synthesis
- `style_hint`: colloquial / contextual / hypothesis-check / follow-up

From M2 curated_evidence: `statement` (interpretive) per evidence span.
From M3 claims: `text` + `kind`.

## Inputs the host LLM MUST NOT use in the query

**Hard constraint, enforced by the validator:**

- No file `path` from any evidence span.
- No basename token (length ≥ 3) from any evidence file. If the evidence
  file is `VX_cache_bypass.sv`, the query cannot contain `VX`,
  `cache`, or `bypass` as standalone tokens. Use behavioral phrasing
  like "the L2 cache bypass path" — that is a behavior term, not a
  symbol name, as long as no file under examination is literally named
  `vx_cache_bypass` (the validator does basename-token matching).
- No full symbol name that matches a basename. `dla_bdma_enable` is
  fine; `bdma.c` is not.

Exception: if `row_plan` carries the tag `file_anchor_required` (set by
`repo_structure_location` and build-flow capabilities), file naming is
allowed — the lint will not flag it.

The host LLM has the path in its inputs so the validator can audit
against the truth. The LLM's job is to phrase without using it.

## Output shape

```jsonc
{
  "case_id": "nvdla-v1_1-L1-031",
  "query": "NVDLA 的 INT8 推理是怎么得到每层量化参数的？",
  "query_rewrite": "确定 NVDLA 低精度推理中每层量化参数的来源与计算方式。",
  "style": "colloquial"
}
```

`style` echoes back the assigned hint (audit only). `query_rewrite`
follows the existing v1.1 rule: normalized information need, no hidden
evidence facts, no construction artifacts.

## How to compose

Combine four orthogonal dimensions. The validator only checks structural
conformance; you choose the surface form.

### Dimension 1 — answer_type framing (grammatical form)

| answer_type | Chinese pattern | English pattern |
|---|---|---|
| `yes_no` | end with `吗？` / `是否…？` / `能否…？` | "Does …?" / "Will …?" / "Can …?" |
| `mechanism` | `…是怎么实现的？` / `…机制是？` | "How does …?" |
| `fact_check` | `…说法对吗？` / `…是真的吗？` | "Is it true that …?" |
| `comparison` | `…和…的区别在哪？` | "How does X compare to Y?" |
| `location` | `…在哪？` / `…定义在哪里？` | "Where is …?" |
| `procedure` | `怎么…？` / `…的步骤？` | "What are the steps to …?" |
| `negative` | confidently phrased declarative or yes/no — the agent must determine no answer exists | as Chinese |
| `synthesis` | `整体看…什么样？` | "What's the overall picture of …?" |

### Dimension 2 — style register (surface form)

Pre-assigned in `row_plan.style_hint`. Use it.

| style | shape | example shell |
|---|---|---|
| `colloquial` | short, casual, often uses 吗/呢, ≤ 30 chars | `NVDLA 的 X 是怎么做的？` |
| `contextual` | sets up a scenario in ~60 chars, ends with the question | `在排查 X 时我想确认 Y——具体是怎么处理的？` |
| `hypothesis-check` | embeds a hypothesis the agent must confirm or reject | `我感觉 NVDLA 的 X 是 Y 干的，是这样吗？` |
| `follow-up` | pretends a conversation precedes, asks for one specific detail | `我们之前聊到 X，现在我想看具体的 Y 是怎么实现的。` |

For English-anchored content (e.g., NVDLA `LowPrecision.md` or Vortex
docs), use the English equivalent of the style.

### Dimension 3 — axis-2 (retrieval-difficulty) adaptations

| axis2 attribute | how the query must surface it |
|---|---|
| `long_tail` | Ask about a less-famous, low-traffic entity. Avoid name-dropping the most popular module. |
| `distracting_info` | Phrase using a term that *could* match multiple modules; the answer must name the right one. Example: "NVDLA 的 dual reg 是哪个 engine 实现的？" when multiple engines have *_dual_reg.v files. |
| `version_fork` | Do NOT specify the version. Phrase as if asking about "the" behavior; the answer surfaces that two source sets disagree. |
| `non_code_anchor` | Ask about a build, script, or config behavior — "Makefile 里 X 这个开关会怎么影响构建？" |

### Dimension 4 — axis-3 (reasoning-difficulty) adaptations

| axis3 attribute | how the query must surface it |
|---|---|
| `conditional_behavior` | Embed the guard literally: "When X / 当 X 满足时, does/会 Y?" The answer must enumerate the condition. |
| `doc_code_divergence` | Phrase from the doc's perspective. The answer surfaces the code's actual behavior. Example: "文档说 X，代码也是这样吗？" |
| `implicit_domain_knowledge` | Use the domain term naturally without spelling it out. "NVDLA 的 INT8 是怎么标定的？" assumes the reader knows what calibration is for. |
| `quantitative_aggregation` | Ask for a count, sum, or comparison. "NVDLA 里有几个 engine 实现了 bias add？" |
| `false_premise` | Embed a specific wrong claim, not "X has no useful information." The premise must be falsifiable by the evidence. Example: "我记得 BDMA 在 num_transfers=0 时还是会触发硬件，对吗？" (when the code actually short-circuits). |
| `negative_evidence` | Phrase confidently as if the behavior exists; the agent must determine it does not. |

### Per-answerability rules (override the above)

- **`answerable`**: combine all four dimensions normally.
- **`unanswerable_missing_evidence`**: confident user request phrased so
  the gap is the answer. **No refusal cues** — do not say "我没有看到证据",
  "请说明能确认什么、不能确认什么", "the docs don't say." Phrase as if
  you fully expect a concrete answer; the agent must detect the gap by
  searching and failing.
- **`unanswerable_false_premise`**: the query *asserts* a specific
  evidence-contradicted fact and asks for confirmation. The wrong fact
  must be precise enough that the M2 evidence can refute it.
- **`unanswerable_ambiguous`**: the query is well-formed but the
  evidence supports ≥ 2 plausible answers. The agent must name both.

## Few-shot exemplars

Each example shows: `row_plan` + relevant M3 claims → composed query.
Comments after the example explain which dimensions are at play.

### Example A — L1 / answerable / mechanism / long_tail+implicit_domain_knowledge / colloquial

```
row_plan: L1, answerable, mechanism, [long_tail], [implicit_domain_knowledge], colloquial
claims:   ["NVDLA's low-precision path uses TensorRT's calibration tool
          to sweep per-layer output tensors over a calibration dataset
          and derive scale factors."]

→ query:        "NVDLA 的 INT8 推理是怎么得到每层量化参数的？"
→ query_rewrite: "确定 NVDLA 低精度推理中每层量化参数的来源与计算方式。"
```
*answer_type=mechanism → `是怎么…的？` form. style=colloquial → short.
implicit_domain_knowledge → "INT8 / 量化" is a domain term the reader is
expected to know. long_tail → no name-dropping of TensorRT in the query;
the agent must surface it.*

### Example B — L2 / answerable / fact_check / non_code_anchor+conditional_behavior / hypothesis-check

```
row_plan: L2, answerable, fact_check, [non_code_anchor], [conditional_behavior], hypothesis-check
claims:   ["The Vortex hw Makefile reads ROOT_DIR via realpath, then
          includes config.mk before any build target fires."]

→ query:        "我感觉 Vortex 的硬件构建是先解析 ROOT_DIR、再读 config.mk 才会决定要不要重新生成 RTL，对吗？"
→ query_rewrite: "判断 Vortex 硬件构建顺序：ROOT_DIR 解析与 config.mk 加载是否先于 RTL 生成。"
```
*answer_type=fact_check → `对吗？` ending. style=hypothesis-check → "我感觉…对吗" frame.
non_code_anchor → focus on the Makefile behavior. conditional_behavior →
embed the conditional ordering.*

### Example C — L3 / answerable / mechanism / distracting_info+conditional_behavior / contextual

```
row_plan: L3, answerable, mechanism, [distracting_info], [conditional_behavior], contextual
claims:   3 claims tracing a chain through CDMA scheduler

→ query:        "排查 CDMA 卡住时我想理清调度链路：发起搬运的请求是谁触发的，FIFO 满的时候怎么反压回上游？"
→ query_rewrite: "梳理 NVDLA CDMA 调度链路：请求触发方与 FIFO 满时的反压路径。"
```
*answer_type=mechanism → `是怎么…` phrasing. style=contextual → setup
scenario. distracting_info → CDMA has multiple similarly-named blocks;
the question doesn't pin which. conditional_behavior → "FIFO 满的时候".*

### Example D — L1 / unanswerable_missing_evidence / negative / long_tail+implicit_domain_knowledge / contextual

```
row_plan: L1, unanswerable_missing_evidence, negative, [long_tail],
          [implicit_domain_knowledge], contextual

→ query:        "在排查一个 CI 失败时我想知道 NVDLA simulator 的退出码语义——超时和断言失败会用同一个退出码，还是会分开？"
→ query_rewrite: "判断 NVDLA simulator 的退出码是否区分超时与断言失败。"
```
*Confident framing; no refusal cue. The agent has to search the
simulator code, realize the snapshot doesn't disambiguate the exit codes,
and refuse honestly.*

### Example E — L2 / unanswerable_false_premise / fact_check / distracting_info+conditional_behavior / hypothesis-check

```
row_plan: L2, unanswerable_false_premise, fact_check, [distracting_info],
          [conditional_behavior], hypothesis-check
claims:   correct fact: "FIFO_EMPTY is signalled by raddr_fifo's state
          machine; only when raddr_fifo asserts empty do downstream reads
          stall."

→ query:        "我记得 NVDLA 的读地址 FIFO 是用 wdata_fifo 的 empty 信号控制反压的，对吗？"
→ query_rewrite: "核对 NVDLA 读地址 FIFO 是否依赖 wdata_fifo 的 empty 信号反压。"
```
*Specific wrong claim (it's raddr_fifo, not wdata_fifo). The evidence
refutes it concretely. distracting_info → the two FIFO names are easy
to confuse.*

### Example F — L1 / unanswerable_ambiguous / negative / distracting_info+implicit_domain_knowledge / colloquial

```
row_plan: L1, unanswerable_ambiguous, negative, [distracting_info],
          [implicit_domain_knowledge], colloquial

→ query:        "NVDLA 的 dual_reg 是 CACC 还是 CDMA 那边的？"
→ query_rewrite: "区分 NVDLA dual_reg 模块归属：CACC 还是 CDMA。"
```
*The evidence shows dual_reg files in both CACC and CDMA paths; the
question presents the actual ambiguity. The answer must enumerate both
and refuse to pick one without further context.*

## Validation

```bash
python skills/benchmark-generator/scripts/validate_module_outputs.py \
  --module M5 \
  --candidates drafts/<project>.candidates.jsonl \
  --curated drafts/<project>.curated_evidence.jsonl \
  drafts/<project>.queries.jsonl
```

The validator FAILs on:
- missing/extra case_ids vs. candidates file
- query contains a file basename token from any evidence path (unless
  `file_anchor_required` is set)
- query contains a refusal cue on `unanswerable_*` rows
  (`我没有看到`, `没有提供任何可用信息`, `请说明能确认什么`)
- `yes_no` / `fact_check` row without an interrogative marker
  (`吗`, `？`, `?`, `是否`, `能否`, `Does`, `Is`, `Can`)
- query length outside [10, 240] chars
- query_rewrite duplicates the query verbatim and the query has chatty
  markers (existing v1.1 rule)
- query_rewrite contains hidden-context markers (existing v1.1 rule)

WARNs on:
- style mismatch — e.g. `colloquial` row whose query > 60 chars
- query repeated verbatim across the corpus (low diversity)
