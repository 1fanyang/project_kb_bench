# Doc-Code Synchronization in Evolving Knowledge Corpora — A Research Survey

Status: research notes
Date: 2026-06-23
Trigger: observed snapshot-vs-upstream drift while reviewing `runs/vortex_benchmark_v1.jsonl` rows L2-009, L2-013, L2-014, L2-024, L1-028 against the Vortex master branch. Three real drift cases surfaced inside a single 8-day window: a flag rename (`-DL2_ENABLE` → `-DVX_CFG_L2_ENABLE`), a directory removal (`runtime/{opae,xrt,simx}/` gone), and a build-rule gutting (`hw/Makefile` no longer generates `VX_config.h`). The user-facing setup doc (`docs/fpga_setup.md`) was updated for the flag rename but not for the directory removal — a clean instance of the broader "RAG-empowered agent meets evolving source" problem.

This document formulates that problem and surveys SOTA in both the research and industrial communities, ending with the open challenges that current work does not yet close.

---

## 1. Problem formulation

Let an evolving knowledge corpus be a sequence of snapshots $S_0, S_1, S_2, \ldots$ where each $S_t = (C_t, D_t, M_t, G_t)$ comprises:

- $C_t$: code artifacts (functions, configs, build scripts, schemas)
- $D_t$: documentation (READMEs, design docs, tutorials, in-code comments)
- $M_t$: process metadata (issues, PRs, commits, ADRs)
- $G_t$: a derived knowledge graph / vector index used by the RAG layer

A transition $S_t \to S_{t+1}$ is a commit produced by one of several agents (dev groups, bots, LLM coders). It may touch any subset of $\{C, D, M\}$. Three sub-problems then become well-defined:

**P1 — Consistency detection.** Given $S_{t+1}$, identify pairs $(a, b)$ across $C, D$ (and within each) that *should* express a consistent claim but now disagree. The `fpga_setup.md → runtime/opae` example is in $D \times C$.

**P2 — Impact propagation.** Given a code change $\Delta C$, predict which $D$ and $G$ entities require an update to remain consistent. Classical "change impact analysis," generalized to docs/KG.

**P3 — Representation update.** Given detected inconsistencies plus a declared "ground truth," produce the minimal patch to $G_{t+1}$ (vector entries, KG nodes/edges, RAG snippets) that restores consistency without degrading retrieval quality elsewhere.

Three structural complications:

- **Authority ambiguity** — when code and doc disagree, which wins? Sometimes doc is the spec; sometimes code is. Need per-artifact authority.
- **Multi-party concurrency** — independent dev-group edits can each be locally correct yet globally inconsistent (the CRDT problem applied to knowledge).
- **Asymmetric update costs** — full re-index is O(corpus); incremental patch is O(diff) but requires entity-level provenance most pipelines don't maintain.

Common metrics:

- Drift precision / recall / F1 (P1)
- Change-impact recall@k (P2)
- Patch fidelity vs. full rebuild (P3)
- Retrieval freshness (commit-to-visible latency)
- Answer faithfulness under drift (end-to-end)

---

## 2. Research SOTA, by sub-problem

### P1 — Consistency detection

Three generations:

1. **Static / rule-based (2007–2018).** Tan et al.'s `iComment` family — pattern-matching between comment annotations and AST features. Still useful for low-level invariants; brittle.
2. **Supervised classifiers (2018–2023).** Liu / Panthaplackel et al. on "is this comment outdated given this diff?" Standard benchmarks **JITDATA** (~33k Java samples) and **CCIBENCH**; BERT/Longformer encoders pushed F1 into the high-70s.
3. **LLM-based (2023–2026).**
   - **DocChecker** (Fang et al. 2023) — fine-tuned encoder+generator; detects *and rectifies* code-comment mismatches; current SOTA on the ICCD task.
   - **MPDetector** (2024) — symbolic execution + LLM-extracted API constraints for multi-parameter doc/code inconsistency.
   - **"Larger Is Not Always Better"** (arXiv 2512.19883, Dec 2025) — structured-diff input beats long-context LLM brute-force on CCI. The signal lives in the diff structure.

For *doc-level* (not just comments): **"Wait, wasn't that code here before?"** (Aghajani et al., arXiv 2307.04291) is the seminal framing of doc-level drift detection. Less mature than the comment side because entity resolution (which paragraph belongs to which symbol?) is harder.

For commit-message ↔ diff: **CodeFuse-CommitEval** (arXiv 2511.19875, Nov 2025) benchmarks LLMs at detecting commit messages that misdescribe their diffs.

### P2 — Impact propagation

