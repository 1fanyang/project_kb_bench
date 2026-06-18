# NVDLA v1.1 Smoke Generation Report

## Summary

- Generated 20 smoke benchmark rows using migrated v1.1 evidence anchors plus signal-index-backed unanswerable rows.
- Answerable rows keep direct evidence spans from migrated rows; unanswerable rows are bounded refusals or false-premise/ambiguous checks.
- Query rewrites are limited to visible query semantics.

## Counts

- Rows: 20
- Answerability: answerable=14, unanswerable_ambiguous=1, unanswerable_false_premise=2, unanswerable_missing_evidence=3
- Layers: L1=20
- Difficulty attributes: distracting_info=10, implicit_domain_knowledge=20, long_tail=20

## Sampling Notes

- Attribute-first constraints were satisfied by selecting difficulty attributes only when backed by real signal IDs from `signal_index.jsonl`.
- The signal indexes do not expose `false_premise` or `negative_evidence` attributes, so false-premise answerability rows cite available real retrieval/reasoning signals instead of synthetic difficulty claims.
- All rows include `answerability` and `difficulty.claim_sources`.

## Validation

- `validate_benchmark.py lint --schema-version v1.1`: PASS (`Rows: 20`, `FAIL: 0`, `WARN: 0`).
- `adversarial_gate.py --dry-run`: PASS, wrote 50 records to `runs/nvdla_benchmark_v1_1_smoke.adversarial_gate.jsonl`.
- `uv run --with pytest pytest tests/test_*.py -q`: PASS (`50 passed, 2 subtests passed`).
