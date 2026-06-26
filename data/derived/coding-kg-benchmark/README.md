# Coding KG-Agent Benchmark

Public data artifacts for the coding knowledge graph agent benchmark experiment.

## Experiment

4 models × 4 conditions × 9 tasks × 5 runs = 585 total runs

- **Models:** qwen2.5:7b, mistral:7b, llama3.1:8b (Ollama), GLM-5.2 (DeepInfra, frontier B0 ceiling)
- **Conditions:** B0 (vanilla), KG (graph navigation), KG-NL (NL serialization), MA+KG (multi-agent + directional reasoning)
- **Tasks:** 9 code tasks across generation, repair, and completion on a 4-module Python codebase
- **Evaluation:** Pass@1 via pytest (5 runs per task/condition/model)

## Files

| File | Description |
|---|---|
| `code-graph.json` | Knowledge graph: 178 nodes, 348 edges, 4 convention nodes |
| `tasks.json` | 9 task definitions with prompts, modules, and test file paths |
| `full-qwen2-57b-mqur77ed.json` | qwen2.5:7b results (180 runs: 4 conditions × 9 tasks × 5 runs) |
| `full-mistral7b-mquvar1s.json` | mistral:7b results (178 runs) |
| `full-llama3-18b-mquzge6s.json` | llama3.1:8b results (180 runs) |
| `frontier-b0.json` | GLM-5.2 frontier B0 ceiling (45 runs: 9 tasks × 5 runs) |

## Result Format

Each JSON file contains an array of run results with:

```json
{
  "task_id": "gen-cancel-subscription",
  "task_type": "generation",
  "model": "qwen2.5:7b",
  "condition": "ma-kg",
  "run": 0,
  "pass": 3,
  "total": 4,
  "pass_rate": 0.75,
  "llm_calls": 15,
  "tokens_in": 45000,
  "tokens_out": 3000,
  "duration_ms": 65000,
  "generated_code": "...",
  "kg_visited_nodes": ["..."],
  "kg_reasoning_gaps": []
}
```

## Headline Results

| Condition | qwen 7B | mistral 7B | llama 8B | GLM-5.2 |
|---|---:|---:|---:|---:|
| B0 | 28.1% | 19.8% | 45.9% | — |
| KG | 16.9% | 19.3% | 24.5% | — |
| KG-NL | 15.4% | 20.2% | 16.9% | — |
| MA+KG | 23.9% | 38.0% | 48.3% | — |
| Frontier B0 | — | — | — | 83.9% |

Full analysis: https://00n.ai/research/coding-kg-agent-benchmark/