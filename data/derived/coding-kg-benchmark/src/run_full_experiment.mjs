#!/usr/bin/env node
/**
 * run_full_experiment.mjs — Full coding KG experiment with all 4 directional-reasoning fixes.
 *
 * Design:
 *   3 models (qwen2.5:7b, mistral:7b, llama3.1:8b)
 *   × 4 conditions (B0, KG, KG-NL, MA+KG)
 *   × 9 tasks
 *   × 5 runs
 *   = 540 runs
 *
 *   + Frontier B0 (GLM-5.2) × 9 tasks × 5 runs = 45 runs (ceiling reference)
 *
 * Usage (run once per model):
 *   LLM_PROVIDER=ollama LLM_MODEL=qwen2.5:7b node src/run_full_experiment.mjs --runs 5
 *   LLM_PROVIDER=ollama LLM_MODEL=mistral:7b node src/run_full_experiment.mjs --runs 5
 *   LLM_PROVIDER=ollama LLM_MODEL=llama3.1:8b node src/run_full_experiment.mjs --runs 5
 *   LLM_PROVIDER=deepinfra LLM_MODEL=deepinfra/zai-org/GLM-5.2 node src/run_full_experiment.mjs --frontier --runs 5
 *
 * Results saved to results/full-<model>-<timestamp>.json
 * Incremental save after each run.
 */

import fs from 'node:fs';
import nodePath from 'node:path';
import { execSync } from 'node:child_process';
import { runCodeKGAgent, runCodeB0 } from './code_kg_agent.js';
import { runMAKGAgent } from './ma_kg_agent.js';

const PYTEST = '/home/linuxbrew/.linuxbrew/bin/pytest';
const REPO_SRC = nodePath.join(process.cwd(), 'example-repo', 'src');
const TASKS = JSON.parse(fs.readFileSync('tasks/tasks.json', 'utf8'));
const RESULTS_DIR = 'results';

if (!fs.existsSync(RESULTS_DIR)) fs.mkdirSync(RESULTS_DIR, { recursive: true });

// Parse args
const args = process.argv.slice(2);
const runsFlag = args.indexOf('--runs');
const RUNS = runsFlag >= 0 ? parseInt(args[runsFlag + 1]) : 5;
const isFrontier = args.includes('--frontier');
const CONDITIONS = isFrontier ? ['frontier-b0'] : ['b0', 'kg', 'kg-nl', 'ma-kg'];
const MODEL = process.env.LLM_MODEL || 'qwen2.5:7b';

// ─── Extract code from LLM output ───
function extractCode(llmOutput) {
  const m = llmOutput.match(/```python\n([\s\S]*?)```/);
  return m ? m[1] : llmOutput;
}

// ─── Clean pycache ───
function cleanPycache() {
  for (const dir of [
    'example-repo/src/__pycache__', 'example-repo/tests/__pycache__', 'tasks/tests/__pycache__'
  ]) {
    try { fs.rmSync(nodePath.join(process.cwd(), dir), { recursive: true, force: true }); } catch {}
  }
}

