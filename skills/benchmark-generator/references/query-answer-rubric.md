# Query, Answer, and Rubric Rules v1

## query

`query` should look like something a real user might ask. Use varied forms:

- short colloquial questions;
- context-heavy questions;
- hypothesis checks;
- doc/code mismatch checks;
- follow-up style questions;
- Chinese with realistic English technical terms.

## query_rewrite

`query_rewrite` is the normalized user information need before retrieval and reasoning.

Allowed:

- remove filler such as `帮我`, `我想确认`, `到底`, `顺便`;
- normalize yes/no phrasing;
- keep files, modules, symbols, source scopes, and citation requests explicitly visible in `query`;
- add only project name or source scope when it is already explicit in row context and does not add a technical assumption.

Forbidden:

- technical entities absent from `query`;
- retrieved source facts;
- answer conclusions;
- hidden construction notes;
- prefixes like `验证假设：`, `检索并回答`, `优先参考实体`, `范围约束`;
- broad rubric text such as `需要定位触发条件、状态/数据更新、以及后续调用或消费关系`.

Example:

```text
query: 这个地方 num_transfers 是 0 的时候还会 launch 吗？看下 bdma.c
good: 判断 bdma.c 中 num_transfers == 0 时是否还会 launch。
bad: 验证 dla_bdma_enable 在 num_transfers == 0 时设置 DLA_EVENT_OP_COMPLETED 并跳过 CFG_LAUNCH0/1。
```

## expected_answer

The expected answer is the standard reference answer, not instructions for an answer.

Rules:

1. The first sentence directly answers the target unknown.
2. For yes/no cases, the first sentence begins with an equivalent of `会`, `不会`, or `无法判断`.
3. If the query asks for evidence, code evidence, citations, or line proof, embed evidence citations in the answer body.
4. Every key conclusion is supported by `evidence`.
5. No claim exceeds the evidence authority or version scope.
6. Do not write rubric language such as `应说明...`, `答案需要...`, or `检索并串联...`.

## answer_rubric

`answer_rubric` is a structured decomposition of `expected_answer` for scoring. It is not another answer.

Required shape:

```json
{
  "answer_goal": "The target unknown being scored.",
  "required_atoms": [
    {
      "id": "A1",
      "role": "conclusion",
      "statement": "num_transfers == 0 时不会 launch 硬件",
      "match_type": "semantic_yes_no",
      "evidence_ids": ["E1", "E2"],
      "weight": 2
    }
  ],
  "forbidden_atoms": [
    {
      "id": "F1",
      "statement": "num_transfers == 0 时仍会 launch 硬件",
      "match_type": "semantic_contradiction",
      "severity": "fatal"
    }
  ],
  "citation_policy": {
    "required": "when_query_requests_evidence",
    "required_evidence_ids": ["E1", "E2"],
    "acceptable_granularity": "path_line"
  }
}
```

## Atom Definition

An atom is the smallest independently scoreable semantic proposition.

Use an atom when:

- missing it would change whether the answer is correct;
- it can be supported by one or a few evidence spans;
- it does not combine multiple independent conclusions.

Entities such as modules, functions, and files are not atoms by themselves. They are subjects or objects inside atom statements.

Common atom roles:

```text
conclusion evidence_fact reasoning boundary location procedure_step comparison_point
```

Common match types:

```text
semantic_yes_no semantic_fact semantic_reasoning path_or_symbol
numeric_or_version list_set semantic_contradiction
```

## Scoring Intention

Retrieval quality is scored from `references` and `evidence`, not from rubric atoms.

Answer quality is scored from:

```text
required atom coverage
fatal forbidden atom detection
citation policy compliance when triggered
```

This split keeps source retrieval, answer semantics, and citation formatting separate.
