import { transformationGraphBindingErrors } from "./graph-records.js";
/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/. */

import schema from "@earworm/core/schemas/transformation-graph.schema.json" with { type: "json" };
import { assertSupportedContracts, compileContractSchema, schemaErrors } from "./listening-contracts.js";

export const graphRequiredContracts = source => ['earworm/transformation-graph/v1', 'masa/0.2.0',
  ...(source?.history?.events?.some(e => e?.extensions && Object.hasOwn(e.extensions, 'earworm:transposition')) ? ['earworm/transposition-recipe/v1'] : [])];
export const TRANSFORMATION_GRAPH_CONTRACT = "earworm/transformation-graph/v1";
const validate = compileContractSchema(schema);
const effects = new Set(["derive", "transform", "render", "map"]);
const finite = (v) => typeof v === "number" ? Number.isFinite(v) :
  v && typeof v === "object" ? Object.values(v).every(finite) : true;
const stable = (v) => JSON.stringify(v && typeof v === "object" ?
  Array.isArray(v) ? v.map((x) => JSON.parse(stable(x))) :
    Object.fromEntries(Object.keys(v).sort().map((k) => [k, JSON.parse(stable(v[k]))])) : v);

function derive(record, nodes, { validateMasa, lineageDirections }) {
  if (typeof validateMasa !== "function" || !lineageDirections || typeof lineageDirections !== "object" || Array.isArray(lineageDirections)) {
    throw new TypeError("Use the host's MASA validator and versioned lineageRelationDirections registry");
  }
  // Give foreign validators a detached value: validation cannot edit retained evidence.
  const errors = validateMasa(structuredClone(record));
  if (!Array.isArray(errors) || errors.some((e) => typeof e !== "string")) throw new TypeError("MASA validator must return error strings");
  if (errors.length) throw new Error(errors.join("; "));
  if (record.masaVersion !== "0.2.0" || record.history?.mode !== "embedded" ||
      !Array.isArray(record.history.events) || !Array.isArray(record.representations) || !Array.isArray(record.relations)) {
    throw new Error("Graph requires MASA 0.2.0 and embedded operation history");
  }
  const reps = new Set(record.representations.map((r) => r.id));
  const byRep = new Map(nodes.map((n) => [n.representation_ref, n.node_id]));
  if (byRep.size !== nodes.length || new Set(nodes.map((n) => n.node_id)).size !== nodes.length ||
      byRep.size !== reps.size || [...reps].some((id) => !byRep.has(id))) {
    throw new Error("Patch nodes must map every representation exactly once with distinct node IDs");
  }
  const receipts = record.history.events.filter((e) => effects.has(e.effectClass));
  const byOperation = new Map(receipts.map((e) => [e.id, e]));
  if (byOperation.size !== receipts.length) throw new Error("Duplicate operation receipt");
  for (const receipt of receipts) {
    if (receipt.finalStatus !== "completed" && receipt.outputs.length) throw new Error("Incomplete operations with outputs are outside this graph scope");
    if (receipt.finalStatus === "completed" && (!receipt.inputs.length || !receipt.outputs.length ||
        [...receipt.inputs, ...receipt.outputs].some((id) => !reps.has(id)) || receipt.outputs.some((id) => receipt.inputs.includes(id)))) {
      throw new Error("Completed transformations require retained input and distinct output representations");
    }
  }
  const edges = [];
  for (const relation of record.relations) {
    const receipt = byOperation.get(relation.operationRef);
    if (!receipt || receipt.finalStatus !== "completed" || !Object.hasOwn(lineageDirections, relation.predicate)) continue;
    const direction = lineageDirections[relation.predicate];
    if (!["subject-is-descendant", "object-is-descendant"].includes(direction)) throw new Error("Invalid MASA lineage direction");
    const [parent, child] = direction === "subject-is-descendant" ? [relation.object, relation.subject] : [relation.subject, relation.object];
    if (!receipt.inputs.includes(parent) || !receipt.outputs.includes(child)) throw new Error("Lineage direction disagrees with operation inputs and outputs");
    edges.push({ relation_ref: relation.id, operation_ref: receipt.id, from_node: byRep.get(parent), to_node: byRep.get(child) });
  }
  for (const receipt of receipts.filter((r) => r.finalStatus === "completed")) {
    for (const output of receipt.outputs) {
      if (!edges.some((e) => e.operation_ref === receipt.id && e.to_node === byRep.get(output))) {
        throw new Error("Each completed output needs a directed receipt-backed lineage relation");
      }
    }
  }
  return { edges, operation_refs: receipts.map((r) => r.id) };
}

/** Application mapping only; source receipts, parameters, rates and integrity stay canonical. */
export function createTransformationGraph(record, options, masa) {
  assertSupportedContracts(graphRequiredContracts(record), options.supported_contracts);
  const graph = { contract: TRANSFORMATION_GRAPH_CONTRACT, graph_id: options.graph_id,
    revision: options.revision, authored_by: options.authored_by, scope: "completed_representation_lineage",
    source_record: structuredClone(record), nodes: structuredClone(options.nodes), edges: [], operation_refs: [] };
  const errors = schemaErrors(validate, graph);
  if (errors.length || !finite(graph)) throw new Error(errors.join("; ") || "Graph requires finite JSON numbers");
  Object.assign(graph, derive(graph.source_record, graph.nodes, masa));
  const bindingErrors = transformationGraphBindingErrors(graph);
  if (bindingErrors.length) throw new Error(bindingErrors.join("; "));
  return graph;
}

/** Recompute edges; a modified patch must not silently change the retained operation direction. */
export function transformationGraphErrors(graph, masa) {
  if (!finite(graph)) return ["Graph requires finite JSON numbers"];
  const errors = transformationGraphBindingErrors(graph);
  if (errors.length) return errors;
  try {
    const expected = derive(graph.source_record, graph.nodes, masa);
    if (stable(expected.edges) !== stable(graph.edges) || stable(expected.operation_refs) !== stable(graph.operation_refs)) {
      errors.push("Graph edges or operation references differ from retained MASA evidence");
    }
  } catch (error) {
    if (error instanceof TypeError) throw error;
    errors.push(error.message);
  }
  return errors;
}
