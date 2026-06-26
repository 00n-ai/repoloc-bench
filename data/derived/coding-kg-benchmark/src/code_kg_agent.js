// code_kg_agent.js — Graph-navigation agent for code knowledge graphs
//
// Pipeline:
//   1. Decompose: Break the coding task into knowledge needs
//   2. Navigate: Query the code KG → read nodes → follow edges → build context
//   3. Reason: Trace a reasoning path through the graph connecting code elements
//   4. Synthesize: Generate code using the reasoning path + accumulated evidence
//
// Usage:
//   import { runCodeKGAgent } from './code_kg_agent.js';
//   const result = await runCodeKGAgent(task, logger);

import { callLLM } from '../../multi-agent-framework/src/agents.js';

function getDefaultModel() { return process.env.LLM_MODEL || 'qwen2.5:7b'; }

const MAX_NAVIGATION_STEPS = 8;
const MAX_NODES_PER_STEP = 10;

// Convention nodes are always surfaced first — they give DIRECTION not just facts
function getConventionNodes(moduleName, graph) {
  return graph.nodes.filter(n => 
    n.type === 'convention' && 
    (n.module === moduleName || n.label.includes(moduleName))
  );
}

import fs from 'node:fs';
import nodePath from 'node:path';

let _graph = null;
function loadGraph() {
  if (!_graph) {
    const graphPath = nodePath.join(process.cwd(), 'code-graph.json');
    _graph = JSON.parse(fs.readFileSync(graphPath, 'utf8'));
  }
  return _graph;
}

// Keyword-based graph query
function queryGraph(query, maxNodes = MAX_NODES_PER_STEP) {
  const graph = loadGraph();
  const keywords = query.toLowerCase()
    .split(/\s+/)
    .filter(k => k.length > 2)
    .filter(k => !STOPWORDS.has(k));

  const scored = graph.nodes.map(node => {
    const text = [
      node.id, node.label, node.natural_language || '',
      node.docstring || '', (node.args || []).join(' '),
      node.returns || '', node.type, node.domain || ''
    ].join(' ').toLowerCase();
    let score = 0;
    for (const kw of keywords) {
      if (text.includes(kw)) score += 1;
      if (node.id.toLowerCase().includes(kw)) score += 2;
      if (node.label.toLowerCase().equals && node.label.toLowerCase() === kw) score += 3;
    }
    return { node, score };
  });

  const matched = scored.filter(s => s.score > 0)
    .sort((a, b) => b.score - a.score)
    .slice(0, maxNodes);
  return matched.map(s => s.node);
}

const STOPWORDS = new Set([
  'the', 'how', 'what', 'does', 'why', 'can', 'you', 'tell', 'about',
  'find', 'show', 'get', 'all', 'list', 'from', 'that', 'this', 'with',
  'for', 'and', 'not', 'but', 'are', 'was', 'has', 'have', 'been',
  'its', 'use', 'using', 'used', 'into', 'our', 'their', 'your',
  'which', 'where', 'when', 'who', 'will', 'would', 'could', 'should',
]);

function getNodeWithEdges(nodeId) {
  const graph = loadGraph();
  const node = graph.nodes.find(n => n.id === nodeId);
  if (!node) return null;
  const edges = graph.edges.filter(e => e.source === nodeId || e.target === nodeId);
  return { node, edges };
}

