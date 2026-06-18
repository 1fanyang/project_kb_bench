# NVDLA v1.1 Generation Report

## Inputs

- Context bundle: `runs/nvdla_context_bundle`
- Profile: `runs/nvdla_generation_profile_v1_1.yaml`
- Signal index: `runs/nvdla_context_bundle/signal_index.jsonl`

## Output Summary

- Rows admitted: 200
- Layers: `{"L1": 50, "L2": 90, "L3": 60}`
- Answerability: `{"answerable": 140, "unanswerable_ambiguous": 10, "unanswerable_false_premise": 20, "unanswerable_missing_evidence": 30}`
- Difficulty attributes: `{"conditional_behavior": 113, "distracting_info": 60, "doc_code_divergence": 25, "implicit_domain_knowledge": 87, "long_tail": 115, "non_code_anchor": 25}`

## Generation Notes

- Rows were generated deterministically from source inventory and real signal_index IDs.
- Rejected candidates file is present and empty because this deterministic pass emits only structurally valid candidates.
- Quotas for attributes absent from the signal index are infeasible and therefore not emitted.
- Vortex emits no `version_fork` rows.
