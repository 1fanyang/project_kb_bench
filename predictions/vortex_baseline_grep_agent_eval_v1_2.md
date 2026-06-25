# Method Evaluation Report

## Summary

- Cases: 100
- Strict E2E pass rate: 0.000
- Retrieval pass rate: 0.060
- Evidence recall@10: 0.185
- Evidence precision@10: 0.094
- Citation pass rate: 0.040
- LLM Judge coverage: 0.000
- Mean LLM Judge score: 0.000
- LLM Judge verdicts: {'not_run': 100}
- Token usage coverage: 1.000
- Mean total tokens: 644152.6
- Sum total tokens: 64415263

## Slice Summary

### layer
- `L1`: cases=20 strict=0.000 retrieval=0.250 ev_recall=0.250 judge=0.000 tokens=558116.7
- `L2`: cases=40 strict=0.000 retrieval=0.025 ev_recall=0.150 judge=0.000 tokens=702651.2
- `L3`: cases=40 strict=0.000 retrieval=0.000 ev_recall=0.188 judge=0.000 tokens=628672.1

### capability
- `build_simulation_flow`: cases=10 strict=0.000 retrieval=0.000 ev_recall=0.050 judge=0.000 tokens=456691.9
- `doc_code_cross_check`: cases=18 strict=0.000 retrieval=0.056 ev_recall=0.167 judge=0.000 tokens=651566.5
- `mechanism_trace`: cases=19 strict=0.000 retrieval=0.053 ev_recall=0.158 judge=0.000 tokens=719647.1
- `negative_insufficient_evidence`: cases=17 strict=0.000 retrieval=0.059 ev_recall=0.206 judge=0.000 tokens=626439.3
- `repo_structure_location`: cases=18 strict=0.000 retrieval=0.111 ev_recall=0.278 judge=0.000 tokens=678644.3
- `tests_debug_evidence`: cases=18 strict=0.000 retrieval=0.056 ev_recall=0.194 judge=0.000 tokens=643432.6

### answer_type
- `fact_check`: cases=18 strict=0.000 retrieval=0.000 ev_recall=0.111 judge=0.000 tokens=787634.6
- `location`: cases=19 strict=0.000 retrieval=0.053 ev_recall=0.211 judge=0.000 tokens=446143.9
- `mechanism`: cases=17 strict=0.000 retrieval=0.118 ev_recall=0.235 judge=0.000 tokens=642365.8
- `negative`: cases=4 strict=0.000 retrieval=0.000 ev_recall=0.000 judge=0.000 tokens=449413.5
- `procedure`: cases=21 strict=0.000 retrieval=0.048 ev_recall=0.095 judge=0.000 tokens=791364.7
- `synthesis`: cases=21 strict=0.000 retrieval=0.095 ev_recall=0.310 judge=0.000 tokens=591646.3

## Per Case

