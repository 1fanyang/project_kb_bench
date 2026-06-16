# Method Evaluation Report

## Summary

- Cases: 50
- Strict E2E pass rate: 0.820
- Retrieval pass rate: 0.980
- Evidence recall@5: 0.980
- Evidence precision@5: 0.515
- Citation pass rate: 0.960
- LLM Judge coverage: 1.000
- Mean LLM Judge score: 0.940
- LLM Judge verdicts: {'correct': 41, 'partial': 9}

## Slice Summary

### layer
- `L1`: cases=19 strict=0.789 retrieval=0.947 ev_recall=0.947 judge=0.923
- `L2`: cases=24 strict=0.833 retrieval=1.000 ev_recall=1.000 judge=0.939
- `L3`: cases=7 strict=0.857 retrieval=1.000 ev_recall=1.000 judge=0.986

### capability
- `build_sim_verif_flow`: cases=3 strict=1.000 retrieval=1.000 ev_recall=1.000 judge=1.000
- `doc_code_cross_check`: cases=6 strict=0.667 retrieval=1.000 ev_recall=1.000 judge=0.895
- `mechanism_trace`: cases=18 strict=0.889 retrieval=1.000 ev_recall=1.000 judge=0.976
- `repo_structure_location`: cases=1 strict=1.000 retrieval=1.000 ev_recall=1.000 judge=1.000
- `rtl_symbol_location`: cases=2 strict=0.500 retrieval=1.000 ev_recall=1.000 judge=0.850
- `software_stack_path`: cases=20 strict=0.800 retrieval=0.950 ev_recall=0.950 judge=0.917

### answer_type
- `comparison`: cases=3 strict=0.667 retrieval=1.000 ev_recall=1.000 judge=0.833
- `fact_check`: cases=12 strict=0.833 retrieval=1.000 ev_recall=1.000 judge=0.931
- `location`: cases=2 strict=0.500 retrieval=1.000 ev_recall=1.000 judge=0.850
- `mechanism`: cases=13 strict=0.769 retrieval=1.000 ev_recall=1.000 judge=0.944
- `procedure`: cases=5 strict=1.000 retrieval=1.000 ev_recall=1.000 judge=1.000
- `synthesis`: cases=3 strict=0.667 retrieval=0.667 ev_recall=0.667 judge=0.890
- `yes_no`: cases=12 strict=0.917 retrieval=1.000 ev_recall=1.000 judge=0.973

## Per Case

