/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/. */
import graphSchema from '@earworm/core/schemas/transformation-graph.schema.json' with { type: 'json' };
import { compileContractSchema, schemaErrors, assertSupportedContracts } from './listening-contracts.js';
import { parseContractInstant } from './listening-context.js';
import { createTransformationGraph, transformationGraphErrors, graphRequiredContracts } from './transformation-graph.js';
import { transpositionRecipeErrors } from './transposition-recipes.js';
import { nextRecordErrors } from './record-evolution.js';
const validate = compileContractSchema(graphSchema);
const effects = new Set(['derive', 'transform', 'render', 'map']);
const strings = v => Array.isArray(v) && v.every(x => typeof x === 'string' && x.trim());
const stable = v => Array.isArray(v) ? `[${v.map(stable).join(',')}]` : v && typeof v === 'object' ? `{${Object.keys(v).sort().map(k => JSON.stringify(k)+':'+stable(v[k])).join(',')}}` : JSON.stringify(v);
const finite = v => typeof v === 'number' ? Number.isFinite(v) : v && typeof v === 'object' ? Object.values(v).every(finite) : true;

/** Local binding checks do not replace MASA's policy/profile/direction validation. */
export function transformationGraphBindingErrors(graph) {
  const errors = schemaErrors(validate, graph);
  if (errors.length || !finite(graph)) return errors.length ? errors : ['Graph requires finite JSON numbers'];
  const source = graph.source_record;
  const reps = source.representations, events = source.history?.events, relations = source.relations;
  if (source.masaVersion !== '0.2.0' || source.history?.mode !== 'embedded' ||
      [reps, events, relations].some(a => !Array.isArray(a) || a.some(x => !x || typeof x.id !== 'string') || new Set(a.map(x => x.id)).size !== a.length)) return ['Malformed graph source identity scope'];
  if (events.some(e => !strings(e.inputs) || !strings(e.outputs) || typeof e.effectClass !== 'string' || typeof e.finalStatus !== 'string') || relations.some(r => !strings([r.subject, r.object, r.predicate]))) return ['Malformed operation or relation references'];
  const nodes = new Map(graph.nodes.map(n => [n.node_id, n.representation_ref]));
  if (nodes.size !== graph.nodes.length || new Set(nodes.values()).size !== reps.length || nodes.size !== reps.length || reps.some(r => ![...nodes.values()].includes(r.id))) return ['Patch nodes must map each representation exactly once'];
  const receipts = events.filter(e => effects.has(e.effectClass));
  if (stable(graph.operation_refs) !== stable(receipts.map(e => e.id))) errors.push('Operation reference list differs from retained receipts');
  const seen = new Set();
  for (const edge of graph.edges) {
    const receipt = receipts.find(e => e.id === edge.operation_ref), relation = relations.find(r => r.id === edge.relation_ref);
    const parent = nodes.get(edge.from_node), child = nodes.get(edge.to_node);
    if (seen.has(edge.relation_ref) || !receipt || !relation || relation.operationRef !== receipt.id || receipt.finalStatus !== 'completed' || !parent || !child || parent === child || !receipt.inputs.includes(parent) || !receipt.outputs.includes(child) ||
        !((relation.subject === parent && relation.object === child) || (relation.subject === child && relation.object === parent))) errors.push('Graph edge does not bind its retained operation and relation');
    seen.add(edge.relation_ref);
  }
  for (const receipt of receipts) {
    if (receipt.finalStatus !== 'completed' && receipt.outputs.length) errors.push('Incomplete operation cannot have graph outputs');
    if (receipt.finalStatus === 'completed') {
      if (!receipt.inputs.length || !receipt.outputs.length || [...receipt.inputs, ...receipt.outputs].some(id => !reps.some(r => r.id === id)) || receipt.outputs.some(id => receipt.inputs.includes(id))) errors.push('Transformation requires distinct retained representations');
      for (const output of receipt.outputs) if (!graph.edges.some(e => e.operation_ref === receipt.id && nodes.get(e.to_node) === output)) errors.push('Completed output needs a receipt-backed graph edge');
    }
  }
  errors.push(...transpositionRecipeErrors(source));
  return errors;
}

