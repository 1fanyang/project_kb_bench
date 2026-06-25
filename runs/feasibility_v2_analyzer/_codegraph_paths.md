# CodeGraph install paths and runtime requirements

Recorded during Phase 0 Task 4. Subsequent Phase 0 tasks (and Phase 1+
plans) read this file to find the binary and the SQLite DB.

## Pinned upstream commit

See `_codegraph_commit.txt` (same directory): `colbymchenry/codegraph@4077ed1`.
CodeGraph upstream version at that sha: **1.1.1** (per `package.json`).

## Runtime requirement (important)

CodeGraph requires **Node.js ≥ 22.5** because it uses `node:sqlite` (the
built-in SQLite module, marked Experimental in v22). On this dev box the
system Node is 20.20.2, so all `codegraph` invocations must use the
homebrew-installed `node@22`:

```bash
/opt/homebrew/opt/node@22/bin/node tools/codegraph/dist/bin/codegraph.js …
```

For convenience, Phase 0+ shell snippets export `CG_BIN` to a helper
script that wraps this invocation; sourcing this file via the snippet
below gives you `CG_BIN` and `CG_DB` for any project bundle.

## Path variables (copy-paste to source)

```sh
# Binary entry — wraps node@22 around the codegraph CLI:
CG_BIN="/opt/homebrew/opt/node@22/bin/node $PWD/tools/codegraph/dist/bin/codegraph.js"
export CG_BIN

# Vortex SQLite DB (populated in Phase 0 Task 4):
CG_DB="/Users/yangyifan/projects/work/kb_benchmark/repo_sources/vortex/.codegraph/codegraph.db"
export CG_DB
```

## What got indexed in Task 4 (Vortex non-RTL)

CodeGraph's `EXTENSION_MAP` does not include `.sv` / `.v` / `.svh` / `.vh`,
so RTL files are silently skipped. No explicit exclude flag is needed.

| metric           | value |
|---|---|
| files indexed    | 366 |
| nodes            | 7,727 |
| edges            | 16,133 |
| init wall-clock  | ~3.3 s |
| DB size          | ~14 MB |

| language | files |
|---|---|
| cpp      | 228 |
| c        | 122 |
| python   | 13 |
| yaml     | 2 (file-level only; no symbol extraction) |
| php      | 1 |

| top node kinds | count |
|---|---|
| function     | 2035 |
| import       | 1852 |
| method       | 1773 |
| enum_member  | 458  |
| file         | 364  |
| class        | 363  |
| struct       | 361  |
| type_alias   | 304  |
| variable     | 144  |
| enum         | 69   |

## Tables (full schema dumped in Task 6)

`schema_versions`, `nodes`, `edges`, `files`, `unresolved_refs`,
`project_metadata`, plus the FTS5 virtual tables
(`nodes_fts`, `nodes_fts_config`, `nodes_fts_data`, `nodes_fts_docsize`,
`nodes_fts_idx`).

## Phase 1/2 implications

- **Phase 1** (Verilog language module): must register `.sv` / `.v` /
  `.svh` / `.vh` in `EXTENSION_MAP` and add `verilog` to
  `WASM_GRAMMAR_FILES`. The integration point is
  `tools/codegraph/src/extraction/grammars.ts` (the registry), with a
  matching extractor under `tools/codegraph/src/extraction/languages/`.
- **Phase 2** (bundle exporter): table names confirmed as `nodes` /
  `edges` / `files` (the Phase 2 plan's placeholder `symbols` / `relations`
  names need to be replaced before that plan executes). The Phase 2
  exporter contract should freeze on these names + the v1.1.1 schema.
- **Phase 0 plan vs reality:** the original plan assumed CodeGraph's bin
  was at `tools/codegraph/bin/codegraph`; actual path is
  `tools/codegraph/dist/bin/codegraph.js` requiring `node@22`.
