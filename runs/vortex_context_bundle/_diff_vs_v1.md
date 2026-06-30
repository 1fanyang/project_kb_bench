# v2 vs v1 bundle diff

- v1 dir: `runs/vortex_context_bundle`
- v2 dir: `runs/vortex_context_bundle_v2`

## Totals

| metric | v1 | v2 | delta |
|---|---|---|---|
| sources | 1504 | 577 | -927 |
| entities | 12449 | 5745 | -6704 |
| relations | 14737 | 14925 | +188 |

## Languages

| language | v1 | v2 |
|---|---|---|
| assembly | 4 | 0 |
| binary | 637 | 0 |
| c | 31 | 122 |
| c_cpp_header | 154 | 0 |
| cmake | 1 | 0 |
| config | 2 | 0 |
| cpp | 164 | 228 |
| ini | 1 | 0 |
| json | 1 | 0 |
| make | 128 | 0 |
| markdown | 21 | 0 |
| opencl | 21 | 0 |
| php | 0 | 1 |
| python | 13 | 13 |
| shell | 21 | 0 |
| systemverilog | 186 | 0 |
| tcl | 20 | 0 |
| text | 7 | 0 |
| unknown | 75 | 0 |
| verilog | 15 | 211 |
| yaml | 2 | 2 |

## Entity kinds

| kind | v1 | v2 |
|---|---|---|
| class | 826 | 363 |
| config_key | 270 | 0 |
| constant | 0 | 462 |
| enum | 72 | 69 |
| env_var | 57 | 0 |
| flag | 13 | 0 |
| function | 2614 | 3874 |
| heading | 210 | 0 |
| interface | 0 | 23 |
| macro | 1711 | 0 |
| make_target | 287 | 0 |
| module | 167 | 145 |
| parameter | 1594 | 0 |
| signal | 4113 | 0 |
| struct | 515 | 361 |
| type_alias | 0 | 304 |
| variable | 0 | 144 |

## Predicate distribution

| predicate | v1 | v2 |
|---|---|---|
| calls | 0 | 7847 |
| contains | 210 | 5790 |
| defines | 12239 | 0 |
| doc_mentions_entity | 257 | 0 |
| extends | 0 | 158 |
| imports_or_includes | 2031 | 592 |
| instantiates | 0 | 441 |
| references | 0 | 97 |
