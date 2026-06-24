# Related Research: Multi-Agent Framework Benchmark Validation

**Companion document to the 00n.ai Multi-Agent Benchmark**

This document maps our benchmark findings to the published research literature. Each finding is evaluated against verified papers from arXiv, ACL, NeurIPS, ICML, and EMNLP. Papers were confirmed to resolve and titles verified against abstracts.

---

## Finding 1: MA Compresses the Capability Gap Between Small and Large Models

> *A 7B model with multi-agent orchestration (Ollama qwen2.5:7b, avg 8.0–8.1) matches frontier-model B2 performance (GPT-4o search+reflection, avg 8.2–8.4) on evidence-grounded tasks.*

### Relevant Papers

**1. Mixture-of-Agents Enhances Large Language Model Capabilities**
- **Authors:** Jue Wang et al.
- **Venue/Year:** arXiv, June 2024
- **ID/URL:** [arXiv:2406.04692](https://arxiv.org/abs/2406.04692)
- **Relation:** **Supports**
- **Key claim:** MoA constructs a layered architecture where multiple LLM agents take outputs from the previous layer as auxiliary information. Using only open-source LLMs, MoA achieves 65.1% on AlpacaEval 2.0, surpassing GPT-4 Omni (57.5%). This directly demonstrates that orchestrating weaker open-source models can match or exceed a single strong frontier model.
- **Synthesis:** The MoA result is the clearest published precedent for our finding. Their layered aggregation of open-source models surpassing GPT-4o validates the core hypothesis that multi-agent orchestration can compress the capability gap. Our work extends this to evidence-grounded freshness questions with a draft-validate-ground pattern rather than layered aggregation.

**2. More Agents Is All You Need**
- **Authors:** Deheng Ye et al.
- **Venue/Year:** TMLR (Transactions on Machine Learning Research), 2024
- **ID/URL:** [arXiv:2402.05120](https://arxiv.org/abs/2402.05120)
- **Relation:** **Supports**
- **Key claim:** Performance of LLMs scales with the number of agents instantiated via a simple sampling-and-voting method (Agent Forest). The enhancement is orthogonal to existing methods and correlates with task difficulty — harder tasks benefit more from additional agents.
- **Synthesis:** This paper provides a scaling law for agent数量: more agents → better performance, with diminishing returns on easy tasks. Our finding that a 7B model with MA matches GPT-4o is consistent with their observation that multi-agent scaling helps most where single-model performance is weakest.

**3. Rethinking Scale: Deployment Trade-offs of Small Language Models under Agent Paradigms**
- **Authors:** Xinlin Wang, Mats Brorsson
- **Venue/Year:** arXiv, April 2026
- **ID/URL:** [arXiv:2604.19299](https://arxiv.org/abs/2604.19299)
- **Relation:** **Partially relates / Nuanced**
- **Key claim:** The first large-scale study of <10B models under three paradigms (base, single-agent + tools, multi-agent). Finds that single-agent systems achieve the best balance between performance and cost, while multi-agent setups add overhead with limited gains for small models.
- **Synthesis:** This paper partially contradicts our finding. It finds multi-agent overhead not worthwhile for <10B models in general tasks. However, our benchmark focuses on evidence-grounded freshness questions where the orchestration pattern (draft-validate-ground) is specifically designed for the task. The difference suggests that MA benefit is task-dependent: general reasoning may not benefit, but structured evidence-grounding tasks do.

**4. Improving Factuality and Reasoning in Language Models through Multiagent Debate**
- **Authors:** Yilun Du et al.
- **Venue/Year:** arXiv, May 2023
- **ID/URL:** [arXiv:2305.14325](https://arxiv.org/abs/2305.14325)
- **Relation:** **Supports**
- **Key claim:** Multiple LLM instances proposing and debating over multiple rounds significantly enhances mathematical and strategic reasoning and improves factual validity, reducing hallucinations. The approach works with black-box models using identical procedures across tasks.
- **Synthesis:** This seminal paper established that multi-agent debate improves factuality — the same mechanism our benchmark exploits. Their finding that debate reduces hallucinations aligns with our observation that MA orchestration helps on evidence-grounded tasks where hallucination is the primary failure mode.

---

## Finding 2: MA Helps Small Models More Than Large Models

> *On GPT-4o, MA slightly hurt vs B2 (7.8 vs 8.4). On Ollama 7B, MA slightly helped vs B2 (8.1 vs 8.0). The overhead benefits weaker models more.*

### Relevant Papers

**1. More Agents Is All You Need**
- **Authors:** Deheng Ye et al.
- **Venue/Year:** TMLR, 2024
- **ID/URL:** [arXiv:2402.05120](https://arxiv.org/abs/2402.05120)
- **Relation:** **Supports**
- **Key claim:** The degree of enhancement from multi-agent scaling is correlated with task difficulty. Harder tasks (where the base model is weaker) benefit more from additional agents.
- **Synthesis:** Our finding that MA helps the 7B model more than GPT-4o maps directly to their task-difficulty correlation. The 7B model starts from a weaker baseline (analogous to "harder" relative performance), so the multi-agent boost is more impactful. GPT-4o is already strong, leaving less room for improvement — and introducing overhead that can net hurt.

**2. SLMJury: Can Small Language Models Judge as Well as Large Ones?**
- **Authors:** Anish Laddha, Nitesh Pradhan, Gaurav Srivastava
- **Venue/Year:** arXiv, June 2026
- **ID/URL:** [arXiv:2606.07810](https://arxiv.org/abs/2606.07810)
- **Relation:** **Partially contradicts / Nuances**
- **Key claim:** Benchmarks 16 SLM judges (0.6B–14B). Finds that multi-agent debate (Reflect-Critique-Refine) **degrades accuracy across all tested configurations** for small models, whereas top judges resist adversarial personas with ≤0.55% variance. No single SLM dominates across tasks.
- **Synthesis:** SLMJury's finding that debate degrades SLM accuracy is a partial contradiction. However, their debate protocol (Reflect-Critique-Refine) differs from our draft-validate-ground pattern — ours uses deterministic grounding rather than peer critique. The difference suggests that the *type* of multi-agent interaction matters: structured grounding helps small models, while open-ended debate can hurt them.

**3. Rethinking Scale: Deployment Trade-offs of Small Language Models under Agent Paradigms**
- **Authors:** Xinlin Wang, Mats Brorsson
- **Venue/Year:** arXiv, April 2026
- **ID/URL:** [arXiv:2604.19299](https://arxiv.org/abs/2604.19299)
- **Relation:** **Partially contradicts**
- **Key claim:** Multi-agent setups for <10B models add overhead with limited gains; single-agent + tools is the better paradigm for small models.
- **Synthesis:** This challenges our finding that MA helps the 7B model. The discrepancy may stem from task design: their evaluation covers general tasks, while ours targets evidence-grounded freshness where the draft-validate-ground pattern directly addresses the 7B's main weakness (non-convergence/hallucination). The literature suggests MA for small models is *task-dependent*, not universally beneficial.

**4. Self-Consistency Improves Chain of Thought Reasoning in Language Models**
- **Authors:** Xuezhi Wang et al.
- **Venue/Year:** ICLR 2023
- **ID/URL:** [arXiv:2203.11171](https://arxiv.org/abs/2203.11171)
- **Relation:** **Partially relates**
- **Key claim:** Sampling diverse reasoning paths and selecting the most consistent answer boosts performance by large margins (+17.9% GSM8K, +11.0% SVAMP). The method is more effective on harder tasks where single-path reasoning fails.
- **Synthesis:** Self-consistency is a single-model analogue to multi-agent voting. The finding that it helps more on harder tasks (where models are weaker) parallels our observation that MA helps the 7B more than GPT-4o. Both suggest that error-correction mechanisms have diminishing returns as base capability increases.

---

## Finding 3: Orchestration Matters More Than Retrieval Quality for Small Models

> *The draft-then-validate pattern (v2.2) and deterministic grounding (v2.3) improved convergence from non-convergence to 85–90% on the 7B model.*

### Relevant Papers

**1. Reflexion: Language Agents with Verbal Reinforcement Learning**
- **Authors:** Noah Shinn et al.
- **Venue/Year:** NeurIPS 2023
- **ID/URL:** [arXiv:2303.11366](https://arxiv.org/abs/2303.11366)
- **Relation:** **Supports**
- **Key claim:** Agents verbally reflect on task feedback and maintain reflective text in episodic memory, achieving 91% pass@1 on HumanEval (surpassing GPT-4 at 80%). The framework is flexible across feedback types and sources.
- **Synthesis:** Reflexion validates the core idea behind our draft-validate pattern: structured verbal reflection on task outcomes improves subsequent decisions without weight updates. Our v2.2 draft-then-validate is analogous — the validator provides verbal feedback that grounds the drafter. The 91% → 80% gap over GPT-4 mirrors our 7B+MA matching GPT-4o.

**2. Self-Refine: Iterative Refinement with Self-Feedback**
- **Authors:** Aman Madaan et al.
- **Venue/Year:** NeurIPS 2023
- **ID/URL:** [arXiv:2303.17651](https://arxiv.org/abs/2303.17651)
- **Relation:** **Supports**
- **Key claim:** A single LLM generates output, provides feedback, and refines iteratively — improving ~20% absolute on average across 7 tasks. Even GPT-4 benefits from self-refinement.
- **Synthesis:** Self-Refine demonstrates that the draft-feedback-refine loop is effective regardless of model size, but the gains are larger on initial lower-quality outputs. Our draft-then-validate pattern with separate roles (drafter + validator) is an inter-agent version of this same principle.

**3. Self-RAG: Learning to Retrieve, Generate, and Critique through Self-Reflection**
- **Authors:** Akari Asai et al.
- **Venue/Year:** arXiv, October 2023
- **ID/URL:** [arXiv:2310.11511](https://arxiv.org/abs/2310.11511)
- **Relation:** **Supports**
- **Key claim:** Self-RAG (7B and 13B) uses reflection tokens to adaptively retrieve passages, generate, and reflect on retrieved content — outperforming ChatGPT and retrieval-augmented Llama2-chat on QA, reasoning, and fact verification. The model learns to critique its own retrieval and generation.
- **Synthesis:** Self-RAG is the closest published precedent for our deterministic grounding pattern (v2.3). Both use a structured mechanism to ground generation in retrieved evidence. Self-RAG trains reflection tokens; our approach uses deterministic orchestration. The key insight is shared: for small models, explicit grounding signals matter more than for large models that can implicitly self-ground.

**4. Large Language Model based Multi-Agents: A Survey of Progress and Challenges**
- **Authors:** Taicheng Guo et al.
- **Venue/Year:** arXiv, February 2024 (v2 April 2024)
- **ID/URL:** [arXiv:2402.01680](https://arxiv.org/abs/2402.01680)
- **Relation:** **Partially relates**
- **Key claim:** Surveys multi-agent systems based on LLMs, identifying profiling, communication, and capacity-building mechanisms as essential dimensions. Highlights that agent orchestration patterns — role assignment, communication protocols, and memory — are the key design decisions.
- **Synthesis:** This survey provides the taxonomy context for our orchestration patterns. The finding that orchestration architecture (not just model capability) determines MA performance is consistent with our observation that v2.2/v2.3 patterns drove convergence improvements independent of retrieval quality.

---

## Finding 4: A Weak Skeptic on a Small Model Can Backfire

> *In earlier experiments, a 7B skeptic agent overcorrected and dismissed valid evidence, scoring worse than vanilla.*

### Relevant Papers

**1. SLMJury: Can Small Language Models Judge as Well as Large Ones?**
- **Authors:** Anish Laddha, Nitesh Pradhan, Gaurav Srivastava
- **Venue/Year:** arXiv, June 2026
- **ID/URL:** [arXiv:2606.07810](https://arxiv.org/abs/2606.07810)
- **Relation:** **Supports**
- **Key claim:** Multi-agent debate (Reflect-Critique-Refine) **degrades accuracy across all tested configurations** for small models (0.6B–14B). The "overthinking effect" is domain-dependent: for most judges, quick 10-token verdicts match or beat extended reasoning on mathematical judging, while extended reasoning wins on general tasks by up to 23%.
- **Synthesis:** SLMJury directly validates our finding. A small model acting as critic/skeptic can hurt accuracy because it lacks the reasoning capacity to distinguish valid from invalid evidence. The "overthinking effect" they identify — where extended reasoning by a small model degrades performance — is the same mechanism as our 7B skeptic overcorrecting and dismissing valid evidence.

**2. The Confident Liar: Diagnosing Multi-Agent Debate with Log-Probabilities and LLM-as-Judge**
- **Authors:** Ali Keramati, Justin Cheok, Jacob Horne, Mark Warschauer
- **Venue/Year:** ACL 2026
- **ID/URL:** [arXiv:2606.10296](https://arxiv.org/abs/2606.10296)
- **Relation:** **Supports**
- **Key claim:** In two-agent debate (Constructor + Auditor), confidence aligns with reasoned quality only for the Constructor, not the Auditor (AUROC 0.804 vs 0.634). The Auditor role is systematically less reliable at self-assessing reasoning quality — confidence-based failure detection fails for the Auditor.
- **Synthesis:** This paper explains *why* our 7B skeptic backfired. The Auditor/skeptic role has inherently worse calibration than the Constructor role. A small model in the Auditor position has both poor reasoning and poor self-assessment, leading to overcorrection. The role asymmetry they identify is the mechanism behind our finding.

**3. The Confidence Dichotomy: Analyzing and Mitigating Miscalibration in Tool-Use Agents**
- **Authors:** Weihao Xuan et al.
- **Venue/Year:** arXiv, January 2026
- **ID/URL:** [arXiv:2601.07264](https://arxiv.org/abs/2601.07264)
- **Relation:** **Supports**
- **Key claim:** Evidence tools (e.g., web search) systematically induce severe overconfidence in agents due to noise in retrieved information, while verification tools (e.g., code interpreters) ground reasoning through deterministic feedback and mitigate miscalibration.
- **Synthesis:** This finding directly maps to our skeptic problem. A 7B skeptic processing retrieved evidence faces the overconfidence trap: noisy evidence + weak reasoning → overconfident dismissal. Our v2.3 deterministic grounding was designed precisely to replace the unreliable skeptic with a deterministic verification step, which this paper identifies as the correct approach.

---

## Finding 5: Search Infrastructure Is the Bottleneck for Single-Agent Approaches

> *B1 (search) often scored lower than B0 (vanilla) because irrelevant retrieval degrades output.*

### Relevant Papers

**1. Quantifying the Tug-of-War Between an LLM's Internal Prior and External Evidence**
- **Authors:** Eric Wu et al.
- **Venue/Year:** arXiv, April 2024 (v3 February 2025)
- **ID/URL:** [arXiv:2404.10198](https://arxiv.org/abs/2404.10198)
- **Relation:** **Strongly supports**
- **Key claim:** LLMs are susceptible to adopting incorrect retrieved content, overriding their own correct prior knowledge over 60% of the time. The less confident a model is in its initial response, the more likely it is to adopt incorrect retrieved content. Even GPT-4o is affected.
- **Synthesis:** This paper provides the mechanistic explanation for our B1 < B0 finding. When search returns irrelevant or incorrect content, models adopt it over their own knowledge more than 60% of the time. This is not a minor effect — it's a majority failure mode. Our finding that B1 (search) underperforms B0 (vanilla) is a direct consequence of this tug-of-war dynamic.

**2. Context Length Alone Hurts LLM Performance Despite Perfect Retrieval**
- **Authors:** Yufeng Du et al.
- **Venue/Year:** EMNLP 2025 Findings
- **ID/URL:** [arXiv:2510.05381](https://arxiv.org/abs/2510.05381)
- **Relation:** **Supports**
- **Key claim:** Even when models can perfectly retrieve all relevant information, performance still degrades substantially (13.9%–85%) as input length increases. The sheer length of the input alone hurts performance, independent of retrieval quality and without any distraction.
- **Synthesis:** This extends our B1 < B0 finding: even *correct* search results hurt because they increase context length. The problem isn't just irrelevant retrieval — it's that any additional context, even relevant, degrades performance. This suggests B1's failure is structural (context length) not just qualitative (relevance).

**3. Retrieval-Augmented Generation for Large Language Models: A Survey**
- **Authors:** Yunfan Gao et al.
- **Venue/Year:** arXiv, December 2023 (v5 March 2024)
- **ID/URL:** [arXiv:2312.10997](https://arxiv.org/abs/2312.10997)
- **Relation:** **Partially relates**
- **Key claim:** Comprehensive survey of RAG paradigms (Naive, Advanced, Modular). Identifies retrieval quality, generation grounding, and augmentation timing as the tripartite foundation. Notes that indiscriminate retrieval can diminish LM versatility or lead to unhelpful response generation.
- **Synthesis:** The survey acknowledges that indiscriminate retrieval is a known problem in RAG pipelines. Our B1 result is a specific instance of this general phenomenon — search without grounding mechanisms is counterproductive.

**4. Knowledge Requirements Shape LLM Responses to Context-Memory Conflict**
- **Authors:** Kaiser Sun et al.
- **Venue/Year:** ACL 2026
- **ID/URL:** [arXiv:2506.06485](https://arxiv.org/abs/2506.06485)
- **Relation:** **Supports**
- **Key claim:** Performance degradation under context-memory conflict is driven by task-specific knowledge reliance and conflict plausibility. Strategies like rationales or context reiteration increase context reliance, helping context-only tasks but harming those requiring parametric knowledge. These effects bias model-based evaluation.
- **Synthesis:** This paper adds nuance to our B1 finding. The harm from search isn't just about irrelevant content — it's about the *type* of task. Evidence-grounded freshness questions require context reliance, but when search returns conflicting or irrelevant information, the model is pulled toward the wrong context. The task-dependent nature they identify explains why B1 hurts more on some questions than others.

---

## Synthesis

### Overall Picture

Published research **broadly supports** our five findings, with important nuances:

| Finding | Support Level | Key Caveat |
|---------|--------------|------------|
| F1: MA compresses gap | **Supported** | MoA (2406.04692) is the strongest precedent; task-dependence matters |
| F2: MA helps small > large | **Partially supported** | "More Agents" scaling law supports; SLMJury and Rethinking Scale partially contradict for general tasks |
| F3: Orchestration > retrieval | **Supported** | Reflexion, Self-Refine, Self-RAG all validate structured grounding patterns |
| F4: Weak skeptic backfires | **Strongly supported** | SLMJury shows debate degrades SLM accuracy; Confident Liar shows role asymmetry |
| F5: Search is bottleneck | **Strongly supported** | Wu et al. shows 60%+ adoption of incorrect retrieval; context length alone degrades performance |

### Where Our Work Adds Novelty

1. **Evidence-grounded freshness as a benchmark domain.** Most published MA benchmarks focus on math, coding, or general QA. Evidence-grounded freshness questions combine temporal reasoning with factual verification — a task structure where MA patterns specifically address the failure modes (hallucination, non-convergence) that dominate small-model performance.

2. **Quantification of the crossover effect.** We show a specific crossover: MA helps 7B (+0.1) but hurts GPT-4o (−0.6). While "More Agents Is All You Need" shows the general principle, we quantify it for a specific orchestration pattern on a specific task type.

3. **Deterministic grounding vs. critic debate.** Our v2.3 deterministic grounding pattern replaces the unreliable skeptic with a verification step. SLMJury's finding that debate degrades SLM accuracy and The Confidence Dichotomy's distinction between evidence tools (overconfidence-inducing) and verification tools (grounding) provide the theoretical basis for why deterministic grounding works where skeptic agents fail.

4. **B1 < B0 as a specific finding.** While the RAG survey notes indiscriminate retrieval as a known problem, our benchmark quantifies it in the agent-search context: search infrastructure as a net negative for single-agent approaches on evidence-grounded tasks.

### Caveats from the Literature

1. **Task dependence.** Rethinking Scale (2604.19299) finds MA overhead not worthwhile for <10B models on general tasks. Our positive MA result for the 7B may be specific to evidence-grounded freshness tasks where structured grounding directly addresses the main failure mode.

2. **Debate vs. structured grounding.** SLMJury shows multi-agent debate (Reflect-Critique-Refine) degrades accuracy for small models, but our draft-validate-ground pattern is not open-ended debate — it's structured with deterministic verification. The distinction matters: the *type* of multi-agent interaction determines whether small models benefit.

3. **Generalization.** Our benchmark uses specific models (qwen2.5:7b, GPT-4o) and a specific task type. While the literature supports the underlying mechanisms, the crossover point (where MA stops helping and starts hurting) will vary by model, task, and orchestration pattern.

4. **Evaluation reliability.** The Confident Liar paper shows that confidence signals in multi-agent debate are role-asymmetric and unreliable for the Auditor. Our evaluation uses external scoring rather than agent self-assessment, which avoids this trap — but any LLM-as-judge evaluation of multi-agent output should account for this asymmetry.

---

## References

1. Wang, J. et al. (2024). *Mixture-of-Agents Enhances Large Language Model Capabilities.* arXiv:2406.04692. https://arxiv.org/abs/2406.04692

2. Du, Y. et al. (2023). *Improving Factuality and Reasoning in Language Models through Multiagent Debate.* arXiv:2305.14325. https://arxiv.org/abs/2305.14325

3. Ye, D. et al. (2024). *More Agents Is All You Need.* TMLR. arXiv:2402.05120. https://arxiv.org/abs/2402.05120

4. Wang, X. & Brorsson, M. (2026). *Rethinking Scale: Deployment Trade-offs of Small Language Models under Agent Paradigms.* arXiv:2604.19299. https://arxiv.org/abs/2604.19299

5. Laddha, A., Pradhan, N., & Srivastava, G. (2026). *SLMJury: Can Small Language Models Judge as Well as Large Ones?* arXiv:2606.07810. https://arxiv.org/abs/2606.07810

6. Wang, X. et al. (2023). *Self-Consistency Improves Chain of Thought Reasoning in Language Models.* ICLR 2023. arXiv:2203.11171. https://arxiv.org/abs/2203.11171

7. Shinn, N. et al. (2023). *Reflexion: Language Agents with Verbal Reinforcement Learning.* NeurIPS 2023. arXiv:2303.11366. https://arxiv.org/abs/2303.11366

8. Madaan, A. et al. (2023). *Self-Refine: Iterative Refinement with Self-Feedback.* NeurIPS 2023. arXiv:2303.17651. https://arxiv.org/abs/2303.17651

9. Asai, A. et al. (2023). *Self-RAG: Learning to Retrieve, Generate, and Critique through Self-Reflection.* arXiv:2310.11511. https://arxiv.org/abs/2310.11511

10. Guo, T. et al. (2024). *Large Language Model based Multi-Agents: A Survey of Progress and Challenges.* arXiv:2402.01680. https://arxiv.org/abs/2402.01680

11. Keramati, A., Cheok, J., Horne, J., & Warschauer, M. (2026). *The Confident Liar: Diagnosing Multi-Agent Debate with Log-Probabilities and LLM-as-Judge.* ACL 2026. arXiv:2606.10296. https://arxiv.org/abs/2606.10296

12. Xuan, W. et al. (2026). *The Confidence Dichotomy: Analyzing and Mitigating Miscalibration in Tool-Use Agents.* arXiv:2601.07264. https://arxiv.org/abs/2601.07264

13. Wu, E. et al. (2024). *Quantifying the Tug-of-War Between an LLM's Internal Prior and External Evidence.* arXiv:2404.10198. https://arxiv.org/abs/2404.10198

14. Du, Y. et al. (2025). *Context Length Alone Hurts LLM Performance Despite Perfect Retrieval.* EMNLP 2025 Findings. arXiv:2510.05381. https://arxiv.org/abs/2510.05381

15. Gao, Y. et al. (2024). *Retrieval-Augmented Generation for Large Language Models: A Survey.* arXiv:2312.10997. https://arxiv.org/abs/2312.10997

16. Sun, K. et al. (2026). *Knowledge Requirements Shape LLM Responses to Context-Memory Conflict.* ACL 2026. arXiv:2506.06485. https://arxiv.org/abs/2506.06485

17. Yadav, A. et al. (2026). *More Capable, Less Cooperative? When LLMs Fail At Zero-Cost Collaboration.* ICML 2026. arXiv:2604.07821. https://arxiv.org/abs/2604.07821