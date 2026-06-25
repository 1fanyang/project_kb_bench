# Method Evaluation Report

## Summary

- Cases: 100
- Strict E2E pass rate: 0.490
- Retrieval pass rate: 1.000
- Evidence recall@10: 1.000
- Evidence precision@10: 1.000
- Citation pass rate: 0.580
- LLM Judge coverage: 1.000
- Mean LLM Judge score: 0.809
- LLM Judge verdicts: {'correct': 66, 'incorrect': 8, 'partial': 26}
- Token usage coverage: 1.000
- Mean total tokens: 34151.4
- Sum total tokens: 3415143

## Slice Summary

### layer
- `L1`: cases=20 strict=0.800 retrieval=1.000 ev_recall=1.000 judge=0.905 tokens=33983.1
- `L2`: cases=40 strict=0.475 retrieval=1.000 ev_recall=1.000 judge=0.820 tokens=34256.2
- `L3`: cases=40 strict=0.350 retrieval=1.000 ev_recall=1.000 judge=0.750 tokens=34130.9

### capability
- `build_simulation_flow`: cases=10 strict=0.600 retrieval=1.000 ev_recall=1.000 judge=0.867 tokens=34150.1
- `doc_code_cross_check`: cases=18 strict=0.611 retrieval=1.000 ev_recall=1.000 judge=0.828 tokens=34180.8
- `mechanism_trace`: cases=19 strict=0.526 retrieval=1.000 ev_recall=1.000 judge=0.809 tokens=34179.5
- `negative_insufficient_evidence`: cases=17 strict=0.412 retrieval=1.000 ev_recall=1.000 judge=0.796 tokens=34084.7
- `repo_structure_location`: cases=18 strict=0.278 retrieval=1.000 ev_recall=1.000 judge=0.730 tokens=34090.8
- `tests_debug_evidence`: cases=18 strict=0.556 retrieval=1.000 ev_recall=1.000 judge=0.848 tokens=34216.8

### answer_type
- `fact_check`: cases=18 strict=0.389 retrieval=1.000 ev_recall=1.000 judge=0.806 tokens=34315.8
- `location`: cases=19 strict=0.421 retrieval=1.000 ev_recall=1.000 judge=0.786 tokens=34056.8
- `mechanism`: cases=17 strict=0.471 retrieval=1.000 ev_recall=1.000 judge=0.773 tokens=34184.6
- `negative`: cases=4 strict=1.000 retrieval=1.000 ev_recall=1.000 judge=1.000 tokens=34261.5
- `procedure`: cases=21 strict=0.762 retrieval=1.000 ev_recall=1.000 judge=0.862 tokens=34173.9
- `synthesis`: cases=21 strict=0.286 retrieval=1.000 ev_recall=1.000 judge=0.772 tokens=34025.8

## Per Case

