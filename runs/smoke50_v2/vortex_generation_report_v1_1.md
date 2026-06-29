# VORTEX v1.1 Generation Report

## Inputs

- Context bundle: `runs/vortex_context_bundle_v2`
- Profile: `runs/vortex_generation_profile_v1_1.yaml`
- Signal index: `runs/vortex_context_bundle_v2/signal_index.jsonl`

## Output Summary

- Target rows: 200; admitted: 198; gap: 2 (under target — see drop log below)
- Layers: `{"L1": 50, "L2": 88, "L3": 60}`
- Answerability: `{"answerable": 138, "unanswerable_ambiguous": 10, "unanswerable_false_premise": 20, "unanswerable_missing_evidence": 30}`
- Difficulty attributes: `{"conditional_behavior": 60, "distracting_info": 63, "implicit_domain_knowledge": 47, "long_tail": 66, "negative_evidence": 30}`

## Drop log

- M2 (empty selected_evidence) dropped: 2
- M9 (adversarial gate failed) dropped: 0
  - m2_dropped: vortex-v1_1-L2-117, vortex-v1_1-L2-130

## Generation Notes

- Rows were generated deterministically from source inventory and real signal_index IDs.
- Rejected candidates file is present and empty because this deterministic pass emits only structurally valid candidates.
- Quotas for attributes absent from the signal index are infeasible and therefore not emitted.
- Vortex emits no `version_fork` rows.
