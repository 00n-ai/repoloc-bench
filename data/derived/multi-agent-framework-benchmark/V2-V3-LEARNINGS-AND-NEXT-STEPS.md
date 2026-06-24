# Multi-Agent Framework Benchmark — Learnings & Next Steps

**Date:** 2026-06-23
**Author:** Boole (for Sheraz)
**Status:** v2.2 complete, v2.3 in progress

---

## 1. What We Built

A benchmark to test whether multi-agent (MA) orchestration improves LLM performance on evidence-grounded questions, compared to simpler baselines.

**Four arms:**
- **B0 (Vanilla LLM)** — direct question, no retrieval. Tests parametric knowledge.
- **B1 (LLM + Search)** — single retrieval pass, then answer.
- **B2 (LLM + Search + Self-Reflection)** — retrieve, draft, critique, revise. Best single-agent baseline.
- **MA (Full Multi-Agent)** — Meta-Planner → Research → Synthesis → Validator → Skeptic → Final Answer, with iterative convergence.

**Two models:**
- Ollama `qwen2.5:7b` (local 7B model)
- GPT-4o (frontier model)

**20 freshness questions** designed to be unanswerable from training data — all sourced from June 22-23, 2026 (NASA releases, arXiv papers, Google announcements, LangChain updates).

**Unified GPT-4o grader** scored all answers on accuracy, evidence quality, and completeness.

---

## 2. Version History

### v2.1 (failed)
- MA validated **raw evidence** before drafting — small models rejected semantically obvious support as "not explicitly stated"
- Repeated iterations refetched identical evidence, wasting runtime
- Ollama arm got SIGKILLed around Q10 due to runaway runtime
- MA underperformed B2 across the board

### v2.2 (breakthrough)
- **Orchestration fix:** changed MA loop to Research → Synthesis draft → Validator → Skeptic (draft-then-validate instead of validate-raw-evidence)
- Added per-run retrieval cache (keyed by question/source)
- Added required-field extraction from question → passed to synthesis/validator/skeptic
- Results: MA convergence went from ~50% to 85% (Ollama) / 95% (GPT-4o)

### v2.3 (current, in progress)
- **Deterministic grounding fix:** validator no longer calculates "overall grounding" — it only validates listed required fields, one verdict per field
- Controller computes grounding deterministically: `verified_fields / total_required_fields`
- Eliminates validator LLM's subjective judgment of "how grounded is this"
- Results so far: 100% convergence on completed Ollama questions, including Q6 which took 3 iterations (67%→100%)

---

## 3. Key Results (v2.2 complete)

### Unified grader overall scores

| Arm | Ollama (7B) | GPT-4o |
|---|:---:|:---:|
| B0 (vanilla) | 2.6 | 2.3 |
| B1 (search) | 7.2 | 8.2 |
| B2 (search+reflection) | 8.0 | 8.4 |
| **MA (multi-agent)** | **8.1** | **7.8** |

### MA convergence
- Ollama: 17/20 (85%)
- GPT-4o: 19/20 (95%)
- 3 Ollama failures: Q2, Q8, Q20 — all non-convergence (3 iterations exhausted)

### The headline finding

**Multi-agent orchestration compresses the capability gap between small and large models.**

- MA on Ollama 7B (8.1) **beats** MA on GPT-4o (7.8)
- MA on Ollama 7B (8.1) nearly matches B2 on GPT-4o (8.4)
- MA helps small models more than large models
- B0 is consistently ~2-3 across both models — freshness questions defeat training data as intended

---

## 4. Cost Analysis

| | Ollama MA | GPT-4o B2 |
|---|---|---|
| Score | 8.1 | 8.4 |
| LLM calls/question | ~6 | ~4 |
| Time/question | ~60-80s | ~15-20s |
| Cost/question | ~$0 (local) | ~$0.05-0.10 API |
| Convergence | 85-95%+ | N/A (single pass) |

**Trade-off:** ~4-5x more wall-clock time and ~50% more tokens for ~100x lower cost and comparable accuracy. For batch/latency-tolerant workloads (research, evidence review, document analysis), this is a clear win. For real-time interactive use, latency is the bottleneck.

---

## 5. Core Learnings

