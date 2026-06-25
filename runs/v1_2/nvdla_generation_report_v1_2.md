# NVDLA Benchmark v1.2 Generation Report

- Final rows: 100
- Source pool rows: 153
- Clean pool rows: 123
- Layer quotas: {'L1': 20, 'L2': 40, 'L3': 40}
- Answer types: {'mechanism': 16, 'synthesis': 18, 'location': 21, 'procedure': 17, 'fact_check': 20, 'negative': 8}
- Pipeline: v1.2 host-LLM-assisted modular M2-M9 (`drafts/v1_2_llm`)
- Selection: validator-clean + generator-lint-clean, evidence span reuse cap <= 3.
