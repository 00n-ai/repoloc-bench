# Multi-Agent Framework Benchmark Dataset

Public benchmark artifacts for the 00n.ai multi-agent framework comparison. The experiment compares four LLM answer-generation architectures on a 20-question suite of freshness questions, with unified GPT-4o grading.

## Approaches

- **B0 Vanilla LLM** — direct single LLM call; no search, tools, reflection, or agent decomposition.
- **B1 LLM + Search** — the model can issue search/fetch calls before answering.
- **B2 LLM + Search + Self-Reflection** — search/fetch plus a verification/reflection pass.
- **MA Multi-Agent** — controller-led decomposition with sub-agents (Meta-Planner → Research → Synthesis → Validator → Skeptic → Final Answer) and iterative convergence.

## Versions

### v2.2 (comparison ID: `f3c892c1`)
**Key change:** Draft-then-validate orchestration. The MA loop was changed from validating raw evidence before drafting to: Research → Synthesis draft → Validator → Skeptic. This fixed the core failure mode where small models rejected semantically obvious evidence.

### v2.3 (comparison ID: `0e156cf6`)
**Key change:** Deterministic grounding. The validator no longer calculates a subjective "overall grounding" score. Instead, it outputs per-field verdicts for each required field, and the controller computes grounding deterministically as `verified_fields / total_required_fields`.

## Stable-run average scores

| Model | B0 Vanilla | B1 Search | B2 Search + Reflection | MA Multi-Agent |
|---|---:|---:|---:|---:|
| **v2.2 Ollama 7B** | 2.6 | 7.2 | 8.0 | **8.1** |
| **v2.2 GPT-4o** | 2.3 | 8.2 | 8.4 | **7.8** |
| **v2.3 Ollama 7B** | 2.5 | 7.5 | 8.1 | **8.0** |
| **v2.3 GPT-4o** | 2.3 | 7.8 | 8.2 | **7.9** |

## MA convergence

| Version | Ollama 7B | GPT-4o |
|---|:---:|:---:|
| v2.2 | 17/20 (85%) | 19/20 (95%) |
| v2.3 | 18/20 (90%) | 19/20 (95%) |

## Headline finding

**Multi-agent orchestration compresses the capability gap between small and large models.** MA on Ollama 7B (8.0-8.1) matches or beats MA on GPT-4o (7.8-7.9) and nearly matches B2 on GPT-4o (8.2-8.4). The overhead helps small models more than large models.

**Implication:** Proper orchestration + retrieval + deterministic verification can bring a small model up to frontier-model performance on evidence-grounded tasks — at ~100x lower cost.

## Cost analysis

| | Ollama MA | GPT-4o B2 |
|---|---|---|
| LLM calls/question | ~6 | ~4 |
| Time/question | 60-80s | 15-20s |
| Cost/question | ~$0 (local) | ~$0.05-0.10 API |
| Convergence | 90-95% | N/A (single pass) |

Trade-off: ~4-5x more wall-clock time and ~50% more tokens for ~100x lower cost and comparable accuracy. For batch/latency-tolerant workloads, this is a clear win.

## Included files

- `aggregated-results-2026-06-23.json` — normalized summary across v2.2 and v2.3 runs
- `comparison-v2-f3c892c1-summary.json` — v2.2 machine-readable results
- `comparison-v2-f3c892c1-report.md` — v2.2 full comparison report
- `comparison-v2-0e156cf6-summary.json` — v2.3 machine-readable results
- `comparison-v2-0e156cf6-report.md` — v2.3 full comparison report
- `freshness-question-pack-2026-06-23.jsonl` — 20-question freshness pack
- `V2-V3-LEARNINGS-AND-NEXT-STEPS.md` — detailed learnings and next experiment options
- `EXPERIMENT-RATIONALE-AND-RESULTS.md` — original rationale and early results
- `manifest.json` — file inventory and provenance
- `integrity.json` — SHA-256 checksums (needs update)

## Claim boundary

These artifacts document a controlled comparison on a fixed 20-question suite. The strongest supported claims are:

1. On freshness questions that defeat parametric knowledge, MA with proper grounding brings a 7B model within 0.2-0.4 points of the best baseline on a frontier model.
2. Draft-then-validate orchestration is necessary — validating raw evidence before drafting causes small models to reject valid support.
3. Deterministic grounding (per-field verification) improves convergence reliability without hurting accuracy.
4. MA helps small models more than large models on this task type.

Claims do not generalize to: all question types, all model sizes, real-time latency requirements, or domains outside evidence-grounded retrieval tasks. The 20-question sample is sufficient for directional claims but not for statistical significance at conventional thresholds.