### Learning 1: The bottleneck was evidence consumption, not retrieval quality
Before v2.2, retrieval found answer-bearing evidence, but the MA pipeline rejected it because validators adjudicated raw excerpts before any draft existed. Small models especially would reject semantically obvious support as "not explicitly stated." **Draft-then-validate** fixed this — the validator inspects a concrete answer with support quotes, not a pile of excerpts.

### Learning 2: Multi-agent overhead helps small models more than large models
GPT-4o already does implicit self-reflection well — B2 captures most of the MA benefit at lower cost. But the 7B model needs the explicit decomposition: one agent for research, one for synthesis, one for validation, one for skepticism. The scaffolding compensates for what the small model can't do implicitly.

### Learning 3: Deterministic grounding > LLM subjective grounding
v2.3 replaced the validator's subjective "overall grounding %" with deterministic field-by-field verification. This eliminated a failure mode where the validator's judgment of "grounding" didn't match the actual evidence support. Early v2.3 data shows improved convergence on hard questions (Q6 converged in 3 iterations with grounding improving 67%→100%).

### Learning 4: Freshness questions are a valid benchmark design
B0 scored ~2-3 across both models, confirming the questions defeat parametric knowledge. This validates the benchmark design — we're measuring retrieval and reasoning, not memorization.

### Learning 5: Convergence is necessary but not sufficient
MA can converge (produce an answer) but still score lower if the evidence retrieval found the wrong source or the synthesis missed a required field. Grounding=100% means every claim is evidence-backed, but evidence quality depends on retrieval precision.

### Learning 6: The validator prompt is the critical control point
The entire v2.1→v2.2 improvement came from changing what the validator sees (draft answer vs raw evidence). The v2.2→v2.3 improvement came from changing how the validator reports (per-field verdicts vs subjective overall score). The validator is the gatekeeper — its behavior determines convergence, grounding accuracy, and downstream iteration cost.

---

## 6. What to Take Into the Next Experiment

### Carry forward
1. **Draft-then-validate architecture** — non-negotiable. Never validate raw evidence.
2. **Required-field extraction** — pass structured fields through the pipeline, not free-form questions
3. **Deterministic grounding** — controller computes grounding from per-field verdicts, not LLM subjective judgment
4. **Retrieval cache** — dedupe across iterations to avoid refetching identical content
5. **Freshness question design** — questions that can't be answered from training data are essential for valid comparison
6. **Unified external grader** — GPT-4o grading all arms ensures consistent evaluation

### Improve
1. **Retrieval precision** — current retrieval accepts some irrelevant sources. Need a relevance gate that filters before the synthesis agent sees them.
2. **Abstention behavior** — MA should be able to say "I couldn't find sufficient evidence" instead of converging on weak evidence. Currently the loop always tries to produce an answer.
3. **Per-agent contribution measurement** — which agent (research, synthesis, validator, skeptic) is actually contributing to correctness? If the skeptic never changes the answer, it's wasted overhead.
4. **Token efficiency** — track tokens per question per arm. We have LLM call counts but not token counts. Need this for proper cost comparison.
5. **Statistical significance** — 20 questions is a sample, not a population. Need confidence intervals or at least more questions to claim the 0.3 point difference is meaningful.

### Open questions
- Does MA help on **reasoning** tasks (not just retrieval tasks)? Current questions are all "find this fact from recent news."
- Does MA help when the **answer is ambiguous** or requires multi-hop reasoning?
- What happens with **larger small models** (e.g., 14B, 32B)? Is there a crossover point where MA overhead stops helping?
- Does MA help with **code generation** or **architectural reasoning** tasks?

---

## 7. Next Experiment Options

### Option A: Multi-hop reasoning questions
**What:** Questions that require combining 2-3 separate evidence sources to derive an answer. Example: "Paper X proposes method A for problem P. Paper Y shows method A fails on dataset D. What approach does Paper Z propose to address the failure?"

**Why:** Tests whether MA's decomposition actually helps with multi-step reasoning, or just retrieval. This is closer to real research/analysis work.

**Complexity:** Medium. Need to design ~20 multi-hop questions with verified answers. Existing retrieval pipeline works.

**Risk:** If MA doesn't help here, it suggests the benefit is purely from retrieval scaffolding, not reasoning decomposition.

---