function formatNodeStructured(n) {
  if (n.type === 'convention') {
    const parts = [`📌 CONVENTION: ${n.label}`];
    if (n.natural_language) parts.push(`  ${n.natural_language}`);
    if (n.functions?.length) parts.push(`  Followed by: ${n.functions.join(', ')}`);
    return parts.join('\n');
  }
  const parts = [`${n.label} (${n.type})`];
  if (n.natural_language) parts.push(`  Description: ${n.natural_language}`);
  if (n.docstring) parts.push(`  Docstring: ${n.docstring}`);
  if (n.args?.length) parts.push(`  Args: ${n.args.join(', ')}`);
  if (n.arg_types && Object.keys(n.arg_types).length) parts.push(`  Arg types: ${Object.entries(n.arg_types).map(([k,v]) => `${k}: ${v}`).join(', ')}`);
  if (n.returns) parts.push(`  Returns: ${n.returns}`);
  if (n.bases?.length) parts.push(`  Inherits: ${n.bases.join(', ')}`);
  if (n.methods?.length) parts.push(`  Methods: ${n.methods.join(', ')}`);
  if (n.class_attributes?.length) parts.push(`  Attributes: ${n.class_attributes.map(a => a.name).join(', ')}`);
  if (n.enum_values?.length) parts.push(`  Enum values: ${n.enum_values.map(v => v.name+'='+v.value).join(', ')}`);
  if (n.raises?.length) parts.push(`  Raises: ${n.raises.map(r => r.type + (r.condition ? ' if '+r.condition : '')).join(', ')}`);
  if (n.return_conditions?.length) parts.push(`  Return conditions: ${n.return_conditions.map(rc => rc.condition ? 'if '+rc.condition+' then '+rc.returns : rc.returns).join('; ')}`);
  if (n.import_convention) parts.push(`  Import convention: ${n.import_convention}`);
  if (n.module_variables?.length) parts.push(`  Module state: ${n.module_variables.map(v => v.name).join(', ')}`);
  if (n.type_hint) parts.push(`  Type: ${n.type_hint}`);
  if (n.value) parts.push(`  Value: ${n.value}`);
  return parts.join('\n');
}

function formatNodeNL(n) {
  if (n.type === 'convention') {
    const parts = [`📌 CONVENTION: ${n.label}`];
    if (n.natural_language) parts.push(n.natural_language);
    if (n.functions?.length) parts.push(`Followed by: ${n.functions.join(', ')}`);
    return parts.join('\n');
  }
  const parts = [`${n.label} (${n.type})`];
  if (n.natural_language) parts.push(n.natural_language);
  if (n.docstring) parts.push(`  Docstring: ${n.docstring}`);
  if (n.args?.length) parts.push(`  Parameters: ${n.args.join(', ')}`);
  if (n.arg_types && Object.keys(n.arg_types).length) parts.push(`  Arg types: ${Object.entries(n.arg_types).map(([k,v]) => `${k}: ${v}`).join(', ')}`);
  if (n.returns) parts.push(`  Returns: ${n.returns}`);
  if (n.bases?.length) parts.push(`  Inherits from: ${n.bases.join(', ')}`);
  if (n.methods?.length) parts.push(`  Methods: ${n.methods.join(', ')}`);
  if (n.class_attributes?.length) parts.push(`  Attributes: ${n.class_attributes.map(a => a.name).join(', ')}`);
  if (n.enum_values?.length) parts.push(`  Enum values: ${n.enum_values.map(v => v.name+'='+v.value).join(', ')}`);
  if (n.raises?.length) parts.push(`  Raises: ${n.raises.map(r => r.type + (r.condition ? ' if '+r.condition : '')).join(', ')}`);
  if (n.return_conditions?.length) parts.push(`  Return conditions: ${n.return_conditions.map(rc => rc.condition ? 'if '+rc.condition+' then '+rc.returns : rc.returns).join('; ')}`);
  if (n.import_convention) parts.push(`  Import convention: ${n.import_convention}`);
  if (n.module_variables?.length) parts.push(`  Module state: ${n.module_variables.map(v => v.name).join(', ')}`);
  if (n.type_hint) parts.push(`  Type: ${n.type_hint}`);
  if (n.value) parts.push(`  Value: ${n.value}`);
  return parts.join('\n');
}

function formatEdges(edges, graph) {
  return edges.map(e => {
    const srcLabel = graph.nodes.find(n => n.id === e.source)?.label || e.source;
    const tgtLabel = graph.nodes.find(n => n.id === e.target)?.label || e.target;
    let s = `${srcLabel} ${e.relation} ${tgtLabel}`;
    if (e.assertion) s += ` — ${e.assertion}`;
    if (e.bridge) s += ` [BRIDGE: ${e.bridge}]`;
    return s;
  }).join('\n');
}

