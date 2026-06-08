# Repo attachment steps

Use this when you have the public GitHub repo ready to bind to the pilot package.

1. **Make the repo public** and confirm the license.
2. **Record the canonical repo URL** in the benchmark manifest.
3. **Freeze a base commit** for the pilot snapshot.
4. **Identify the task set**:
   - issue/requirement text
   - linked PRs
   - fix commits
   - affected files
   - linked tests
5. **Mirror the repo locally** into `data/raw/<repo-name>`.
6. **Extract structure**:
   - classes/modules
   - methods/functions
   - call edges
   - test nodes
7. **Extract evidence**:
   - issues
   - PRs
   - reviews
   - checks
   - CI runs
   - test reports
8. **Build gold labels**:
   - implementation file/method labels
   - test file/method labels
   - positive/negative/partial cases
9. **Generate task manifests** for the benchmark splits.
10. **Run a smoke pass** on the first 5–10 tasks before expanding.

## Recommended attachment fields

- `repo_url`
- `repo_owner`
- `repo_name`
- `default_branch`
- `license_spdx`
- `base_commit_sha`
- `fix_commit_sha`
- `issue_number`
- `pr_number`
- `test_command`
- `ci_run_id`
- `test_report_paths`
- `gold_code_files`
- `gold_test_files`

## What to send me next

- Repo URL
- Default branch
- One representative issue/PR pair
- Test command used in CI or locally
- Any notes on license or redistribution limits
