# iTrust Requirement-to-Code Traceability Benchmark Dataset

## Objective

Create a benchmark-ready dataset that can recover hidden trace links and explain them with structured evidence.

## Why we are doing this

- Ground Paper 1 in a real repo-backed benchmark.
- Measure whether heterogeneous structure improves trace recovery over flat retrieval.
- Separate true trace compatibility from simple semantic similarity.
- Support reranking, symbolic verification, and uncertainty experiments later.
- Produce a reproducible and auditable package for the manuscript.

## What this dataset is for

- method localization benchmarking
- structured graph retrieval baselines
- masked-edge recovery experiments
- train/validation/test evaluation

## Claim boundary

- Primary branch is original requirement text.
- LLM-imputed requirements are auxiliary sensitivity data only.
- Gold links use traces with goldfinal == 'T'.
- This package is a method-localization benchmark foundation, not yet a test-localization benchmark.

## Contents

- 34 requirements
- 4907 methods
- 718 classes
- 166838 total traces
- 307 gold traces

## Build artifacts

- requirement, method, class, parameter, and field nodes
- typed graph edges
- gold trace edge table
- requirement train/validation/test splits
- masked gold-edge suites at 10/20/30%
- manifest and integrity hashes

## Acceptance criteria

- every node has a stable ID, type, and provenance
- every edge points to valid nodes and has a defined relation type
- gold trace links are documented and reproducible
- masked splits are non-overlapping and leakage-free
- the first retrieval baseline can run end-to-end on the dataset
- benchmark metrics can be reported from the same dataset package
- the dataset is understandable by a future reader without hidden assumptions