function parseSubQuestions(output) {
  const matches = [...output.matchAll(/SQ\d+:\s*(.+)/gi)];
  return matches.map(m => m[1].trim()).filter(s => s.length > 0);
}

function serializeAllNodesStructured(nodes) {
  const byType = {};
  for (const n of nodes) {
    byType[n.type] = byType[n.type] || [];
    byType[n.type].push(n);
  }
  // Conventions FIRST — they give DIRECTION, not just facts
  const typeOrder = ['convention', 'module', 'variable', 'class', 'enum_value', 'function', 'method', 'exception', 'test_class', 'test_method', 'external_module', 'imported_name'];
  const lines = [];
  for (const type of typeOrder) {
    if (!byType[type]) continue;
    if (type === 'convention') lines.push('=== IMPLEMENTATION CONVENTIONS (DIRECTION — follow these patterns) ===');
    for (const n of byType[type]) {
      lines.push(formatNodeStructured(n));
      lines.push('');
    }
  }
  return lines.join('\n');
}

function serializeAllNodesNL(nodes) {
  // Conventions get their own foregrounded section
  const conventions = nodes.filter(n => n.type === 'convention');
  const otherNodes = nodes.filter(n => n.type !== 'convention');
  
  const byDomain = {};
  for (const n of otherNodes) {
    const d = n.domain || 'core';
    byDomain[d] = byDomain[d] || [];
    byDomain[d].push(n);
  }
  const lines = [];
  
  // Conventions first — DIRECTION the implementer must follow
  if (conventions.length > 0) {
    lines.push('## IMPLEMENTATION CONVENTIONS (DIRECTION — follow these patterns)\n');
    for (const c of conventions) {
      lines.push(formatNodeNL(c));
      lines.push('');
    }
  }
  
  for (const [domain, ns] of Object.entries(byDomain).sort()) {
    lines.push(`## ${domain.toUpperCase()}\n`);
    for (const n of ns) {
      lines.push(formatNodeNL(n));
      lines.push('');
    }
  }
  return lines.join('\n');
}

// ─── Main Code KG-agent runner ───

// ─── Helper: Detect target module from task prompt ───
function detectTargetModule(task) {
  const t = (typeof task === 'string' ? task : task.prompt || '').toLowerCase();
  if (t.includes('payments module') || t.includes('payment module')) return 'payments';
  if (t.includes('user_service module') || t.includes('user service module')) return 'user_service';
  if (t.includes('notifications module') || t.includes('notification module')) return 'notifications';
  // Fallback: keyword matching
  if (t.includes('payment') || t.includes('subscription') || t.includes('refund') || t.includes('revenue')) return 'payments';
  if (t.includes('user') || t.includes('password') || t.includes('admin')) return 'user_service';
  if (t.includes('notif') || t.includes('email') || t.includes('queue')) return 'notifications';
  return null;
}

