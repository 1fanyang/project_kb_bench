# CodeGraph resolution probe transcript

Project: `/Users/yangyifan/projects/work/kb_benchmark/repo_sources/vortex`
Symbol probed: `Core`
Binary: `/opt/homebrew/opt/node@22/bin/node /Users/yangyifan/projects/work/kb_benchmark/.claude/worktrees/dev-v1.3-analyzer-codegraph-phase0/tools/codegraph/dist/bin/codegraph.js`

## query-symbol-by-name

```
$ /opt/homebrew/opt/node@22/bin/node /Users/yangyifan/projects/work/kb_benchmark/.claude/worktrees/dev-v1.3-analyzer-codegraph-phase0/tools/codegraph/dist/bin/codegraph.js query --path /Users/yangyifan/projects/work/kb_benchmark/repo_sources/vortex --limit 5 --json Core
[
  {
    "node": {
      "id": "method:437b309fbdab657ef30529363e93648a",
      "kind": "method",
      "name": "Core",
      "qualifiedName": "Core::Core",
      "filePath": "vortex/sim/simx/core.cpp",
      "language": "cpp",
      "startLine": 28,
      "endLine": 172,
      "startColumn": 0,
      "endColumn": 1,
      "visibility": null,
      "isExported": false,
      "isAsync": false,
      "isStatic": false,
      "isAbstract": false,
      "updatedAt": 1782382652296
    },
    "score": 113.03969108152364
  },
  {
    "node": {
      "id": "class:4bde861b2aa61dbbe846e3813435230d",
      "kind": "class",
      "name": "Core",
      "qualifiedName": "Core",
      "filePath": "vortex/sim/simx/core.h",
      "language": "cpp",
      "startLine": 44,
      "endLine": 239,
      "startColumn": 0,
      "endColumn": 1,
      "visibility": null,
      "isExported": false,
      "isAsync": false,
      "isStatic": false,
      "isAbstract": false,
      "updatedAt": 1782382652309
    },
    "score": 111.0256451847623
  },
  {
    "node": {
      "id": "class:118b86884d8f1539ec92e1dec74dd17b",
      "kind": "class",
      "name": "Core",
      "qualifiedName": "Core",
      "filePath": "vortex/sim/simx/dispatcher.h",
      "language": "cpp",
      "startLine": 22,
      "endLine": 22,
      "startColumn": 0,
      "endColumn": 10,
      "visibility": null,
      "isExported": false,
      "isAsync": false,
      "isStatic": false,
      "isAbstract": false,
      "updatedAt": 1782382652340
    },
    "score": 98.0256451847623
  },
  {
    "node": {
      "id": "class:7d0e0c668989ab47b9bb8cd6d7d10227",
      "kind": "class",
      "name": "Core",
      "qualifiedName": "Core",
      "filePath": "vortex/sim/simx/emulator.h",
      "language": "cpp",
      "startLine": 36,
      "endLine": 36,
      "startColumn": 0,
      "endColumn": 10,
      "visibility": null,
      "isExported": false,
      "isAsync": false,
      "isStatic": false,
      "isAbstract": false,
  
[…stdout truncated…]

--- stderr ---
(node:37328) ExperimentalWarning: SQLite is an experimental feature and might change at any time
(Use `node --trace-warnings ...` to show where the warning was created)

exit_code=0
```

## files-listing