1. **Classical CIA.** Graph walks over import/call/data-flow (Robillard, Wong, Murphy). Reports change-impact recall in the 60–80% range on small Java/C# corpora. *Docs rarely appear in these graphs* — that's the gap.
2. **Temporal graph + GNN.** "To change or not to change? Modeling software system interactions using Temporal Graphs and GNNs" (ScienceDirect 2024) treats successive snapshots as temporal-graph slices and predicts co-change probability.
3. **LLM-as-impact-oracle.** Emerging: ask an LLM "given this diff, which docs/configs/tests need updating?" Limited published benchmarks; mostly demos.

### P3 — Representation update

The most active 2024–2026 area, much of it inside the GraphRAG family:

- **LightRAG** (2024) — explicit incremental index patching; ~60% reduction in re-indexing token cost vs. rebuild.
- **HippoRAG / HippoRAG-2** (Gutiérrez et al. 2024–2025) — Personalized PageRank over an open KG; non-parametric continual-learning framework; adds new triples without retraining.
- **Microsoft GraphRAG** (Edge et al. 2024) — community-detection KG over a doc corpus. Explicitly acknowledges that "graph indices grow super-linearly with corpus size, complicating incremental updates"; their library now ships incremental re-build of affected community summaries.
- **Entity-Event KGs for RAG** (arXiv 2506.05939, Jun 2025) — adds explicit temporal-causal nodes so "the same entity at $t$ vs. $t+1$" is representable.
- **RAG Meets Temporal Graphs** (arXiv 2510.13590, Oct 2025) — every fact carries a validity interval; queries time-scoped.
- **GAM-RAG** (arXiv 2603.01783, Mar 2026) — gain-adaptive memory that scores when to overwrite stale facts.
- **KCoEvo** (arXiv 2603.07581, Mar 2026) and **SemanticForge** (arXiv 2511.07584, Nov 2025) — KG-augmented frameworks specifically targeting code/API evolution; model rename/relocate/deprecate as first-class edges in a version-aware KG.

### Downstream of P1 + P3 — contradiction detection in RAG answers

- **RAGTruth** (Wu et al., ACL 2024) — 18k naturally-generated RAG responses; word-level hallucination/contradiction labels; span-level IAA 78.8%. The most-cited corpus for "answer disagrees with retrieved evidence."
- **Contradiction Detection in RAG Systems** (arXiv 2504.00180, Apr 2025) — benchmarks NLI vs. LLM-judge vs. hybrid as context validators.
- **LegalWiz** (arXiv 2510.03418, Oct 2025) — multi-agent contradiction detection across legal docs (multi-doc, not just sentence-pair).
- **DocNLI** (Yin et al. 2021) — still the canonical document-level NLI corpus.

---

## 3. Industrial SOTA

Different products optimize different sub-problems. No vendor solves the full P1+P2+P3 loop.

**Sourcegraph Cody** — best public design for incremental code-index update:

- Per-commit, "outdated embeddings of deleted and modified files are removed; new embeddings of modified and added files are added." Default 24h debounce.
- Architecture: vector embeddings + lexical search + SCIP/LSIF code-intel, fused at retrieval. **The LSIF layer is what gives entity-level identity** — that's what makes per-symbol patches safe (the underlying problem #2 from §5).
- Doesn't tackle code ↔ doc consistency — keeps the vector index synced to file content only.

**Glean** — best public design for enterprise-graph incremental maintenance:

- Per-source change-rate tracked; index "identifies and incorporates changes that have occurred since the last crawl."
- Permission-aware patches (every patch carries permission state, re-checked at serve time) — multi-party concurrency applied to access control.
- Explicit hybrid live/indexed: "use the index for broad recall and the API for recent rows, long-tail objects, or attributes that are not stored in the index." Frank admission that the index will always be slightly stale; design around it.

**GitHub Copilot Workspace / Cursor / Continue.dev** — file-watcher: changes trigger re-embedding of affected files. No public cross-file-drift design.

**Microsoft GraphRAG (OSS)** — incremental indexers that rebuild only affected community summaries; otherwise treats the build as a batch job.

**Docs-as-code tooling — the doc-side analog.** Where the 2024–2026 startup wave is concentrated:

- **Doc Detective** — parses markdown, *executes* documented procedures, validates against OpenAPI schemas. If a doc says `make -C runtime/opae` and that directory is gone, the test fails.
- **DocDrift** — diffs each commit against linked docs with LLMs to flag "documentation is wrong/incomplete/missing." Closest direct analog to what would have caught the Vortex `fpga_setup.md` drift.
- **Doctective / DeepDocs / Fern** — all market "doc-CI": link doc paragraphs to code symbols (via tree-sitter / LSIF), block PRs that change a symbol without touching its linked doc.

