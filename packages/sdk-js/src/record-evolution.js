import { graphRecordErrors, graphRevisionErrors } from "./graph-records.js";
import {agentSectorBindingErrors, descriptorRelationErrors} from "./agent-sectors.js";
/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/. */
import { observationBindingErrors } from "./observation-accounts.js";
import nextSchema from "@earworm/core/schemas/akousma-1.7.schema.json" with { type: "json" };
import legacySchema from "@earworm/core/schemas/akousma.schema.json" with { type: "json" };
import { compileContractSchema, schemaErrors, assertSupportedContracts } from "./listening-contracts.js";
import { parseContractInstant } from "./listening-context.js";

export const NEXT_AKOUSMA_SCHEMA_VERSION = "1.7.0";
export const NEXT_AUDITUM_CONTRACT = "earworm/auditum/v3";
export const RECORD_EVOLUTION_CONTRACT = "earworm/akousma/v1.7";
const validateNext = compileContractSchema(nextSchema);
const validateLegacy = compileContractSchema(legacySchema);
const finiteJson = (value) => typeof value === "number" ? Number.isFinite(value)
  : value && typeof value === "object" ? Object.values(value).every(finiteJson) : true;

export function nextRecordErrors(record) {
  if (!finiteJson(record)) return ["record must contain only finite JSON numbers"];
  const errors = schemaErrors(validateNext, record);
  if (errors.length) return errors;
  errors.push(...auditumReferenceErrors(record));
  errors.push(...observationBindingErrors(record));
  errors.push(...agentSectorBindingErrors(record));
  errors.push(...graphRecordErrors(record));
  const relations = record.lineage.relations ?? [];
  const typed = relations.filter((relation) => relation.contract === "earworm/relations/v1");
  const ids = new Set();
  for (const relation of typed) {
    if (ids.has(relation.relation_id)) errors.push("relation_id is duplicated");
    ids.add(relation.relation_id);
    if (relation.target_akousma_id === record.akousma_id) errors.push("typed relation cannot target its own record");
    if (relation.type !== "similar_by" && relation.criterion !== undefined) errors.push("criterion belongs only to similar_by");
    if (relation.type === "similar_by" && !relation.criterion.input_refs.includes(relation.target_akousma_id)) errors.push("similarity criterion must identify the target input");
  }
  const appeal = record.auditum?.appeal;
  if (appeal && appeal.resolution && appeal.status !== "resolved") errors.push("appeal resolution requires resolved status");
  const research = record.extensions?.earworm_research;
  const decision = record.extensions?.earworm_generation_decision;
  if (research) {
    if (record.record_kind !== "research_proposal") errors.push("research extension requires research_proposal record_kind");
    for (const ref of research.proposed_relation_refs) if (!ids.has(ref)) errors.push("unresolved proposed relation");
  }
  if (decision) {
    if (record.record_kind !== "generation_decision") errors.push("decision extension requires generation_decision record_kind");
    if (!decision.input_refs.includes(decision.generation_ref)) errors.push("generation must remain an explicit decision input");
    if (!typed.some((relation) => relation.type === "decision_on" && relation.target_akousma_id === decision.generation_ref)) errors.push("decision_on relation must identify the generation");
    const pairs = decision.subsequent_listenings.map((item) => JSON.stringify([item.record_ref, item.listening_ref]));
    if (new Set(pairs).size !== pairs.length) errors.push("subsequent listening reference is duplicated");
    for (const item of decision.subsequent_listenings) {
      if (!decision.input_refs.includes(item.record_ref)) errors.push("subsequent listening record must remain an explicit input");
    }
    if (["keep", "discard"].includes(decision.outcome) && (decision.next_job.status !== "none" || decision.stop_outcome === "continue")) errors.push("keep/discard cannot schedule a next job");
    if (decision.stop_outcome === "continue" && decision.next_job.status !== "planned") errors.push("continue requires an explicit planned next job");
    if (decision.stop_outcome !== "continue" && decision.next_job.status !== "none") errors.push("stop/defer cannot schedule a next job");
  }
  return errors;
}