```
$ /opt/homebrew/opt/node@22/bin/node /Users/yangyifan/projects/work/kb_benchmark/.claude/worktrees/dev-v1.3-analyzer-codegraph-phase0/tools/codegraph/dist/bin/codegraph.js files --path /Users/yangyifan/projects/work/kb_benchmark/repo_sources/vortex
[1m
Project Structure (366 files):
[0m
└── vortex
    ├── .github
    │   └── workflows
    │       ├── apptainer-ci.yml[2m (yaml, 0 symbols)[0m
    │       └── ci.yml[2m (yaml, 0 symbols)[0m
    ├── ci
    │   ├── datagen.py[2m (python, 7 symbols)[0m
    │   ├── dtm_test.py[2m (python, 47 symbols)[0m
    │   ├── sst_test_vortex_conform.py[2m (python, 3 symbols)[0m
    │   ├── sst_test_vortex_fibonacci.py[2m (python, 3 symbols)[0m
    │   ├── sst_test_vortex_hello.py[2m (python, 3 symbols)[0m
    │   ├── sst_test_vortex_vecadd.py[2m (python, 3 symbols)[0m
    │   ├── trace_csv.py[2m (python, 25 symbols)[0m
    │   └── travis_run.py[2m (python, 10 symbols)[0m
    ├── hw
    │   ├── dpi
    │   │   ├── float_dpi.cpp[2m (cpp, 41 symbols)[0m
    │   │   └── util_dpi.cpp[2m (cpp, 25 symbols)[0m
    │   ├── scripts
    │   │   ├── bin2coe.py[2m (python, 9 symbols)[0m
    │   │   ├── gen_config.py[2m (python, 15 symbols)[0m
    │   │   ├── repl_params.py[2m (python, 9 symbols)[0m
    │   │   └── scope.py[2m (python, 17 symbols)[0m
    │   ├── syn
    │   │   ├── modelsim
    │   │   │   ├── vortex_dpi.cpp[2m (cpp, 19 symbols)[0m
    │   │   │   └── vortex_dpi.h[2m (c, 1 symbols)[0m
    │   │   └── synopsys
    │   │       └── models
    │   │           └── memory
    │   │               └── cln28hpc
    │   │                   └── rf2_32x128_wm1
    │   │                       └── testbench.cpp[2m (cpp, 4 symbols)[0m
    │   └── unittest
    │       ├── cache_top
    │       │   └── main.cpp[2m (cpp, 6 symbols)[0m
    │       ├── common
    │       │   └── vl_simulator.h[2m (cpp, 13 symbols)[0m
    │       ├── core_top
    │       │   └── main.cpp[2m (cpp, 6 symbols)[0m
    │       ├── generic_queue
    │       │   └── main.cpp[2m (cpp, 9 symbols)[0m
    │       ├── issue_top
    │       │   └── main.cpp[2m (cpp, 6 symbols)[0m
    │       ├── local_mem_top
    │       │   └── main.cpp[2m (cpp, 6 symbols)[0m
    │       ├─
[…stdout truncated…]

--- stderr ---
(node:37426) ExperimentalWarning: SQLite is an experimental feature and might change at any time
(Use `node --trace-warnings ...` to show where the warning was created)

exit_code=0
```

## node-detail-with-trail

