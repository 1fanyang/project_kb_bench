# Benchmark Validation Report

## Verdict: PASS

- Rows: 100
- FAIL: 0
- WARN: 0

## Coverage

### project
- `vortex`: 100

### layer
- `L1`: 20
- `L2`: 40
- `L3`: 40

### capability
- `build_simulation_flow`: 10
- `doc_code_cross_check`: 18
- `mechanism_trace`: 19
- `negative_insufficient_evidence`: 17
- `repo_structure_location`: 18
- `tests_debug_evidence`: 18

### answer_type
- `fact_check`: 18
- `location`: 19
- `mechanism`: 17
- `negative`: 4
- `procedure`: 21
- `synthesis`: 21

## Findings

- No findings.

## Sampled Cases

### vortex-v1_2-L1-031

- Query: Where is the AFU control module defined in the hardware tree?
- Rewrite: Where is the AFU control module defined in the hardware tree?
- References:
  - `src_vortex_00070` `repo_sources/vortex/vortex/hw/rtl/afu/xrt/VX_afu_ctrl.sv`
- Evidence:
  - `E1` `repo_sources/vortex/vortex/hw/rtl/afu/xrt/VX_afu_ctrl.sv:14-16`: This control module is part of the AFU/XRT hardware wrapper layer and is built against the GPU package definitions.

```text
13: 
14: `include "vortex_afu.vh"
15: 
16: module VX_afu_ctrl import VX_gpu_pkg::*; #(
17:     parameter S_AXI_ADDR_WIDTH = 8,
```


### vortex-v1_2-L1-032

- Query: What kind of module is the AFU wrapper in the hardware tree?
- Rewrite: What kind of module is the AFU wrapper in the hardware tree?
- References:
  - `src_vortex_00071` `repo_sources/vortex/vortex/hw/rtl/afu/xrt/VX_afu_wrap.sv`
- Evidence:
  - `E1` `repo_sources/vortex/vortex/hw/rtl/afu/xrt/VX_afu_wrap.sv:16-18`: The wrapper is defined in the AFU XRT RTL layer and imports the GPU package, which places it in the AFU integration path.

```text
15: 
16: `include "vortex_afu.vh"
17: 
18: module VX_afu_wrap import VX_gpu_pkg::*; #(
19: 	parameter C_S_AXI_CTRL_ADDR_WIDTH = 8,
```


### vortex-v1_2-L1-033

- Query: Where is the top-level AFU module defined in the hardware tree?
- Rewrite: Where is the top-level AFU module defined in the hardware tree?
- References:
  - `src_vortex_00072` `repo_sources/vortex/vortex/hw/rtl/afu/xrt/vortex_afu.v`
- Evidence:
  - `E1` `repo_sources/vortex/vortex/hw/rtl/afu/xrt/vortex_afu.v:14-16`: The `vortex_afu` module lives in the AFU XRT RTL source and is declared there directly.

