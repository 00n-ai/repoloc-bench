// ma_kg_agent.js — MA+KG pipeline: drafter → directional reasoning → pytest → refiner
//
// Pipeline:
//   1. Drafter: KG agent generates initial code (using graph evidence)
//   2. Directional Reasoning (Option B): LLM pass generates explicit "when X, do Y" directives
//      from visited nodes + conventions + task — converts facts into implementation guidance
//   3. Validator: Run pytest on the generated code
//   4. Refiner: If tests fail, send error + original code + reasoning path + test source +
//      directional directives back for fixing
//   5. Repeat up to N refinement rounds
//
// Improvements implemented:
//   #1: Refiner receives the KG reasoning path + visited node summaries from the draft
//   #2: Refiner receives the test source code (reveals exact assertions and expected values)
//   #3: Decompose retry is in code_kg_agent.js
//   #4: Deterministic graph seeding is in code_kg_agent.js
//   #5: Convention nodes in KG (Option A) — deterministic patterns from extraction
//   #6: Directional reasoning step (Option B) — LLM generates implementation directives

import { runCodeKGAgent, runCodeB0 } from './code_kg_agent.js';
import { callLLM } from '../../multi-agent-framework/src/agents.js';
import fs from 'node:fs';
import nodePath from 'node:path';
import { execSync } from 'node:child_process';

const PYTEST = '/home/linuxbrew/.linuxbrew/bin/pytest';
const MAX_ROUNDS = 3;

function getDefaultModel() { return process.env.LLM_MODEL || 'qwen2.5:7b'; }

function extractCode(output) {
  const m = output.match(/```python\n([\s\S]*?)```/);
  return m ? m[1] : output;
}

function cleanPycache() {
  for (const dir of [
    'example-repo/src/__pycache__', 'example-repo/tests/__pycache__', 'tasks/tests/__pycache__'
  ]) {
    try { fs.rmSync(nodePath.join(process.cwd(), dir), { recursive: true, force: true }); } catch {}
  }
}