/** Resolve record-valued links within an explicit scope; never fetch references. */
export function nextRecordReferenceErrors(record, records) {
  const errors = nextRecordErrors(record);
  if (errors.length) return errors;
  if (!Array.isArray(records) || records.some((item) => !item || typeof item.akousma_id !== "string")) return ["reference scope must contain identified records"];
  const scope = new Map(records.map((item) => [item.akousma_id, item]));
  if (scope.size !== records.length) return ["reference scope has duplicate record identities"];
  for (const source of scope.values()) {
    const problems = source.schema_version === NEXT_AKOUSMA_SCHEMA_VERSION ? nextRecordErrors(source) : schemaErrors(validateLegacy, source);
    if (problems.length || !finiteJson(source)) errors.push(`invalid referenced record: ${source.akousma_id}`);
  }
  if (errors.length) return errors;
  const graph = record.extensions?.earworm_transformation_graph;
  if (graph?.revision > 1) {
    const previous = scope.get(record.auditum?.revision?.revises_akousma_id);
    if (!previous) errors.push("Unresolved graph revision parent");
    else errors.push(...graphRevisionErrors(record, previous));
  }
  const legacy = record.auditum?.appeal?.legacy_source;
  if (legacy) {
    const source = scope.get(legacy.record_ref);
    const payload = source?.extensions?.oida;
    if (!payload || !Object.hasOwn(payload, "appeal")) errors.push("unresolved legacy appeal source");
    else if (stableJson(payload.appeal) !== stableJson(legacy.payload)) errors.push("legacy appeal payload differs from its retained source");
  }
  for (const relation of record.lineage.relations ?? []) {
    if (relation.contract === "earworm/relations/v1" && !scope.has(relation.target_akousma_id)) errors.push(`unresolved relation target: ${relation.target_akousma_id}`);
  }
  errors.push(...descriptorRelationErrors(record,scope));
  const decision = record.extensions?.earworm_generation_decision;
  if (!decision) return errors;
  const generation = scope.get(decision.generation_ref);
  if (!generation || generation.provenance?.source_type !== "generated") errors.push("generation_ref must resolve to a generated record");
  for (const ref of decision.subsequent_listenings) {
    const source = scope.get(ref.record_ref);
    const listening = source?.auditum?.listenings?.find((item) => item.listening_id === ref.listening_ref);
    if (!listening) { errors.push("unresolved subsequent listening"); continue; }
    try {
      if (generation && parseContractInstant(listening.created_at) < parseContractInstant(generation.created_at)) errors.push("listening precedes generation");
      if (parseContractInstant(record.created_at) < parseContractInstant(listening.created_at)) errors.push("decision precedes its listening input");
    } catch { errors.push("cannot establish generation/listening/decision chronology"); }
  }
  return errors;
}

