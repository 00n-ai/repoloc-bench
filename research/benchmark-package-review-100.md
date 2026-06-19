# Paper 1 Benchmark Package Review (100-bootstrap iteration run)

## Question
Does graph/context augmentation improve traceability retrieval over simpler baselines in the RepoLoc benchmark package?

## Bottom line
Yes, directionally. The strongest LLM-based context-aware runs are the top overall runs in the review, and context-aware / graph-aware variants beat TF-IDF and Euclidean baselines.

## Method
This is a statistics pass over existing benchmark outputs, not a retraining run.

- Analyzer: `research/scripts/analyze_benchmark_package.py`
- Bootstrap iterations: `100`
- Package root: `data/derived/oss-method-repoloc-bench/`
- Inputs: per-requirement and ranking CSVs from OSS/LOSO/LLM benchmark runs in the paper workspace

The review summarizes:
- MRR
- MAP
- Hits@1/5/10
- recall@k / NDCG@k where rankings are present
- paired deltas across selected comparisons

## Key findings
1. Simple baselines are weak.
2. Trace/candidate ranking helps a lot.
3. Context-aware runs are strongest overall.
4. Graph-only is not enough.
5. LOSO confirms the value of context.

## Interpretation
This supports the RepoLoc direction that relational/contextual evidence matters more than pure geometry or lexical similarity alone.

## Caveats
- This is a summary over existing outputs, not a fresh model training run.
- Bootstrap iterations were set to `100`, so uncertainty estimates are coarse.
- Many paired comparisons are tested, so Holm correction is conservative.

## Conclusion
The benchmark package supports structured/contextual evidence routing, not geometry-only retrieval.
