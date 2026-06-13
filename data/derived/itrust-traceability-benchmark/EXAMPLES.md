# Paper 1 Benchmark Examples

## Example 1: Original requirement task

```json
{
  "task_id": "orig:itrust:R1",
  "branch": "original",
  "system": "itrust",
  "requirement_id": 1,
  "query_text": "Add a New Patient ...",
  "gold_method_ids": [154, 2851, 2986, 2992, 3125, 3126, 4655],
  "positive_trace_count": 7,
  "auxiliary": false
}
```

## Example 2: Requirement node

```json
{
  "node_id": "requirement:itrust:1",
  "system": "itrust",
  "original_text": "Add a New Patient ...",
  "imputed_text": "The system shall allow the addition of a new patient with basic information and generate a unique MID for them.",
  "gold_method_count": 7,
  "trace_label_counts": {"T": 7, "E": 4687, "N": 213, "UNK": 0}
}
```

## Example 3: Masked gold-edge suite

```json
{
  "mask_percent": 10,
  "totals": {
    "gold_edges": 307,
    "held_out_gold_edges": 39,
    "observed_gold_edges": 268
  }
}
```

## Example 4: Manifest summary

```json
{
  "dataset_name": "paper1-benchmark",
  "system": "itrust",
  "requirements": 34,
  "methods": 4907,
  "classes": 718,
  "gold_traces": 307
}
```
