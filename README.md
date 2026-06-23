# 00n.ai RepoLoc Benchmark

Public research benchmark for structured repository knowledge trees, code localization, and evidence-grounded requirement tracing.

## Contents
- `data/derived/oss-method-repoloc-bench/` — current pilot dataset package
- `data/derived/itrust-traceability-benchmark/` — iTrust requirement-to-code benchmark package
- `data/derived/multi-agent-framework-benchmark/` — public multi-agent framework benchmark artifacts and freshness question pack
- `research/benchmark-package-review-100.md` — benchmark review summary
- `research/reproduction/benchmark_package_review_100/` — fuller reproduction bundle
- `research/scripts/analyze_benchmark_package.py` — benchmark review analyzer
- `research/scripts/build_repoloc_pilot_dataset.py` — reproducible pilot package builder

## Claim boundary
- Primary branch: original requirement text
- Auxiliary branch: LLM-imputed requirement text for sensitivity analysis only
- Gold links: traces with `goldfinal == 'T'`
- Test-localization ground truth is not yet included in this first release

## Use
Start with the pilot package manifest:
- `data/derived/oss-method-repoloc-bench/manifest.json`

For the multi-agent framework benchmark, start with:
- `data/derived/multi-agent-framework-benchmark/README.md`
- `data/derived/multi-agent-framework-benchmark/manifest.json`
