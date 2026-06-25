# Method Evaluation Report

## Summary

- Cases: 100
- Strict E2E pass rate: 0.000
- Retrieval pass rate: 1.000
- Evidence recall@10: 1.000
- Evidence precision@10: 1.000
- Citation pass rate: 0.580
- LLM Judge coverage: 0.000
- Mean LLM Judge score: 0.000
- LLM Judge verdicts: {'not_run': 100}
- Token usage coverage: 1.000
- Mean total tokens: 34151.4
- Sum total tokens: 3415143

## Slice Summary

### layer
- `L1`: cases=20 strict=0.000 retrieval=1.000 ev_recall=1.000 judge=0.000 tokens=33983.1
- `L2`: cases=40 strict=0.000 retrieval=1.000 ev_recall=1.000 judge=0.000 tokens=34256.2
- `L3`: cases=40 strict=0.000 retrieval=1.000 ev_recall=1.000 judge=0.000 tokens=34130.9

### capability
- `build_simulation_flow`: cases=10 strict=0.000 retrieval=1.000 ev_recall=1.000 judge=0.000 tokens=34150.1
- `doc_code_cross_check`: cases=18 strict=0.000 retrieval=1.000 ev_recall=1.000 judge=0.000 tokens=34180.8
- `mechanism_trace`: cases=19 strict=0.000 retrieval=1.000 ev_recall=1.000 judge=0.000 tokens=34179.5
- `negative_insufficient_evidence`: cases=17 strict=0.000 retrieval=1.000 ev_recall=1.000 judge=0.000 tokens=34084.7
- `repo_structure_location`: cases=18 strict=0.000 retrieval=1.000 ev_recall=1.000 judge=0.000 tokens=34090.8
- `tests_debug_evidence`: cases=18 strict=0.000 retrieval=1.000 ev_recall=1.000 judge=0.000 tokens=34216.8

### answer_type
- `fact_check`: cases=18 strict=0.000 retrieval=1.000 ev_recall=1.000 judge=0.000 tokens=34315.8
- `location`: cases=19 strict=0.000 retrieval=1.000 ev_recall=1.000 judge=0.000 tokens=34056.8
- `mechanism`: cases=17 strict=0.000 retrieval=1.000 ev_recall=1.000 judge=0.000 tokens=34184.6
- `negative`: cases=4 strict=0.000 retrieval=1.000 ev_recall=1.000 judge=0.000 tokens=34261.5
- `procedure`: cases=21 strict=0.000 retrieval=1.000 ev_recall=1.000 judge=0.000 tokens=34173.9
- `synthesis`: cases=21 strict=0.000 retrieval=1.000 ev_recall=1.000 judge=0.000 tokens=34025.8

## Per Case