- `vortex-v1_2-L1-031` strict=False ev_recall=1.00 citation=True judge=partial:0.2 tokens=34400 notes=llm judge did not mark answer correct query=Where is the AFU control module defined in the hardware tree?
- `vortex-v1_2-L1-032` strict=True ev_recall=1.00 citation=True judge=correct:1.0 tokens=33902 notes=ok query=What kind of module is the AFU wrapper in the hardware tree?
- `vortex-v1_2-L1-033` strict=True ev_recall=1.00 citation=True judge=correct:1.0 tokens=34316 notes=ok query=Where is the top-level AFU module defined in the hardware tree?
- `vortex-v1_2-L1-034` strict=True ev_recall=1.00 citation=True judge=correct:1.0 tokens=33963 notes=ok query=How is the AFU header meant to be used by the RTL modules?
- `vortex-v1_2-L1-035` strict=True ev_recall=1.00 citation=True judge=correct:1.0 tokens=34262 notes=ok query=What mechanism is this behavior using?
- `vortex-v1_2-L1-036` strict=True ev_recall=1.00 citation=True judge=correct:1.0 tokens=33797 notes=ok query=What overall behavior is established here?
- `vortex-v1_2-L1-037` strict=True ev_recall=1.00 citation=True judge=correct:1.0 tokens=33924 notes=ok query=Which part of the implementation does this behavior belong to?
- `vortex-v1_2-L1-038` strict=True ev_recall=1.00 citation=True judge=correct:1.0 tokens=33911 notes=ok query=What sequence does this behavior follow?
- `vortex-v1_2-L1-039` strict=True ev_recall=1.00 citation=True judge=correct:1.0 tokens=34022 notes=ok query=What mechanism is this behavior using?
- `vortex-v1_2-L1-040` strict=False ev_recall=1.00 citation=True judge=partial:0.7 tokens=33911 notes=llm judge did not mark answer correct query=What overall behavior is established here?
- `vortex-v1_2-L1-041` strict=True ev_recall=1.00 citation=True judge=correct:1.0 tokens=33985 notes=ok query=Which part of the implementation does this behavior belong to?
- `vortex-v1_2-L1-042` strict=False ev_recall=1.00 citation=True judge=partial:0.7 tokens=33954 notes=llm judge did not mark answer correct query=What sequence does this behavior follow?
- `vortex-v1_2-L1-043` strict=True ev_recall=1.00 citation=True judge=correct:1.0 tokens=34047 notes=ok query=What mechanism is this behavior using?
- `vortex-v1_2-L1-044` strict=True ev_recall=1.00 citation=True judge=correct:1.0 tokens=33798 notes=ok query=What is the cache replacement module used for?
- `vortex-v1_2-L1-045` strict=True ev_recall=1.00 citation=True judge=correct:1.0 tokens=33870 notes=ok query=Which part of the implementation does this behavior belong to?
- `vortex-v1_2-L1-046` strict=True ev_recall=1.00 citation=True judge=correct:1.0 tokens=33897 notes=ok query=What sequence does this behavior follow?
- `vortex-v1_2-L1-047` strict=True ev_recall=1.00 citation=True judge=correct:1.0 tokens=34021 notes=ok query=Where is the cache wrapper module located?
- `vortex-v1_2-L1-048` strict=False ev_recall=1.00 citation=True judge=partial:0.5 tokens=33832 notes=llm judge did not mark answer correct query=Where is the integer ALU module defined?
- `vortex-v1_2-L1-049` strict=True ev_recall=1.00 citation=True judge=correct:1.0 tokens=33842 notes=ok query=Where is the multiply/divide ALU module located?
- `vortex-v1_2-L1-050` strict=True ev_recall=1.00 citation=True judge=correct:1.0 tokens=34008 notes=ok query=What sequence does this behavior follow?
- `vortex-v1_2-L2-052` strict=False ev_recall=1.00 citation=False judge=correct:1.0 tokens=34140 notes=citation policy not satisfied query=How does the opcode unit handle bank selection when the design is banked?
- `vortex-v1_2-L2-053` strict=False ev_recall=1.00 citation=False judge=correct:1.0 tokens=34308 notes=citation policy not satisfied query=When the relevant guard condition is true, what happens next?
- `vortex-v1_2-L2-054` strict=True ev_recall=1.00 citation=True judge=correct:1.0 tokens=34383 notes=ok query=What sequence does this behavior follow?
- `vortex-v1_2-L2-055` strict=False ev_recall=1.00 citation=False judge=correct:1.0 tokens=34133 notes=citation policy not satisfied query=How does the scheduler update warp state?
- `vortex-v1_2-L2-056` strict=False ev_recall=1.00 citation=False judge=correct:1.0 tokens=34118 notes=citation policy not satisfied query=When the relevant guard condition is true, what happens next?
- `vortex-v1_2-L2-058` strict=True ev_recall=1.00 citation=True judge=correct:1.0 tokens=34272 notes=ok query=What role does the scheduler module play in the core tree?
- `vortex-v1_2-L2-059` strict=False ev_recall=1.00 citation=False judge=incorrect:0.0 tokens=34408 notes=citation policy not satisfied; llm judge did not mark answer correct query=When the relevant guard condition is true, what happens next?
- `vortex-v1_2-L2-060` strict=False ev_recall=1.00 citation=False judge=incorrect:0.0 tokens=33984 notes=citation policy not satisfied; llm judge did not mark answer correct query=When the relevant guard condition is true, what happens next?
- `vortex-v1_2-L2-061` strict=False ev_recall=1.00 citation=False judge=correct:1.0 tokens=34177 notes=citation policy not satisfied query=How does the write-control unit handle the last-lane selection logic?
- `vortex-v1_2-L2-062` strict=False ev_recall=1.00 citation=True judge=incorrect:0.0 tokens=34636 notes=llm judge did not mark answer correct query=What sequence does this behavior follow?
- `vortex-v1_2-L2-063` strict=False ev_recall=1.00 citation=False judge=correct:1.0 tokens=34239 notes=citation policy not satisfied query=How does the multiply/divide ALU handle word-sized multiplies?
- `vortex-v1_2-L2-064` strict=True ev_recall=1.00 citation=True judge=correct:1.0 tokens=34139 notes=ok query=What overall behavior is established here?
- `vortex-v1_2-L2-065` strict=False ev_recall=1.00 citation=False judge=partial:0.3 tokens=33720 notes=citation policy not satisfied; llm judge did not mark answer correct query=When the relevant guard condition is true, what happens next?
- `vortex-v1_2-L2-066` strict=True ev_recall=1.00 citation=True judge=correct:1.0 tokens=33876 notes=ok query=What sequence does this behavior follow?
- `vortex-v1_2-L2-067` strict=True ev_recall=1.00 citation=True judge=correct:1.0 tokens=33810 notes=ok query=What mechanism is this behavior using?
- `vortex-v1_2-L2-068` strict=True ev_recall=1.00 citation=True judge=correct:1.0 tokens=34521 notes=ok query=How does the shared FPU utility build its output across lanes, and what does that suggest about the surrounding FPU support?
- `vortex-v1_2-L2-069` strict=True ev_recall=1.00 citation=True judge=correct:1.0 tokens=34121 notes=ok query=Which part of the implementation does this behavior belong to?
- `vortex-v1_2-L2-070` strict=True ev_recall=1.00 citation=True judge=correct:1.0 tokens=34531 notes=ok query=How is the FPU conversion unit configured through the shared FPU headers?
- `vortex-v1_2-L2-071` strict=True ev_recall=1.00 citation=True judge=correct:1.0 tokens=34287 notes=ok query=I suspect this behavior is not actually implemented. Is that right?
- `vortex-v1_2-L2-072` strict=False ev_recall=1.00 citation=False judge=correct:1.0 tokens=34287 notes=citation policy not satisfied query=Does the FMA unit always take the same path for every operation?
- `vortex-v1_2-L2-073` strict=False ev_recall=1.00 citation=False judge=correct:1.0 tokens=34399 notes=citation policy not satisfied query=I suspect this behavior is not actually implemented. Is that right?
- `vortex-v1_2-L2-074` strict=True ev_recall=1.00 citation=True judge=correct:1.0 tokens=34344 notes=ok query=I suspect this behavior is not actually implemented. Is that right?
- `vortex-v1_2-L2-076` strict=True ev_recall=1.00 citation=True judge=correct:1.0 tokens=34297 notes=ok query=I suspect this behavior is not actually implemented. Is that right?
- `vortex-v1_2-L2-077` strict=True ev_recall=1.00 citation=True judge=correct:1.0 tokens=34203 notes=ok query=I suspect this behavior is not actually implemented. Is that right?
- `vortex-v1_2-L2-078` strict=False ev_recall=1.00 citation=False judge=correct:1.0 tokens=34083 notes=citation policy not satisfied query=How is the IP-dom stack sized relative to warp count?
- `vortex-v1_2-L2-079` strict=False ev_recall=1.00 citation=True judge=incorrect:0.0 tokens=34454 notes=llm judge did not mark answer correct query=I suspect this behavior is not actually implemented. Is that right?
- `vortex-v1_2-L2-080` strict=False ev_recall=1.00 citation=True judge=partial:0.5 tokens=34516 notes=llm judge did not mark answer correct query=I suspect this behavior is not actually implemented. Is that right?
- `vortex-v1_2-L2-081` strict=False ev_recall=1.00 citation=False judge=correct:1.0 tokens=34157 notes=citation policy not satisfied query=Where is the decode-to-issue handoff implemented in the core?
- `vortex-v1_2-L2-082` strict=True ev_recall=1.00 citation=True judge=correct:1.0 tokens=34508 notes=ok query=I suspect this behavior is not actually implemented. Is that right?
- `vortex-v1_2-L2-083` strict=True ev_recall=1.00 citation=True judge=correct:1.0 tokens=34368 notes=ok query=I suspect this behavior is not actually implemented. Is that right?
- `vortex-v1_2-L2-084` strict=False ev_recall=1.00 citation=True judge=incorrect:0.0 tokens=34228 notes=llm judge did not mark answer correct query=I suspect this behavior is not actually implemented. Is that right?
- `vortex-v1_2-L2-085` strict=False ev_recall=1.00 citation=False judge=correct:1.0 tokens=34233 notes=citation policy not satisfied query=Where is the FPU conversion control actually implemented?
- `vortex-v1_2-L2-086` strict=True ev_recall=1.00 citation=True judge=correct:1.0 tokens=34318 notes=ok query=I suspect this behavior is not actually implemented. Is that right?
- `vortex-v1_2-L2-088` strict=False ev_recall=1.00 citation=True judge=incorrect:0.0 tokens=34568 notes=llm judge did not mark answer correct query=I suspect this behavior is not actually implemented. Is that right?
- `vortex-v1_2-L2-089` strict=False ev_recall=1.00 citation=False judge=correct:1.0 tokens=34205 notes=citation policy not satisfied query=How does branch tracking get initialized in the scheduler?
- `vortex-v1_2-L2-090` strict=False ev_recall=1.00 citation=False judge=correct:1.0 tokens=34229 notes=citation policy not satisfied query=I suspect this behavior is not actually implemented. Is that right?
- `vortex-v1_2-L2-091` strict=True ev_recall=1.00 citation=True judge=correct:1.0 tokens=34231 notes=ok query=Does this snippet fully define the FPU result interface behavior?
- `vortex-v1_2-L2-092` strict=True ev_recall=1.00 citation=True judge=correct:1.0 tokens=34278 notes=ok query=The evidence seems to point in more than one direction; what can we confirm, and what remains unresolved?
- `vortex-v1_2-L2-094` strict=True ev_recall=1.00 citation=True judge=correct:1.0 tokens=34256 notes=ok query=The evidence seems to point in more than one direction; what can we confirm, and what remains unresolved?
- `vortex-v1_2-L2-095` strict=True ev_recall=1.00 citation=True judge=correct:1.0 tokens=34281 notes=ok query=The evidence seems to point in more than one direction; what can we confirm, and what remains unresolved?
- `vortex-v1_2-L3-141` strict=False ev_recall=1.00 citation=False judge=partial:0.67 tokens=34282 notes=citation policy not satisfied; llm judge did not mark answer correct query=Which part of the implementation does this behavior belong to?
- `vortex-v1_2-L3-142` strict=False ev_recall=1.00 citation=False judge=incorrect:0.0 tokens=34396 notes=citation policy not satisfied; llm judge did not mark answer correct query=What sequence does this behavior follow?
- `vortex-v1_2-L3-143` strict=False ev_recall=1.00 citation=False judge=partial:0.6 tokens=34314 notes=citation policy not satisfied; llm judge did not mark answer correct query=When the relevant guard condition is true, what happens next?
- `vortex-v1_2-L3-144` strict=False ev_recall=1.00 citation=False judge=partial:0.67 tokens=34118 notes=citation policy not satisfied; llm judge did not mark answer correct query=How does the serial divider handle reset?
- `vortex-v1_2-L3-145` strict=False ev_recall=1.00 citation=False judge=partial:0.5 tokens=33998 notes=citation policy not satisfied; llm judge did not mark answer correct query=Where is the reset behavior for the serial multiplier?
- `vortex-v1_2-L3-146` strict=False ev_recall=1.00 citation=False judge=partial:0.4 tokens=34396 notes=citation policy not satisfied; llm judge did not mark answer correct query=What sequence does this behavior follow?
- `vortex-v1_2-L3-148` strict=False ev_recall=1.00 citation=False judge=partial:0.5 tokens=34090 notes=citation policy not satisfied; llm judge did not mark answer correct query=When the relevant guard condition is true, what happens next?
- `vortex-v1_2-L3-149` strict=False ev_recall=1.00 citation=False judge=correct:1.0 tokens=34060 notes=citation policy not satisfied query=Where does the stream arbiter handle the case with more inputs than outputs?
- `vortex-v1_2-L3-150` strict=True ev_recall=1.00 citation=True judge=correct:1.0 tokens=34156 notes=ok query=What sequence does this behavior follow?
- `vortex-v1_2-L3-151` strict=False ev_recall=1.00 citation=False judge=partial:0.5 tokens=34225 notes=citation policy not satisfied; llm judge did not mark answer correct query=When the relevant guard condition is true, what happens next?
- `vortex-v1_2-L3-152` strict=False ev_recall=1.00 citation=False judge=partial:0.67 tokens=34184 notes=citation policy not satisfied; llm judge did not mark answer correct query=When the relevant guard condition is true, what happens next?
- `vortex-v1_2-L3-153` strict=True ev_recall=1.00 citation=True judge=correct:1.0 tokens=34225 notes=ok query=Which part of the implementation does this behavior belong to?
- `vortex-v1_2-L3-154` strict=True ev_recall=1.00 citation=True judge=correct:1.0 tokens=34305 notes=ok query=What sequence does this behavior follow?
- `vortex-v1_2-L3-155` strict=False ev_recall=1.00 citation=False judge=partial:0.67 tokens=34153 notes=citation policy not satisfied; llm judge did not mark answer correct query=How does the stream crossbar handle nontrivial sizes?
- `vortex-v1_2-L3-156` strict=False ev_recall=1.00 citation=False judge=partial:0.67 tokens=34166 notes=citation policy not satisfied; llm judge did not mark answer correct query=When the relevant guard condition is true, what happens next?
- `vortex-v1_2-L3-157` strict=False ev_recall=1.00 citation=False judge=partial:0.6 tokens=34074 notes=citation policy not satisfied; llm judge did not mark answer correct query=When the relevant guard condition is true, what happens next?
- `vortex-v1_2-L3-158` strict=True ev_recall=1.00 citation=True judge=correct:1.0 tokens=34230 notes=ok query=How should I think about the stream crossbar file?
- `vortex-v1_2-L3-159` strict=True ev_recall=1.00 citation=True judge=correct:1.0 tokens=34164 notes=ok query=What mechanism is this behavior using?
- `vortex-v1_2-L3-160` strict=False ev_recall=1.00 citation=False judge=partial:0.67 tokens=34093 notes=citation policy not satisfied; llm judge did not mark answer correct query=How does the gbar arbiter behave on reset?
- `vortex-v1_2-L3-161` strict=True ev_recall=1.00 citation=True judge=correct:1.0 tokens=34277 notes=ok query=Which part of the implementation does this behavior belong to?
- `vortex-v1_2-L3-162` strict=True ev_recall=1.00 citation=True judge=correct:1.0 tokens=33969 notes=ok query=What sequence does this behavior follow?
- `vortex-v1_2-L3-163` strict=False ev_recall=1.00 citation=False judge=partial:0.5 tokens=33820 notes=citation policy not satisfied; llm judge did not mark answer correct query=What mechanism is this behavior using?
- `vortex-v1_2-L3-164` strict=False ev_recall=1.00 citation=False judge=partial:0.67 tokens=33728 notes=citation policy not satisfied; llm judge did not mark answer correct query=When does local memory compute request bank indices?
- `vortex-v1_2-L3-166` strict=True ev_recall=1.00 citation=True judge=correct:1.0 tokens=34080 notes=ok query=What sequence does this behavior follow?
- `vortex-v1_2-L3-167` strict=True ev_recall=1.00 citation=True judge=correct:1.0 tokens=34682 notes=ok query=How does the request-tag selector output behave when there are more inputs than outputs?
- `vortex-v1_2-L3-168` strict=False ev_recall=1.00 citation=False judge=correct:1.0 tokens=33856 notes=citation policy not satisfied query=How is the population count result assembled in this design?
- `vortex-v1_2-L3-169` strict=False ev_recall=1.00 citation=False judge=partial:0.67 tokens=33625 notes=citation policy not satisfied; llm judge did not mark answer correct query=Where is the request-tag output selection handled when there are more inputs than outputs?
- `vortex-v1_2-L3-170` strict=True ev_recall=1.00 citation=True judge=correct:1.0 tokens=34084 notes=ok query=How do you integrate the LSU memory arbiter into the build flow?
- `vortex-v1_2-L3-172` strict=False ev_recall=1.00 citation=False judge=partial:0.5 tokens=33576 notes=citation policy not satisfied; llm judge did not mark answer correct query=How does the fused multiply path choose between fp16 and bf16 results?
- `vortex-v1_2-L3-173` strict=False ev_recall=1.00 citation=False judge=partial:0.7 tokens=34121 notes=citation policy not satisfied; llm judge did not mark answer correct query=Where is the format-specific branch for the fused DP DPI path?
- `vortex-v1_2-L3-174` strict=True ev_recall=1.00 citation=True judge=correct:1.0 tokens=34244 notes=ok query=How do you set up the memory switch module for use?
- `vortex-v1_2-L3-175` strict=False ev_recall=1.00 citation=False judge=partial:0.67 tokens=34192 notes=citation policy not satisfied; llm judge did not mark answer correct query=How does the integer fused multiply path start computing products?
- `vortex-v1_2-L3-176` strict=False ev_recall=1.00 citation=False judge=partial:0.67 tokens=34096 notes=citation policy not satisfied; llm judge did not mark answer correct query=How is the fused DP delay pipe reset?
- `vortex-v1_2-L3-177` strict=False ev_recall=1.00 citation=False judge=incorrect:0.0 tokens=34105 notes=citation policy not satisfied; llm judge did not mark answer correct query=Where is the serial divider logic implemented?
- `vortex-v1_2-L3-178` strict=False ev_recall=1.00 citation=False judge=correct:1.0 tokens=34174 notes=citation policy not satisfied query=How do you use the TCU integer module in the design?
- `vortex-v1_2-L3-179` strict=True ev_recall=1.00 citation=True judge=correct:1.0 tokens=34247 notes=ok query=What mechanism is this behavior using?
- `vortex-v1_2-L3-180` strict=True ev_recall=1.00 citation=True judge=correct:1.0 tokens=34278 notes=ok query=What overall behavior is established here?
- `vortex-v1_2-L3-181` strict=False ev_recall=1.00 citation=False judge=partial:0.5 tokens=34050 notes=citation policy not satisfied; llm judge did not mark answer correct query=Where is the conditional index selection handled?
- `vortex-v1_2-L3-182` strict=True ev_recall=1.00 citation=True judge=correct:1.0 tokens=34187 notes=ok query=What sequence does this behavior follow?
- `vortex-v1_2-L3-184` strict=False ev_recall=1.00 citation=False judge=correct:1.0 tokens=34215 notes=citation policy not satisfied query=How does the BF16 fused multiply helper handle recursive inputs?
