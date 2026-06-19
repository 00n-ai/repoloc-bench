#!/usr/bin/env python3
"""Build a reproducibility/statistical summary for OSS method experiments.

This script consumes the existing per-requirement and ranking CSV outputs. It
does not rerun models. The goal is to make the current benchmark package
reviewable: paired uncertainty, set-level metrics, and a manifest of available
raw outputs.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import random
from collections import defaultdict
from pathlib import Path
from statistics import mean, median


DEFAULT_RUNS = {
    "orig_option1_tfidf": "experiments/oss_method/option1_tfidf",
    "orig_option2_trace_ranker": "experiments/oss_method/option2_trace_ranker",
    "orig_option3_pairwise": "experiments/oss_method/option3_pairwise_blend0p1",
    "orig_option4_graph_ppr": "experiments/oss_method/option4_graph_ppr",
    "orig_option5_euclidean": "experiments/oss_method/option5_euclidean",
    "orig_option5_hyperbolic": "experiments/oss_method/option5_hyperbolic",
    "llm_option1_tfidf": "experiments/oss_method_llm_requirements/eval_options_1_5/option1_tfidf",
    "llm_option2_trace_ranker": "experiments/oss_method_llm_requirements/eval_options_1_5/option2_trace_ranker",
    "llm_option3_pairwise": "experiments/oss_method_llm_requirements/eval_options_1_5/option3_pairwise_blend0p1",
    "llm_option4_graph_ppr": "experiments/oss_method_llm_requirements/eval_options_1_5/option4_graph_ppr",
    "llm_option5_euclidean": "experiments/oss_method_llm_requirements/eval_options_1_5/option5_euclidean",
    "llm_option5_hyperbolic": "experiments/oss_method_llm_requirements/eval_options_1_5/option5_hyperbolic",
    "llm_option7_best": "experiments/oss_method_llm_requirements/option7_hybrid_evidence/option7_text_blend0p5",
    "llm_option8_best": "experiments/oss_method_llm_requirements/option8_poincare_hybrid/option8_text0p5_evidence0p35_poincare0p15",
    "llm_option9_best": "experiments/oss_method_llm_requirements/option9_cone_order/option9_text0p5_evidence0p35_cone0p15",
    "llm_option10_best": "experiments/oss_method_llm_requirements/option10_directed_order/option10_text0p5_evidence0p35_order0p15",
    "llm_option11_context_only": "experiments/oss_method_llm_requirements/option11_contextual_directed_features/option11_contextual_directed",
    "llm_option11_best": "experiments/oss_method_llm_requirements/option11_contextual_directed_features/option11_text_blend0p5",
    "llm_option12_graph_only": "experiments/oss_method_llm_requirements/option12_typed_directed_graph_embedding/option12_typed_graph",
    "llm_option12_best_hits10": "experiments/oss_method_llm_requirements/option12_typed_directed_graph_embedding/option12_text0p5_context0p40_graph0p1",
    "loso_original_option1_tfidf": "experiments/oss_method_loso/original_loso_option1_tfidf",
    "loso_original_option2_trace_ranker": "experiments/oss_method_loso/original_loso_option2_trace_ranker",
    "loso_original_option3_pairwise": "experiments/oss_method_loso/original_loso_option3_pairwise",
    "loso_original_option11_context": "experiments/oss_method_loso/original_loso_option11_context",
    "loso_llm_option1_tfidf": "experiments/oss_method_loso/llm_loso_option1_tfidf",
    "loso_llm_option2_trace_ranker": "experiments/oss_method_loso/llm_loso_option2_trace_ranker",
    "loso_llm_option3_pairwise": "experiments/oss_method_loso/llm_loso_option3_pairwise",
    "loso_llm_option11_context": "experiments/oss_method_loso/llm_loso_option11_context",
    "loso_original_option11_static_counts": "experiments/oss_method_loso_context_ablation/original_loso_option11_ablate_static_counts",
    "loso_original_option11_no_interactions": "experiments/oss_method_loso_context_ablation/original_loso_option11_ablate_no_interactions",
    "loso_llm_option11_static_counts": "experiments/oss_method_loso_context_ablation/llm_loso_option11_ablate_static_counts",
    "loso_llm_option11_no_interactions": "experiments/oss_method_loso_context_ablation/llm_loso_option11_ablate_no_interactions",
}


PAIRWISE_COMPARISONS = [
    ("llm_option11_best", "llm_option7_best"),
    ("llm_option11_best", "llm_option8_best"),
    ("llm_option11_best", "llm_option10_best"),
    ("llm_option11_best", "llm_option12_best_hits10"),
    ("llm_option11_best", "llm_option12_graph_only"),
    ("llm_option11_best", "llm_option3_pairwise"),
    ("llm_option7_best", "llm_option3_pairwise"),
    ("loso_original_option11_context", "loso_original_option1_tfidf"),
    ("loso_llm_option11_context", "loso_llm_option1_tfidf"),
    ("loso_llm_option11_context", "loso_llm_option2_trace_ranker"),
    ("loso_original_option11_static_counts", "loso_original_option11_context"),
    ("loso_original_option11_static_counts", "loso_original_option1_tfidf"),
    ("loso_llm_option11_static_counts", "loso_llm_option11_context"),
    ("loso_llm_option11_static_counts", "loso_llm_option1_tfidf"),
]


PER_REQ_SUFFIX = "_per_requirement.csv"
RANKINGS_SUFFIX = "_rankings.csv"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def float_or_zero(value: str | None) -> float:
    if value is None or value == "":
        return 0.0
    return float(value)


def read_per_requirement(prefix: Path) -> dict[str, dict[str, object]]:
    rows = read_csv(prefix.with_name(prefix.name + PER_REQ_SUFFIX))
    result: dict[str, dict[str, object]] = {}
    for row in rows:
        rid = row["requirement_id"]
        gold_count = int(float_or_zero(row.get("gold_count")))
        result[rid] = {
            "system": row["system"],
            "requirement_id": rid,
            "gold_count": gold_count,
            "first_relevant_rank": None
            if row.get("first_relevant_rank", "") == ""
            else int(float(row["first_relevant_rank"])),
            "average_precision": float_or_zero(row.get("average_precision")),
            "reciprocal_rank": float_or_zero(row.get("reciprocal_rank")),
            "hits_at_1": float_or_zero(row.get("hits_at_1")),
            "hits_at_5": float_or_zero(row.get("hits_at_5")),
            "hits_at_10": float_or_zero(row.get("hits_at_10")),
        }
    return result


def read_rankings(prefix: Path) -> dict[str, list[dict[str, object]]]:
    rows = read_csv(prefix.with_name(prefix.name + RANKINGS_SUFFIX))
    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        grouped[row["requirement_id"]].append(
            {
                "rank": int(row["rank"]),
                "is_gold": int(row["is_gold"]),
                "method_id": row["method_id"],
                "score": float_or_zero(row.get("score")),
            }
        )
    for req_rows in grouped.values():
        req_rows.sort(key=lambda r: int(r["rank"]))
    return grouped


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    xs = sorted(values)
    idx = (len(xs) - 1) * p
    lo = math.floor(idx)
    hi = math.ceil(idx)
    if lo == hi:
        return xs[lo]
    return xs[lo] * (hi - idx) + xs[hi] * (idx - lo)


def bootstrap_ci(values: list[float], iterations: int, rng: random.Random) -> dict[str, float]:
    values = [v for v in values if not math.isnan(v)]
    if not values:
        return {"mean": 0.0, "ci_low": 0.0, "ci_high": 0.0}
    samples = []
    n = len(values)
    for _ in range(iterations):
        samples.append(mean(values[rng.randrange(n)] for _ in range(n)))
    return {
        "mean": mean(values),
        "ci_low": percentile(samples, 0.025),
        "ci_high": percentile(samples, 0.975),
    }


def paired_randomization_p(diffs: list[float], iterations: int, rng: random.Random) -> float:
    diffs = [d for d in diffs if not math.isnan(d)]
    if not diffs:
        return 1.0
    observed = abs(mean(diffs))
    more_extreme = 0
    for _ in range(iterations):
        synthetic = [d if rng.random() < 0.5 else -d for d in diffs]
        if abs(mean(synthetic)) >= observed:
            more_extreme += 1
    return (more_extreme + 1) / (iterations + 1)


def holm_adjust(pairs: list[dict[str, object]]) -> None:
    ordered = sorted(enumerate(pairs), key=lambda item: float(item[1]["p_value"]))
    m = len(ordered)
    adjusted_by_index: dict[int, float] = {}
    running_max = 0.0
    for rank, (idx, pair) in enumerate(ordered):
        raw = float(pair["p_value"])
        adjusted = min(1.0, raw * (m - rank))
        running_max = max(running_max, adjusted)
        adjusted_by_index[idx] = running_max
    for idx, value in adjusted_by_index.items():
        pairs[idx]["holm_p_value"] = value


def dcg(relevances: list[int]) -> float:
    return sum(rel / math.log2(i + 2) for i, rel in enumerate(relevances))


def set_metrics(per_req: dict[str, dict[str, object]], rankings: dict[str, list[dict[str, object]]]) -> dict[str, float]:
    ks = [1, 5, 10, 50]
    acc: dict[str, list[float]] = {f"recall_at_{k}": [] for k in ks}
    acc.update({f"ndcg_at_{k}": [] for k in ks})
    acc.update({f"all_gold_covered_at_{k}": [] for k in ks})
    ranked_candidate_counts = []
    for rid, row in per_req.items():
        gold_count = int(row["gold_count"])
        if gold_count <= 0:
            continue
        rows = rankings.get(rid, [])
        ranked_candidate_counts.append(float(len(rows)))
        for k in ks:
            top = rows[:k]
            rels = [int(r["is_gold"]) for r in top]
            retrieved_gold = sum(rels)
            acc[f"recall_at_{k}"].append(retrieved_gold / gold_count)
            ideal = [1] * min(gold_count, k)
            ideal_dcg = dcg(ideal)
            acc[f"ndcg_at_{k}"].append(0.0 if ideal_dcg == 0 else dcg(rels) / ideal_dcg)
            acc[f"all_gold_covered_at_{k}"].append(1.0 if retrieved_gold >= gold_count else 0.0)
    result = {name: mean(vals) if vals else 0.0 for name, vals in acc.items()}
    result["ranked_candidates_mean"] = mean(ranked_candidate_counts) if ranked_candidate_counts else 0.0
    result["ranked_candidates_median"] = median(ranked_candidate_counts) if ranked_candidate_counts else 0.0
    return result


def summarize_run(name: str, prefix: Path, iterations: int, rng: random.Random) -> dict[str, object]:
    per_req_path = prefix.with_name(prefix.name + PER_REQ_SUFFIX)
    rankings_path = prefix.with_name(prefix.name + RANKINGS_SUFFIX)
    if not per_req_path.exists():
        return {"name": name, "prefix": str(prefix), "available": False, "missing": str(per_req_path)}
    per_req = read_per_requirement(prefix)
    rankings = read_rankings(prefix) if rankings_path.exists() else {}
    rows_with_gold = [r for r in per_req.values() if int(r["gold_count"]) > 0]
    metrics = {
        "requirements_with_gold": len(rows_with_gold),
        "mrr": bootstrap_ci([float(r["reciprocal_rank"]) for r in rows_with_gold], iterations, rng),
        "map": bootstrap_ci([float(r["average_precision"]) for r in rows_with_gold], iterations, rng),
        "hits_at_1": bootstrap_ci([float(r["hits_at_1"]) for r in rows_with_gold], iterations, rng),
        "hits_at_5": bootstrap_ci([float(r["hits_at_5"]) for r in rows_with_gold], iterations, rng),
        "hits_at_10": bootstrap_ci([float(r["hits_at_10"]) for r in rows_with_gold], iterations, rng),
        "set_metrics": set_metrics(per_req, rankings) if rankings else {},
    }
    return {
        "name": name,
        "prefix": str(prefix),
        "available": True,
        "per_requirement_csv": str(per_req_path),
        "rankings_csv": str(rankings_path) if rankings_path.exists() else None,
        "metrics": metrics,
    }


def compare_runs(
    run_a: str,
    run_b: str,
    prefixes: dict[str, Path],
    iterations: int,
    rng: random.Random,
) -> dict[str, object]:
    a = read_per_requirement(prefixes[run_a])
    b = read_per_requirement(prefixes[run_b])
    common = sorted(set(a) & set(b))
    common = [rid for rid in common if int(a[rid]["gold_count"]) > 0 and int(b[rid]["gold_count"]) > 0]
    metrics = {}
    for col in ["reciprocal_rank", "average_precision", "hits_at_1", "hits_at_5", "hits_at_10"]:
        diffs = [float(a[rid][col]) - float(b[rid][col]) for rid in common]
        ci = bootstrap_ci(diffs, iterations, rng)
        metrics[col] = {
            "mean_delta": ci["mean"],
            "ci_low": ci["ci_low"],
            "ci_high": ci["ci_high"],
            "p_value": paired_randomization_p(diffs, iterations, rng),
        }
    return {"a": run_a, "b": run_b, "n_common_requirements": len(common), "metrics": metrics}


def write_markdown(output: Path, runs: list[dict[str, object]], comparisons: list[dict[str, object]]) -> None:
    lines = [
        "# Benchmark Package Statistical Summary",
        "",
        "Generated from existing per-requirement and ranking CSV outputs. This does not rerun model training.",
        "",
        "## Run Inventory",
        "",
        "| run | available | per-requirement CSV | rankings CSV |",
        "|---|---:|---|---|",
    ]
    for run in runs:
        lines.append(
            f"| {run['name']} | {str(run['available']).lower()} | "
            f"{run.get('per_requirement_csv', run.get('missing', ''))} | {run.get('rankings_csv', '')} |"
        )
    lines.extend(
        [
            "",
            "## Aggregate Metrics with Bootstrap 95% CIs",
            "",
            "| run | MRR | MAP | Hits@1 | Hits@10 | Recall@10 | NDCG@10 |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for run in runs:
        if not run.get("available"):
            continue
        m = run["metrics"]
        sm = m["set_metrics"]
        lines.append(
            f"| {run['name']} | "
            f"{m['mrr']['mean']:.4f} [{m['mrr']['ci_low']:.4f}, {m['mrr']['ci_high']:.4f}] | "
            f"{m['map']['mean']:.4f} [{m['map']['ci_low']:.4f}, {m['map']['ci_high']:.4f}] | "
            f"{m['hits_at_1']['mean']:.4f} [{m['hits_at_1']['ci_low']:.4f}, {m['hits_at_1']['ci_high']:.4f}] | "
            f"{m['hits_at_10']['mean']:.4f} [{m['hits_at_10']['ci_low']:.4f}, {m['hits_at_10']['ci_high']:.4f}] | "
            f"{sm.get('recall_at_10', 0.0):.4f} | {sm.get('ndcg_at_10', 0.0):.4f} |"
        )
    lines.extend(
        [
            "",
            "## Paired Comparisons",
            "",
            "Deltas are `a - b` over matched requirements with at least one gold trace.",
            "",
            "| comparison | metric | delta | 95% CI | randomization p | Holm p |",
            "|---|---|---:|---:|---:|---:|",
        ]
    )
    for comp in comparisons:
        for metric, vals in comp["metrics"].items():
            lines.append(
                f"| {comp['a']} - {comp['b']} | {metric} | "
                f"{vals['mean_delta']:.4f} | [{vals['ci_low']:.4f}, {vals['ci_high']:.4f}] | "
                f"{vals['p_value']:.4f} | {vals['holm_p_value']:.4f} |"
            )
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", default=".", help="Project root directory")
    parser.add_argument("--output-dir", default="experiments/benchmark_package_review")
    parser.add_argument("--iterations", type=int, default=5000)
    parser.add_argument("--seed", type=int, default=20260523)
    args = parser.parse_args()

    root = Path(args.project_root).resolve()
    output_dir = root / args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    rng = random.Random(args.seed)
    prefixes = {name: root / path for name, path in DEFAULT_RUNS.items()}

    runs = [summarize_run(name, prefix, args.iterations, rng) for name, prefix in prefixes.items()]
    available = {run["name"] for run in runs if run.get("available")}

    comparisons = []
    flat_tests: list[dict[str, object]] = []
    for a, b in PAIRWISE_COMPARISONS:
        if a not in available or b not in available:
            continue
        comp = compare_runs(a, b, prefixes, args.iterations, rng)
        comparisons.append(comp)
        for metric, vals in comp["metrics"].items():
            flat_tests.append(vals)
    holm_adjust(flat_tests)

    (output_dir / "benchmark_package_summary.json").write_text(
        json.dumps({"runs": runs, "paired_comparisons": comparisons}, indent=2),
        encoding="utf-8",
    )
    write_markdown(output_dir / "README.md", runs, comparisons)


if __name__ == "__main__":
    main()
