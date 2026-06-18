# Benchmark Validation Report

## Verdict: PASS

- Rows: 200
- FAIL: 0
- WARN: 0

## Coverage

### project
- `vortex`: 200

### layer
- `L1`: 50
- `L2`: 90
- `L3`: 60

### capability
- `build_simulation_flow`: 33
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

### vortex-v1_1-L1-001

- Query: vortex 里能确认runtime API 的返回码是否区分队列已满和参数非法吗？我现在没找到对应证据。
- Rewrite: 判断 vortex 中“runtime API 的返回码是否区分队列已满和参数非法”是否有可核验证据。
- References:
- Evidence:

### vortex-v1_1-L1-002

- Query: vortex 里能确认DMA 配置项缺省值在仿真和硬件路径是否一致吗？我现在没找到对应证据。
- Rewrite: 判断 vortex 中“DMA 配置项缺省值在仿真和硬件路径是否一致”是否有可核验证据。
- References:
- Evidence:

### vortex-v1_1-L1-003

- Query: vortex 里能确认某个 debug 开关是否会改变 trace 输出格式吗？我现在没找到对应证据。
- Rewrite: 判断 vortex 中“某个 debug 开关是否会改变 trace 输出格式”是否有可核验证据。
- References:
- Evidence:

### vortex-v1_1-L1-004

- Query: vortex 里能确认构建脚本是否支持增量清理单个 backend吗？我现在没找到对应证据。
- Rewrite: 判断 vortex 中“构建脚本是否支持增量清理单个 backend”是否有可核验证据。
- References:
- Evidence:

### vortex-v1_1-L1-005

- Query: vortex 里能确认寄存器字段写 0 后是否会自动恢复默认值吗？我现在没找到对应证据。
- Rewrite: 判断 vortex 中“寄存器字段写 0 后是否会自动恢复默认值”是否有可核验证据。
- References:
- Evidence:
