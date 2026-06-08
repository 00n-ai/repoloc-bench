# 00n.ai RepoLoc Benchmark

Public research benchmark for structured repository knowledge trees, code localization, and evidence-grounded requirement tracing.

## Contents
- `data/derived/oss-method-repoloc-bench/` — current pilot dataset package
- `research/scripts/build_repoloc_pilot_dataset.py` — reproducible package builder

## Claim boundary
- Primary branch: original requirement text
- Auxiliary branch: LLM-imputed requirement text for sensitivity analysis only
- Gold links: traces with `goldfinal == 'T'`
- Test-localization ground truth is not yet included in this first release

## Use
Start with the pilot package manifest:
- `data/derived/oss-method-repoloc-bench/manifest.json`