- `vortex-v1_2-L1-031` strict=False ev_recall=1.00 citation=False judge=not_run:None tokens=138462 notes=citation policy not satisfied; llm judge not available query=Where is the AFU control module defined in the hardware tree?
- `vortex-v1_2-L1-032` strict=False ev_recall=1.00 citation=True judge=not_run:None tokens=348751 notes=llm judge not available query=What kind of module is the AFU wrapper in the hardware tree?
- `vortex-v1_2-L1-033` strict=False ev_recall=0.00 citation=False judge=not_run:None tokens=142394 notes=gold evidence not fully retrieved; citation policy not satisfied; llm judge not available query=Where is the top-level AFU module defined in the hardware tree?
- `vortex-v1_2-L1-034` strict=False ev_recall=0.00 citation=False judge=not_run:None tokens=671564 notes=gold evidence not fully retrieved; citation policy not satisfied; llm judge not available query=How is the AFU header meant to be used by the RTL modules?
- `vortex-v1_2-L1-035` strict=False ev_recall=0.00 citation=False judge=not_run:None tokens=874878 notes=gold evidence not fully retrieved; citation policy not satisfied; llm judge not available query=What mechanism is this behavior using?
- `vortex-v1_2-L1-036` strict=False ev_recall=0.00 citation=False judge=not_run:None tokens=341158 notes=gold evidence not fully retrieved; citation policy not satisfied; llm judge not available query=What overall behavior is established here?
- `vortex-v1_2-L1-037` strict=False ev_recall=0.00 citation=False judge=not_run:None tokens=337287 notes=gold evidence not fully retrieved; citation policy not satisfied; llm judge not available query=Which part of the implementation does this behavior belong to?
- `vortex-v1_2-L1-038` strict=False ev_recall=0.00 citation=False judge=not_run:None tokens=1121936 notes=gold evidence not fully retrieved; citation policy not satisfied; llm judge not available query=What sequence does this behavior follow?
- `vortex-v1_2-L1-039` strict=False ev_recall=0.00 citation=False judge=not_run:None tokens=482202 notes=gold evidence not fully retrieved; citation policy not satisfied; llm judge not available query=What mechanism is this behavior using?
- `vortex-v1_2-L1-040` strict=False ev_recall=0.00 citation=False judge=not_run:None tokens=1187997 notes=gold evidence not fully retrieved; citation policy not satisfied; llm judge not available query=What overall behavior is established here?
- `vortex-v1_2-L1-041` strict=False ev_recall=0.00 citation=False judge=not_run:None tokens=637078 notes=gold evidence not fully retrieved; citation policy not satisfied; llm judge not available query=Which part of the implementation does this behavior belong to?
- `vortex-v1_2-L1-042` strict=False ev_recall=0.00 citation=False judge=not_run:None tokens=1027112 notes=gold evidence not fully retrieved; citation policy not satisfied; llm judge not available query=What sequence does this behavior follow?
- `vortex-v1_2-L1-043` strict=False ev_recall=0.00 citation=False judge=not_run:None tokens=976391 notes=gold evidence not fully retrieved; citation policy not satisfied; llm judge not available query=What mechanism is this behavior using?
- `vortex-v1_2-L1-044` strict=False ev_recall=0.00 citation=False judge=not_run:None tokens=217736 notes=gold evidence not fully retrieved; citation policy not satisfied; llm judge not available query=What is the cache replacement module used for?
- `vortex-v1_2-L1-045` strict=False ev_recall=0.00 citation=False judge=not_run:None tokens=403033 notes=gold evidence not fully retrieved; citation policy not satisfied; llm judge not available query=Which part of the implementation does this behavior belong to?
- `vortex-v1_2-L1-046` strict=False ev_recall=0.00 citation=False judge=not_run:None tokens=975413 notes=gold evidence not fully retrieved; citation policy not satisfied; llm judge not available query=What sequence does this behavior follow?
- `vortex-v1_2-L1-047` strict=False ev_recall=1.00 citation=True judge=not_run:None tokens=153684 notes=llm judge not available query=Where is the cache wrapper module located?
- `vortex-v1_2-L1-048` strict=False ev_recall=1.00 citation=True judge=not_run:None tokens=247992 notes=llm judge not available query=Where is the integer ALU module defined?
- `vortex-v1_2-L1-049` strict=False ev_recall=1.00 citation=True judge=not_run:None tokens=134991 notes=llm judge not available query=Where is the multiply/divide ALU module located?
- `vortex-v1_2-L1-050` strict=False ev_recall=0.00 citation=False judge=not_run:None tokens=742274 notes=gold evidence not fully retrieved; citation policy not satisfied; llm judge not available query=What sequence does this behavior follow?
- `vortex-v1_2-L2-052` strict=False ev_recall=0.50 citation=False judge=not_run:None tokens=360740 notes=gold evidence not fully retrieved; citation policy not satisfied; llm judge not available query=How does the opcode unit handle bank selection when the design is banked?
- `vortex-v1_2-L2-053` strict=False ev_recall=0.00 citation=False judge=not_run:None tokens=465659 notes=gold evidence not fully retrieved; citation policy not satisfied; llm judge not available query=When the relevant guard condition is true, what happens next?
- `vortex-v1_2-L2-054` strict=False ev_recall=0.00 citation=False judge=not_run:None tokens=1158520 notes=gold evidence not fully retrieved; citation policy not satisfied; llm judge not available query=What sequence does this behavior follow?
- `vortex-v1_2-L2-055` strict=False ev_recall=0.50 citation=False judge=not_run:None tokens=461561 notes=gold evidence not fully retrieved; citation policy not satisfied; llm judge not available query=How does the scheduler update warp state?
- `vortex-v1_2-L2-056` strict=False ev_recall=0.00 citation=False judge=not_run:None tokens=1183822 notes=gold evidence not fully retrieved; citation policy not satisfied; llm judge not available query=When the relevant guard condition is true, what happens next?
- `vortex-v1_2-L2-058` strict=False ev_recall=0.00 citation=False judge=not_run:None tokens=200843 notes=gold evidence not fully retrieved; citation policy not satisfied; llm judge not available query=What role does the scheduler module play in the core tree?
- `vortex-v1_2-L2-059` strict=False ev_recall=0.00 citation=False judge=not_run:None tokens=770830 notes=gold evidence not fully retrieved; citation policy not satisfied; llm judge not available query=When the relevant guard condition is true, what happens next?
- `vortex-v1_2-L2-060` strict=False ev_recall=0.00 citation=False judge=not_run:None tokens=1233068 notes=gold evidence not fully retrieved; citation policy not satisfied; llm judge not available query=When the relevant guard condition is true, what happens next?
- `vortex-v1_2-L2-061` strict=False ev_recall=0.50 citation=False judge=not_run:None tokens=402834 notes=gold evidence not fully retrieved; citation policy not satisfied; llm judge not available query=How does the write-control unit handle the last-lane selection logic?
- `vortex-v1_2-L2-062` strict=False ev_recall=0.00 citation=False judge=not_run:None tokens=618161 notes=gold evidence not fully retrieved; citation policy not satisfied; llm judge not available query=What sequence does this behavior follow?
- `vortex-v1_2-L2-063` strict=False ev_recall=0.50 citation=False judge=not_run:None tokens=445377 notes=gold evidence not fully retrieved; citation policy not satisfied; llm judge not available query=How does the multiply/divide ALU handle word-sized multiplies?
- `vortex-v1_2-L2-064` strict=False ev_recall=0.00 citation=False judge=not_run:None tokens=999773 notes=gold evidence not fully retrieved; citation policy not satisfied; llm judge not available query=What overall behavior is established here?
- `vortex-v1_2-L2-065` strict=False ev_recall=0.50 citation=False judge=not_run:None tokens=553326 notes=gold evidence not fully retrieved; citation policy not satisfied; llm judge not available query=When the relevant guard condition is true, what happens next?
- `vortex-v1_2-L2-066` strict=False ev_recall=0.00 citation=False judge=not_run:None tokens=389982 notes=gold evidence not fully retrieved; citation policy not satisfied; llm judge not available query=What sequence does this behavior follow?
- `vortex-v1_2-L2-067` strict=False ev_recall=0.00 citation=False judge=not_run:None tokens=721164 notes=gold evidence not fully retrieved; citation policy not satisfied; llm judge not available query=What mechanism is this behavior using?
- `vortex-v1_2-L2-068` strict=False ev_recall=0.50 citation=False judge=not_run:None tokens=490175 notes=gold evidence not fully retrieved; citation policy not satisfied; llm judge not available query=How does the shared FPU utility build its output across lanes, and what does that suggest about the surrounding FPU support?
- `vortex-v1_2-L2-069` strict=False ev_recall=0.00 citation=False judge=not_run:None tokens=882171 notes=gold evidence not fully retrieved; citation policy not satisfied; llm judge not available query=Which part of the implementation does this behavior belong to?
- `vortex-v1_2-L2-070` strict=False ev_recall=1.00 citation=False judge=not_run:None tokens=792965 notes=citation policy not satisfied; llm judge not available query=How is the FPU conversion unit configured through the shared FPU headers?
- `vortex-v1_2-L2-071` strict=False ev_recall=0.00 citation=False judge=not_run:None tokens=1941545 notes=gold evidence not fully retrieved; citation policy not satisfied; llm judge not available query=I suspect this behavior is not actually implemented. Is that right?
- `vortex-v1_2-L2-072` strict=False ev_recall=0.50 citation=False judge=not_run:None tokens=380073 notes=gold evidence not fully retrieved; citation policy not satisfied; llm judge not available query=Does the FMA unit always take the same path for every operation?
- `vortex-v1_2-L2-073` strict=False ev_recall=0.00 citation=False judge=not_run:None tokens=1060844 notes=gold evidence not fully retrieved; citation policy not satisfied; llm judge not available query=I suspect this behavior is not actually implemented. Is that right?
- `vortex-v1_2-L2-074` strict=False ev_recall=0.00 citation=False judge=not_run:None tokens=594558 notes=gold evidence not fully retrieved; citation policy not satisfied; llm judge not available query=I suspect this behavior is not actually implemented. Is that right?
- `vortex-v1_2-L2-076` strict=False ev_recall=0.00 citation=False judge=not_run:None tokens=767417 notes=gold evidence not fully retrieved; citation policy not satisfied; llm judge not available query=I suspect this behavior is not actually implemented. Is that right?
- `vortex-v1_2-L2-077` strict=False ev_recall=0.00 citation=False judge=not_run:None tokens=1210653 notes=gold evidence not fully retrieved; citation policy not satisfied; llm judge not available query=I suspect this behavior is not actually implemented. Is that right?
- `vortex-v1_2-L2-078` strict=False ev_recall=0.50 citation=False judge=not_run:None tokens=223682 notes=gold evidence not fully retrieved; citation policy not satisfied; llm judge not available query=How is the IP-dom stack sized relative to warp count?
- `vortex-v1_2-L2-079` strict=False ev_recall=0.00 citation=False judge=not_run:None tokens=850016 notes=gold evidence not fully retrieved; citation policy not satisfied; llm judge not available query=I suspect this behavior is not actually implemented. Is that right?
- `vortex-v1_2-L2-080` strict=False ev_recall=0.00 citation=False judge=not_run:None tokens=609022 notes=gold evidence not fully retrieved; citation policy not satisfied; llm judge not available query=I suspect this behavior is not actually implemented. Is that right?
- `vortex-v1_2-L2-081` strict=False ev_recall=0.00 citation=False judge=not_run:None tokens=314629 notes=gold evidence not fully retrieved; citation policy not satisfied; llm judge not available query=Where is the decode-to-issue handoff implemented in the core?
- `vortex-v1_2-L2-082` strict=False ev_recall=0.00 citation=False judge=not_run:None tokens=774666 notes=gold evidence not fully retrieved; citation policy not satisfied; llm judge not available query=I suspect this behavior is not actually implemented. Is that right?
- `vortex-v1_2-L2-083` strict=False ev_recall=0.00 citation=False judge=not_run:None tokens=1543400 notes=gold evidence not fully retrieved; citation policy not satisfied; llm judge not available query=I suspect this behavior is not actually implemented. Is that right?
- `vortex-v1_2-L2-084` strict=False ev_recall=0.00 citation=False judge=not_run:None tokens=363633 notes=gold evidence not fully retrieved; citation policy not satisfied; llm judge not available query=I suspect this behavior is not actually implemented. Is that right?
- `vortex-v1_2-L2-085` strict=False ev_recall=0.50 citation=False judge=not_run:None tokens=981200 notes=gold evidence not fully retrieved; citation policy not satisfied; llm judge not available query=Where is the FPU conversion control actually implemented?
- `vortex-v1_2-L2-086` strict=False ev_recall=0.00 citation=False judge=not_run:None tokens=990958 notes=gold evidence not fully retrieved; citation policy not satisfied; llm judge not available query=I suspect this behavior is not actually implemented. Is that right?
- `vortex-v1_2-L2-088` strict=False ev_recall=0.00 citation=False judge=not_run:None tokens=800395 notes=gold evidence not fully retrieved; citation policy not satisfied; llm judge not available query=I suspect this behavior is not actually implemented. Is that right?
- `vortex-v1_2-L2-089` strict=False ev_recall=0.50 citation=False judge=not_run:None tokens=397502 notes=gold evidence not fully retrieved; citation policy not satisfied; llm judge not available query=How does branch tracking get initialized in the scheduler?
- `vortex-v1_2-L2-090` strict=False ev_recall=0.00 citation=False judge=not_run:None tokens=373230 notes=gold evidence not fully retrieved; citation policy not satisfied; llm judge not available query=I suspect this behavior is not actually implemented. Is that right?
- `vortex-v1_2-L2-091` strict=False ev_recall=0.00 citation=False judge=not_run:None tokens=420313 notes=gold evidence not fully retrieved; citation policy not satisfied; llm judge not available query=Does this snippet fully define the FPU result interface behavior?
- `vortex-v1_2-L2-092` strict=False ev_recall=0.00 citation=False judge=not_run:None tokens=768423 notes=gold evidence not fully retrieved; citation policy not satisfied; llm judge not available query=The evidence seems to point in more than one direction; what can we confirm, and what remains unresolved?
- `vortex-v1_2-L2-094` strict=False ev_recall=0.00 citation=False judge=not_run:None tokens=361671 notes=gold evidence not fully retrieved; citation policy not satisfied; llm judge not available query=The evidence seems to point in more than one direction; what can we confirm, and what remains unresolved?
- `vortex-v1_2-L2-095` strict=False ev_recall=0.00 citation=False judge=not_run:None tokens=247247 notes=gold evidence not fully retrieved; citation policy not satisfied; llm judge not available query=The evidence seems to point in more than one direction; what can we confirm, and what remains unresolved?
- `vortex-v1_2-L3-141` strict=False ev_recall=0.00 citation=False judge=not_run:None tokens=813408 notes=gold evidence not fully retrieved; citation policy not satisfied; llm judge not available query=Which part of the implementation does this behavior belong to?
- `vortex-v1_2-L3-142` strict=False ev_recall=0.00 citation=False judge=not_run:None tokens=1055102 notes=gold evidence not fully retrieved; citation policy not satisfied; llm judge not available query=What sequence does this behavior follow?
- `vortex-v1_2-L3-143` strict=False ev_recall=0.00 citation=False judge=not_run:None tokens=209158 notes=gold evidence not fully retrieved; citation policy not satisfied; llm judge not available query=When the relevant guard condition is true, what happens next?
- `vortex-v1_2-L3-144` strict=False ev_recall=0.50 citation=False judge=not_run:None tokens=142274 notes=gold evidence not fully retrieved; citation policy not satisfied; llm judge not available query=How does the serial divider handle reset?
- `vortex-v1_2-L3-145` strict=False ev_recall=0.50 citation=False judge=not_run:None tokens=289981 notes=gold evidence not fully retrieved; citation policy not satisfied; llm judge not available query=Where is the reset behavior for the serial multiplier?
- `vortex-v1_2-L3-146` strict=False ev_recall=0.00 citation=False judge=not_run:None tokens=529392 notes=gold evidence not fully retrieved; citation policy not satisfied; llm judge not available query=What sequence does this behavior follow?
- `vortex-v1_2-L3-148` strict=False ev_recall=0.00 citation=False judge=not_run:None tokens=474175 notes=gold evidence not fully retrieved; citation policy not satisfied; llm judge not available query=When the relevant guard condition is true, what happens next?
- `vortex-v1_2-L3-149` strict=False ev_recall=0.50 citation=False judge=not_run:None tokens=129706 notes=gold evidence not fully retrieved; citation policy not satisfied; llm judge not available query=Where does the stream arbiter handle the case with more inputs than outputs?
- `vortex-v1_2-L3-150` strict=False ev_recall=0.00 citation=False judge=not_run:None tokens=770682 notes=gold evidence not fully retrieved; citation policy not satisfied; llm judge not available query=What sequence does this behavior follow?
- `vortex-v1_2-L3-151` strict=False ev_recall=0.00 citation=False judge=not_run:None tokens=421070 notes=gold evidence not fully retrieved; citation policy not satisfied; llm judge not available query=When the relevant guard condition is true, what happens next?
- `vortex-v1_2-L3-152` strict=False ev_recall=0.00 citation=False judge=not_run:None tokens=380430 notes=gold evidence not fully retrieved; citation policy not satisfied; llm judge not available query=When the relevant guard condition is true, what happens next?
- `vortex-v1_2-L3-153` strict=False ev_recall=0.00 citation=False judge=not_run:None tokens=433093 notes=gold evidence not fully retrieved; citation policy not satisfied; llm judge not available query=Which part of the implementation does this behavior belong to?
- `vortex-v1_2-L3-154` strict=False ev_recall=0.00 citation=False judge=not_run:None tokens=445930 notes=gold evidence not fully retrieved; citation policy not satisfied; llm judge not available query=What sequence does this behavior follow?
- `vortex-v1_2-L3-155` strict=False ev_recall=0.50 citation=False judge=not_run:None tokens=320080 notes=gold evidence not fully retrieved; citation policy not satisfied; llm judge not available query=How does the stream crossbar handle nontrivial sizes?
- `vortex-v1_2-L3-156` strict=False ev_recall=0.00 citation=False judge=not_run:None tokens=458670 notes=gold evidence not fully retrieved; citation policy not satisfied; llm judge not available query=When the relevant guard condition is true, what happens next?
- `vortex-v1_2-L3-157` strict=False ev_recall=0.00 citation=False judge=not_run:None tokens=659274 notes=gold evidence not fully retrieved; citation policy not satisfied; llm judge not available query=When the relevant guard condition is true, what happens next?
- `vortex-v1_2-L3-158` strict=False ev_recall=0.00 citation=False judge=not_run:None tokens=351279 notes=gold evidence not fully retrieved; citation policy not satisfied; llm judge not available query=How should I think about the stream crossbar file?
- `vortex-v1_2-L3-159` strict=False ev_recall=0.00 citation=False judge=not_run:None tokens=450611 notes=gold evidence not fully retrieved; citation policy not satisfied; llm judge not available query=What mechanism is this behavior using?
- `vortex-v1_2-L3-160` strict=False ev_recall=0.50 citation=False judge=not_run:None tokens=595046 notes=gold evidence not fully retrieved; citation policy not satisfied; llm judge not available query=How does the gbar arbiter behave on reset?
- `vortex-v1_2-L3-161` strict=False ev_recall=0.00 citation=False judge=not_run:None tokens=562974 notes=gold evidence not fully retrieved; citation policy not satisfied; llm judge not available query=Which part of the implementation does this behavior belong to?
- `vortex-v1_2-L3-162` strict=False ev_recall=0.00 citation=False judge=not_run:None tokens=1497564 notes=gold evidence not fully retrieved; citation policy not satisfied; llm judge not available query=What sequence does this behavior follow?
- `vortex-v1_2-L3-163` strict=False ev_recall=0.00 citation=False judge=not_run:None tokens=1406219 notes=gold evidence not fully retrieved; citation policy not satisfied; llm judge not available query=What mechanism is this behavior using?
- `vortex-v1_2-L3-164` strict=False ev_recall=0.50 citation=False judge=not_run:None tokens=1053524 notes=gold evidence not fully retrieved; citation policy not satisfied; llm judge not available query=When does local memory compute request bank indices?
- `vortex-v1_2-L3-166` strict=False ev_recall=0.00 citation=False judge=not_run:None tokens=946447 notes=gold evidence not fully retrieved; citation policy not satisfied; llm judge not available query=What sequence does this behavior follow?
- `vortex-v1_2-L3-167` strict=False ev_recall=0.00 citation=False judge=not_run:None tokens=701655 notes=gold evidence not fully retrieved; citation policy not satisfied; llm judge not available query=How does the request-tag selector output behave when there are more inputs than outputs?
- `vortex-v1_2-L3-168` strict=False ev_recall=0.50 citation=False judge=not_run:None tokens=176495 notes=gold evidence not fully retrieved; citation policy not satisfied; llm judge not available query=How is the population count result assembled in this design?
- `vortex-v1_2-L3-169` strict=False ev_recall=0.50 citation=False judge=not_run:None tokens=308494 notes=gold evidence not fully retrieved; citation policy not satisfied; llm judge not available query=Where is the request-tag output selection handled when there are more inputs than outputs?
- `vortex-v1_2-L3-170` strict=False ev_recall=0.50 citation=False judge=not_run:None tokens=416629 notes=gold evidence not fully retrieved; citation policy not satisfied; llm judge not available query=How do you integrate the LSU memory arbiter into the build flow?
- `vortex-v1_2-L3-172` strict=False ev_recall=0.50 citation=False judge=not_run:None tokens=269322 notes=gold evidence not fully retrieved; citation policy not satisfied; llm judge not available query=How does the fused multiply path choose between fp16 and bf16 results?
- `vortex-v1_2-L3-173` strict=False ev_recall=0.50 citation=False judge=not_run:None tokens=401947 notes=gold evidence not fully retrieved; citation policy not satisfied; llm judge not available query=Where is the format-specific branch for the fused DP DPI path?
- `vortex-v1_2-L3-174` strict=False ev_recall=0.50 citation=False judge=not_run:None tokens=376078 notes=gold evidence not fully retrieved; citation policy not satisfied; llm judge not available query=How do you set up the memory switch module for use?
- `vortex-v1_2-L3-175` strict=False ev_recall=0.50 citation=False judge=not_run:None tokens=1926413 notes=gold evidence not fully retrieved; citation policy not satisfied; llm judge not available query=How does the integer fused multiply path start computing products?
- `vortex-v1_2-L3-176` strict=False ev_recall=0.50 citation=False judge=not_run:None tokens=196445 notes=gold evidence not fully retrieved; citation policy not satisfied; llm judge not available query=How is the fused DP delay pipe reset?
- `vortex-v1_2-L3-177` strict=False ev_recall=0.00 citation=False judge=not_run:None tokens=200001 notes=gold evidence not fully retrieved; citation policy not satisfied; llm judge not available query=Where is the serial divider logic implemented?
- `vortex-v1_2-L3-178` strict=False ev_recall=0.00 citation=False judge=not_run:None tokens=1416104 notes=gold evidence not fully retrieved; citation policy not satisfied; llm judge not available query=How do you use the TCU integer module in the design?
- `vortex-v1_2-L3-179` strict=False ev_recall=0.00 citation=False judge=not_run:None tokens=460464 notes=gold evidence not fully retrieved; citation policy not satisfied; llm judge not available query=What mechanism is this behavior using?
- `vortex-v1_2-L3-180` strict=False ev_recall=0.00 citation=False judge=not_run:None tokens=1489255 notes=gold evidence not fully retrieved; citation policy not satisfied; llm judge not available query=What overall behavior is established here?
- `vortex-v1_2-L3-181` strict=False ev_recall=0.00 citation=False judge=not_run:None tokens=719084 notes=gold evidence not fully retrieved; citation policy not satisfied; llm judge not available query=Where is the conditional index selection handled?
- `vortex-v1_2-L3-182` strict=False ev_recall=0.00 citation=False judge=not_run:None tokens=1114682 notes=gold evidence not fully retrieved; citation policy not satisfied; llm judge not available query=What sequence does this behavior follow?
- `vortex-v1_2-L3-184` strict=False ev_recall=0.50 citation=False judge=not_run:None tokens=577725 notes=gold evidence not fully retrieved; citation policy not satisfied; llm judge not available query=How does the BF16 fused multiply helper handle recursive inputs?
