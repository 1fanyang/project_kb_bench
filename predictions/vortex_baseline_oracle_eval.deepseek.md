# Method Evaluation Report

## Summary

- Cases: 50
- Strict E2E pass rate: 0.940
- Retrieval pass rate: 1.000
- Evidence recall@5: 1.000
- Evidence precision@5: 1.000
- Citation pass rate: 0.980
- LLM Judge coverage: 1.000
- Mean LLM Judge score: 0.988
- LLM Judge verdicts: {'correct': 48, 'partial': 2}
- Token usage coverage: 0.000
- Mean total tokens: 0.0
- Sum total tokens: 0

## Slice Summary

### layer
- `L1`: cases=15 strict=0.933 retrieval=1.000 ev_recall=1.000 judge=0.978 tokens=0.0
- `L2`: cases=30 strict=0.967 retrieval=1.000 ev_recall=1.000 judge=0.992 tokens=0.0
- `L3`: cases=5 strict=0.800 retrieval=1.000 ev_recall=1.000 judge=1.000 tokens=0.0

### capability
- `build_simulation_flow`: cases=6 strict=0.833 retrieval=1.000 ev_recall=1.000 judge=0.945 tokens=0.0
- `cache_and_perf`: cases=5 strict=1.000 retrieval=1.000 ev_recall=1.000 judge=1.000 tokens=0.0
- `doc_code_cross_check`: cases=6 strict=1.000 retrieval=1.000 ev_recall=1.000 judge=1.000 tokens=0.0
- `mechanism_trace`: cases=3 strict=1.000 retrieval=1.000 ev_recall=1.000 judge=1.000 tokens=0.0
- `negative_insufficient_evidence`: cases=3 strict=1.000 retrieval=1.000 ev_recall=1.000 judge=1.000 tokens=0.0
- `repo_structure_location`: cases=2 strict=1.000 retrieval=1.000 ev_recall=1.000 judge=1.000 tokens=0.0
- `rtl_hierarchy_trace`: cases=4 strict=1.000 retrieval=1.000 ev_recall=1.000 judge=1.000 tokens=0.0
- `runtime_api_trace`: cases=9 strict=1.000 retrieval=1.000 ev_recall=1.000 judge=1.000 tokens=0.0
- `software_test_path`: cases=4 strict=1.000 retrieval=1.000 ev_recall=1.000 judge=1.000 tokens=0.0
- `tests_debug_evidence`: cases=8 strict=0.750 retrieval=1.000 ev_recall=1.000 judge=0.969 tokens=0.0

### answer_type
- `comparison`: cases=5 strict=0.800 retrieval=1.000 ev_recall=1.000 judge=0.934 tokens=0.0
- `fact_check`: cases=9 strict=1.000 retrieval=1.000 ev_recall=1.000 judge=1.000 tokens=0.0
- `location`: cases=2 strict=1.000 retrieval=1.000 ev_recall=1.000 judge=1.000 tokens=0.0
- `mechanism`: cases=10 strict=1.000 retrieval=1.000 ev_recall=1.000 judge=1.000 tokens=0.0
- `negative`: cases=3 strict=1.000 retrieval=1.000 ev_recall=1.000 judge=1.000 tokens=0.0
- `procedure`: cases=6 strict=0.833 retrieval=1.000 ev_recall=1.000 judge=0.958 tokens=0.0
- `synthesis`: cases=4 strict=0.750 retrieval=1.000 ev_recall=1.000 judge=1.000 tokens=0.0
- `yes_no`: cases=11 strict=1.000 retrieval=1.000 ev_recall=1.000 judge=1.000 tokens=0.0

## Per Case