```text
13: 
14: `include "vortex_afu.vh"
15: 
16: module vortex_afu #(
17: 	parameter C_S_AXI_CTRL_ADDR_WIDTH = 8,
```


### vortex-v1_2-L1-034

- Query: How is the AFU header meant to be used by the RTL modules?
- Rewrite: How is the AFU header meant to be used by the RTL modules?
- References:
  - `src_vortex_00073` `repo_sources/vortex/vortex/hw/rtl/afu/xrt/vortex_afu.vh`
- Evidence:
  - `E1` `repo_sources/vortex/vortex/hw/rtl/afu/xrt/vortex_afu.vh:106-108`: The AFU header is guarded as a dedicated include file and terminates its own include guard, so it is meant to be included before the module definitions use it.

```text
105: 
106: `include "VX_define.vh"
107: 
108: `endif // VORTEX_AFU_VH
```


### vortex-v1_2-L1-035

- Query: What mechanism is this behavior using?
- Rewrite: What mechanism is this behavior using?
- References:
  - `src_vortex_00074` `repo_sources/vortex/vortex/hw/rtl/cache/VX_cache.sv`
- Evidence:
  - `E1` `repo_sources/vortex/vortex/hw/rtl/cache/VX_cache.sv:14-16`: The cache module is defined in the cache RTL tree and is parameterized from the shared cache definitions package.

```text
13: 
14: `include "VX_cache_define.vh"
15: 
16: module VX_cache import VX_gpu_pkg::*; #(
17:     parameter `STRING INSTANCE_ID   = "",
```


### vortex-v1_2-L1-036

- Query: What overall behavior is established here?
- Rewrite: What overall behavior is established here?
- References:
  - `src_vortex_00075` `repo_sources/vortex/vortex/hw/rtl/cache/VX_cache_bank.sv`
- Evidence:
  - `E1` `repo_sources/vortex/vortex/hw/rtl/cache/VX_cache_bank.sv:14-16`: The cache-bank module is defined in the cache RTL tree and depends on shared cache definitions.

```text
13: 
14: `include "VX_cache_define.vh"
15: 
16: module VX_cache_bank import VX_gpu_pkg::*; #(
17:     parameter `STRING INSTANCE_ID= "",
```


### vortex-v1_2-L1-037

- Query: Which part of the implementation does this behavior belong to?
- Rewrite: Which part of the implementation does this behavior belong to?
- References:
  - `src_vortex_00076` `repo_sources/vortex/vortex/hw/rtl/cache/VX_cache_bypass.sv`
- Evidence:
  - `E1` `repo_sources/vortex/vortex/hw/rtl/cache/VX_cache_bypass.sv:14-16`: The bypass logic is defined in the cache RTL tree and pulls in the shared cache constants header.

```text
13: 
14: `include "VX_cache_define.vh"
15: 
16: module VX_cache_bypass import VX_gpu_pkg::*; #(
17:     parameter NUM_REQS          = 1,
```


### vortex-v1_2-L1-038

- Query: What sequence does this behavior follow?
- Rewrite: What sequence does this behavior follow?
- References:
  - `src_vortex_00077` `repo_sources/vortex/vortex/hw/rtl/cache/VX_cache_cluster.sv`
- Evidence:
  - `E1` `repo_sources/vortex/vortex/hw/rtl/cache/VX_cache_cluster.sv:14-16`: The cache cluster module is defined in the cache RTL tree and shares the common cache definition header.

```text
13: 
14: `include "VX_cache_define.vh"
15: 
16: module VX_cache_cluster import VX_gpu_pkg::*; #(
17:     parameter `STRING INSTANCE_ID    = "",
```


### vortex-v1_2-L1-039

- Query: What mechanism is this behavior using?
- Rewrite: What mechanism is this behavior using?
- References:
  - `src_vortex_00078` `repo_sources/vortex/vortex/hw/rtl/cache/VX_cache_data.sv`
- Evidence:
  - `E1` `repo_sources/vortex/vortex/hw/rtl/cache/VX_cache_data.sv:14-16`: The cache data module is defined in the cache RTL tree and imports the shared GPU package.

```text
13: 
14: `include "VX_cache_define.vh"
15: 
16: module VX_cache_data import VX_gpu_pkg::*; #(
17:     // Size of cache in bytes
```


### vortex-v1_2-L1-040

- Query: What overall behavior is established here?
- Rewrite: What overall behavior is established here?
- References:
  - `src_vortex_00079` `repo_sources/vortex/vortex/hw/rtl/cache/VX_cache_define.vh`
- Evidence:
  - `E1` `repo_sources/vortex/vortex/hw/rtl/cache/VX_cache_define.vh:17-19`: The shared cache-define header establishes request-selection sizing and related cache constants.

```text
16: 
17: `include "VX_define.vh"
18: 
19: `define CS_REQ_SEL_BITS         `CLOG2(NUM_REQS)
20: 
```