// ─── Helper: Seed target module nodes deterministically ───
function seedTargetModuleNodes(moduleName, visitedNodes, accumulatedEvidence, graph) {
  if (!moduleName) return;
  const moduleId = `mod-${moduleName.replace('_', '-')}`;
  const moduleNode = graph.nodes.find(n => n.id === moduleId);
  if (!moduleNode) return;

  // Add the module node itself
  if (!visitedNodes.has(moduleId)) {
    visitedNodes.add(moduleId);
    accumulatedEvidence.push({ source: 'deterministic-seed', node: moduleNode });
  }

  // Add ALL nodes that belong to this module (functions, classes, variables, etc.)
  let seeded = 0;
  for (const n of graph.nodes) {
    if (n.module === moduleName && !visitedNodes.has(n.id)) {
      visitedNodes.add(n.id);
      accumulatedEvidence.push({ source: 'deterministic-seed', node: n });
      seeded++;
    }
  }

  // Add cross-module edges (RUNTIME_IMPORT, DEPENDS_ON) connected to this module's nodes
  for (const e of graph.edges) {
    if (e.relation === 'RUNTIME_IMPORT' || e.relation === 'DEPENDS_ON') {
      // If the source is in our module, add the target module node
      if (visitedNodes.has(e.source) && !visitedNodes.has(e.target)) {
        const targetNode = graph.nodes.find(n => n.id === e.target);
        if (targetNode) {
          visitedNodes.add(e.target);
          accumulatedEvidence.push({ source: 'deterministic-seed (cross-module edge)', node: targetNode });
          seeded++;
        }
      }
    }
  }

  // Also seed convention nodes for this module (Option A: deterministic conventions)
  const conventions = getConventionNodes(moduleName, graph);
  for (const conv of conventions) {
    if (!visitedNodes.has(conv.id)) {
      visitedNodes.add(conv.id);
      accumulatedEvidence.push({ source: 'deterministic-seed (convention)', node: conv });
      seeded++;
    }
  }

  console.log(`  🌱 Seeded ${seeded} nodes from target module "${moduleName}" (${conventions.length} conventions) (deterministic)`);
}

