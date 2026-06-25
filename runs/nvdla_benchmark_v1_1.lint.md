# Benchmark Validation Report

## Verdict: PASS

- Rows: 200
- FAIL: 0
- WARN: 0

## Coverage

### project
- `nvdla`: 200

### layer
- `L1`: 50
- `L2`: 90
- `L3`: 60

### capability
- `build_sim_verif_flow`: 33
- `doc_code_cross_check`: 34
- `mechanism_trace`: 33
- `negative_insufficient_evidence`: 33
- `repo_structure_location`: 34
- `tests_debug_evidence`: 33

### answer_type
- `fact_check`: 20
- `location`: 35
- `mechanism`: 35
- `negative`: 40
- `procedure`: 35
- `synthesis`: 35

## Findings

- No findings.

## Sampled Cases

### nvdla-v1_1-L1-001

- Query: NVDLA 中能确认 runtime API 的返回码是否区分队列已满和参数非法吗？我没有看到可核验证据。
- Rewrite: 判断 NVDLA 中是否有证据支持“runtime API 的返回码是否区分队列已满和参数非法”。
- References:
- Evidence:

### nvdla-v1_1-L1-002

- Query: NVDLA 中能确认 DMA 配置项缺省值在仿真和硬件路径是否一致吗？我没有看到可核验证据。
- Rewrite: 判断 NVDLA 中是否有证据支持“DMA 配置项缺省值在仿真和硬件路径是否一致”。
- References:
- Evidence:

### nvdla-v1_1-L1-003

- Query: NVDLA 中能确认 某个 debug 开关是否会改变 trace 输出格式吗？我没有看到可核验证据。
- Rewrite: 判断 NVDLA 中是否有证据支持“某个 debug 开关是否会改变 trace 输出格式”。
- References:
- Evidence:

### nvdla-v1_1-L1-004

- Query: NVDLA 中能确认 构建脚本是否支持增量清理单个 backend吗？我没有看到可核验证据。
- Rewrite: 判断 NVDLA 中是否有证据支持“构建脚本是否支持增量清理单个 backend”。
- References:
- Evidence:

### nvdla-v1_1-L1-005

- Query: NVDLA 中能确认 寄存器字段写 0 后是否会自动恢复默认值吗？我没有看到可核验证据。
- Rewrite: 判断 NVDLA 中是否有证据支持“寄存器字段写 0 后是否会自动恢复默认值”。
- References:
- Evidence:
