# Benchmark Package Reproduction Bundle

This bundle captures the exact benchmark review snapshot for the RepoLoc benchmark package.

## What is included
- `summary.json` — full statistical summary snapshot
- `report.md` — human-readable benchmark review
- `../../scripts/analyze_benchmark_package.py` — reusable analyzer script
- `run.sh` — convenience wrapper for re-running the review
- `source_refs.json` — commit hashes, seed, and input path references

## Source of truth
- Benchmark source repo: `state-estimation-traceability`
- Benchmark source commit: `477981bb50550d393dbdb1a70855b091b15bc1e6`
- Public benchmark mirror repo: `repoloc-bench`
- Mirror commit for this bundle: `f50204e32f7f33aee5dcf93f7e328d2d72ea7c53`

## Reproduce
From a checkout that also has `state-estimation-traceability` available locally:

```bash
bash research/reproduction/benchmark_package_review_100/run.sh /path/to/state-estimation-traceability
```

Or call the analyzer directly:

```bash
python3 research/scripts/analyze_benchmark_package.py \
  --project-root /path/to/state-estimation-traceability \
  --output-dir experiments/benchmark_package_review_100 \
  --iterations 100 \
  --seed 20260523
```

## Notes
- This review summarizes existing CSV outputs; it does not retrain models.
- The bundled `summary.json` is the exact saved output snapshot from the source repo.
- The bundled `report.md` is the narrative summary generated from that snapshot.