export async function runCodeKGAgent(task, logger, opts = {}) {
  const model = opts.model || getDefaultModel();
  const useNL = opts.useNL ?? false;
  const runStart = Date.now();
  let totalLLMCalls = 0;
  let totalTokensIn = 0;
  let totalTokensOut = 0;
  const visitedNodes = new Set();
  const accumulatedEvidence = [];

  // Extract task string and module info
  const taskStr = typeof task === 'string' ? task : (task.prompt || task);
  const taskModule = typeof task === 'object' ? task.module : detectTargetModule(taskStr);

  console.log(`▶ Code KG-Agent: Graph Navigation (${useNL ? 'NL' : 'structured'} mode)`);

  const graph = loadGraph();

  // ─── STEP 0: Deterministic graph seeding (#4) ───
  // Always seed visited nodes with ALL nodes from the target module.
  // This guarantees the drafter sees the target module's functions/classes/state
  // regardless of decompose quality.
  console.log('  🌱 Step 0: Deterministic graph seeding');
  seedTargetModuleNodes(taskModule || detectTargetModule(taskStr), visitedNodes, accumulatedEvidence, graph);

  // ─── STEP 1: Decompose task into knowledge needs ───
  console.log('  🧠 Step 1: Decompose task');
  const decompSys = `You are a code planning agent. Break down a coding task into 2-4 sub-questions representing the code knowledge you need to look up.

Frame each as a CONCEPT YOU WANT TO UNDERSTAND, not as a keyword search.

ALWAYS include a sub-question about user validation if the task involves user operations.
ALWAYS include a sub-question about cross-module dependencies if the task might involve functions from other modules.

For example, if the task is "Add a cancel_subscription function":
- "How does the payments module validate that a user exists before processing operations?"
- "How does the Payment class manage payment status transitions?"
- "What function retrieves a user's payment history?"
- "How does the payments module access user_service functions (import convention)?"

Output format:
SQ1: <sub-question>
SQ2: <sub-question>
...`;

  const decompUsr = `Task: ${taskStr}\n\nBreak this into 2-4 sub-questions representing the code knowledge you need:`;

  let decompRes = await callLLM(decompSys, decompUsr, model, 0.3);
  totalLLMCalls++;
  totalTokensIn += decompRes.tokens_in;
  totalTokensOut += decompRes.tokens_out;

  let subQuestions = parseSubQuestions(decompRes.output);
  console.log(`  ✓ ${subQuestions.length} sub-questions: ${subQuestions.map(sq => `"${sq}"`).join(', ')}`);

  // ─── #3: Decompose retry if 0 sub-questions ───
  if (subQuestions.length === 0) {
    console.log('  ⚠ Decompose returned 0 sub-questions — retrying with structured fallback');
    const retrySys = `You are a code planning agent. A previous attempt failed to produce sub-questions. You MUST produce exactly 3 sub-questions for this coding task.

The task targets the ${taskModule || detectTargetModule(taskStr)} module. Based on the task, generate 3 sub-questions:
- SQ1: About the main data structures or functions in the target module
- SQ2: About user validation or error handling patterns in this module
- SQ3: About cross-module dependencies or import conventions used by this module

You MUST use this exact format:
SQ1: <question>
SQ2: <question>
SQ3: <question>`;

    const retryUsr = `Task: ${taskStr}\n\nModule: ${taskModule || detectTargetModule(taskStr)}\n\nGenerate exactly 3 sub-questions:`;
    const retryRes = await callLLM(retrySys, retryUsr, model, 0.4);
    totalLLMCalls++;
    totalTokensIn += retryRes.tokens_in;
    totalTokensOut += retryRes.tokens_out;
    subQuestions = parseSubQuestions(retryRes.output);
    console.log(`  ✓ Retry: ${subQuestions.length} sub-questions: ${subQuestions.map(sq => `"${sq}"`).join(', ')}`);

    logger.log({
      step: 'code-kg-decompose-retry', agent: 'code-kg-agent', role: 'Task decomposition (retry)',
      input: { task: taskStr }, system_prompt: retrySys, user_prompt: retryUsr,
      model, temperature: 0.4, output: retryRes.output,
      duration_ms: retryRes.duration_ms, tokens_in: retryRes.tokens_in, tokens_out: retryRes.tokens_out,
    });
  }

  logger.log({
    step: 'code-kg-decompose', agent: 'code-kg-agent', role: 'Task decomposition',
    input: { task: taskStr }, system_prompt: decompSys, user_prompt: decompUsr,
    model, temperature: 0.3, output: decompRes.output,
    duration_ms: decompRes.duration_ms, tokens_in: decompRes.tokens_in, tokens_out: decompRes.tokens_out,
  });

  // ─── STEP 2: Navigate the graph for each sub-question ───
  console.log('  🧭 Step 2: Graph navigation');
  let stepsUsed = 0;

  for (let qi = 0; qi < subQuestions.length && stepsUsed < MAX_NAVIGATION_STEPS; qi++) {
    const sq = subQuestions[qi];
    console.log(`  🧭 Step 2.${qi+1}: Navigate for "${sq}" (${stepsUsed+1}/${MAX_NAVIGATION_STEPS} steps used)`);

    const initialNodes = queryGraph(sq);
    for (const n of initialNodes) {
      if (!visitedNodes.has(n.id)) {
        visitedNodes.add(n.id);
        accumulatedEvidence.push({ source: sq, node: n });
      }
    }
    console.log(`    ✓ Found ${initialNodes.length} new nodes (${stepsUsed+1}/${MAX_NAVIGATION_STEPS} steps used)`);

    // Relevance check — if the initial results are sufficient, skip edge-following
    const relevanceSys = `You are exploring a code knowledge graph. Based on the sub-question "${sq}", decide if the current context is sufficient to answer it.

Current nodes found:
${[...visitedNodes].map(id => {
  const n = graph.nodes.find(x => x.id === id);
  return n ? formatNodeStructured(n) : '';
}).join('\n')}

Reply with:
SUFFICIENT (if you have enough context)
or
NEED_MORE: <what specific node or relationship you still need>`;

    const relevanceRes = await callLLM(relevanceSys, `Sub-question: ${sq}`, model, 0.2);
    totalLLMCalls++;
    totalTokensIn += relevanceRes.tokens_in;
    totalTokensOut += relevanceRes.tokens_out;
    stepsUsed++;

    if (!relevanceRes.output.toUpperCase().includes('SUFFICIENT')) {
      // Follow edges from the most relevant nodes
      const topNodes = initialNodes.slice(0, 3);
      for (const startNode of topNodes) {
        if (stepsUsed >= MAX_NAVIGATION_STEPS) break;
        const nodeData = getNodeWithEdges(startNode.id);
        if (!nodeData) continue;
        const nodeText = formatNodeStructured(nodeData.node);
        const edgesText = formatEdges(nodeData.edges, graph);

        const followSys = `You are exploring a code knowledge graph node. Based on the sub-question "${sq}", decide which connected node to explore next.

Current node:
${nodeText}

Edges:
${edgesText}

Reply with:
NEXT: <node-id>
or
DONE (if no useful edges to follow)`;

        const followRes = await callLLM(followSys, `Sub-question: ${sq}`, model, 0.2);
        totalLLMCalls++;
        totalTokensIn += followRes.tokens_in;
        totalTokensOut += followRes.tokens_out;
        stepsUsed++;

        const nextMatch = followRes.output.match(/NEXT:\s*(\S+)/i);
        if (nextMatch) {
          const nextId = nextMatch[1].trim();
          const nextData = getNodeWithEdges(nextId);
          if (nextData && !visitedNodes.has(nextId)) {
            visitedNodes.add(nextId);
            accumulatedEvidence.push({ source: sq + ' (edge-follow)', node: nextData.node });
            console.log(`    ✓ Found ${nextData.node.label} via edge-follow`);
          }
        }
      }
    } else {
      console.log(`    ✓ Agent: context sufficient for this sub-question`);
    }
  }

  console.log(`  📊 Navigation complete: ${visitedNodes.size} nodes visited, ${stepsUsed} steps, ${accumulatedEvidence.length} evidence packets`);

  // ─── STEP 3: Reason over graph evidence ───
  console.log('  🔗 Step 3: Reason over graph evidence');
  const visitedNodeObjs = [...visitedNodes].map(id => graph.nodes.find(n => n.id === id)).filter(Boolean);
  const visitedEdges = graph.edges.filter(e => visitedNodes.has(e.source) && visitedNodes.has(e.target));

  const formatForReason = useNL ? formatNodeNL : formatNodeStructured;

  const reasonSys = `You are an expert code reasoner. You have been navigating a code knowledge graph and have accumulated nodes and their relationships. Your task is to trace a REASONING PATH through the graph that connects the code elements needed to complete the task.

A reasoning path is a sequence of steps where each step:
1. States a FACT from a specific node (cite the node by label)
2. Follows an EDGE to another node (cite the relationship type)
3. Shows how the next fact builds on or relates to the previous one

The path should form a CHAINED ARGUMENT that leads directly to the solution.

For example, for "Add a cancel_subscription function":

Step 1: FACT: Payment class has a status field with states: PENDING, COMPLETED, FAILED, REFUNDED. [node: Payment]
Step 2: EDGE: Payment DEFINES_FUNCTION refund() — refund() sets status to REFUNDED. [edge: DEFINES_FUNCTION]
Step 3: FACT: get_payment_history returns all payments for a user_id. [node: get_payment_history]
Step 4: EDGE: process_payment CALLS get_user_profile via _get_user_service() — validates user exists before processing. [edge: RUNTIME_IMPORT]
Step 5: FACT: process_payment raises ValueError if user not found. [node: process_payment, field: raises]
Step 6: CONCLUSION: The task asks us to WRITE a function called cancel_subscription. Its implementation should: (1) validate user exists using _get_user_service().get_user_profile(user_id), raising ValueError if not found, (2) call get_payment_history(user_id) to get payments, (3) filter for COMPLETED payments and find the most recent by created_at, (4) call refund_payment(payment_id) on it, (5) return the Payment object or None. The function name MUST be cancel_subscription.

Rules:
- Only use nodes and edges from the provided graph evidence
- If there is a gap in the path (no edge connects two needed facts), state GAP: <description>
- End with CONCLUSION: <what code to write and why, including the EXACT function name from the task>
- Number each step
- Do NOT repeat the same fact or edge in multiple steps
- Keep the path linear: fact → edge → fact → edge → conclusion.`;

  const reasonUsr = `Task: ${task}

Sub-questions explored:
${subQuestions.map((sq, i) => `  ${i + 1}. ${sq}`).join('\n')}

Visited nodes and their content:
${visitedNodeObjs.map(n => formatForReason(n)).join('\n\n')}

Edges between visited nodes:
${visitedEdges.map(e => {
  const srcLabel = graph.nodes.find(n => n.id === e.source)?.label || e.source;
  const tgtLabel = graph.nodes.find(n => n.id === e.target)?.label || e.target;
  return `- ${e.source} ${e.relation} ${e.target}${e.assertion ? ' — ' + e.assertion : ''}${e.bridge ? ' [BRIDGE: ' + e.bridge + ']' : ''}`;
}).join('\n')}

Trace a reasoning path through these nodes and edges that shows how to complete the task. Follow edges explicitly. If you encounter a gap where no edge connects two facts you need, state it as GAP.`;

  const reasonRes = await callLLM(reasonSys, reasonUsr, model, 0.3, 3000);
  totalLLMCalls++;
  totalTokensIn += reasonRes.tokens_in;
  totalTokensOut += reasonRes.tokens_out;

  let reasoningPath = reasonRes.output;
  const gapMatches = [...reasoningPath.matchAll(/GAP:\s*(.+)/gi)];
  const reasoningGaps = gapMatches.map(m => m[1].trim());

  console.log(`  ✓ Reasoning path traced (${reasoningGaps.length} gaps identified)`);

  logger.log({
    step: 'code-kg-reason', agent: 'code-kg-agent', role: 'Graph reasoning',
    input: { task, visitedNodes: [...visitedNodes], evidenceCount: accumulatedEvidence.length },
    system_prompt: reasonSys, user_prompt: reasonUsr,
    model, temperature: 0.3, output: reasoningPath,
    duration_ms: reasonRes.duration_ms, tokens_in: reasonRes.tokens_in, tokens_out: reasonRes.tokens_out,
    kg_visited_nodes: [...visitedNodes], kg_reasoning_gaps: reasoningGaps,
  });

  // ─── STEP 4: Synthesize code from reasoning path + evidence ───
  console.log('  📝 Step 4: Synthesize code');
  const evidenceBlock = useNL
    ? serializeAllNodesNL(visitedNodeObjs)
    : serializeAllNodesStructured(visitedNodeObjs);

  const synthSys = `You are an expert programmer completing a coding task using a reasoning path traced through a code knowledge graph.

You will receive:
1. A reasoning path — a chained argument that connects code elements through graph edges
2. The accumulated evidence from graph navigation (node descriptions, signatures, relationships)

Use the reasoning path as the SKELETON of your solution. Write code that follows the reasoning path.

CODING RULES (follow ALL of them):
1. Write ONLY the new function requested by the task. Do NOT redefine existing functions.
2. Functions in the target module already exist. Call them directly: get_payment_history(user_id), refund_payment(payment_id).
3. For user_service functions, use: user_svc = _get_user_service(); user_svc.get_user_profile(user_id). _get_user_service() takes NO arguments.
4. Use EXACT function and attribute names from the evidence (e.g., refund_payment not refund; p.created_at not p.timestamp).
5. Validate user existence: raise ValueError if user not found (follow process_payment pattern).
6. Return the Payment object itself, not .to_dict(). After refund_payment(payment_id), return the original payment object.
7. Prefer calling functions over raw state variable access (_payment_db).
8. Do NOT use import statements — all functions are already available at module level.
9. If the task says return None, return None (do not raise ValueError instead).
10. Follow the task: if it says cancel_subscription, write cancel_subscription.

Output format:
\`\`\`python
# <brief explanation>
<your code>
\`\`\`

**Approach:** <2-3 sentences explaining how you used the graph structure>`;

  const synthUsr = `Task: ${task}

=== REASONING PATH ===
${reasoningPath}

${reasoningGaps.length > 0 ? `=== IDENTIFIED GAPS ===\n${reasoningGaps.map((g, i) => `${i + 1}. ${g}`).join('\n')}\n` : ''}
=== GRAPH EVIDENCE ===
${evidenceBlock}

REMEMBER: The task asks you to write a specific NEW function. Look at the task prompt: it says what function to write (e.g., "Add a cancel_subscription function"). You MUST write that exact function. Do NOT write helper functions, do NOT reimplement existing functions shown in the evidence. The reasoning path tells you HOW to implement it — the task prompt tells you WHAT to implement.

Write your solution following the reasoning path. Use exact function signatures and names from the evidence.`;

  const synthRes = await callLLM(synthSys, synthUsr, model, 0.3, 3000);
  totalLLMCalls++;
  totalTokensIn += synthRes.tokens_in;
  totalTokensOut += synthRes.tokens_out;

  console.log(`  ✓ Code KG-Agent complete (${Date.now() - runStart}ms, ${totalLLMCalls} LLM calls, ${visitedNodes.size} nodes visited)`);

  logger.log({
    step: 'code-kg-synthesize', agent: 'code-kg-agent', role: 'Code synthesis from reasoning path + graph evidence',
    input: { task, visitedNodes: [...visitedNodes], reasoningGaps },
    system_prompt: synthSys, user_prompt: synthUsr,
    model, temperature: 0.3, output: synthRes.output,
    duration_ms: synthRes.duration_ms, tokens_in: synthRes.tokens_in, tokens_out: synthRes.tokens_out,
  });

  return {
    answer: synthRes.output,
    tokens_in: totalTokensIn,
    tokens_out: totalTokensOut,
    duration_ms: Date.now() - runStart,
    llm_calls: totalLLMCalls,
    kg_visited_nodes: [...visitedNodes],
    kg_reasoning_path: reasoningPath,
    kg_reasoning_gaps: reasoningGaps,
  };
}

