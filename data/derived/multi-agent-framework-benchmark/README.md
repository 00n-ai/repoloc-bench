# Multi-Agent Framework Benchmark Dataset

Public benchmark artifacts for the 00n.ai multi-agent framework comparison. The experiment compares a direct single-model answer path against retrieval-augmented and multi-agent paths on a fixed 20-question suite, with unified GPT-4o grading.

## Approaches

- **B0 Vanilla LLM** — direct single LLM call; no search, tools, reflection, or agent decomposition.
- **B1 LLM + Search** — the model can issue search/fetch calls before answering.
- **B2 LLM + Search + Self-Reflection** — search/fetch plus a verification/reflection pass.
- **MA Multi-Agent** — controller-led decomposition with sub-agents and synthesized final answer.

## Included files

- `aggregated-results-2026-06-23.json` — normalized summary across stable completed runs.
- `comparison-v2-06965864-summary.json` — GPT-4o stable 20-question run machine-readable results.
- `comparison-v2-06965864-report.md` — GPT-4o stable 20-question run report.
- `comparison-v2-219881f7-summary.json` — Ollama/qwen2.5:7b stable 20-question run machine-readable results.
- `comparison-v2-219881f7-report.md` — Ollama/qwen2.5:7b stable 20-question run report.
- `freshness-question-pack-2026-06-23.jsonl` — 20-question freshness/retrieval stress pack built from recent public facts.
- `EXPERIMENT-RATIONALE-AND-RESULTS.md` — rationale, interpretation, and result notes.
- `manifest.json` — file inventory, provenance, and claim boundaries.
- `integrity.json` — SHA-256 checksums and byte sizes.

## Stable-run average scores

| Model | B0 Vanilla | B1 Search | B2 Search + Reflection | MA Multi-Agent |
|---|---:|---:|---:|---:|
| GPT-4o | 6.50 | 5.83 | 6.34 | 5.54 |
| Ollama/qwen2.5:7b | 6.42 | 2.21 | 2.70 | 4.94 |

## Claim boundary

These artifacts document an exploratory framework-level comparison, not a universal claim that one architecture always dominates. The strongest supported observation is narrower: under this harness, naïve search and naïve multi-agent decomposition can add retrieval noise, synthesis burden, latency, and failure modes; benefits depend on task design, source quality, routing, and verification discipline.

The freshness question pack is included as a public evaluation input. Full fresh-run result artifacts should be added separately after the long-running run completes and is reviewed.
