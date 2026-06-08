# Test Evidence Schema Stub

Use this as the placeholder schema for the next pilot layer.

## Goal
Attach test evidence to each task so we can evaluate test localization and test adequacy later.

## Record shape

```json
{
  "task_id": "",
  "system": "",
  "repo_url": "",
  "base_commit_sha": "",
  "fix_commit_sha": "",
  "test_nodes": [],
  "test_edges": [],
  "test_reports": [],
  "ci_runs": [],
  "test_command": "",
  "gold_test_files": [],
  "gold_test_methods": [],
  "test_status": "passed|failed|flaky|unknown",
  "evidence_status": "direct|indirect|stale|missing",
  "notes": ""
}
```

## Test node fields
- `node_id`
- `file_path`
- `test_name`
- `test_signature`
- `framework`
- `language`
- `status`
- `source_hash`

## Test edge fields
- `edge_id`
- `source_node_id`
- `target_node_id`
- `edge_type`
- `evidence_kind`
- `confidence`

## Evidence sources
- local test execution
- CI workflow logs
- test report XML/JSON
- coverage output
- issue / PR links when they identify the relevant test

## Status taxonomy
- `direct`: exact test evidence for the task
- `indirect`: nearby or supporting test evidence
- `stale`: evidence from the wrong commit or branch
- `missing`: no usable test evidence found

## Next action
Populate this schema after the GitHub repo is attached.