// ─── Inject + test (for B0, KG, KG-NL) ───
function injectAndTest(task, generatedCode) {
  const modulePath = nodePath.join(REPO_SRC, `${task.module}.py`);
  const orig = fs.readFileSync(modulePath, 'utf8');
  const tmpDir = nodePath.join(process.cwd(), '.tmp-test');
  try {
    fs.mkdirSync(tmpDir, { recursive: true });
    const testSrc = nodePath.join(process.cwd(), task.test_file);
    const testDst = nodePath.join(tmpDir, nodePath.basename(task.test_file));
    fs.copyFileSync(testSrc, testDst);
    fs.writeFileSync(modulePath, orig + '\n\n# ─── GENERATED CODE (experiment) ───\n\n' + generatedCode);
    cleanPycache();

    // Syntax check
    let syntaxError = null;
    try {
      execSync(`python3 -c "import ast; ast.parse(open('${modulePath}').read())"`, { encoding: 'utf8', timeout: 5000 });
    } catch (e) {
      syntaxError = e.stderr || e.stdout || e.message || '';
    }
    if (syntaxError) {
      return { pass: 0, total: 0, raw: `SYNTAX ERROR: ${syntaxError}` };
    }

    const cmd = `PYTHONPATH=${REPO_SRC}:${nodePath.join(process.cwd(), 'example-repo')} ${PYTEST} ${testDst} -v --tb=short -p no:cacheprovider --rootdir=${tmpDir} 2>&1`;
    let out;
    try { out = execSync(cmd, { encoding: 'utf8', timeout: 30000 }); }
    catch (e) { out = e.stdout || e.stderr || e.message || ''; }

    const collectedMatch = out.match(/collected (\d+) items?/);
    const collected = collectedMatch ? parseInt(collectedMatch[1]) : 0;
    const inlinePassed = (out.match(/::\S+\s+PASSED\s+\[/g) || []).length;
    const inlineFailed = (out.match(/::\S+\s+FAILED\s+\[/g) || []).length;
    const passed = inlinePassed;
    const total = collected > 0 ? collected : (inlinePassed + inlineFailed);
    return { pass: passed, total, raw: out };
  } finally {
    fs.writeFileSync(modulePath, orig);
    cleanPycache();
    try { fs.rmSync(tmpDir, { recursive: true, force: true }); } catch {}
  }
}

// ─── Run one condition ───
async function runCondition(task, model, condition, runIdx) {
  const logger = { logs: [], log(entry) { this.logs.push(entry); } };
  const start = Date.now();
  let result;

  try {
    if (condition === 'b0' || condition === 'frontier-b0') {
      result = await runCodeB0(task.prompt, logger, { model });
    } else if (condition === 'kg') {
      result = await runCodeKGAgent(task.prompt, logger, { model, useNL: false });
    } else if (condition === 'kg-nl') {
      result = await runCodeKGAgent(task.prompt, logger, { model, useNL: true });
    } else if (condition === 'ma-kg') {
      result = await runMAKGAgent(task, logger, { model });
    } else {
      throw new Error(`Unknown condition: ${condition}`);
    }
  } catch (err) {
    return {
      task_id: task.id, task_type: task.type, model, condition, run: runIdx,
      pass: 0, total: task.test_names.length, pass_rate: 0,
      error: err.message, llm_calls: 0, tokens_in: 0, tokens_out: 0,
      duration_ms: Date.now() - start, generated_code: '', test_output: '',
      kg_visited_nodes: [], kg_reasoning_gaps: [],
    };
  }

  // For MA+KG, the pipeline already ran tests internally
  if (condition === 'ma-kg') {
    return {
      task_id: task.id, task_type: task.type, model, condition, run: runIdx,
      pass: result.final_pass, total: result.final_total,
      pass_rate: result.final_total > 0 ? result.final_pass / result.final_total : 0,
      error: null,
      llm_calls: result.llm_calls, tokens_in: result.tokens_in, tokens_out: result.tokens_out,
      duration_ms: Date.now() - start,
      generated_code: result.answer?.substring(0, 3000) || '',
      test_output: '',
      kg_visited_nodes: result.kg_visited_nodes || [],
      kg_reasoning_gaps: result.kg_reasoning_gaps || [],
      kg_rounds: result.rounds?.length || 0,
    };
  }

  // For B0, KG, KG-NL: inject + test
  const code = extractCode(result.answer);
  const testResult = injectAndTest(task, code);

  return {
    task_id: task.id, task_type: task.type, model, condition, run: runIdx,
    pass: testResult.pass, total: testResult.total || task.test_names.length,
    pass_rate: testResult.total > 0 ? testResult.pass / testResult.total : 0,
    error: testResult.error,
    llm_calls: result.llm_calls || 1, tokens_in: result.tokens_in, tokens_out: result.tokens_out,
    duration_ms: Date.now() - start,
    generated_code: code.substring(0, 3000),
    test_output: testResult.raw?.substring(0, 2000) || '',
    kg_visited_nodes: result.kg_visited_nodes || [],
    kg_reasoning_gaps: result.kg_reasoning_gaps || [],
  };
}

// ─── Main ───
async function main() {
  const modelSlug = MODEL.replace(/[/\\.]/g, '-').replace(/[^a-zA-Z0-9-]/g, '');
  const runId = `full-${modelSlug}-${Date.now().toString(36)}`;
  const resultsPath = nodePath.join(RESULTS_DIR, `${runId}.json`);
  const allResults = [];

  const totalRuns = TASKS.length * CONDITIONS.length * RUNS;

  console.log('╔══════════════════════════════════════════════════════════╗');
  console.log('║     CODING KG-AGENT FULL EXPERIMENT                      ║');
  console.log('╚══════════════════════════════════════════════════════════╝');
  console.log(`Model: ${MODEL}`);
  console.log(`Conditions: ${CONDITIONS.join(', ')}`);
  console.log(`Tasks: ${TASKS.length}`);
  console.log(`Runs per task/condition: ${RUNS}`);
  console.log(`Total runs: ${totalRuns}`);
  console.log(`Results: ${resultsPath}`);
  console.log('');

  let runCount = 0;
  const startTime = Date.now();

  for (let runIdx = 0; runIdx < RUNS; runIdx++) {
    for (const condition of CONDITIONS) {
      for (const task of TASKS) {
        runCount++;
        const pct = ((runCount / totalRuns) * 100).toFixed(1);
        console.log(`[${runCount}/${totalRuns} ${pct}%] Run ${runIdx + 1}/${RUNS} | ${condition} | ${task.id}`);

        const result = await runCondition(task, MODEL, condition, runIdx);
        allResults.push(result);

        const status = result.pass === result.total && result.total > 0 ? '✅' :
                       result.pass > 0 ? '⚠️' : '❌';
        console.log(`  ${status} ${result.pass}/${result.total} (${(result.duration_ms / 1000).toFixed(1)}s, ${result.llm_calls} LLM calls)`);

        // Save incrementally
        fs.writeFileSync(resultsPath, JSON.stringify({
          run_id: runId,
          model: MODEL,
          conditions: CONDITIONS,
          runs: RUNS,
          tasks: TASKS.length,
          total_runs: totalRuns,
          completed: allResults.length,
          results: allResults,
        }, null, 2));
      }
    }
  }

  const elapsed = ((Date.now() - startTime) / 1000).toFixed(0);

  // ─── Summary ───
  console.log('\n╔══════════════════════════════════════════════════════════╗');
  console.log('║                    SUMMARY                               ║');
  console.log('╚══════════════════════════════════════════════════════════╝\n');

  // Per-condition summary
  console.log('Condition     Pass@1 (avg)    Best    Avg tokens   Avg time   Total tests passed');
  console.log('─'.repeat(85));
  for (const condition of CONDITIONS) {
    const condResults = allResults.filter(r => r.condition === condition);
    const testPassRates = condResults.map(r => r.total > 0 ? r.pass / r.total : 0);
    const avgRate = (testPassRates.reduce((s, v) => s + v, 0) / testPassRates.length * 100).toFixed(1);
    const bestRate = (Math.max(...testPassRates) * 100).toFixed(0);
    const avgTokens = Math.round(condResults.reduce((s, r) => s + r.tokens_in + r.tokens_out, 0) / condResults.length);
    const avgTime = (condResults.reduce((s, r) => s + r.duration_ms, 0) / condResults.length / 1000).toFixed(1);
    const totalPassed = condResults.reduce((s, r) => s + r.pass, 0);
    const totalTests = condResults.reduce((s, r) => s + r.total, 0);
    console.log(`${condition.padEnd(13)} ${avgRate.padStart(8)}%     ${bestRate.padStart(4)}%    ${avgTokens.toString().padStart(10)}    ${avgTime.padStart(6)}s    ${totalPassed}/${totalTests}`);
  }

  // Per-task breakdown
  console.log('\nPer-task results (avg Pass@1 %):');
  console.log('Task                       Type         ' + CONDITIONS.map(c => c.padEnd(10)).join(''));
  console.log('─'.repeat(85));
  for (const task of TASKS) {
    const row = [task.id.padEnd(26), task.type.padEnd(12)];
    for (const condition of CONDITIONS) {
      const condResults = allResults.filter(r => r.task_id === task.id && r.condition === condition);
      const rates = condResults.map(r => r.total > 0 ? r.pass / r.total : 0);
      const avg = rates.length > 0 ? (rates.reduce((s, v) => s + v, 0) / rates.length * 100).toFixed(0) : '-';
      row.push((avg + '%').padEnd(10));
    }
    console.log(row.join(''));
  }

  // Per-task × per-run detail (for variance analysis)
  console.log('\nVariance detail (pass/total per run):');
  console.log('Task                       ' + CONDITIONS.map(c => c.padEnd(12)).join(''));
  console.log('─'.repeat(85));
  for (const task of TASKS) {
    for (let runIdx = 0; runIdx < RUNS; runIdx++) {
      const row = [`${task.id.padEnd(26)}#${runIdx + 1}`.padEnd(27)];
      for (const condition of CONDITIONS) {
        const r = allResults.find(r => r.task_id === task.id && r.condition === condition && r.run === runIdx);
        if (r) {
          row.push(`${r.pass}/${r.total}`.padEnd(12));
        } else {
          row.push('-'.padEnd(12));
        }
      }
      console.log(row.join(''));
    }
  }

  console.log(`\nElapsed: ${elapsed}s`);
  console.log(`Results: ${resultsPath}`);
}

main().catch(err => { console.error('FATAL:', err); process.exit(1); });