**Stripe / Google** — the "process" answer: cultural enforcement in code review that API-surface PRs include doc updates. Documented as practice, not as tooling. The absence of widely-adopted gates is what the doc-CI tooling wave is trying to fill.

---

## 4. Benchmarks

| Benchmark | Sub-problem | What it measures |
|---|---|---|
| **JITDATA, CCIBENCH, CUP2** | P1 (comment) | JIT inconsistency between code diff and adjacent comment |
| **DocChecker benchmark** (2023) | P1 (function doc) | Function-level code-doc consistency |
| **CodeFuse-CommitEval** (2025) | P1 (commit msg) | Commit message ↔ diff inconsistency |
| **DocNLI** (2021) | P1 (general) | Document-level NLI for entailment / contradiction across paragraphs |
| **"Wait, wasn't that code here before?"** companion dataset (2023) | P1 (doc-level) | Outdated software doc detection on mined OSS pairs |
| **RAGTruth** (2024) | P1 + P3 downstream | Word-level hallucination / contradiction of RAG answers vs. context |
| **Contradiction Detection in RAG Systems** (2025) | P1 + P3 downstream | LLM-as-validator over retrieved snippets |
| **ECT-QA** (2025) | P3 | Base / updated-corpus query splits; tests RAG under incremental updates |
| **FreshQA / RealtimeQA / StreamingQA** | P3 (general) | RAG freshness on evolving external knowledge |
| **SWE-bench** | adjacent P2 | PR reproducibility; the failing-then-passing test set is the impact-propagation oracle |
| **API-evolution benchmarks** (KCoEvo, SemanticForge eval sets) | P3 (code) | Version-consistent code generation across API renames |

**The critical gap.** No widely-adopted benchmark measures the full P1 + P2 + P3 loop on a real evolving software repo over time. You would need a corpus that:

1. pins a sequence of commits,
2. annotates code-doc agreement at each step,
3. labels which doc edits *should* have accompanied which code edits, and
4. scores the agent's ability to *detect → attribute → repair*.

The Vortex `runtime/opae` removal is exactly the kind of instance such a benchmark would mine. Existing corpora (ECT-QA, CodeFuse-CommitEval, JITDATA) each cover one slice — nobody has stitched them on a single evolving codebase with annotated authority and ground-truth co-edits.

---

## 5. Open challenges

1. **Authority arbitration.** Current SOTA defaults to "code wins" because code is executable. For published APIs and contract docs this is wrong. No good open mechanism for declaring per-artifact authority — closest is OpenAPI / JSON Schema, which only covers structured contracts.
2. **Cross-modal stable entity IDs.** Code has LSIF / SCIP; docs have tree-sitter span IDs; KGs have URIs. Stable IDs *across* these modalities — so a rename in one carries to the others — is an unsolved engineering problem.
3. **Semantic multi-party merge.** Two PRs each locally consistent that produce a globally inconsistent merge: theorized via CRDT-for-semantics, not deployed.
4. **Super-linear incremental graph cost.** Community-summary methods (GraphRAG, HippoRAG) suffer here. LightRAG and entity-event KGs are the current scaling attempts.
5. **Evaluation under drift.** RAG-agent benchmarks are almost all static-snapshot. There is no standard for "the corpus changes during evaluation; how robust is the agent?" — which is precisely the deployment condition.
6. **Doc-CI gate reliability.** Doc-CI tooling is at the maturity of code-CI circa 2010 — known valuable, tools exist, adoption patchy. The open question is whether LLM-based gates are reliable enough that false-positive blocks aren't a dev-experience killer.

The highest-leverage open contribution is **a P1 + P2 + P3 benchmark grounded in real OSS commit history** — the closest existing artifacts (ECT-QA + CodeFuse-CommitEval + JITDATA) each have one piece; nobody has stitched them on a single evolving codebase with annotated authority and ground-truth co-edits.

---

## Sources

