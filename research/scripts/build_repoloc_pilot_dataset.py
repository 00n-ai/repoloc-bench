#!/usr/bin/env python3
"""Build the Paper 1 pilot benchmark package for repository localization.

This packages the MSR open-source requirement-to-method dataset into a single
self-contained artifact bundle with:
- original requirement tasks (primary branch)
- LLM-imputed requirement tasks (auxiliary branch)
- node tables for requirements, methods, and classes
- graph edges for requirement->method, method->method, method->class, and
  class structure relations
- copied source JSON assets for reproducibility

Claim boundary:
- This is a code-localization / repository-structure pilot.
- It is not yet a full test-localization benchmark because the source dataset
  is method-grounded rather than test-grounded.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOT = PROJECT_ROOT / "data/derived/oss-method-llm-requirements"
GENERATED_ROOT = PROJECT_ROOT / "experiments/oss_method_llm_requirements"
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "data/derived/oss-method-repoloc-pilot"
SYSTEMS = ("chess", "gantt", "itrust", "jhotdraw")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n", encoding="utf-8")


def normalize_text(value: object) -> str:
    return " ".join(str(value or "").split())


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def safe_copytree(src: Path, dst: Path) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)


def method_signature(row: dict[str, Any]) -> str:
    return normalize_text(row.get("methodabbreviation") or row.get("fullmethod") or row.get("methodname") or row.get("method"))


def build_system_bundle(system: str, output_root: Path) -> dict[str, Any]:
    source_dir = SOURCE_ROOT / f"{system}JSON"
    generated_path = GENERATED_ROOT / f"{system}_generated_requirements.jsonl"
    if not source_dir.exists():
        raise FileNotFoundError(source_dir)
    if not generated_path.exists():
        raise FileNotFoundError(generated_path)

    # Copy the raw normalized source bundle into the package.
    bundle_dir = output_root / "systems" / system
    safe_copytree(source_dir, bundle_dir / "source")
    shutil.copy2(generated_path, bundle_dir / "generated_requirements.jsonl")

    requirements = load_json(source_dir / "requirements.json")
    methods = load_json(source_dir / "methods.json")
    classes = load_json(source_dir / "classes.json")
    traces = load_json(source_dir / "traces.json")
    methodcalls_path = source_dir / "methodcalls.json"
    if not methodcalls_path.exists():
        methodcalls_path = source_dir / "methocalls.json"
    methodcalls = load_json(methodcalls_path)
    parameters = load_json(source_dir / "parameters.json")
    fieldclasses = load_json(source_dir / "fieldclasses.json")
    fieldmethods = load_json(source_dir / "fieldmethods.json")
    interfaces = load_json(source_dir / "interfaces.json")
    superclasses = load_json(source_dir / "superclasses.json")
    generated_rows = load_jsonl(generated_path)

    methods_by_id = {int(row["id"]): row for row in methods}
    classes_by_id = {int(row["id"]): row for row in classes}
    requirements_by_id = {int(row["id"]): row for row in requirements}
    generated_by_req = {int(row["requirement_local_id"]): row for row in generated_rows}

    positive_traces = [row for row in traces if str(row.get("goldfinal", "")).upper() == "T"]
    trace_label_counts: dict[int, dict[str, int]] = {}
    for row in traces:
        rid = int(row["requirementid"])
        label = str(row.get("goldfinal", "")).upper() or "UNK"
        trace_label_counts.setdefault(rid, {"T": 0, "E": 0, "N": 0, "UNK": 0})
        trace_label_counts[rid][label if label in {"T", "E", "N"} else "UNK"] += 1

    requirement_nodes: list[dict[str, Any]] = []
    original_tasks: list[dict[str, Any]] = []
    imputed_tasks: list[dict[str, Any]] = []
    method_nodes: list[dict[str, Any]] = []
    class_nodes: list[dict[str, Any]] = []
    parameter_nodes: list[dict[str, Any]] = []
    field_nodes: list[dict[str, Any]] = []
    edge_rows: list[dict[str, Any]] = []

    for req in requirements:
        req_id = int(req["id"])
        req_text = normalize_text(req.get("requirementname") or req.get("requirement") or req.get("title") or "")
        req_node_id = f"requirement:{system}:{req_id}"
        gold_rows = [row for row in traces if int(row["requirementid"]) == req_id and str(row.get("goldfinal", "")).upper() == "T"]
        gold_method_ids = sorted({int(row["methodid"]) for row in gold_rows})
        gold_method_evidence = [
            {
                "method_id": mid,
                "method_signature": method_signature(methods_by_id[mid]),
                "class_id": int(methods_by_id[mid].get("classid", 0) or 0),
                "class_name": normalize_text(methods_by_id[mid].get("classname")),
            }
            for mid in gold_method_ids
            if mid in methods_by_id
        ]
        gen = generated_by_req.get(req_id, {})
        gen_req = gen.get("generated", {}) if isinstance(gen, dict) else {}

        requirement_nodes.append(
            {
                "node_id": req_node_id,
                "system": system,
                "requirement_id": req_id,
                "source_label": normalize_text(req.get("requirementname") or req.get("requirement") or f"R{req_id}"),
                "original_text": req_text,
                "original_text_sha256": sha256_text(req_text),
                "imputed_title": normalize_text(gen_req.get("title")),
                "imputed_text": normalize_text(gen_req.get("requirement")),
                "functional_capabilities": gen_req.get("functional_capabilities", []),
                "acceptance_criteria": gen_req.get("acceptance_criteria", []),
                "imputed_confidence": gen_req.get("confidence"),
                "imputed_evidence_summary": normalize_text(gen_req.get("evidence_summary")),
                "imputed_leakage_risk": normalize_text(gen.get("leakage_risk")),
                "generation_mode": normalize_text(gen.get("generation_mode")),
                "generated_prompt_sha256": normalize_text(gen.get("prompt_sha256")),
                "generated_elapsed_seconds": gen.get("elapsed_seconds"),
                "gold_method_ids": gold_method_ids,
                "gold_method_count": len(gold_method_ids),
                "gold_method_evidence": gold_method_evidence,
                "trace_label_counts": trace_label_counts.get(req_id, {"T": 0, "E": 0, "N": 0, "UNK": 0}),
            }
        )

        original_tasks.append(
            {
                "task_id": f"orig:{system}:R{req_id}",
                "branch": "original",
                "system": system,
                "requirement_id": req_id,
                "requirement_node_id": req_node_id,
                "query_text": req_text,
                "query_text_sha256": sha256_text(req_text),
                "source_label": normalize_text(req.get("requirementname") or req.get("requirement") or f"R{req_id}"),
                "gold_method_ids": gold_method_ids,
                "gold_method_count": len(gold_method_ids),
                "gold_method_evidence": gold_method_evidence,
                "positive_trace_count": len(gold_rows),
                "trace_label_counts": trace_label_counts.get(req_id, {"T": 0, "E": 0, "N": 0, "UNK": 0}),
                "auxiliary": False,
                "notes": "Primary branch for Paper 1 experiments.",
            }
        )

        imputed_text = normalize_text(gen_req.get("requirement") or req_text)
        imputed_tasks.append(
            {
                "task_id": f"llm:{system}:R{req_id}",
                "branch": "llm_imputed",
                "system": system,
                "requirement_id": req_id,
                "requirement_node_id": req_node_id,
                "query_text": imputed_text,
                "query_text_sha256": sha256_text(imputed_text),
                "imputed_title": normalize_text(gen_req.get("title")),
                "functional_capabilities": gen_req.get("functional_capabilities", []),
                "acceptance_criteria": gen_req.get("acceptance_criteria", []),
                "imputed_confidence": gen_req.get("confidence"),
                "imputed_evidence_summary": normalize_text(gen_req.get("evidence_summary")),
                "imputed_leakage_risk": normalize_text(gen.get("leakage_risk")),
                "generation_mode": normalize_text(gen.get("generation_mode")),
                "generated_prompt_sha256": normalize_text(gen.get("prompt_sha256")),
                "generated_elapsed_seconds": gen.get("elapsed_seconds"),
                "source_requirement_text": req_text,
                "source_requirement_sha256": sha256_text(req_text),
                "gold_method_ids": gold_method_ids,
                "gold_method_count": len(gold_method_ids),
                "gold_method_evidence": gold_method_evidence,
                "positive_trace_count": len(gold_rows),
                "trace_label_counts": trace_label_counts.get(req_id, {"T": 0, "E": 0, "N": 0, "UNK": 0}),
                "auxiliary": True,
                "notes": "Auxiliary LLM-imputed branch for sensitivity analysis only.",
            }
        )

    for method in methods:
        method_id = int(method["id"])
        method_node_id = f"method:{system}:{method_id}"
        method_nodes.append(
            {
                "node_id": method_node_id,
                "system": system,
                "method_id": method_id,
                "class_id": int(method.get("classid", 0) or 0),
                "class_name": normalize_text(method.get("classname")),
                "method_name": normalize_text(method.get("methodname")),
                "method_name_refined": normalize_text(method.get("methodnamerefined")),
                "method_signature": method_signature(method),
                "full_method": normalize_text(method.get("fullmethod")),
                "source_code": method.get("method", ""),
            }
        )

    for cls in classes:
        class_id = int(cls["id"])
        class_nodes.append(
            {
                "node_id": f"class:{system}:{class_id}",
                "system": system,
                "class_id": class_id,
                "class_name": normalize_text(cls.get("classname")),
            }
        )

    # Graph edges.
    for row in traces:
        rid = int(row["requirementid"])
        mid = int(row["methodid"])
        label = normalize_text(row.get("goldfinal", ""))
        edge_rows.append(
            {
                "edge_id": f"{system}:req-method:{row['id']}",
                "system": system,
                "edge_type": "requirement_to_method",
                "source_node_id": f"requirement:{system}:{rid}",
                "target_node_id": f"method:{system}:{mid}",
                "trace_label": label,
                "is_gold": label == "T",
                "requirement_id": rid,
                "method_id": mid,
            }
        )

    for row in methodcalls:
        caller = int(row["callermethodid"])
        callee = int(row["calleemethodid"])
        edge_rows.append(
            {
                "edge_id": f"{system}:method-call:{row['id']}",
                "system": system,
                "edge_type": "method_calls_method",
                "source_node_id": f"method:{system}:{caller}",
                "target_node_id": f"method:{system}:{callee}",
                "caller_name": normalize_text(row.get("callername")),
                "callee_name": normalize_text(row.get("calleename")),
                "caller_class": normalize_text(row.get("callerclass")),
                "callee_class": normalize_text(row.get("calleeclass")),
            }
        )

    for row in parameters:
        method_id = int(row["methodid"])
        param_id = int(row["id"])
        parameter_nodes.append(
            {
                "node_id": f"parameter:{system}:{param_id}",
                "system": system,
                "parameter_id": param_id,
                "method_id": method_id,
                "parameter_name": normalize_text(row.get("parametername")),
                "parameter_type": normalize_text(row.get("parametertype")),
                "is_return": int(row.get("isreturn", 0) or 0),
                "source_code": row.get("sourcecode", ""),
            }
        )
        edge_rows.append(
            {
                "edge_id": f"{system}:method-param:{row['id']}",
                "system": system,
                "edge_type": "method_has_parameter",
                "source_node_id": f"method:{system}:{method_id}",
                "target_node_id": f"parameter:{system}:{param_id}",
                "parameter_name": normalize_text(row.get("parametername")),
                "parameter_type": normalize_text(row.get("parametertype")),
                "is_return": int(row.get("isreturn", 0) or 0),
            }
        )

    for row in fieldclasses:
        owner = int(row["ownerclassid"])
        fieldclass_raw = row.get("fieldclassid")
        if fieldclass_raw is None:
            continue
        fieldclass_id = int(fieldclass_raw)
        field_nodes.append(
            {
                "node_id": f"fieldclass:{system}:{fieldclass_id}",
                "system": system,
                "fieldclass_id": fieldclass_id,
                "owner_class_id": owner,
                "owner_class_name": normalize_text(row.get("classname")),
                "field_name": normalize_text(row.get("fieldname")),
                "field_type": normalize_text(row.get("fieldtype")),
                "read": normalize_text(row.get("read")),
            }
        )
        edge_rows.append(
            {
                "edge_id": f"{system}:fieldclass:{row['id']}",
                "system": system,
                "edge_type": "class_owns_fieldclass",
                "source_node_id": f"class:{system}:{owner}",
                "target_node_id": f"fieldclass:{system}:{fieldclass_id}",
                "field_name": normalize_text(row.get("fieldname")),
                "field_type": normalize_text(row.get("fieldtype")),
                "read": normalize_text(row.get("read")),
            }
        )

    for row in fieldmethods:
        owner = int(row["ownerclassid"])
        fieldclass_raw = row.get("fieldclassid")
        if fieldclass_raw is None:
            continue
        fieldclass_id = int(fieldclass_raw)
        edge_rows.append(
            {
                "edge_id": f"{system}:fieldmethod:{row['id']}",
                "system": system,
                "edge_type": "method_reads_or_writes_field",
                "source_node_id": f"method:{system}:{int(row['ownermethodid'])}",
                "target_node_id": f"fieldclass:{system}:{fieldclass_id}",
                "owner_class_id": owner,
                "field_name": normalize_text(row.get("fieldname")),
                "read": normalize_text(row.get("read")),
                "owner_method_name": normalize_text(row.get("ownermethodname")),
            }
        )

    for row in interfaces:
        owner = int(row["ownerclassid"])
        interface_id = int(row["interfaceclassid"])
        edge_rows.append(
            {
                "edge_id": f"{system}:interface:{row['id']}",
                "system": system,
                "edge_type": "class_implements_interface",
                "source_node_id": f"class:{system}:{owner}",
                "target_node_id": f"class:{system}:{interface_id}",
                "interface_name": normalize_text(row.get("interfacename")),
            }
        )

    for row in superclasses:
        owner = int(row["ownerclassid"])
        superclass_id = int(row["superclassid"])
        edge_rows.append(
            {
                "edge_id": f"{system}:superclass:{row['id']}",
                "system": system,
                "edge_type": "class_inherits_from_class",
                "source_node_id": f"class:{system}:{owner}",
                "target_node_id": f"class:{system}:{superclass_id}",
                "superclass_name": normalize_text(row.get("superclassname")),
            }
        )

    # A compact summary for the manifest.
    summary = {
        "system": system,
        "source_dir": str(source_dir),
        "generated_requirements_path": str(generated_path),
        "requirements": len(requirements),
        "methods": len(methods),
        "classes": len(classes),
        "traces": len(traces),
        "gold_traces": len(positive_traces),
        "methodcalls": len(methodcalls),
        "parameters": len(parameters),
        "fieldclasses": len(fieldclasses),
        "fieldmethods": len(fieldmethods),
        "interfaces": len(interfaces),
        "superclasses": len(superclasses),
    }

    # Write per-system normalized assets.
    write_json(bundle_dir / "summary.json", summary)
    write_jsonl(bundle_dir / "requirements_nodes.jsonl", requirement_nodes)
    write_jsonl(bundle_dir / "original_tasks.jsonl", original_tasks)
    write_jsonl(bundle_dir / "imputed_tasks.jsonl", imputed_tasks)
    write_jsonl(bundle_dir / "methods_nodes.jsonl", method_nodes)
    write_jsonl(bundle_dir / "classes_nodes.jsonl", class_nodes)
    write_jsonl(bundle_dir / "parameter_nodes.jsonl", parameter_nodes)
    write_jsonl(bundle_dir / "field_nodes.jsonl", field_nodes)
    write_jsonl(bundle_dir / "edges.jsonl", edge_rows)

    # Keep direct copies of the original source tables for convenience.
    source_names = [
        "requirements.json",
        "methods.json",
        "classes.json",
        "traces.json",
        methodcalls_path.name,
        "parameters.json",
        "fieldclasses.json",
        "fieldmethods.json",
        "interfaces.json",
        "superclasses.json",
    ]
    for name in source_names:
        shutil.copy2(source_dir / name, bundle_dir / name)

    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the Paper 1 pilot benchmark package.")
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--force", action="store_true", help="Overwrite the output directory if it exists.")
    args = parser.parse_args()

    if args.output_root.exists():
        if not args.force:
            raise SystemExit(f"output already exists: {args.output_root} (use --force to rebuild)")
        shutil.rmtree(args.output_root)
    args.output_root.mkdir(parents=True, exist_ok=True)

    system_summaries = [build_system_bundle(system, args.output_root) for system in SYSTEMS]

    total_requirements = sum(s["requirements"] for s in system_summaries)
    total_methods = sum(s["methods"] for s in system_summaries)
    total_classes = sum(s["classes"] for s in system_summaries)
    total_traces = sum(s["traces"] for s in system_summaries)
    total_gold = sum(s["gold_traces"] for s in system_summaries)

    manifest = {
        "dataset_name": "oss-method-repoloc-pilot",
        "paper": "Paper 1: Structured Repository Knowledge Trees for LLM-Grounded Code and Test Localization",
        "scope": "pilot code-localization benchmark built from the MSR open-source requirement-to-method traceability dataset",
        "source": {
            "raw_zip": str(PROJECT_ROOT / "data/raw/oss-method/MSRCaseStudy.zip"),
            "derived_source_root": str(SOURCE_ROOT),
            "generated_requirement_root": str(GENERATED_ROOT),
        },
        "claim_boundary": [
            "Primary branch is original requirement text.",
            "LLM-imputed requirements are auxiliary sensitivity data only.",
            "Gold links use traces with goldfinal == 'T'.",
            "This package does not yet include test-localization ground truth.",
        ],
        "totals": {
            "systems": len(SYSTEMS),
            "requirements": total_requirements,
            "methods": total_methods,
            "classes": total_classes,
            "traces": total_traces,
            "gold_traces": total_gold,
        },
        "systems": system_summaries,
        "package_layout": {
            "requirements_nodes": "systems/<system>/requirements_nodes.jsonl",
            "original_tasks": "systems/<system>/original_tasks.jsonl",
            "imputed_tasks": "systems/<system>/imputed_tasks.jsonl",
            "methods_nodes": "systems/<system>/methods_nodes.jsonl",
            "classes_nodes": "systems/<system>/classes_nodes.jsonl",
            "edges": "systems/<system>/edges.jsonl",
            "source_tables": "systems/<system>/*.json",
        },
        "recommended_primary_split": "original",
        "recommended_auxiliary_split": "llm_imputed",
        "evaluation_intent": [
            "Hits@k / MRR for method localization",
            "ablation of hierarchy and structural edges",
            "token-efficiency / retrieval-budget analysis",
        ],
    }

    write_json(args.output_root / "manifest.json", manifest)
    write_json(
        args.output_root / "README.json",
        {
            "title": "OSS Method RepoLoc Pilot Package",
            "usage": [
                "Load systems/<system>/original_tasks.jsonl for primary experiments.",
                "Use systems/<system>/imputed_tasks.jsonl only for auxiliary sensitivity runs.",
                "Use systems/<system>/edges.jsonl to build the knowledge tree / graph context.",
            ],
        },
    )

    readme = [
        "# OSS Method RepoLoc Pilot",
        "",
        "Self-contained pilot package for Paper 1: structured repository knowledge trees for LLM-grounded localization.",
        "",
        "Primary branch:",
        "- original requirement text",
        "",
        "Auxiliary branch:",
        "- LLM-imputed requirement text",
        "",
        "Gold semantics:",
        "- traces with `goldfinal == 'T'` are gold links",
        "",
        "Includes:",
        f"- {total_requirements} requirements",
        f"- {total_methods} methods",
        f"- {total_classes} classes",
        f"- {total_traces} total traces",
        f"- {total_gold} positive traces",
        "",
        "Claim boundary:",
        "- This is a code-localization benchmark foundation, not yet a test-localization benchmark.",
    ]
    (args.output_root / "README.md").write_text("\n".join(readme) + "\n", encoding="utf-8")

    # Hash the key package files for quick integrity checking.
    integrity = {
        "manifest_sha256": file_sha256(args.output_root / "manifest.json"),
        "readme_sha256": file_sha256(args.output_root / "README.md"),
        "system_summaries": {s["system"]: sha256_text(json.dumps(s, sort_keys=True)) for s in system_summaries},
    }
    write_json(args.output_root / "integrity.json", integrity)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