```
$ /opt/homebrew/opt/node@22/bin/node /Users/yangyifan/projects/work/kb_benchmark/.claude/worktrees/dev-v1.3-analyzer-codegraph-phase0/tools/codegraph/dist/bin/codegraph.js node --path /Users/yangyifan/projects/work/kb_benchmark/repo_sources/vortex Core
**12 definitions named "Core"**
Returning 12 in full — pick the one you need (no Read required).

**Core** (enum_member)

**Location:** vortex/sim/simx/cache_sim.cpp:163

```cpp
163			Core   = 3
```

---

**Core** (method)

**Location:** vortex/sim/simx/core.cpp:28

```cpp
28	Core::Core(const SimContext& ctx,
29	           uint32_t core_id,
30	           Socket* socket,
31	           const Arch &arch,
32	           const DCRS &dcrs
33	           )
34	  : SimObject(ctx, StrFormat("core%d", core_id))
35	  , icache_req_ports(1, this)
36	  , icache_rsp_ports(1, this)
37	  , dcache_req_ports(DCACHE_NUM_REQS, this)
38	  , dcache_rsp_ports(DCACHE_NUM_REQS, this)
39	  , core_id_(core_id)
40	  , socket_(socket)
41	  , arch_(arch)
42	#ifdef EXT_TCU_ENABLE
43	  , tensor_unit_(TensorUnit::Create("tcu", arch, this))
44	#endif
45	#ifdef EXT_V_ENABLE
46	  , vec_unit_(VecUnit::Create("vpu", arch, this))
47	#endif
48	  , emulator_(arch, dcrs, this)
49	  , ibuffers_(arch.num_warps(), IBUF_SIZE)
50	  , scoreboard_(arch_)
51	  , operands_(ISSUE_WIDTH)
52	  , dispatchers_((uint32_t)FUType::Count)
53	  , func_units_((uint32_t)FUType::Count)
54	  , lmem_switch_(NUM_LSU_BLOCKS)
55	  , mem_coalescers_(NUM_LSU_BLOCKS)
56	  , pending_icache_(arch_.num_warps())
57	  , commit_arbs_(ISSUE_WIDTH)
58	  , ibuffer_arbs_(ISSUE_WIDTH, {ArbiterType::RoundRobin, PER_ISSUE_WARPS})
59	{
60	  char sname[100];
61	
62	  for (uint32_t iw = 0; iw < ISSUE_WIDTH; ++iw) {
63	    operands_.at(iw) = Operands::Create(this);
64	  }
65	
66	  // create the memory coalescer
67	  for (uint32_t b = 0; b < NUM_LSU_BLOCKS; ++b) {
68	    snprintf(sname, 100, "%s-coalescer%d", this->name().c_str(), b);
69	    mem_coalescers_.at(b) = MemCoalescer::Create(sname, LSU_CHANNELS, DCACHE_CHANNELS, DCACHE_WORD_SIZE, LSUQ_OUT_SIZE, 1);
70	  }
71	
72	  // create local memory
73	  snprintf(sname, 100, "%s-lmem", this->name().c_str());
74	  local_mem_ = LocalMem::Create(sname, LocalMem::Config{
75	    (1 << LMEM_LOG_SIZE),
76	    LSU_WOR
[…stdout truncated…]

--- stderr ---
(node:37517) ExperimentalWarning: SQLite is an experimental feature and might change at any time
(Use `node --trace-warnings ...` to show where the warning was created)

exit_code=0
```

## callers-cross-file

```
$ /opt/homebrew/opt/node@22/bin/node /Users/yangyifan/projects/work/kb_benchmark/.claude/worktrees/dev-v1.3-analyzer-codegraph-phase0/tools/codegraph/dist/bin/codegraph.js callers --path /Users/yangyifan/projects/work/kb_benchmark/repo_sources/vortex --limit 10 --json Core
{
  "symbol": "Core",
  "callers": []
}

--- stderr ---
(node:37542) ExperimentalWarning: SQLite is an experimental feature and might change at any time
(Use `node --trace-warnings ...` to show where the warning was created)

exit_code=0
```

## callees-cross-file

```
$ /opt/homebrew/opt/node@22/bin/node /Users/yangyifan/projects/work/kb_benchmark/.claude/worktrees/dev-v1.3-analyzer-codegraph-phase0/tools/codegraph/dist/bin/codegraph.js callees --path /Users/yangyifan/projects/work/kb_benchmark/repo_sources/vortex --limit 10 --json Core
{
  "symbol": "Core",
  "callees": [
    {
      "name": "Create",
      "kind": "method",
      "filePath": "vortex/sim/common/simobject.h",
      "startLine": 554
    },
    {
      "name": "name",
      "kind": "method",
      "filePath": "vortex/sim/simx/vpu/vec_ops.h",
      "startLine": 25
    },
    {
      "name": "log2ceil",
      "kind": "function",
      "filePath": "vortex/sim/common/bitmanip.h",
      "startLine": 48
    },
    {
      "name": "bind",
      "kind": "method",
      "filePath": "vortex/sim/common/simobject.h",
      "startLine": 90
    },
    {
      "name": "at",
      "kind": "function",
      "filePath": "vortex/runtime/common/nlohmann_json.hpp",
      "startLine": 21155
    },
    {
      "name": "reset",
      "kind": "method",
      "filePath": "vortex/sim/simx/core.cpp",
      "startLine": 178
    }
  ]
}

--- stderr ---
(node:37569) ExperimentalWarning: SQLite is an experimental feature and might change at any time
(Use `node --trace-warnings ...` to show where the warning was created)

exit_code=0
```
