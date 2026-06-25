# NVDLA v1.1 Generation Report

## Inputs

- Context bundle: `runs/nvdla_context_bundle`
- Profile: `runs/nvdla_generation_profile_v1_1.yaml`
- Signal index: `runs/nvdla_context_bundle/signal_index.jsonl`

## Output Summary

- Rows admitted: 30
- Layers: `{"L1": 30}`
- Answerability: `{"unanswerable_missing_evidence": 30}`
- Difficulty attributes: `{"distracting_info": 5, "implicit_domain_knowledge": 30, "long_tail": 25}`

## Generation Notes

- Rows were generated deterministically from source inventory and real signal_index IDs.
- Rejected candidates file is present and empty because this deterministic pass emits only structurally valid candidates.
- Quotas for attributes absent from the signal index are infeasible and therefore not emitted.
- Vortex emits no `version_fork` rows.
