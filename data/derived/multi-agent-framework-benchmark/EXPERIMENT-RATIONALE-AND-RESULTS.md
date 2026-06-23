# Multi-Agent Framework Experiment — Rationale and Results

Date: 2026-06-23

## Objective

Evaluate whether a structured multi-agent answer pipeline improves answer quality compared with simpler baselines, especially when questions require evidence gathering, calibration, and resistance to false premises.

The experiment compares four approaches:

1. **B0: Vanilla LLM** — one direct model answer, no tools and no search.
2. **B1: LLM + Search** — one model generates search queries, retrieves/fetches sources, and answers from evidence.
3. **B2: LLM + Search + Reflection** — search-based answer followed by critique and revision.
4. **MA: Multi-Agent** — planner, researcher, skeptic, validator, synthesis, and final-answer roles with iterative convergence checks.

## Why vanilla matters

"Vanilla" measures the model's built-in or parametric knowledge: what it can answer from training plus reasoning without external retrieval. If B0 performs well, that usually means the question is stable, common, or broadly represented in model training data. If the goal is to test retrieval and multi-agent value, B0 should not be expected to already know the answer.

## Why we are adding a freshness question pack

The initial 20-question set mixed stable legal/technical/medical questions with some niche/recent research questions. Results showed that strong models can answer many of these directly from prior knowledge. That makes it hard to isolate the value of search or multi-agent orchestration.

The new question pack is intentionally time-sensitive and source-anchored. It uses items published in the last 24–48 hours, such as NASA releases, arXiv preprints, a Google Developers post, and GitHub release-feed facts. These questions ask for exact details from newly published sources. The intended effect is:

- B0 should often be uncertain or wrong because the information is too new.
- B1/B2 should improve if search finds the right source and the model uses it correctly.
- MA should improve further if planning, skepticism, validation, and synthesis reduce retrieval drift and hallucination.

This creates a stronger test of retrieval and orchestration, not just model memory.

## Completed 20-question experiment results

Both current 20-question runs completed successfully and produced comparison reports.

### GPT-4o run

- Summary artifact: `comparison-v2-06965864-summary.json`
- Report artifact: `comparison-v2-06965864-report.md`
- Questions complete: 20/20
- Unified grader: GPT-4o

Unified overall averages:

| Approach | Count | Avg Overall /10 |
|---|---:|---:|
| B0: Vanilla LLM | 20 | 6.50 |
| B1: LLM + Search | 20 | 5.83 |
| B2: LLM + Search + Reflection | 20 | 6.34 |
| MA: Multi-Agent | 20 | 5.54 |

Interpretation:

- GPT-4o's vanilla baseline was strong because many questions were stable, broad, or already present in model knowledge.
- Search did not automatically improve quality; retrieval sometimes added noisy or weakly relevant evidence.
- Reflection recovered some quality versus simple search, but still did not beat vanilla on average.
- The multi-agent workflow was more expensive and did not outperform the simpler baselines on this set. Likely reasons: the questions did not consistently require deep retrieval, and the pipeline may have accumulated retrieval noise or overcomplicated answers.

### Ollama/qwen2.5:7b run

- Summary artifact: `comparison-v2-219881f7-summary.json`
- Report artifact: `comparison-v2-219881f7-report.md`
- Questions complete: 20/20
- Unified grader: GPT-4o

Unified overall averages:

| Approach | Count | Avg Overall /10 |
|---|---:|---:|
| B0: Vanilla LLM | 20 | 6.42 |
| B1: LLM + Search | 20 | 2.21 |
| B2: LLM + Search + Reflection | 20 | 2.70 |
| MA: Multi-Agent | 20 | 4.94 |

Interpretation:

- Ollama's vanilla answers were often reasonable on stable/common topics.
- The simple search baselines performed poorly, apparently because query generation, retrieval selection, and evidence use were brittle; several answers drifted to irrelevant fetched content.
- The multi-agent approach substantially improved over Ollama's simple search baselines, suggesting that planner/researcher/skeptic/validator structure helps weaker models recover from retrieval noise.
- However, MA still did not beat Ollama vanilla on the original set, again indicating the benchmark did not sufficiently force retrieval.

## Current hypothesis

The original benchmark primarily measured a mix of parametric knowledge and general reasoning. It was not hard enough on freshness/source specificity. Therefore, the apparent underperformance of multi-agent orchestration may be partly a benchmark-design artifact: when the answer is already in the model, extra retrieval and agents can add latency, noise, and failure modes.

The new freshness pack should better test the actual question we care about:

> When the model does not already know the answer, does search/reflection/multi-agent orchestration produce more accurate, better-cited, and better-calibrated answers than vanilla?

## Freshness pack

- File: `freshness-question-pack-2026-06-23.jsonl`
- Questions: 20
- Includes answer keys and source URLs.
- Designed to be regenerated daily or per run, because freshness decays quickly.

## Runner updates made for the freshness experiment

`src/compare-v2.js` now supports:

- `--questions-file <path.jsonl>` for loading external JSONL question packs.
- Per-question `answer`, `source`, and `id` metadata.
- Summary/report inclusion of answer keys and sources.

`src/baselines.js` grading now supports:

- Optional authoritative answer key and source context.
- Unified grader instructions to grade against the answer key instead of relying on the grader's own memory.

Validation run:

- `node --check src/compare-v2.js` passed.
- `node --check src/baselines.js` passed.
- `npm test` passed; there are currently zero Node test files.

## Restart note for fresh run

The first fresh-pack attempt created comparison ID `75fc5bfc`, but it was stopped during Q1 because the multi-agent controller had captured `gpt-4o` at module import time and tried to use that model even during the Ollama run. `src/controller.js` was patched so multi-agent calls resolve `process.env.LLM_MODEL` dynamically at execution time, matching the baseline behavior.

Additional validation after this patch:

- `node --check src/controller.js` passed.
- `npm test` passed; there are currently zero Node test files.