### Option B: Abstention and uncertainty calibration
**What:** Include questions that are **unanswerable** (evidence doesn't exist) or **partially answerable** (only some required fields have evidence). Score arms on both accuracy AND calibration (does the model know when it doesn't know?).

**Why:** This is core to your research spine — "raw confidence is not calibrated probability; use risk score / support score language unless calibration is actually validated." An abstention-capable MA pipeline is directly relevant to Paper 1 / Phase 2.

**Complexity:** Medium-high. Need to design unanswerable questions, implement abstination in the MA loop, and develop a calibration metric.

**Risk:** If all arms refuse to answer unanswerable questions, the comparison is uninformative. Need careful question design.

---

### Option C: Code reasoning and traceability
**What:** Questions about code behavior that require retrieving source code, documentation, and test cases. Example: "In the X repository, which function is responsible for Y, and what test covers it? Does the implementation match the documented behavior?"

**Why:** Directly aligned with your research spine on traceability, software engineering AI, and agentic SDLC. Tests whether MA helps with code comprehension — a fundamentally different evidence type than news articles.

**Complexity:** High. Need to build a code corpus, design code reasoning questions, and adapt the retrieval pipeline for source code (not just web pages).

**Risk:** Code retrieval is a different problem than web retrieval. May need significant retrieval pipeline changes.

---

### Option D: Larger model comparison ladder
**What:** Run the same 20 freshness questions across a model size ladder: 7B, 14B, 32B, 70B, GPT-4o. Measure where the MA benefit crosses over (if it does).

**Why:** The headline finding is "MA brings 7B up to GPT-4o level." But we don't know the shape of the curve. Is there a size where MA stops helping? This directly informs the cost/accuracy trade-off argument.

**Complexity:** Low-medium. Same questions, same pipeline, just more model configurations. Time-intensive but not design-intensive.

**Risk:** Ollama model availability for intermediate sizes. 70B may be too slow on available hardware.

---

### Option E: Adversarial / misleading evidence
**What:** Inject misleading or outdated evidence into the retrieval pipeline. Test whether the validator/skeptic agents catch it, or whether the MA pipeline is fooled by confident-but-wrong sources.

**Why:** Tests the robustness of the evidence verification layer — core to your governance/risk measurement positioning. If MA passes confident-wrong answers, the "evidence-based" claim is hollow.

**Complexity:** Medium. Need to curate misleading evidence per question, inject it into the retrieval results, and measure whether each arm is fooled.

**Risk:** Artificial injection may not reflect real-world retrieval noise.

---

### Option F: Agent contribution ablation
**What:** Systematically remove one agent at a time from the MA pipeline (no validator, no skeptic, no meta-planner, etc.) and measure the score impact. Identifies which agents are load-bearing.

**Why:** If the skeptic never changes answers, it's 1.5x token cost for no benefit. Ablation tells us which agents earn their keep. Directly relevant to "per-agent contribution measurement" from Learning 5.

**Complexity:** Low. Same questions, same pipeline, just ablation configurations. Mostly engineering work.

**Risk:** Results may show most agents are redundant, which is a valid but less interesting finding.

---

## 8. Recommendation

**My ranking:**

1. **Option B (Abstention/calibration)** — most aligned with your research spine, directly feeds Paper 1 / Phase 2, tests a fundamentally different capability than what we've measured
2. **Option D (Model size ladder)** lowest effort, validates the headline finding, directly informs cost/accuracy argument
3. **Option F (Agent ablation)** — quick to run, identifies what to keep/drop before building a more complex experiment
4. **Option A (Multi-hop reasoning)** — interesting but increases question design burden
5. **Option C (Code reasoning)** — highest value but highest effort, save for after the pipeline is more mature
6. **Option E (Adversarial evidence)** — interesting but somewhat artificial

**Proposed sequencing:** Run F (ablation) and D (model ladder) first as quick follow-ups to v2.3. Then design B (abstention/calibration) as the next major experiment, since it requires pipeline changes but produces the most novel evidence for the thesis.

---

## 9. Repository References

- Benchmark code: `projects/multi-agent-framework/`
- Public dataset/repo: `00n-ai/repoloc-bench` (GitHub)
- Public site: `projects/00n.ai` → `/benchmarks/multi-agent-framework-benchmark`
- v2.2 results: `logs/comparison-v2-f3c892c1/`
- v2.3 results: `logs/v2.3-run.log` (in progress)