- [Wait, wasn't that code here before? Detecting Outdated Software Documentation (Aghajani et al., arXiv 2307.04291)](https://arxiv.org/pdf/2307.04291)
- [CodeFuse-CommitEval: Towards Benchmarking LLM's Power on Commit Message and Code Change Inconsistency Detection (arXiv 2511.19875)](https://arxiv.org/pdf/2511.19875)
- [Larger Is Not Always Better: Leveraging Structured Code Diffs for Comment Inconsistency Detection (arXiv 2512.19883)](https://arxiv.org/html/2512.19883v2)
- [Code Comment Inconsistency Detection and Rectification Using a Large Language Model (ResearchGate)](https://researchgate.net/publication/392955493_Code_Comment_Inconsistency_Detection_and_Rectification_Using_a_Large_Language_Model)
- [Investigating the Impact of Code Comment Inconsistency on Bug Introducing (arXiv 2409.10781)](https://arxiv.org/html/2409.10781v1)
- [Deep Just-In-Time Inconsistency Detection Between Comments and Source Code (arXiv 2010.01625)](https://arxiv.org/abs/2010.01625)
- [Code Comment Inconsistency Detection with BERT and Longformer (Steiner & Zhang, Semantic Scholar)](https://www.semanticscholar.org/paper/Code-Comment-Inconsistency-Detection-with-BERT-and-Steiner-Zhang/f60e9d2e7a39fb86ab5f1652d64a7b728c9efd92)
- [panthap2/deep-jit-inconsistency-detection (canonical CCI artifact, GitHub)](https://github.com/panthap2/deep-jit-inconsistency-detection)
- [RAGTruth: A Hallucination Corpus for Developing Trustworthy Retrieval-Augmented Language Models (Wu et al., ACL 2024)](https://aclanthology.org/2024.acl-long.585/)
- [Contradiction Detection in RAG Systems: Evaluating LLMs as Context Validators (arXiv 2504.00180)](https://arxiv.org/pdf/2504.00180)
- [LegalWiz: A Multi-Agent Framework for Contradiction Detection in Legal Documents (arXiv 2510.03418)](https://arxiv.org/pdf/2510.03418)
- [Respecting Temporal-Causal Consistency: Entity-Event Knowledge Graphs for Retrieval-Augmented Generation (arXiv 2506.05939)](https://arxiv.org/pdf/2506.05939)
- [RAG Meets Temporal Graphs: Time-Sensitive Modeling and Retrieval for Evolving Knowledge (arXiv 2510.13590)](https://arxiv.org/pdf/2510.13590)
- [GAM-RAG: Gain-Adaptive Memory for Evolving Retrieval (arXiv 2603.01783)](https://arxiv.org/pdf/2603.01783)
- [Retrieval-Augmented Generation with Knowledge Graphs: A Survey (OpenReview)](https://openreview.net/forum?id=ZikTuGY28C)
- [A Systematic Review of Key Retrieval-Augmented Generation (RAG) Systems (arXiv 2507.18910)](https://arxiv.org/pdf/2507.18910)
- [Beyond Static Retrieval: Opportunities and Pitfalls of Iterative Retrieval in GraphRAG (arXiv 2509.25530)](https://arxiv.org/pdf/2509.25530)
- [KCoEvo: A Knowledge Graph Augmented Framework for Evolutionary Code Generation (arXiv 2603.07581)](https://arxiv.org/html/2603.07581)
- [SemanticForge: Repository-Level Code Generation through Semantic Knowledge Graphs (arXiv 2511.07584)](https://arxiv.org/pdf/2511.07584)
- [Temporal Reasoning with LLMs Augmented by Evolving Knowledge Graphs (arXiv 2509.15464)](https://arxiv.org/pdf/2509.15464)
- [To change or not to change? Modeling software system interactions using Temporal Graphs and GNNs (ScienceDirect)](https://www.sciencedirect.com/science/article/abs/pii/S0950584923002239)
- [Why CI/CD Still Doesn't Include Continuous Documentation (DeepDocs)](https://deepdocs.dev/why-ci-cd-still-doesnt-include-continuous-documentation/)
- [Doc Detective — Docs-as-tests for Markdown / OpenAPI (Hacker News overview)](https://news.ycombinator.com/item?id=47526603)
- [Docs Linting Guide (Fern, 2026)](https://buildwithfern.com/post/docs-linting-guide)
- [A Key to High-Quality Documentation: Docs Linting in CI/CD (Netlify)](https://www.netlify.com/blog/a-key-to-high-quality-documentation-docs-linting-in-ci-cd/)
- [Sourcegraph Cody — Incremental embeddings (docs)](https://docs.sourcegraph.com/cody/core-concepts/embeddings)
- [Sourcegraph Cody — Generate an Embeddings Index (docs)](https://docs.sourcegraph.com/cody/core-concepts/embeddings/embedding-index)
- [The Glean Knowledge Graph (Glean)](https://www.glean.com/resources/guides/glean-knowledge-graph)
- [Glean — Crawling & Learning Process (docs)](https://docs.glean.com/get-started/learn/crawling-and-learning)