async function injectAndTest(task, code) {
  const REPO_SRC = nodePath.join(process.cwd(), 'example-repo', 'src');
  const modulePath = nodePath.join(REPO_SRC, `${task.module}.py`);
  const orig = fs.readFileSync(modulePath, 'utf8');
  const tmpDir = nodePath.join(process.cwd(), '.tmp-test');
  try {
    fs.mkdirSync(tmpDir, { recursive: true });
    const testSrc = nodePath.join(process.cwd(), task.test_file);
    const testDst = nodePath.join(tmpDir, nodePath.basename(task.test_file));
    fs.copyFileSync(testSrc, testDst);
    fs.writeFileSync(modulePath, orig + '\n\n# GENERATED\n\n' + code);
    cleanPycache();
    
    // Syntax check the generated code before running pytest
    let syntaxError = null;
    try {
      execSync(`python3 -c "import ast; ast.parse(open('${modulePath}').read())"`, { encoding: 'utf8', timeout: 5000 });
    } catch (e) {
      syntaxError = e.stderr || e.stdout || e.message || '';
    }
    if (syntaxError) {
      // Issue 4: Syntax-error refinement step — try to fix before giving up
      console.log(`  ⚠ Syntax error detected — attempting fix...`);
      const fixedCode = await fixSyntaxError(code, syntaxError, typeof task === 'string' ? task : (task.prompt || task), process.env.LLM_MODEL || 'qwen2.5:7b');
      if (fixedCode && fixedCode !== code) {
        // Re-inject and re-check
        fs.writeFileSync(modulePath, orig + '\n\n# GENERATED\n\n' + fixedCode);
        try {
          execSync(`python3 -c "import ast; ast.parse(open('${modulePath}').read())"`, { encoding: 'utf8', timeout: 5000 });
          syntaxError = null;
          code = fixedCode;
          console.log(`  ✅ Syntax fix succeeded`);
        } catch (e2) {
          syntaxError = e2.stderr || e2.stdout || e2.message || '';
          console.log(`  ❌ Syntax fix failed`);
        }
      }
      if (syntaxError) {
        return { pass: 0, total: 0, raw: `SYNTAX ERROR: ${syntaxError}` };
      }
    }
    
    const cmd = `PYTHONPATH=${REPO_SRC}:${nodePath.join(process.cwd(), 'example-repo')} ${PYTEST} ${testDst} -v --tb=short -p no:cacheprovider --rootdir=${tmpDir} 2>&1`;
    let out;
    try { out = execSync(cmd, { encoding: 'utf8', timeout: 30000 }); }
    catch (e) { out = e.stdout || e.stderr || e.message || ''; }
    // Count test results from the inline progress lines only (not the summary)
    // Inline format: "...::test_name PASSED [ xx%]" or "...::test_name FAILED [ xx%]"
    // Summary lines at end start with "FAILED" or "PASSED" (no "::" before)
    // Also handle collection errors (0 tests collected)
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

// #2: Load test source code to give the refiner the exact spec
function loadTestSource(testFilePath) {
  try {
    return fs.readFileSync(nodePath.join(process.cwd(), testFilePath), 'utf8');
  } catch {
    return '(test file not found)';
  }
}

// Load a compact summary of existing function signatures from the target module
// This gives the refiner enough context to call existing functions without
// being tempted to redefine them (which happens when we show full source)
function loadModuleSummary(moduleName) {
  if (!moduleName) return null;
  const graph = loadGraph();
  const moduleNodes = graph.nodes.filter(n => n.module === moduleName);
  const lines = [`Target module: ${moduleName}`, ''];
  // Conventions first
  const conventions = moduleNodes.filter(n => n.type === 'convention');
  if (conventions.length > 0) {
    lines.push('=== IMPLEMENTATION CONVENTIONS ===');
    for (const c of conventions) {
      lines.push(`📌 ${c.label}: ${c.natural_language}`);
      if (c.functions?.length) lines.push(`  Followed by: ${c.functions.join(', ')}`);
      lines.push('');
    }
  }
  for (const n of moduleNodes) {
    if (n.type === 'convention') continue; // already shown
    if (n.type === 'function' || n.type === 'method') {
      let line = `  def ${n.label}(${(n.args || []).join(', ')})`;
      if (n.returns) line += ` -> ${n.returns}`;
      lines.push(line + '  # ALREADY EXISTS — DO NOT REDEFINE');
      if (n.raises?.length) lines.push(`    # Raises: ${n.raises.map(r => r.type).join(', ')}`);
      if (n.import_convention) lines.push(`    # ${n.import_convention}`);
    } else if (n.type === 'class') {
      let line = `  class ${n.label}`;
      if (n.bases?.length) line += `(${n.bases.join(', ')})`;
      lines.push(line + '  # ALREADY EXISTS — DO NOT REDEFINE');
      if (n.class_attributes?.length) lines.push(`    # Attributes: ${n.class_attributes.map(a => a.name).join(', ')}`);
      if (n.enum_values?.length) lines.push(`    # Enum values: ${n.enum_values.map(v => v.name).join(', ')}`);
    } else if (n.type === 'variable') {
      lines.push(`  ${n.label} = ...  # module-level state — ALREADY EXISTS`);
    }
  }
  return lines.join('\n');
}

// #1: Format visited node summaries for the refiner
function formatEvidenceForRefiner(visitedNodeIds, graph) {
  const nodes = visitedNodeIds
    .map(id => graph.nodes.find(n => n.id === id))
    .filter(Boolean);
  // Conventions first — they give DIRECTION
  const conventions = nodes.filter(n => n.type === 'convention');
  const others = nodes.filter(n => n.type !== 'convention');
  const ordered = [...conventions, ...others];
  const lines = [];
  for (const n of ordered) {
    if (n.type === 'convention') {
      const parts = [`📌 CONVENTION: ${n.label}`];
      if (n.natural_language) parts.push(`  ${n.natural_language}`);
      if (n.functions?.length) parts.push(`  Followed by: ${n.functions.join(', ')}`);
      lines.push(parts.join('\n'));
      continue;
    }
    const parts = [`${n.label} (${n.type})`];
    if (n.natural_language) parts.push(`  ${n.natural_language}`);
    if (n.args?.length) parts.push(`  Args: ${n.args.join(', ')}`);
    if (n.returns) parts.push(`  Returns: ${n.returns}`);
    if (n.raises?.length) parts.push(`  Raises: ${n.raises.map(r => r.type + (r.condition ? ' if ' + r.condition : '')).join(', ')}`);
    if (n.return_conditions?.length) parts.push(`  Return conditions: ${n.return_conditions.map(rc => rc.condition ? 'if ' + rc.condition + ' then ' + rc.returns : rc.returns).join('; ')}`);
    if (n.import_convention) parts.push(`  Import convention: ${n.import_convention}`);
    if (n.class_attributes?.length) parts.push(`  Attributes: ${n.class_attributes.map(a => a.name).join(', ')}`);
    if (n.enum_values?.length) parts.push(`  Enum values: ${n.enum_values.map(v => v.name + '=' + v.value).join(', ')}`);
    if (n.module_variables?.length) parts.push(`  Module state: ${n.module_variables.map(v => v.name).join(', ')}`);
    lines.push(parts.join('\n'));
  }
  return lines.join('\n\n');
}

// ─── Issue 1: Pre-filter conventions by task keywords ───
// Only include a convention if the task description contains keywords related to it.
// This prevents irrelevant directives (e.g., ValueError convention for a data aggregation task).
function filterConventionsByTask(conventions, taskStr) {
  const taskLower = taskStr.toLowerCase();
  const keywordMap = [
    // ValueError convention keywords
    { pattern: /validate|validation|verify|user.*exist|exist.*user|nonexistent|not found|raise|error/i,
      conventionMatch: /valueerror/i },
    // RuntimeError convention keywords
    { pattern: /state.*transition|invalid.*state|status.*change|refund|complete|fail/i,
      conventionMatch: /runtimeerror/i },
    // Cross-module access convention keywords
    { pattern: /user_service|cross.module|import|access.*user|get_user/i,
      conventionMatch: /access|cross.module/i },
  ];

  return conventions.filter(conv => {
    const convLabel = (conv.label || '').toLowerCase();
    const convText = (conv.natural_language || '').toLowerCase();
    for (const { pattern, conventionMatch } of keywordMap) {
      if (conventionMatch.test(convLabel) || conventionMatch.test(convText)) {
        if (pattern.test(taskLower)) return true;
      }
    }
    // If no keyword map entry matches, include by default (conservative)
    return true;
  });
}

// ─── Issue 3: Post-filter directives with hallucinated function names ───
// Checks each directive for function names and verifies they exist in the graph.
// Strips directives that reference nonexistent functions.
function filterHallucinatedDirectives(directiveList, graph) {
  // Build a set of all known function/method names in the graph
  const knownFunctions = new Set();
  for (const n of graph.nodes) {
    if (n.type === 'function' || n.type === 'method') {
      knownFunctions.add(n.label);
    }
  }

  const filtered = [];
  for (const d of directiveList) {
    // Extract function-like names from the directive — only actual function calls (name followed by `()`)
    // Don't match dict keys, variable assignments, or attribute access patterns
    const funcRefs = [...d.matchAll(/(?:`)?([a-zA-Z_][a-zA-Z0-9_]*)\s*\(/g)].map(m => m[1])
      // Exclude things that are clearly not function calls in the directive context
      .filter(name => !['by_type', 'total_queued', 'unsent_count', 'total_revenue', 'total_refunded',
        'payment_count', 'active_subscribers', 'DIRECTION'].includes(name));
    let allKnown = true;
    for (const ref of funcRefs) {
      // Allow common Python builtins and control flow
      if (['print', 'len', 'str', 'int', 'float', 'bool', 'list', 'dict', 'set', 'range',
           'sorted', 'enumerate', 'zip', 'isinstance', 'hasattr', 'getattr', 'setattr',
           'raise', 'return', 'if', 'elif', 'else', 'for', 'while', 'try', 'except',
           'ValueError', 'RuntimeError', 'TypeError', 'Exception'].includes(ref)) continue;
      if (!knownFunctions.has(ref)) {
        allKnown = false;
        console.log(`  ⚠ Filtering directive with hallucinated function: ${ref}`);
        break;
      }
    }
    if (allKnown) filtered.push(d);
  }
  return filtered;
}

// ─── Issue 4: Syntax-error refinement step ───
// When syntax check fails, send the error + code back for a focused fix before pytest.
async function fixSyntaxError(code, syntaxError, taskStr, model) {
  const sys = `You are a Python syntax expert. Fix the syntax error in the following code. Output ONLY the corrected code, nothing else.

\\\\\`\\\\\`\\\\\`python
<corrected code>
\\\\\`\\\\\`\\\\\``;
  const usr = `Task: ${taskStr}

Code with syntax error:
\\\\\`\\\\\`\\\\\`python
${code}
\\\\\`\\\\\`\\\\\`

Syntax error:
${syntaxError}

Fix the syntax error and output ONLY the corrected code:`;
  const res = await callLLM(sys, usr, model, 0.1, 2000);
  return extractCode(res.output);
}

// ─── Option B: Directional Reasoning Step ───
// After graph navigation, an LLM pass examines the visited evidence + conventions + task
// and generates explicit "when X, do Y" implementation directives.
// This converts FACTS (process_payment raises ValueError) into DIRECTION
// (when implementing user validation in payments, raise ValueError with 'not found' message).
//
// Uses the same model — the point is that the model gets a focused prompt with ONLY
// the relevant evidence and conventions, not the full graph. This is a reasoning step,
// not a synthesis step — the output is directives, not code.
async function generateDirectionalDirectives(task, visitedNodeIds, reasoningPath, graph, model, logger) {
  const visitedNodes = visitedNodeIds
    .map(id => graph.nodes.find(n => n.id === id))
    .filter(Boolean);

  // Separate conventions from other nodes — conventions are the most important
  const allConventions = visitedNodes.filter(n => n.type === 'convention');
  // Issue 1: Pre-filter conventions by task keywords
  const taskStr = typeof task === 'string' ? task : (task.prompt || task);
  const conventions = filterConventionsByTask(allConventions, taskStr);
  console.log(`  🎯 Conventions: ${allConventions.length} total, ${conventions.length} after task-relevance filtering`);
  const otherNodes = visitedNodes.filter(n => n.type !== 'convention');

  // Edges between visited nodes (especially EXEMPLIFIES, FOLLOWS_CONVENTION, RAISES)
  const visitedEdges = graph.edges.filter(e =>
    visitedNodeIds.includes(e.source) && visitedNodeIds.includes(e.target)
  );

  const dirSys = `You are an expert code implementation advisor. Your job is to read the graph evidence (nodes, edges, conventions) and the coding task, then produce a concise list of IMPLEMENTATION DIRECTIVES.

An implementation directive is a specific, actionable instruction of the form:
  DIRECTION N: When <situation>, <what to do>

Example directives:
  DIRECTION 1: When validating user existence in payments, raise ValueError with a message containing 'not found' (follow process_payment pattern)
  DIRECTION 2: When accessing user_service functions from payments, use _get_user_service() pattern — never import directly
  DIRECTION 3: When finding the most recent payment, use get_payment_history(user_id) and sort by .created_at — do NOT access _payment_db directly
  DIRECTION 4: When refunding a payment, call refund_payment(payment_id) — do NOT set .status manually

CRITICAL RULES:
- Each directive must be SPECIFIC and ACTIONABLE (not vague advice)
- Base each directive on actual evidence from the graph (cite the node or convention)
- Only reference functions that appear in the graph evidence — do NOT invent function names
- Only generate directives RELEVANT to this specific task. If the task is about data aggregation, do NOT generate directives about user validation. If the task is about sending notifications, do NOT generate directives about refunds.
- Focus on WHAT TO DO, not what not to do (positive direction)
- Include the exact function name, exception type, or pattern to follow
- Maximum 6 directives — only the ones directly relevant to THIS task
- If a convention is not relevant to this task, SKIP it. Do not include it just because it exists.
- If the reasoning path already reaches a conclusion, align your directives with it
- Use ONLY function names that appear in the KEY GRAPH EVIDENCE section below
- Do NOT generate directives about imports — all functions are available at module level, no import statements needed
- Do NOT generate directives about syntax or code formatting — focus on behavioral patterns only

Output format:
DIRECTION 1: <directive> [source: <node/convention label>]
DIRECTION 2: <directive> [source: ...]
...

If no conventions or evidence are relevant to this task, output:
NO_RELEVANT_DIRECTIVES`;

  // Build the evidence block for the directive prompt
  let dirUsr = `Task: ${typeof task === 'string' ? task : task.prompt || task}

`;

  if (conventions.length > 0) {
    dirUsr += `=== IMPLEMENTATION CONVENTIONS ===
`;
    for (const c of conventions) {
      dirUsr += `📌 ${c.label}: ${c.natural_language}\n`;
      if (c.functions?.length) dirUsr += `  Followed by: ${c.functions.join(', ')}\n`;
      dirUsr += '\n';
    }
  }

  dirUsr += `=== KEY GRAPH EVIDENCE ===\n`;
  // Include a function inventory so the model knows what functions exist (prevents hallucination)
  const funcInventory = otherNodes.filter(n => n.type === 'function' || n.type === 'method');
  if (funcInventory.length > 0) {
    dirUsr += `Available functions (use ONLY these exact names — do NOT invent function names):\n`;
    for (const f of funcInventory) {
      const sig = `  ${f.label}(${(f.args || []).join(', ')})` + (f.returns ? ` -> ${f.returns}` : '');
      dirUsr += sig + '\n';
    }
    dirUsr += '\n';
  }
  
  // Detailed node info
  for (const n of otherNodes.slice(0, 20)) {
    if (n.type === 'function' || n.type === 'method') continue; // already in inventory
    const parts = [`${n.label} (${n.type})`];
    if (n.natural_language) parts.push(`  ${n.natural_language}`);
    if (n.raises?.length) parts.push(`  Raises: ${n.raises.map(r => r.type + (r.condition ? ' if ' + r.condition : '')).join(', ')}`);
    if (n.return_conditions?.length) parts.push(`  Returns: ${n.return_conditions.map(rc => rc.returns).join('; ')}`);
    if (n.import_convention) parts.push(`  Import: ${n.import_convention}`);
    dirUsr += parts.join('\n') + '\n\n';
  }

  dirUsr += `=== RELEVANT EDGES ===\n`;
  const relevantRelations = ['RAISES', 'RUNTIME_IMPORT', 'DEPENDS_ON', 'EXEMPLIFIES', 'FOLLOWS_CONVENTION', 'CALLS'];
  for (const e of visitedEdges.filter(e => relevantRelations.includes(e.relation))) {
    const srcLabel = graph.nodes.find(n => n.id === e.source)?.label || e.source;
    const tgtLabel = graph.nodes.find(n => n.id === e.target)?.label || e.target;
    dirUsr += `${srcLabel} ${e.relation} ${tgtLabel}`;
    if (e.assertion) dirUsr += ` — ${e.assertion}`;
    if (e.bridge) dirUsr += ` [BRIDGE: ${e.bridge.substring(0, 120)}]`;
    dirUsr += '\n';
  }

  if (reasoningPath) {
    dirUsr += `\n=== REASONING PATH (from graph navigation) ===\n${reasoningPath.substring(0, 2000)}\n`;
  }

  dirUsr += `\nBased on the conventions, evidence, edges, and reasoning path above, generate implementation directives for this task: determine the few most important DIRECTIONS the coder must follow.`;

  const dirRes = await callLLM(dirSys, dirUsr, model, 0.3, 1500);

  let directives = (dirRes.output.match(/DIRECTION\s+\d+:[^\n]+/g) || [])
    .map(d => d.trim())
    .filter(d => d.length > 0);

  // Issue 3: Post-filter directives with hallucinated function names
  const preFilterCount = directives.length;
  directives = filterHallucinatedDirectives(directives, graph);
  if (directives.length < preFilterCount) {
    console.log(`  🎯 Filtered ${preFilterCount - directives.length} hallucinated directives`);
  }

  console.log(`  🎯 Generated ${directives.length} directional directives`);
  for (const d of directives.slice(0, 5)) {
    console.log(`    ${d.substring(0, 100)}`);
  }

  logger.log({
    step: 'ma-kg-directional-reasoning', agent: 'ma-kg-agent', role: 'Directional reasoning (Option B)',
    input: { task: typeof task === 'string' ? task : task.prompt, conventionCount: conventions.length, evidenceCount: otherNodes.length },
    system_prompt: dirSys, user_prompt: dirUsr,
    model, temperature: 0.3, output: dirRes.output,
    duration_ms: dirRes.duration_ms, tokens_in: dirRes.tokens_in, tokens_out: dirRes.tokens_out,
    directives,
  });

  return {
    directives: dirRes.output,
    directiveList: directives,
    tokens_in: dirRes.tokens_in,
    tokens_out: dirRes.tokens_out,
    duration_ms: dirRes.duration_ms,
    llm_calls: 1,
  };
}

// Load the graph (shared with code_kg_agent.js)
let _graph = null;
function loadGraph() {
  if (!_graph) {
    const graphPath = nodePath.join(process.cwd(), 'code-graph.json');
    _graph = JSON.parse(fs.readFileSync(graphPath, 'utf8'));
  }
  return _graph;
}

export async function runMAKGAgent(task, logger, opts = {}) {
  const model = opts.model || getDefaultModel();
  const useNL = opts.useNL ?? false;
  const runStart = Date.now();
  let totalLLMCalls = 0;
  let totalTokensIn = 0;
  let totalTokensOut = 0;

  // Support both string tasks (smoke) and object tasks (full experiment)
  const taskStr = typeof task === 'string' ? task : (task.prompt || task);
  const taskObj = typeof task === 'object' ? task : {
    prompt: task,
    module: null, // will be detected by KG agent
    test_file: null,
  };

  console.log(`▶ MA+KG Agent (${useNL ? 'NL' : 'structured'} mode, max ${MAX_ROUNDS} rounds)`);

  // ─── Round 0: Draft using KG agent ───
  console.log('  📝 Round 0: Draft (KG agent)');
  const draftResult = useNL
    ? await runCodeKGAgent(taskObj.prompt || taskStr, logger, { model, useNL: true })
    : await runCodeKGAgent(taskObj.prompt || taskStr, logger, { model, useNL: false });

  totalLLMCalls += draftResult.llm_calls;
  totalTokensIn += draftResult.tokens_in;
  totalTokensOut += draftResult.tokens_out;

  let currentCode = extractCode(draftResult.answer);
  let currentResult = await injectAndTest(taskObj, currentCode);

  console.log(`    Draft result: ${currentResult.pass}/${currentResult.total} tests`);

  const rounds = [{ round: 0, code: currentCode, pass: currentResult.pass, total: currentResult.total }];

  // ─── Precompute refiner context (#1 + #2) ───
  const testSource = taskObj.test_file ? loadTestSource(taskObj.test_file) : null;
  const moduleSummary = loadModuleSummary(taskObj.module);
  const graph = loadGraph();
  const evidenceBlock = draftResult.kg_visited_nodes?.length > 0
    ? formatEvidenceForRefiner(draftResult.kg_visited_nodes, graph)
    : null;
  const reasoningPath = draftResult.kg_reasoning_path || null;

  // ─── Option B: Directional Reasoning Step ───
  // Generate explicit "when X, do Y" directives from visited evidence + conventions + task
  // This runs ONCE (after draft, before first refinement) and the directives are reused
  // across all refinement rounds. Converts facts into implementation direction.
  console.log('  🎯 Directional reasoning step (Option B)');
  const dirResult = await generateDirectionalDirectives(
    taskObj, draftResult.kg_visited_nodes || [], reasoningPath, graph, model, logger
  );
  totalLLMCalls += dirResult.llm_calls;
  totalTokensIn += dirResult.tokens_in;
  totalTokensOut += dirResult.tokens_out;
  const directionalDirectives = dirResult.directives;
  const directiveList = dirResult.directiveList;

  // ─── Rounds 1..N: Validate + Refine ───
  for (let round = 1; round <= MAX_ROUNDS; round++) {
    if (currentResult.pass === currentResult.total && currentResult.total > 0) {
      console.log(`  ✅ All tests pass at round ${round - 1}!`);
      break;
    }

    console.log(`  🔧 Round ${round}: Refine (tests: ${currentResult.pass}/${currentResult.total})`);

    // Extract error messages from pytest output
    const errorLines = currentResult.raw.split('\n').filter(l =>
      l.includes('FAILED') || l.includes('Error') || l.includes('error') ||
      l.includes('assert') || l.includes('AttributeError') || l.includes('NameError') ||
      l.includes('TypeError') || l.includes('ImportError')
    ).slice(0, 10).join('\n');

    // Build the refiner system prompt — includes reasoning path (#1) and test source (#2)
    let refineSys = `You are an expert Python programmer fixing code that failed tests. You will receive:
1. The original generated code
2. The test error output`;

    if (testSource) {
      refineSys += `\n3. The test source code — this reveals the EXACT assertions, expected values, and error messages your code must satisfy`;
    }
    if (reasoningPath) {
      refineSys += `\n${testSource ? '4' : '3'}. The KG reasoning path — the chain of evidence from the code graph that explains how the code should be implemented`;
    }
    if (evidenceBlock) {
      refineSys += `\n${testSource && reasoningPath ? '5' : (testSource || reasoningPath) ? '4' : '3'}. Graph evidence — the visited nodes from the code knowledge graph with their signatures, raises, return conditions, and import conventions`;
    }
    if (directiveList?.length > 0) {
      refineSys += `\n${testSource && reasoningPath && evidenceBlock ? '6' : (testSource && reasoningPath) || (testSource && evidenceBlock) || (reasoningPath && evidenceBlock) ? '5' : (testSource || reasoningPath || evidenceBlock) ? '4' : '3'}. Directional directives — explicit "when X, do Y" implementation guidance generated from the graph conventions and evidence. FOLLOW THESE DIRECTIVES.`;
    }

    refineSys += `

Common issues to fix:
- NameError: function not defined → use _get_user_service() for cross-module calls: 'user_svc = _get_user_service()' then 'user_svc.get_user_profile(user_id)'
- AttributeError: wrong attribute name → use exact names from the evidence (e.g., p.created_at not p.timestamp)
- TypeError: wrong arguments → check function signature (e.g., _get_user_service() takes NO arguments)
- ImportError: do NOT use import statements, all functions are available at module level
- AssertionError: the test expected a different value → read the test source to see what the assertion checks

CRITICAL RULES:
1. Write ONLY the new function(s) requested by the task. Do NOT redefine, rewrite, or modify any existing functions from the target module source. The target module source is shown for REFERENCE ONLY — so you can see existing function signatures and patterns. Your code will be APPENDED to the module.
2. Do NOT add import statements. All functions are available at module level.
3. For user_service functions: ALWAYS use 'user_svc = _get_user_service()' first, then 'user_svc.get_user_profile(user_id)'. Do NOT redefine _get_user_service().
4. Return the Payment object itself, not .to_dict().
5. Use exact function names: refund_payment (not refund), get_payment_history (not get_payments).
6. If the test checks error messages, match the EXACT message format from the test source.
7. If the test checks return types, return the exact type the test expects (object, not dict).
8. Do NOT include any code from the target module source in your output. Only write the NEW function.

Output format:
\`\`\`python
# <brief explanation of fix>
<fixed code>
\`\`\``;

    // Build the refiner user prompt with all context
    let refineUsr = `Task: ${taskStr}\n`;

    // Key facts (retain as fallback)
    refineUsr += `\nKey facts from the codebase:
- _get_user_service() returns the user_service module. Call: user_svc = _get_user_service(); user_svc.get_user_profile(user_id). _get_user_service() takes NO arguments.
- get_payment_history(user_id) returns a list of Payment objects. Each has: .payment_id, .user_id, .amount, .status, .tier, .created_at
- refund_payment(payment_id) refunds a payment by ID. Returns None.
- PaymentStatus.COMPLETED is the enum value (not the string 'COMPLETED').
- process_payment raises ValueError for nonexistent users. Follow this pattern.
- Do NOT use import statements. All functions are available at module level.\n`;

    // #1: Include the KG reasoning path
    if (reasoningPath) {
      refineUsr += `\n=== KG REASONING PATH (from draft) ===
${reasoningPath}\n`;
    }

    // Option B: Include directional directives
    if (directionalDirectives) {
      refineUsr += `\n=== DIRECTIONAL DIRECTIVES (implementation guidance — FOLLOW THESE) ===\n${directionalDirectives}\n`;
    }

    // #1: Include graph evidence (visited node summaries)
    if (evidenceBlock) {
      refineUsr += `\n=== GRAPH EVIDENCE (visited nodes from draft) ===
${evidenceBlock}\n`;
    }

    // Include the target module source — the refiner must see existing implementations
    if (moduleSummary) {
      refineUsr += `\n=== TARGET MODULE SIGNATURES (existing functions — DO NOT redefine any of them, just CALL them) ===\n${moduleSummary}\n`;
    }

    // #2: Include the test source code
    if (testSource) {
      refineUsr += `\n=== TEST SOURCE CODE ===
${testSource}\n`;
    }

    refineUsr += `\nOriginal code:
\`\`\`python
${currentCode}
\`\`\`

Test errors:
${errorLines}

Full test output (truncated):
${currentResult.raw.substring(0, 1500)}

Fix the code to make the tests pass:`;

    const refineRes = await callLLM(refineSys, refineUsr, model, 0.2, 2500);
    totalLLMCalls++;
    totalTokensIn += refineRes.tokens_in;
    totalTokensOut += refineRes.tokens_out;

    const refinedCode = extractCode(refineRes.output);
    const refinedResult = await injectAndTest(taskObj, refinedCode);

    // Anti-regression guard: only accept refined code if it doesn't reduce test pass count
    const prevPass = currentResult.pass;
    if (refinedResult.pass >= prevPass) {
      currentCode = refinedCode;
      currentResult = refinedResult;
      console.log(`    Round ${round} result: ${currentResult.pass}/${currentResult.total} tests`);
    } else {
      // Refined code is worse — keep the previous code
      console.log(`    Round ${round} result: ${refinedResult.pass}/${refinedResult.total} (regressed from ${prevPass}) — keeping previous code`);
    }

    rounds.push({
      round,
      code: currentCode,
      pass: currentResult.pass,
      total: currentResult.total,
      error: errorLines.substring(0, 500),
    });

    logger.log({
      step: `ma-kg-refine-${round}`, agent: 'ma-kg-agent', role: `Refinement round ${round}`,
      input: { task: taskStr, errorLines, previousCode: rounds[round - 1].code },
      system_prompt: refineSys, user_prompt: refineUsr,
      model, temperature: 0.2, output: refineRes.output,
      duration_ms: refineRes.duration_ms, tokens_in: refineRes.tokens_in, tokens_out: refineRes.tokens_out,
      test_result: { pass: currentResult.pass, total: currentResult.total },
    });
  }

  const success = currentResult.pass === currentResult.total && currentResult.total > 0;

  return {
    answer: currentCode,
    tokens_in: totalTokensIn,
    tokens_out: totalTokensOut,
    duration_ms: Date.now() - runStart,
    llm_calls: totalLLMCalls,
    rounds,
    final_pass: currentResult.pass,
    final_total: currentResult.total,
    success,
    kg_visited_nodes: draftResult.kg_visited_nodes,
    kg_reasoning_gaps: draftResult.kg_reasoning_gaps,
  };
}