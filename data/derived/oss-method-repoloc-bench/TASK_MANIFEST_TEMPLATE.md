# Task Manifest Template

Use one record per issue/PR pair.

```yaml
task_id: ""
repo_url: "https://github.com/00n-ai/repoloc-bench"
repo_owner: "00n-ai"
repo_name: "repoloc-bench"
language: ""
benchmark_split: "pilot"

issue:
  number: null
  title: ""
  body: ""
  labels: []
  url: ""

pull_request:
  number: null
  title: ""
  body: ""
  url: ""
  merged_at: ""
  review_decision: ""

snapshots:
  base_commit_sha: ""
  fix_commit_sha: ""
  base_tree_sha: ""
  fix_tree_sha: ""

localization_gold:
  code_files: []
  code_methods: []
  test_files: []
  test_methods: []

execution_evidence:
  test_command: ""
  ci_run_id: ""
  ci_status: ""
  test_report_paths: []
  log_paths: []

retrieval:
  knowledge_tree_version: ""
  context_budget_tokens: 0
  context_ids: []

labels:
  status: "satisfied|partial|missing|implemented_untested|ambiguous|not_accepted|stale_evidence"
  evidence_strength: "direct|indirect|weak|missing"
  notes: ""

integrity:
  task_hash: ""
  manifest_version: "1.0.0"
```

## Fill order
1. issue/PR metadata
2. snapshot SHAs
3. code localization gold
4. test localization gold
5. execution evidence
6. final status

## Purpose
This is the working manifest for turning the public repo into a runnable benchmark set.
