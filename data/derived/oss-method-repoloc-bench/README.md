# OSS Method RepoLoc Pilot

Self-contained pilot package for Paper 1: structured repository knowledge trees for LLM-grounded localization.

Primary branch:
- original requirement text

Auxiliary branch:
- LLM-imputed requirement text

Gold semantics:
- traces with `goldfinal == 'T'` are gold links

Includes:
- 81 requirements
- 17192 methods
- 2151 classes
- 400008 total traces
- 3235 positive traces

Claim boundary:
- This is a code-localization benchmark foundation, not yet a test-localization benchmark.

Next step:
- Attach a public GitHub repo and use `REPO_ATTACHMENT_STEPS.md` to wire in code + test evidence.
- Test evidence schema stub: `TEST_EVIDENCE_SCHEMA.md`.
- Task manifest template: `TASK_MANIFEST_TEMPLATE.md`.