- `nvdla-v1-L1-001` strict=False ev_recall=1.00 citation=True judge=partial:0.67 notes=llm judge did not mark answer correct query=NVDLA hw README 里说 nvdlav1 这个 release 是什么版本？给我行号。
- `nvdla-v1-L1-002` strict=True ev_recall=1.00 citation=True judge=correct:1.0 notes=ok query=我想快速知道 nvdla/hw 这个仓库里 vmod、syn、verif、tools 分别放什么，README 有说吗？
- `nvdla-v1-L1-003` strict=True ev_recall=1.00 citation=True judge=correct:1.0 notes=ok query=NVDLA hardware 最基础的 build/sanity simulation 命令是什么？README 里找一下。
- `nvdla-v1-L1-004` strict=True ev_recall=1.00 citation=True judge=correct:1.0 notes=ok query=NVDLA SW README 说 KMD 是不是 Linux out-of-tree module？还有 DMA buffer 用什么机制？
- `nvdla-v1-L1-005` strict=False ev_recall=0.00 citation=False judge=partial:0.67 notes=gold evidence not fully retrieved; citation policy not satisfied; llm judge did not mark answer correct query=NVDLA SW 里的 UMD 到底负责什么？是不是直接把 loadable 交给 KMD？
- `nvdla-v1-L1-006` strict=True ev_recall=1.00 citation=True judge=correct:1.0 notes=ok query=runtime_environment.rst 里 runtime environment 分成哪两块？
- `nvdla-v1-L2-007` strict=False ev_recall=1.00 citation=True judge=partial:0.7 notes=llm judge did not mark answer correct query=NVDLA Loadable 里的 dependency graph 是给谁用来调度 layer 的？runtime_environment.rst 里怎么说？
- `nvdla-v1-L1-008` strict=True ev_recall=1.00 citation=True judge=correct:1.0 notes=ok query=IRuntime 提交 inference job 的大致步骤有哪些？runtime_environment.rst 那个列表帮我整理下。
- `nvdla-v1-L1-009` strict=True ev_recall=1.00 citation=True judge=correct:1.0 notes=ok query=compilation_tool.rst 说 NVDLA compilation 是几步？Parser 和 Compiler 分别干什么？
- `nvdla-v1-L1-010` strict=False ev_recall=1.00 citation=True judge=partial:0.5 notes=llm judge did not mark answer correct query=NVDLA compiler 的输出是不是标准 NVDLA Loadable？compilation_tool.rst 给证据。
- `nvdla-v1-L1-011` strict=True ev_recall=1.00 citation=True judge=correct:1.0 notes=ok query=test_application.rst 里 nvdla_compiler 怎么用？我只要命令格式和帮助参数。
- `nvdla-v1-L1-012` strict=True ev_recall=1.00 citation=True judge=correct:1.0 notes=ok query=nvdla_runtime 的 test app 支持哪些启动方式？loadable、image、server mode 都看下。
- `nvdla-v1-L2-013` strict=True ev_recall=1.00 citation=True judge=correct:1.0 notes=ok query=hwarch.rst 里 NVDLA 的 command-execute-interrupt flow 是怎么循环的？
- `nvdla-v1-L2-014` strict=True ev_recall=1.00 citation=True judge=correct:1.0 notes=ok query=Independent mode 和 fused mode 在 NVDLA hwarch.rst 里差别是什么？别泛泛说。
- `nvdla-v1-L1-015` strict=True ev_recall=1.00 citation=True judge=correct:1.0 notes=ok query=dla_interface.h 里 DLA_OP_* 一共列了哪些 processor？
- `nvdla-v1-L1-016` strict=True ev_recall=1.00 citation=True judge=correct:1.0 notes=ok query=DLA_NUM_GROUPS 在 dla_interface.h 里是多少？这个值表示什么？
- `nvdla-v1-L1-017` strict=True ev_recall=1.00 citation=True judge=correct:1.0 notes=ok query=NUM_MAX_BDMA_OPS 最大值是多少？BDMA surface desc 怎么用它？
- `nvdla-v1-L2-018` strict=True ev_recall=1.00 citation=True judge=correct:1.0 notes=ok query=bdma.c 里 dla_bdma_enable 遇到 num_transfers=0 还会 launch 硬件吗？请给代码证据。
- `nvdla-v1-L2-019` strict=True ev_recall=1.00 citation=True judge=correct:1.0 notes=ok query=bdma.c 的 dla_bdma_program 如果 num_transfers 是 0，会进入 processor_bdma_program_slot 循环吗？
- `nvdla-v1-L2-020` strict=True ev_recall=1.00 citation=True judge=correct:1.0 notes=ok query=BDMA 的 num_transfers 超过 NUM_MAX_BDMA_OPS 时 bdma.c 会继续编程吗？
- `nvdla-v1-L2-021` strict=False ev_recall=1.00 citation=True judge=partial:0.67 notes=llm judge did not mark answer correct query=processor_bdma_program_slot 对 line_size 有 32B 对齐要求吗？看 bdma.c 证据。
- `nvdla-v1-L2-022` strict=True ev_recall=1.00 citation=True judge=correct:1.0 notes=ok query=BDMA slot 最后是怎么真正 enable 一个 OP 的？bdma.c 里看寄存器写顺序。
- `nvdla-v1-L2-023` strict=True ev_recall=1.00 citation=True judge=correct:1.0 notes=ok query=BDMA 有 shadow register group 吗？dla_bdma_is_ready 为什么可能返回 0？
- `nvdla-v1-L1-024` strict=True ev_recall=1.00 citation=True judge=correct:1.0 notes=ok query=dla_bdma_set_producer 这个函数是不是空实现？注释说为什么？
- `nvdla-v1-L2-025` strict=True ev_recall=1.00 citation=True judge=correct:1.0 notes=ok query=utils_get_free_group 看到 processor->group_status == 0x3 时还能分配 group 吗？
- `nvdla-v1-L2-026` strict=True ev_recall=1.00 citation=True judge=correct:1.0 notes=ok query=utils_get_free_group 在两个 group 都 idle 的时候 group_id/rdma_id 从哪里来？
- `nvdla-v1-L2-027` strict=True ev_recall=1.00 citation=True judge=correct:1.0 notes=ok query=dla_read_input_address 遇到 DLA_MEM_HW 类型还需要 DMA address 吗？
- `nvdla-v1-L3-028` strict=True ev_recall=1.00 citation=True judge=correct:1.0 notes=ok query=dynamic ROI 的 input layer 地址在 dla_read_input_address 里怎么计算？
- `nvdla-v1-L3-029` strict=False ev_recall=1.00 citation=True judge=partial:0.9 notes=llm judge did not mark answer correct query=scheduler.c 里 dependency_count 什么时候触发 enable operation？
- `nvdla-v1-L2-030` strict=True ev_recall=1.00 citation=True judge=correct:1.0 notes=ok query=dla_update_consumers 如果 engine->status 已经非零，还会继续更新 dependency 吗？
- `nvdla-v1-L3-031` strict=True ev_recall=1.00 citation=True judge=correct:1.0 notes=ok query=dla_handle_events 处理 CDMA event 和 OP_COMPLETED 的顺序是什么？
- `nvdla-v1-L2-032` strict=True ev_recall=1.00 citation=True judge=correct:1.0 notes=ok query=dla_process_events 怎么判断 task_complete？是不是看 num_operations 和 num_proc_hwl？
- `nvdla-v1-L2-033` strict=True ev_recall=1.00 citation=True judge=correct:1.0 notes=ok query=dla_execute_task 如果 engine->task->task_data 已经不是 NULL，会接受新 task 吗？
- `nvdla-v1-L3-034` strict=True ev_recall=1.00 citation=True judge=correct:1.0 notes=ok query=engine_isr.c 里 BDMA_DONE_STATUS0/1 分别怎么映射到 group event？
- `nvdla-v1-L2-035` strict=True ev_recall=1.00 citation=True judge=correct:1.0 notes=ok query=dla_isr_handler 处理完 interrupt status 后会清 S_INTR_STATUS 吗？
- `nvdla-v1-L2-036` strict=True ev_recall=1.00 citation=True judge=correct:1.0 notes=ok query=nvdla_submit ioctl 路径里用户传进来的 task 是怎么进入 firmware 的？
- `nvdla-v1-L2-037` strict=True ev_recall=1.00 citation=True judge=correct:1.0 notes=ok query=nvdla_fill_task_desc 只是记录 num_addresses 吗？address_list 怎么处理的？
- `nvdla-v1-L2-038` strict=True ev_recall=1.00 citation=True judge=correct:1.0 notes=ok query=NVDLA GEM create object 会把 size round 到 page 吗？DMA 内存在哪里分配？
- `nvdla-v1-L3-039` strict=True ev_recall=1.00 citation=True judge=correct:1.0 notes=ok query=nvdla_gem_dma_addr 从 PRIME fd 到 dma_addr 的路径是什么？
- `nvdla-v1-L1-040` strict=True ev_recall=1.00 citation=True judge=correct:1.0 notes=ok query=nvdla_gem.c 里 DRM ioctl 暴露了哪些 NVDLA driver 命令？
- `nvdla-v1-L2-041` strict=False ev_recall=1.00 citation=True judge=partial:0.5 notes=llm judge did not mark answer correct query=nvdla_core_callbacks.c 里 os_initial、small、large 三个 config 的 BDMA/Rubik 开关一样吗？
- `nvdla-v1-L2-042` strict=False ev_recall=1.00 citation=True judge=partial:0.67 notes=llm judge did not mark answer correct query=dla_get_dma_address 里的 DESTINATION_PROCESSOR 和 DESTINATION_DMA 走的是同一个读地址函数吗？
- `nvdla-v1-L3-043` strict=True ev_recall=1.00 citation=True judge=correct:1.0 notes=ok query=dla_data_write 和 dla_data_read 在 Linux callbacks 里是不是都通过 dma_buf vmap 后 memcpy？差别是什么？
- `nvdla-v1-L1-044` strict=True ev_recall=1.00 citation=True judge=correct:1.0 notes=ok query=IRuntime.h 里 runtime API 是否包括 load、allocateSystemMemory、bindInputTensor、submit？
- `nvdla-v1-L2-045` strict=True ev_recall=1.00 citation=True judge=correct:1.0 notes=ok query=Runtime::load 对 loadable 里的 submit/task/memory entry 数量有最低要求吗？
- `nvdla-v1-L2-046` strict=True ev_recall=1.00 citation=True judge=correct:1.0 notes=ok query=Runtime::bindInputTensor 绑定 input tensor 时是按什么字段找 memory 的？
- `nvdla-v1-L3-047` strict=True ev_recall=1.00 citation=True judge=correct:1.0 notes=ok query=Runtime::fillTaskAddressList 怎么防止 task address list 越界或空 handle？
- `nvdla-v1-L2-048` strict=True ev_recall=1.00 citation=True judge=correct:1.0 notes=ok query=Runtime::submitInternal 没有成功 load 或没有 task/submit set 时会继续 submit 吗？
- `nvdla-v1-L1-049` strict=False ev_recall=1.00 citation=False judge=partial:0.7 notes=citation policy not satisfied; llm judge did not mark answer correct query=NVDLA 顶层 RTL 模块 NV_nvdla 在哪个文件定义？我还想知道它有没有 DBB/CVSRAM/CSB 这些端口。
- `nvdla-v1-L1-050` strict=True ev_recall=1.00 citation=True judge=correct:1.0 notes=ok query=BDMA 的 RTL 顶层 NV_NVDLA_bdma 在哪？顺手确认下它对外连了 cvif/mcif/csb 和 done interrupt 吗。