/** Promote an opaque legacy appeal into a new revision; never alter the source. */
export function promoteLegacyAppeal(record, options) {
  assertSupportedContracts([RECORD_EVOLUTION_CONTRACT, NEXT_AUDITUM_CONTRACT], options.supported_contracts);
  for (const key of ["akousma_id", "revision_id", "created_at", "appeal_id", "recorded_by", "reason"]) {
    if (typeof options[key] !== "string" || !options[key].trim()) throw new TypeError(`Missing promotion option: ${key}`);
  }
  if (options.akousma_id === record.akousma_id) throw new Error("Promotion requires a fresh record id");
  const sourceErrors = record.schema_version === NEXT_AKOUSMA_SCHEMA_VERSION ? nextRecordErrors(record) : schemaErrors(validateLegacy, record);
  if (sourceErrors.length) throw new Error(sourceErrors.join("; "));
  if (!record.auditum || !Array.isArray(record.auditum.route_decisions) || !record.auditum.route_decisions.length) throw new Error("An attributable auditum with route decisions is required");
  if (record.auditum.appeal) throw new Error("A promoted appeal already exists; use an explicit revision");
  if (!record.extensions?.oida || !Object.hasOwn(record.extensions.oida, "appeal")) throw new Error("No retained extensions.oida.appeal payload");
  if (parseContractInstant(options.created_at) < parseContractInstant(record.created_at)) throw new Error("Revision precedes its source record");
  const next = structuredClone(record);
  next.akousma_id = options.akousma_id;
  next.created_at = options.created_at;
  next.schema_version = NEXT_AKOUSMA_SCHEMA_VERSION;
  next.auditum.contract = NEXT_AUDITUM_CONTRACT;
  next.auditum.revision = { revision_id: options.revision_id, revises_akousma_id: record.akousma_id,
    reason: options.reason, changes: ["Promoted retained appeal into negotiated auditum.appeal."], created_at: options.created_at };
  next.auditum.appeal = { contract: "earworm/appeal/v1", appeal_id: options.appeal_id,
    recorded_by: options.recorded_by, subject_refs: structuredClone(options.subject_refs), reason: options.reason,
    status: "unreviewed", evidence_refs: [record.akousma_id],
    legacy_source: { record_ref: record.akousma_id, path: "/extensions/oida/appeal", payload: structuredClone(record.extensions.oida.appeal) } };
  const errors = nextRecordErrors(next);
  if (errors.length) throw new Error(errors.join("; "));
  return next;
}

function stableJson(value) {
  if (Array.isArray(value)) return `[${value.map(stableJson).join(",")}]`;
  if (value && typeof value === "object") return `{${Object.keys(value).sort().map((key) => `${JSON.stringify(key)}:${stableJson(value[key])}`).join(",")}}`;
  return JSON.stringify(value);
}

function auditumReferenceErrors(record) {
  const block = record.auditum;
  if (!block) return [];
  const errors = [];
  const listenings = new Set(block.listenings.map((item) => item.listening_id));
  if (!block.route_decisions?.length && record.record_kind !== "transformation_graph") return ["Revision-only auditum belongs to a graph artifact"];
  const decisions = new Set(block.route_decisions.map((item) => item.decision_id));
  if (listenings.size !== block.listenings.length || decisions.size !== block.route_decisions.length) errors.push("duplicate auditum listening or decision identity");
  for (const listening of block.listenings) {
    for (const ref of listening.route_decision_refs ?? []) if (!decisions.has(ref)) errors.push("unresolved listening route decision");
    for (const influence of listening.influenced_by ?? []) if (!listenings.has(influence.listening_id) || influence.listening_id === listening.listening_id) errors.push("invalid listening influence reference");
  }
  for (const item of [...block.route_decisions, ...block.honest_absences]) if (item.listening_id != null && !listenings.has(item.listening_id)) errors.push("unresolved attributable listening");
  for (const disagreement of block.disagreements) {
    if (disagreement.listening_ids.some((id) => !listenings.has(id))) errors.push("unresolved disagreement listening");
    if (disagreement.positions.some((position) => !disagreement.listening_ids.includes(position.listening_id))) errors.push("unattributable disagreement position");
    if (disagreement.status === "resolved" && !disagreement.resolution_note?.trim()) errors.push("resolved disagreement needs a resolution note");
  }
  if (block.ensemble) {
    const members = new Set(block.ensemble.listening_ids);
    if ([...members].some((id) => !listenings.has(id))) errors.push("unresolved ensemble member");
    for (const edge of block.ensemble.influence_edges) if (!members.has(edge.from_listening_id) || !members.has(edge.to_listening_id) || edge.from_listening_id === edge.to_listening_id) errors.push("invalid ensemble influence reference");
  }
  if (!record.record_kind && !block.listenings.length && !block.route_decisions.some((item) => ["input", "capture"].includes(item.gate) && ["pause", "defer", "abstain", "refuse", "withhold"].includes(item.outcome))) errors.push("empty listening account requires a pre-capture stop");
  if (block.revision?.revises_akousma_id === record.akousma_id) errors.push("revision must reference a different record");
  return errors;
}
