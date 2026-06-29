# Phase 5.5 — npm-audit security review of CodeGraph fork

Date: 2026-06-29
Fork: `tools/codegraph/` on `feat/verilog-language-module @ 88e228f`
CodeGraph upstream baseline: 1.1.1 (commit `4077ed1`)

## Scope

Per Phase 5 acceptance, npm-audit clearance is a hard gate on
promoting the v2 bundle path to canonical. This review covers the
**production dependency tree** of the fork — the deps that ship to
end users via `npm install -g @colbymchenry/codegraph`. The dev
dependencies (vitest, ESLint, tree-sitter-cli, etc.) are excluded
because they don't enter the runtime install or the published bundle.

## Phase 0 R5 baseline (informational)

`npm audit` without `--omit=dev` on the freshly-installed fork
reported **8 vulnerabilities** in the full tree (4 moderate, 3 high,
1 critical) — recorded in Phase 0 § 4 as risk R5. Most of those were
in dev-only deps; the production-scope picture is much smaller.

## Production-scope audit before fix

```
npm audit --omit=dev
```

| metric | count |
|---|---|
| info     | 0 |
| low      | 0 |
| moderate | 0 |
| **high** | **1** |
| critical | 0 |
| **total** | **1** |

Production dep tree size: 13 direct deps; 107 total (incl. dev/optional).

### The single high-severity production advisory

| field | value |
|---|---|
| package | `picomatch` |
| advisory 1 | [GHSA-3v7f-55p6-f55p](https://github.com/advisories/GHSA-3v7f-55p6-f55p) — POSIX character-class method injection (moderate, CVSS 5.3) |
| advisory 2 | [GHSA-c2c7-rcm5-vvqj](https://github.com/advisories/GHSA-c2c7-rcm5-vvqj) — extglob quantifier ReDoS (high, CVSS 7.5) |
| affected range | `>=4.0.0 <4.0.4` |
| fix available | yes — bump to `4.0.4+` |
| how it enters CodeGraph | transitively via `ignore@7.0.5` (the gitignore-respecting walker used in `src/extraction/index.ts`) |

## Fix

```
npm audit fix --omit=dev
```

Bumps `picomatch` to a patched version in `package-lock.json`. No
breaking-change major version bump; deep enough in the tree that
CodeGraph's API surface is unaffected.

## Production-scope audit after fix

| metric | count |
|---|---|
| **total** | **0** |

Zero remaining production-scope advisories.

## Triage summary

| disposition | count | notes |
|---|---|---|
| fixed (auto)     | 1 | picomatch bumped via `npm audit fix --omit=dev` |
| accepted-risk    | 0 | — |
| ignored          | 0 | — |
| pending review   | 0 | — |

## Gate

**gate: pass.**

The CodeGraph fork's production dependency tree has zero outstanding
vulnerabilities. Decision C (promote v2 bundle path to canonical) is
unblocked from the security side; the remaining gate is Decision A's
smoke50 L3 survival measurement.

## Action items for the fork commit

The npm audit fix patched `tools/codegraph/package-lock.json` (no
edits to `package.json`). The patched lockfile lands in the fork
branch `feat/verilog-language-module` as part of the Phase 5 sign-off
commit so future re-installs pull the fixed picomatch.

## Notes on the dev-scope advisories (not gating)

The 4 moderate + 2 high + 1 critical advisories in the dev-only tree
that Phase 0 flagged are all in tooling that doesn't ship to runtime:
- `vitest` and its `vite` transitive chain
- `tree-sitter-cli` (used by `scripts/build-verilog-wasm.sh` at build
  time)
- `@vitest/coverage-v8` Istanbul reporter chain

These would matter if we accepted untrusted code into the build
pipeline, which we don't (only this repo's CI runs against the fork).
File a quarterly dependabot sweep on the dev tree but do not gate
runtime promotion on them.