- `vortex-v1-L1-001` strict=True ev_recall=1.00 citation=True judge=correct:1.0 tokens=None notes=ok query=Vortex README 里 backend driver 到底有哪些？给我引用。
- `vortex-v1-L2-002` strict=True ev_recall=1.00 citation=True judge=correct:1.0 tokens=None notes=ok query=默认不设 VORTEX_DRIVER 的话，Vortex 真的是走 simx 吗？给我代码证据。
- `vortex-v1-L2-003` strict=True ev_recall=1.00 citation=True judge=correct:1.0 tokens=None notes=ok query=vx_dev_open 是怎么根据 VORTEX_DRIVER 加载 driver 的？
- `vortex-v1-L1-004` strict=True ev_recall=1.00 citation=True judge=correct:1.0 tokens=None notes=ok query=从 README 快速跑 vecadd 要哪些命令？
- `vortex-v1-L2-005` strict=True ev_recall=1.00 citation=True judge=correct:1.0 tokens=None notes=ok query=blackbox.sh 默认 app/driver 是什么，和 README 默认 driver 说法冲突吗？
- `vortex-v1-L1-006` strict=True ev_recall=1.00 citation=True judge=correct:1.0 tokens=None notes=ok query=runtime 里面 opae/xrt/rtlsim/simx 分别在哪个目录？
- `vortex-v1-L2-007` strict=True ev_recall=1.00 citation=True judge=correct:1.0 tokens=None notes=ok query=我想改 DCACHE_SIZE/L2_CACHE_SIZE/L3_CACHE_SIZE，blackbox 要怎么传 CONFIGS？
- `vortex-v1-L3-008` strict=True ev_recall=1.00 citation=True judge=correct:1.0 tokens=None notes=ok query=Vortex cache 层级从文档到 RTL 怎么对应？
- `vortex-v1-L2-009` strict=True ev_recall=1.00 citation=True judge=correct:1.0 tokens=None notes=ok query=ci/blackbox.sh 里 --l2cache 会变成 -DL2_ENABLE 吗？看代码行。
- `vortex-v1-L2-010` strict=True ev_recall=1.00 citation=True judge=correct:1.0 tokens=None notes=ok query=blackbox --perf=2 只是运行参数还是也会打开 PERF_ENABLE？
- `vortex-v1-L2-011` strict=True ev_recall=1.00 citation=True judge=correct:1.0 tokens=None notes=ok query=simx runtime 里 vx_start 到 processor.run 的链路是什么？
- `vortex-v1-L2-012` strict=True ev_recall=1.00 citation=True judge=correct:1.0 tokens=None notes=ok query=simx 和 rtlsim runtime 的 start/ready_wait 逻辑有什么差别？
- `vortex-v1-L2-013` strict=True ev_recall=1.00 citation=True judge=correct:1.0 tokens=None notes=ok query=xrt driver 的 start 跟 simx driver 主要差在哪？
- `vortex-v1-L2-014` strict=True ev_recall=1.00 citation=True judge=correct:1.0 tokens=None notes=ok query=opae 和 xrt driver 开始执行时分别怎么触发硬件？
- `vortex-v1-L1-015` strict=True ev_recall=1.00 citation=True judge=correct:1.0 tokens=None notes=ok query=vx_check_occupancy 会检查哪些东西？
- `vortex-v1-L2-016` strict=True ev_recall=1.00 citation=True judge=correct:1.0 tokens=None notes=ok query=vx_check_occupancy 里 group_size 大于 threads_per_core 会直接报错吗？给代码证据。
- `vortex-v1-L1-017` strict=True ev_recall=1.00 citation=True judge=correct:1.0 tokens=None notes=ok query=vx_upload_kernel_file 具体怎么把 kernel file 上传？
- `vortex-v1-L2-018` strict=True ev_recall=1.00 citation=True judge=correct:1.0 tokens=None notes=ok query=vx_upload_kernel_bytes 为啥把 binary 和 bss/global 区域权限分开？
- `vortex-v1-L1-019` strict=True ev_recall=1.00 citation=True judge=correct:1.0 tokens=None notes=ok query=vx_dump_perf 里会读哪些 capability 再决定 perf 输出？
- `vortex-v1-L2-020` strict=True ev_recall=1.00 citation=True judge=correct:1.0 tokens=None notes=ok query=要看到 PERF: instrs/cycles 这种输出，blackbox 参数和代码依据是什么？
- `vortex-v1-L1-021` strict=True ev_recall=1.00 citation=True judge=correct:1.0 tokens=None notes=ok query=simx 直接跑 -d/-p/-V 时，main.cpp 做了什么？
- `vortex-v1-L2-022` strict=False ev_recall=1.00 citation=True judge=partial:0.75 tokens=None notes=llm judge did not mark answer correct query=用 GDB 调 Vortex fibonacci，XLEN 和端口要注意什么？
- `vortex-v1-L2-023` strict=True ev_recall=1.00 citation=True judge=correct:1.0 tokens=None notes=ok query=debug_mode.md 有没有明确说 XLEN 不一致会失败？
- `vortex-v1-L2-024` strict=True ev_recall=1.00 citation=True judge=correct:1.0 tokens=None notes=ok query=sim/simx/main.cpp 在 debug_mode 下没有 program 也不会直接 usage exit 吗？
- `vortex-v1-L2-025` strict=True ev_recall=1.00 citation=True judge=correct:1.0 tokens=None notes=ok query=docs/software.md 能说明 OpenCL API 的具体调用流程吗？
- `vortex-v1-L2-026` strict=True ev_recall=1.00 citation=True judge=correct:1.0 tokens=None notes=ok query=README 的 driver 目录能直接定位 opae/xrt 源码吗？还是要看 codebase.md？
- `vortex-v1-L3-027` strict=True ev_recall=1.00 citation=True judge=correct:1.0 tokens=None notes=ok query=我刚进 Vortex 仓库，要找 RTL、runtime、sim、tests 和文档入口，哪些文件先看？
- `vortex-v1-L1-028` strict=True ev_recall=1.00 citation=True judge=correct:1.0 tokens=None notes=ok query=VX_config.h 是哪个 Makefile 目标生成的？
- `vortex-v1-L2-029` strict=True ev_recall=1.00 citation=True judge=correct:1.0 tokens=None notes=ok query=blackbox 跑 simx/rtlsim 前一定会先 make hw config 和 runtime/stub 吗？
- `vortex-v1-L2-030` strict=True ev_recall=1.00 citation=True judge=correct:1.0 tokens=None notes=ok query=docs/debugging.md 提到 --rebuild=1，当前 ci/blackbox.sh 真的解析 --rebuild 吗？
- `vortex-v1-L1-031` strict=True ev_recall=1.00 citation=True judge=correct:1.0 tokens=None notes=ok query=README 里支持哪些 OS 和预构建 toolchain 依赖？
- `vortex-v1-L1-032` strict=False ev_recall=1.00 citation=True judge=partial:0.67 tokens=None notes=llm judge did not mark answer correct query=install_vortex.md 里 Ubuntu 和 RHEL 的依赖有什么不同？
- `vortex-v1-L2-033` strict=True ev_recall=1.00 citation=True judge=correct:1.0 tokens=None notes=ok query=Vortex 说支持 OpenCL 1.2，测试里真有 OpenCL API 示例吗？
- `vortex-v1-L1-034` strict=True ev_recall=1.00 citation=True judge=correct:1.0 tokens=None notes=ok query=vecadd 的 OpenCL host 代码实际流程是什么？
- `vortex-v1-L2-035` strict=True ev_recall=1.00 citation=True judge=correct:1.0 tokens=None notes=ok query=simulation.md 的输出流程和 tests/opencl/vecadd/main.cc 对得上吗？
- `vortex-v1-L1-036` strict=True ev_recall=1.00 citation=True judge=correct:1.0 tokens=None notes=ok query=kernel/vecadd 的 hostless 版本是怎么 spawn 线程的？
- `vortex-v1-L2-037` strict=True ev_recall=1.00 citation=True judge=correct:1.0 tokens=None notes=ok query=tests/kernel/vecadd 里面是不是说 vx_spawn_threads 未来会被 vx_start 替换？
- `vortex-v1-L1-038` strict=True ev_recall=1.00 citation=True judge=correct:1.0 tokens=None notes=ok query=Vortex 的 SIMT warp/thread 模型文档怎么说？
- `vortex-v1-L1-039` strict=True ev_recall=1.00 citation=True judge=correct:1.0 tokens=None notes=ok query=Vortex pipeline 有哪 6 个 stage？
- `vortex-v1-L1-040` strict=True ev_recall=1.00 citation=True judge=correct:1.0 tokens=None notes=ok query=文档里的 WSPAWN/BAR 这些扩展分别管什么？
- `vortex-v1-L3-041` strict=True ev_recall=1.00 citation=True judge=correct:1.0 tokens=None notes=ok query=文档说 socket/cluster 共享 cache，RTL 层级怎么落到 VX_cluster/VX_socket/VX_core？
- `vortex-v1-L2-042` strict=True ev_recall=1.00 citation=True judge=correct:1.0 tokens=None notes=ok query=cache 文档里 MSHR deadlock 是怎么解释的，RTL 参数里 MSHR/MREQ 对应在哪？
- `vortex-v1-L2-043` strict=True ev_recall=1.00 citation=True judge=correct:1.0 tokens=None notes=ok query=VX_socket 里 icache 和 dcache 都允许写吗？给行号。
- `vortex-v1-L2-044` strict=True ev_recall=1.00 citation=True judge=correct:1.0 tokens=None notes=ok query=L3 和 L2 cache_wrap 的 PASSTHRU 条件分别是什么？
- `vortex-v1-L2-045` strict=True ev_recall=1.00 citation=True judge=correct:1.0 tokens=None notes=ok query=VX_cache_cluster 怎么把多个输入/多个 cache unit 仲裁到 mem bus？
- `vortex-v1-L2-046` strict=True ev_recall=1.00 citation=True judge=correct:1.0 tokens=None notes=ok query=run.log 太大时官方建议怎么比较 rtlsim 和 simx trace？
- `vortex-v1-L2-047` strict=True ev_recall=1.00 citation=True judge=correct:1.0 tokens=None notes=ok query=rtlsim debug 默认就 full trace 所有 libs 吗？
- `vortex-v1-L2-048` strict=True ev_recall=1.00 citation=True judge=correct:1.0 tokens=None notes=ok query=FPGA scope 要怎么开，文档和 blackbox 对文件名的证据分别是什么？
- `vortex-v1-L3-049` strict=True ev_recall=1.00 citation=True judge=correct:1.0 tokens=None notes=ok query=仅凭 simulation.md 能断言所有 opencl benchmark 都能跑吗？
- `vortex-v1-L3-050` strict=False ev_recall=1.00 citation=False judge=correct:1.0 tokens=None notes=citation policy not satisfied query=我怀疑 simx 和 RTL 行为不一致，最短证据链应该查哪些文件？