// ─── B0: Vanilla LLM baseline (no KG, flat source) ───

export async function runCodeB0(task, logger, opts = {}) {
  const model = opts.model || getDefaultModel();
  const runStart = Date.now();

  console.log('▶ B0: Vanilla LLM (no KG)');

  // Load all source files as flat context
  const srcDir = nodePath.join(process.cwd(), 'example-repo', 'src');
  let flatContext = '';
  for (const f of fs.readdirSync(srcDir).filter(f => f.endsWith('.py') && f !== '__init__.py')) {
    const content = fs.readFileSync(nodePath.join(srcDir, f), 'utf8');
    flatContext += `\n=== ${f} ===\n${content}\n`;
  }

  const sys = `You are an expert Python programmer. Complete the task using the provided codebase context. Write clean, working code with type hints and docstrings following the existing style.

CODING RULES:
1. Write ONLY the new function requested by the task. Existing functions already exist — call them, do NOT redefine them.
2. Do NOT use any import statements. All functions are available at module level.
3. For user_service functions: user_svc = _get_user_service(); user_svc.get_user_profile(user_id). _get_user_service() takes NO arguments.
4. Validate user existence: raise ValueError if user not found.
5. Return the Payment object itself, not .to_dict().
6. Prefer calling functions (e.g., get_payment_history) over raw state access (e.g., _payment_db).`;

  const usr = `Task: ${task}

Here is the codebase:
${flatContext}

Write your solution. The code will be appended to the target module file. Do not use relative imports:
\`\`\`python
# <brief explanation>
<your code>
\`\`\`

**Approach:** <2-3 sentences explaining your approach>`;

  const r = await callLLM(sys, usr, model, 0.3, 3000);
  logger.log({
    step: 'b0', agent: 'vanilla-llm', role: 'Single LLM call with flat repo context (no KG)',
    input: { task }, system_prompt: sys, user_prompt: usr,
    model, temperature: 0.3, output: r.output,
    duration_ms: r.duration_ms, tokens_in: r.tokens_in, tokens_out: r.tokens_out,
  });

  return {
    answer: r.output,
    tokens_in: r.tokens_in,
    tokens_out: r.tokens_out,
    duration_ms: Date.now() - runStart,
    llm_calls: 1,
  };
}