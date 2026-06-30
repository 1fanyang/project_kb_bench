# v2 vs v1 bundle diff

- v1 dir: `runs/nvdla_context_bundle`
- v2 dir: `runs/nvdla_context_bundle_v2`

## Totals

| metric | v1 | v2 | delta |
|---|---|---|---|
| sources | 2085 | 1440 | -645 |
| entities | 25436 | 52729 | +27293 |
| relations | 25442 | 166458 | +141016 |

## Languages

| language | v1 | v2 |
|---|---|---|
| ac | 2 | 0 |
| am | 3 | 0 |
| bat | 1 | 0 |
| binary | 105 | 0 |
| c | 459 | 143 |
| cbproj | 3 | 0 |
| conf | 2 | 0 |
| config | 1 | 0 |
| cpp | 360 | 672 |
| css | 1 | 0 |
| css_t | 2 | 0 |
| dat | 28 | 0 |
| do | 1 | 0 |
| el | 1 | 0 |
| f | 3 | 0 |
| fbs | 1 | 0 |
| gradle | 1 | 0 |
| groupproj | 1 | 0 |
| guess | 2 | 0 |
| html | 7 | 0 |
| in | 8 | 0 |
| jar | 1 | 0 |
| java | 111 | 111 |
| js_t | 1 | 0 |
| json | 1 | 0 |
| la | 1 | 0 |
| lua | 1 | 1 |
| m4 | 13 | 0 |
| makefile | 52 | 0 |
| markdown | 11 | 0 |
| md5 | 19 | 0 |
| parms | 1 | 0 |
| pbxproj | 2 | 0 |
| pl | 8 | 0 |
| plist | 2 | 0 |
| pm | 6 | 0 |
| proto | 79 | 0 |
| pump | 4 | 0 |
| python | 90 | 90 |
| rdl | 1 | 0 |
| rst | 26 | 0 |
| sdc | 5 | 0 |
| shell | 15 | 0 |
| sln | 2 | 0 |
| spec | 2 | 0 |
| sub | 2 | 0 |
| svg | 64 | 0 |
| tcl | 5 | 0 |
| text | 31 | 0 |
| tmk | 2 | 0 |
| txn | 12 | 0 |
| uh | 2 | 0 |
| unknown | 64 | 0 |
| vcproj | 8 | 0 |
| verilog | 427 | 420 |
| vim | 1 | 0 |
| vlib | 11 | 0 |
| vm | 1 | 0 |
| xcconfig | 6 | 0 |
| xml | 2 | 2 |
| yaml | 0 | 1 |
| yml | 1 | 0 |

## Entity kinds

| kind | v1 | v2 |
|---|---|---|
| class | 184 | 2545 |
| constant | 0 | 2101 |
| enum | 0 | 389 |
| field | 0 | 457 |
| flag | 364 | 0 |
| function | 7913 | 42161 |
| heading | 423 | 0 |
| interface | 0 | 30 |
| macro | 14132 | 0 |
| make_target | 99 | 0 |
| module | 1443 | 1095 |
| namespace | 0 | 109 |
| parameter | 878 | 0 |
| struct | 0 | 1098 |
| type_alias | 0 | 1986 |
| variable | 0 | 758 |

## Predicate distribution

| predicate | v1 | v2 |
|---|---|---|
| calls | 0 | 72302 |
| contains | 423 | 67724 |
| decorates | 0 | 265 |
| defines | 25013 | 0 |
| doc_mentions_entity | 6 | 0 |
| extends | 0 | 3743 |
| implements | 0 | 31 |
| imports_or_includes | 0 | 3307 |
| instantiates | 0 | 15242 |
| references | 0 | 3844 |