- `vortex-v1_2-L1-031` strict=False ev_recall=1.00 citation=True judge=not_run:None tokens=34400 notes=llm judge not available query=Where is the AFU control module defined in the hardware tree?
- `vortex-v1_2-L1-032` strict=False ev_recall=1.00 citation=True judge=not_run:None tokens=33902 notes=llm judge not available query=What kind of module is the AFU wrapper in the hardware tree?
- `vortex-v1_2-L1-033` strict=False ev_recall=1.00 citation=True judge=not_run:None tokens=34316 notes=llm judge not available query=Where is the top-level AFU module defined in the hardware tree?
- `vortex-v1_2-L1-034` strict=False ev_recall=1.00 citation=True judge=not_run:None tokens=33963 notes=llm judge not available query=How is the AFU header meant to be used by the RTL modules?
- `vortex-v1_2-L1-035` strict=False ev_recall=1.00 citation=True judge=not_run:None tokens=34262 notes=llm judge not available query=What mechanism is this behavior using?
- `vortex-v1_2-L1-036` strict=False ev_recall=1.00 citation=True judge=not_run:None tokens=33797 notes=llm judge not available query=What overall behavior is established here?
- `vortex-v1_2-L1-037` strict=False ev_recall=1.00 citation=True judge=not_run:None tokens=33924 notes=llm judge not available query=Which part of the implementation does this behavior belong to?
- `vortex-v1_2-L1-038` strict=False ev_recall=1.00 citation=True judge=not_run:None tokens=33911 notes=llm judge not available query=What sequence does this behavior follow?
- `vortex-v1_2-L1-039` strict=False ev_recall=1.00 citation=True judge=not_run:None tokens=34022 notes=llm judge not available query=What mechanism is this behavior using?
- `vortex-v1_2-L1-040` strict=False ev_recall=1.00 citation=True judge=not_run:None tokens=33911 notes=llm judge not available query=What overall behavior is established here?
- `vortex-v1_2-L1-041` strict=False ev_recall=1.00 citation=True judge=not_run:None tokens=33985 notes=llm judge not available query=Which part of the implementation does this behavior belong to?
- `vortex-v1_2-L1-042` strict=False ev_recall=1.00 citation=True judge=not_run:None tokens=33954 notes=llm judge not available query=What sequence does this behavior follow?
- `vortex-v1_2-L1-043` strict=False ev_recall=1.00 citation=True judge=not_run:None tokens=34047 notes=llm judge not available query=What mechanism is this behavior using?
- `vortex-v1_2-L1-044` strict=False ev_recall=1.00 citation=True judge=not_run:None tokens=33798 notes=llm judge not available query=What is the cache replacement module used for?
- `vortex-v1_2-L1-045` strict=False ev_recall=1.00 citation=True judge=not_run:None tokens=33870 notes=llm judge not available query=Which part of the implementation does this behavior belong to?
- `vortex-v1_2-L1-046` strict=False ev_recall=1.00 citation=True judge=not_run:None tokens=33897 notes=llm judge not available query=What sequence does this behavior follow?
- `vortex-v1_2-L1-047` strict=False ev_recall=1.00 citation=True judge=not_run:None tokens=34021 notes=llm judge not available query=Where is the cache wrapper module located?
- `vortex-v1_2-L1-048` strict=False ev_recall=1.00 citation=True judge=not_run:None tokens=33832 notes=llm judge not available query=Where is the integer ALU module defined?
- `vortex-v1_2-L1-049` strict=False ev_recall=1.00 citation=True judge=not_run:None tokens=33842 notes=llm judge not available query=Where is the multiply/divide ALU module located?
- `vortex-v1_2-L1-050` strict=False ev_recall=1.00 citation=True judge=not_run:None tokens=34008 notes=llm judge not available query=What sequence does this behavior follow?
- `vortex-v1_2-L2-052` strict=False ev_recall=1.00 citation=False judge=not_run:None tokens=34140 notes=citation policy not satisfied; llm judge not available query=How does the opcode unit handle bank selection when the design is banked?
- `vortex-v1_2-L2-053` strict=False ev_recall=1.00 citation=False judge=not_run:None tokens=34308 notes=citation policy not satisfied; llm judge not available query=When the relevant guard condition is true, what happens next?
- `vortex-v1_2-L2-054` strict=False ev_recall=1.00 citation=True judge=not_run:None tokens=34383 notes=llm judge not available query=What sequence does this behavior follow?
- `vortex-v1_2-L2-055` strict=False ev_recall=1.00 citation=False judge=not_run:None tokens=34133 notes=citation policy not satisfied; llm judge not available query=How does the scheduler update warp state?
- `vortex-v1_2-L2-056` strict=False ev_recall=1.00 citation=False judge=not_run:None tokens=34118 notes=citation policy not satisfied; llm judge not available query=When the relevant guard condition is true, what happens next?
- `vortex-v1_2-L2-058` strict=False ev_recall=1.00 citation=True judge=not_run:None tokens=34272 notes=llm judge not available query=What role does the scheduler module play in the core tree?
- `vortex-v1_2-L2-059` strict=False ev_recall=1.00 citation=False judge=not_run:None tokens=34408 notes=citation policy not satisfied; llm judge not available query=When the relevant guard condition is true, what happens next?
- `vortex-v1_2-L2-060` strict=False ev_recall=1.00 citation=False judge=not_run:None tokens=33984 notes=citation policy not satisfied; llm judge not available query=When the relevant guard condition is true, what happens next?
- `vortex-v1_2-L2-061` strict=False ev_recall=1.00 citation=False judge=not_run:None tokens=34177 notes=citation policy not satisfied; llm judge not available query=How does the write-control unit handle the last-lane selection logic?
- `vortex-v1_2-L2-062` strict=False ev_recall=1.00 citation=True judge=not_run:None tokens=34636 notes=llm judge not available query=What sequence does this behavior follow?
- `vortex-v1_2-L2-063` strict=False ev_recall=1.00 citation=False judge=not_run:None tokens=34239 notes=citation policy not satisfied; llm judge not available query=How does the multiply/divide ALU handle word-sized multiplies?
- `vortex-v1_2-L2-064` strict=False ev_recall=1.00 citation=True judge=not_run:None tokens=34139 notes=llm judge not available query=What overall behavior is established here?
- `vortex-v1_2-L2-065` strict=False ev_recall=1.00 citation=False judge=not_run:None tokens=33720 notes=citation policy not satisfied; llm judge not available query=When the relevant guard condition is true, what happens next?
- `vortex-v1_2-L2-066` strict=False ev_recall=1.00 citation=True judge=not_run:None tokens=33876 notes=llm judge not available query=What sequence does this behavior follow?
- `vortex-v1_2-L2-067` strict=False ev_recall=1.00 citation=True judge=not_run:None tokens=33810 notes=llm judge not available query=What mechanism is this behavior using?
- `vortex-v1_2-L2-068` strict=False ev_recall=1.00 citation=True judge=not_run:None tokens=34521 notes=llm judge not available query=How does the shared FPU utility build its output across lanes, and what does that suggest about the surrounding FPU support?
- `vortex-v1_2-L2-069` strict=False ev_recall=1.00 citation=True judge=not_run:None tokens=34121 notes=llm judge not available query=Which part of the implementation does this behavior belong to?
- `vortex-v1_2-L2-070` strict=False ev_recall=1.00 citation=True judge=not_run:None tokens=34531 notes=llm judge not available query=How is the FPU conversion unit configured through the shared FPU headers?
- `vortex-v1_2-L2-071` strict=False ev_recall=1.00 citation=True judge=not_run:None tokens=34287 notes=llm judge not available query=I suspect this behavior is not actually implemented. Is that right?
- `vortex-v1_2-L2-072` strict=False ev_recall=1.00 citation=False judge=not_run:None tokens=34287 notes=citation policy not satisfied; llm judge not available query=Does the FMA unit always take the same path for every operation?
- `vortex-v1_2-L2-073` strict=False ev_recall=1.00 citation=False judge=not_run:None tokens=34399 notes=citation policy not satisfied; llm judge not available query=I suspect this behavior is not actually implemented. Is that right?
- `vortex-v1_2-L2-074` strict=False ev_recall=1.00 citation=True judge=not_run:None tokens=34344 notes=llm judge not available query=I suspect this behavior is not actually implemented. Is that right?
- `vortex-v1_2-L2-076` strict=False ev_recall=1.00 citation=True judge=not_run:None tokens=34297 notes=llm judge not available query=I suspect this behavior is not actually implemented. Is that right?
- `vortex-v1_2-L2-077` strict=False ev_recall=1.00 citation=True judge=not_run:None tokens=34203 notes=llm judge not available query=I suspect this behavior is not actually implemented. Is that right?
- `vortex-v1_2-L2-078` strict=False ev_recall=1.00 citation=False judge=not_run:None tokens=34083 notes=citation policy not satisfied; llm judge not available query=How is the IP-dom stack sized relative to warp count?
- `vortex-v1_2-L2-079` strict=False ev_recall=1.00 citation=True judge=not_run:None tokens=34454 notes=llm judge not available query=I suspect this behavior is not actually implemented. Is that right?
- `vortex-v1_2-L2-080` strict=False ev_recall=1.00 citation=True judge=not_run:None tokens=34516 notes=llm judge not available query=I suspect this behavior is not actually implemented. Is that right?
- `vortex-v1_2-L2-081` strict=False ev_recall=1.00 citation=False judge=not_run:None tokens=34157 notes=citation policy not satisfied; llm judge not available query=Where is the decode-to-issue handoff implemented in the core?
- `vortex-v1_2-L2-082` strict=False ev_recall=1.00 citation=True judge=not_run:None tokens=34508 notes=llm judge not available query=I suspect this behavior is not actually implemented. Is that right?
- `vortex-v1_2-L2-083` strict=False ev_recall=1.00 citation=True judge=not_run:None tokens=34368 notes=llm judge not available query=I suspect this behavior is not actually implemented. Is that right?
- `vortex-v1_2-L2-084` strict=False ev_recall=1.00 citation=True judge=not_run:None tokens=34228 notes=llm judge not available query=I suspect this behavior is not actually implemented. Is that right?
- `vortex-v1_2-L2-085` strict=False ev_recall=1.00 citation=False judge=not_run:None tokens=34233 notes=citation policy not satisfied; llm judge not available query=Where is the FPU conversion control actually implemented?
- `vortex-v1_2-L2-086` strict=False ev_recall=1.00 citation=True judge=not_run:None tokens=34318 notes=llm judge not available query=I suspect this behavior is not actually implemented. Is that right?
- `vortex-v1_2-L2-088` strict=False ev_recall=1.00 citation=True judge=not_run:None tokens=34568 notes=llm judge not available query=I suspect this behavior is not actually implemented. Is that right?
- `vortex-v1_2-L2-089` strict=False ev_recall=1.00 citation=False judge=not_run:None tokens=34205 notes=citation policy not satisfied; llm judge not available query=How does branch tracking get initialized in the scheduler?
- `vortex-v1_2-L2-090` strict=False ev_recall=1.00 citation=False judge=not_run:None tokens=34229 notes=citation policy not satisfied; llm judge not available query=I suspect this behavior is not actually implemented. Is that right?
- `vortex-v1_2-L2-091` strict=False ev_recall=1.00 citation=True judge=not_run:None tokens=34231 notes=llm judge not available query=Does this snippet fully define the FPU result interface behavior?
- `vortex-v1_2-L2-092` strict=False ev_recall=1.00 citation=True judge=not_run:None tokens=34278 notes=llm judge not available query=The evidence seems to point in more than one direction; what can we confirm, and what remains unresolved?
- `vortex-v1_2-L2-094` strict=False ev_recall=1.00 citation=True judge=not_run:None tokens=34256 notes=llm judge not available query=The evidence seems to point in more than one direction; what can we confirm, and what remains unresolved?
- `vortex-v1_2-L2-095` strict=False ev_recall=1.00 citation=True judge=not_run:None tokens=34281 notes=llm judge not available query=The evidence seems to point in more than one direction; what can we confirm, and what remains unresolved?
- `vortex-v1_2-L3-141` strict=False ev_recall=1.00 citation=False judge=not_run:None tokens=34282 notes=citation policy not satisfied; llm judge not available query=Which part of the implementation does this behavior belong to?
- `vortex-v1_2-L3-142` strict=False ev_recall=1.00 citation=False judge=not_run:None tokens=34396 notes=citation policy not satisfied; llm judge not available query=What sequence does this behavior follow?
- `vortex-v1_2-L3-143` strict=False ev_recall=1.00 citation=False judge=not_run:None tokens=34314 notes=citation policy not satisfied; llm judge not available query=When the relevant guard condition is true, what happens next?
- `vortex-v1_2-L3-144` strict=False ev_recall=1.00 citation=False judge=not_run:None tokens=34118 notes=citation policy not satisfied; llm judge not available query=How does the serial divider handle reset?
- `vortex-v1_2-L3-145` strict=False ev_recall=1.00 citation=False judge=not_run:None tokens=33998 notes=citation policy not satisfied; llm judge not available query=Where is the reset behavior for the serial multiplier?
- `vortex-v1_2-L3-146` strict=False ev_recall=1.00 citation=False judge=not_run:None tokens=34396 notes=citation policy not satisfied; llm judge not available query=What sequence does this behavior follow?
- `vortex-v1_2-L3-148` strict=False ev_recall=1.00 citation=False judge=not_run:None tokens=34090 notes=citation policy not satisfied; llm judge not available query=When the relevant guard condition is true, what happens next?
- `vortex-v1_2-L3-149` strict=False ev_recall=1.00 citation=False judge=not_run:None tokens=34060 notes=citation policy not satisfied; llm judge not available query=Where does the stream arbiter handle the case with more inputs than outputs?
- `vortex-v1_2-L3-150` strict=False ev_recall=1.00 citation=True judge=not_run:None tokens=34156 notes=llm judge not available query=What sequence does this behavior follow?
- `vortex-v1_2-L3-151` strict=False ev_recall=1.00 citation=False judge=not_run:None tokens=34225 notes=citation policy not satisfied; llm judge not available query=When the relevant guard condition is true, what happens next?
- `vortex-v1_2-L3-152` strict=False ev_recall=1.00 citation=False judge=not_run:None tokens=34184 notes=citation policy not satisfied; llm judge not available query=When the relevant guard condition is true, what happens next?
- `vortex-v1_2-L3-153` strict=False ev_recall=1.00 citation=True judge=not_run:None tokens=34225 notes=llm judge not available query=Which part of the implementation does this behavior belong to?
- `vortex-v1_2-L3-154` strict=False ev_recall=1.00 citation=True judge=not_run:None tokens=34305 notes=llm judge not available query=What sequence does this behavior follow?
- `vortex-v1_2-L3-155` strict=False ev_recall=1.00 citation=False judge=not_run:None tokens=34153 notes=citation policy not satisfied; llm judge not available query=How does the stream crossbar handle nontrivial sizes?
- `vortex-v1_2-L3-156` strict=False ev_recall=1.00 citation=False judge=not_run:None tokens=34166 notes=citation policy not satisfied; llm judge not available query=When the relevant guard condition is true, what happens next?
- `vortex-v1_2-L3-157` strict=False ev_recall=1.00 citation=False judge=not_run:None tokens=34074 notes=citation policy not satisfied; llm judge not available query=When the relevant guard condition is true, what happens next?
- `vortex-v1_2-L3-158` strict=False ev_recall=1.00 citation=True judge=not_run:None tokens=34230 notes=llm judge not available query=How should I think about the stream crossbar file?
- `vortex-v1_2-L3-159` strict=False ev_recall=1.00 citation=True judge=not_run:None tokens=34164 notes=llm judge not available query=What mechanism is this behavior using?
- `vortex-v1_2-L3-160` strict=False ev_recall=1.00 citation=False judge=not_run:None tokens=34093 notes=citation policy not satisfied; llm judge not available query=How does the gbar arbiter behave on reset?
- `vortex-v1_2-L3-161` strict=False ev_recall=1.00 citation=True judge=not_run:None tokens=34277 notes=llm judge not available query=Which part of the implementation does this behavior belong to?
- `vortex-v1_2-L3-162` strict=False ev_recall=1.00 citation=True judge=not_run:None tokens=33969 notes=llm judge not available query=What sequence does this behavior follow?
- `vortex-v1_2-L3-163` strict=False ev_recall=1.00 citation=False judge=not_run:None tokens=33820 notes=citation policy not satisfied; llm judge not available query=What mechanism is this behavior using?
- `vortex-v1_2-L3-164` strict=False ev_recall=1.00 citation=False judge=not_run:None tokens=33728 notes=citation policy not satisfied; llm judge not available query=When does local memory compute request bank indices?
- `vortex-v1_2-L3-166` strict=False ev_recall=1.00 citation=True judge=not_run:None tokens=34080 notes=llm judge not available query=What sequence does this behavior follow?
- `vortex-v1_2-L3-167` strict=False ev_recall=1.00 citation=True judge=not_run:None tokens=34682 notes=llm judge not available query=How does the request-tag selector output behave when there are more inputs than outputs?
- `vortex-v1_2-L3-168` strict=False ev_recall=1.00 citation=False judge=not_run:None tokens=33856 notes=citation policy not satisfied; llm judge not available query=How is the population count result assembled in this design?
- `vortex-v1_2-L3-169` strict=False ev_recall=1.00 citation=False judge=not_run:None tokens=33625 notes=citation policy not satisfied; llm judge not available query=Where is the request-tag output selection handled when there are more inputs than outputs?
- `vortex-v1_2-L3-170` strict=False ev_recall=1.00 citation=True judge=not_run:None tokens=34084 notes=llm judge not available query=How do you integrate the LSU memory arbiter into the build flow?
- `vortex-v1_2-L3-172` strict=False ev_recall=1.00 citation=False judge=not_run:None tokens=33576 notes=citation policy not satisfied; llm judge not available query=How does the fused multiply path choose between fp16 and bf16 results?
- `vortex-v1_2-L3-173` strict=False ev_recall=1.00 citation=False judge=not_run:None tokens=34121 notes=citation policy not satisfied; llm judge not available query=Where is the format-specific branch for the fused DP DPI path?
- `vortex-v1_2-L3-174` strict=False ev_recall=1.00 citation=True judge=not_run:None tokens=34244 notes=llm judge not available query=How do you set up the memory switch module for use?
- `vortex-v1_2-L3-175` strict=False ev_recall=1.00 citation=False judge=not_run:None tokens=34192 notes=citation policy not satisfied; llm judge not available query=How does the integer fused multiply path start computing products?
- `vortex-v1_2-L3-176` strict=False ev_recall=1.00 citation=False judge=not_run:None tokens=34096 notes=citation policy not satisfied; llm judge not available query=How is the fused DP delay pipe reset?
- `vortex-v1_2-L3-177` strict=False ev_recall=1.00 citation=False judge=not_run:None tokens=34105 notes=citation policy not satisfied; llm judge not available query=Where is the serial divider logic implemented?
- `vortex-v1_2-L3-178` strict=False ev_recall=1.00 citation=False judge=not_run:None tokens=34174 notes=citation policy not satisfied; llm judge not available query=How do you use the TCU integer module in the design?
- `vortex-v1_2-L3-179` strict=False ev_recall=1.00 citation=True judge=not_run:None tokens=34247 notes=llm judge not available query=What mechanism is this behavior using?
- `vortex-v1_2-L3-180` strict=False ev_recall=1.00 citation=True judge=not_run:None tokens=34278 notes=llm judge not available query=What overall behavior is established here?
- `vortex-v1_2-L3-181` strict=False ev_recall=1.00 citation=False judge=not_run:None tokens=34050 notes=citation policy not satisfied; llm judge not available query=Where is the conditional index selection handled?
- `vortex-v1_2-L3-182` strict=False ev_recall=1.00 citation=True judge=not_run:None tokens=34187 notes=llm judge not available query=What sequence does this behavior follow?
- `vortex-v1_2-L3-184` strict=False ev_recall=1.00 citation=False judge=not_run:None tokens=34215 notes=citation policy not satisfied; llm judge not available query=How does the BF16 fused multiply helper handle recursive inputs?
