# VORTEX v1.1 Generation Report

## Inputs

- Context bundle: `runs/vortex_context_bundle`
- Profile: `runs/vortex_generation_profile_v1_1.yaml`
- Signal index: `runs/vortex_context_bundle/signal_index.jsonl`

## Output Summary

- Target rows: 200; admitted: 1; gap: 199 (under target — see drop log below)
- Layers: `{"L1": 1}`
- Answerability: `{"unanswerable_missing_evidence": 1}`
- Difficulty attributes: `{"negative_evidence": 1}`

## Drop log

- M2 (empty selected_evidence) dropped: 0
- M9 (adversarial gate failed) dropped: 199
  - gate_dropped: vortex-v1_1-L1-002, vortex-v1_1-L1-003, vortex-v1_1-L1-004, vortex-v1_1-L1-005, vortex-v1_1-L1-006, vortex-v1_1-L1-007, vortex-v1_1-L1-008, vortex-v1_1-L1-009, vortex-v1_1-L1-010, vortex-v1_1-L1-011, ...(+189)

## Generation Notes

- Rows were generated deterministically from source inventory and real signal_index IDs.
- Rejected candidates file is present and empty because this deterministic pass emits only structurally valid candidates.
- Quotas for attributes absent from the signal index are infeasible and therefore not emitted.
- Vortex emits no `version_fork` rows.