export function graphRecordErrors(record) {
  const graph = record.extensions?.earworm_transformation_graph;
  if (graph === undefined) return [];
  const errors = transformationGraphBindingErrors(graph);
  if (errors.length) return errors;
  if (record.record_kind !== 'transformation_graph' || record.subject !== graph.graph_id) errors.push('Graph record kind and subject must identify the graph');
  const revision = record.auditum?.revision;
  if (graph.revision === 1 && (revision || record.akousma_id !== graph.graph_id)) errors.push('Initial graph identity must equal its root record ID and have no revision parent');
  if (graph.revision > 1 && (!revision || revision.revises_akousma_id === record.akousma_id || revision.created_at !== record.created_at)) errors.push('Graph revision needs an explicit fresh record revision');
  return errors;
}

export function graphRevisionErrors(record, previous) {
  const errors = [...graphRecordErrors(record), ...graphRecordErrors(previous)];
  if (errors.length) return errors;
  const current = record.extensions?.earworm_transformation_graph, prior = previous.extensions?.earworm_transformation_graph;
  if (!current || !prior || record.auditum?.revision?.revises_akousma_id !== previous.akousma_id || current.graph_id !== prior.graph_id || current.revision !== prior.revision + 1) return ['Graph revisions must retain their family and advance their explicit parent by one'];
  if (stable(current.source_record) !== stable(prior.source_record)) errors.push('Patch revision must preserve the complete imported MASA source');
  try { if (parseContractInstant(record.created_at) < parseContractInstant(previous.created_at)) errors.push('Graph revision predates its parent'); }
  catch { errors.push('Graph revision requires valid UTC timestamps'); }
  return errors;
}

export function createGraphRecord(graph, options, masa) {
  assertSupportedContracts(['earworm/akousma/v1.7', ...graphRequiredContracts(graph?.source_record)], options.supported_contracts);
  const errors = transformationGraphErrors(graph, masa);
  if (errors.length) throw new Error(errors.join('; '));
  parseContractInstant(options.created_at);
  const record = { akousma_id: graph.graph_id, schema_version: '1.7.0', record_kind: 'transformation_graph',
    created_at: options.created_at, subject: graph.graph_id, provenance: { source_type: 'unknown', origin: 'unknown', originating_app: options.originating_app, created_at: options.created_at },
    lineage: { parent_akousma_ids: [] }, extensions: { earworm_transformation_graph: structuredClone(graph) } };
  const problems = nextRecordErrors(record);
  if (problems.length) throw new Error(problems.join('; '));
  return record;
}

export function reviseGraphRecord(record, options, masa) {
  assertSupportedContracts(['earworm/akousma/v1.7', 'earworm/auditum/v3', 'earworm/transformation-graph/v1', 'masa/0.2.0'], options.supported_contracts);
  const errors = nextRecordErrors(record);
  if (errors.length || !record.extensions?.earworm_transformation_graph) throw new Error(errors.join('; ') || 'Graph record required');
  const graph = record.extensions.earworm_transformation_graph;
  const problems = transformationGraphErrors(graph, masa);
  if (problems.length) throw new Error(problems.join('; '));
  const next = structuredClone(record);
  next.akousma_id = options.akousma_id; next.created_at = options.created_at;
  next.extensions.earworm_transformation_graph = createTransformationGraph(graph.source_record, {
    graph_id: graph.graph_id, revision: graph.revision + 1, authored_by: options.authored_by,
    nodes: options.nodes, supported_contracts: options.supported_contracts
  }, masa);
  next.auditum ??= { listenings: [], route_decisions: [], disagreements: [], honest_absences: [], actions: [] }; next.auditum.contract = 'earworm/auditum/v3';
  next.auditum.revision = { revision_id: options.revision_id, revises_akousma_id: record.akousma_id,
    reason: options.reason, changes: ['Revised application patch mapping; retained MASA source unchanged.'], created_at: options.created_at };
  const invalid = [...nextRecordErrors(next), ...graphRevisionErrors(next, record)];
  if (invalid.length) throw new Error(invalid.join('; '));
  return next;
}
